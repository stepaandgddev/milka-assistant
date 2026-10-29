import copy
import json
import shutil
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QPainter, QPixmap
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QRadioButton,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from extension_shop import extensions_from_catalog, fetch_catalog

from autostart import (
    autostart_enabled,
    autostart_supported,
    set_autostart,
)
from addon_manager import (
    addon_records,
    addons_directory,
    coerce_addon_setting,
    configure_addons,
)
from github_skills import (
    SkillInstallError,
    install_skill_from_github,
    parse_github_url,
)
from outfit_store import SLOT_LABELS, load_outfit, save_outfit
from settings_store import (
    DRAWING_PROVIDERS,
    PROVIDER_TYPES,
    default_tts,
    normalize_addons,
    normalize_drawing,
    normalize_history,
    normalize_life,
    normalize_search,
    normalize_vision,
    save_settings,
)


class _SkillInstallWorker(QThread):
    """Download and install a GitHub skill without blocking the dialog."""

    completed = Signal(dict)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        try:
            result = install_skill_from_github(self._url)
        except Exception as error:
            result = {"error": str(error)}
        self.completed.emit(result)


class _ShopCatalogWorker(QThread):
    completed = Signal(object, str)

    def run(self):
        try:
            self.completed.emit(fetch_catalog(), "")
        except Exception as error:
            self.completed.emit({}, str(error))


class SettingsDialog(QDialog):

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Settings")
        self.resize(720, 650)

        self._settings = copy.deepcopy(settings)
        self._providers = self._settings["providers"]
        self._tts = self._settings.get("tts") or default_tts()
        self._drawing = normalize_drawing(self._settings.get("drawing"))
        self._vision = normalize_vision(self._settings.get("vision"))
        self._life = normalize_life(self._settings.get("life"))
        self._search = normalize_search(self._settings.get("search"))
        self._history = normalize_history(self._settings.get("history"))
        self._addons = normalize_addons(self._settings.get("addons"))
        self._initial_addons = copy.deepcopy(self._addons)
        self._addons_restored = False
        self._addons_applied = False
        self._addon_settings_id = ""
        self._addon_settings_schema = []
        self._addon_setting_widgets = {}
        self._outfit = load_outfit()
        self._install_worker = None
        self._loading = False
        self._network = QNetworkAccessManager(self)
        self._health_reply = None
        self._cloudflare_reply = None
        self._cloudflare_testing = False

        self._build_ui()
        self._refresh_list(self._active_row())
        self._load_vision()
        self._load_tts()
        self._load_drawing()
        self._load_life()
        self._load_search()
        self._load_history()
        self._load_addons()
        self._refresh_shop()
        self._refresh_outfit_list()

    def _build_ui(self):
        root = QVBoxLayout(self)

        tabs = QTabWidget()
        root.addWidget(tabs)

        general_scroll = QScrollArea()
        general_scroll.setWidgetResizable(True)
        general_scroll.setFrameShape(QFrame.Shape.NoFrame)
        general_page = QWidget()
        general_root = QVBoxLayout(general_page)
        general_scroll.setWidget(general_page)
        tabs.addTab(general_scroll, "Model and voice")

        content = QHBoxLayout()
        general_root.addLayout(content)

        left = QVBoxLayout()
        left.addWidget(QLabel("Endpoints"))
        self.provider_list = QListWidget()
        self.provider_list.currentRowChanged.connect(self._load_provider)
        left.addWidget(self.provider_list)

        buttons = QHBoxLayout()
        add_button = QPushButton("Add")
        remove_button = QPushButton("Remove")
        add_button.clicked.connect(self._add_provider)
        remove_button.clicked.connect(self._remove_provider)
        buttons.addWidget(add_button)
        buttons.addWidget(remove_button)
        left.addLayout(buttons)
        content.addLayout(left, 2)

        right = QWidget()
        form = QFormLayout(right)
        self.name_edit = QLineEdit()
        self.type_combo = QComboBox()
        for value, label in PROVIDER_TYPES:
            self.type_combo.addItem(label, value)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://openrouter.ai/api/v1")
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("openai/gpt-4o-mini")
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.active_check = QCheckBox("Use this endpoint")
        self.autostart_check = QCheckBox(
            "Launch Milky at login"
        )
        self.autostart_check.setChecked(autostart_enabled())
        if not autostart_supported():
            self.autostart_check.setChecked(False)
            self.autostart_check.setEnabled(False)
            self.autostart_check.setToolTip(
                "Autostart is currently supported on Linux, Windows, and macOS."
            )
        hint = QLabel(
            "For OpenRouter, Groq, and other OpenAI-compatible services, "
            "enter the base URL, usually ending in /v1.\n"
            "OpenRouter prompt and response caching is enabled automatically."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #777;")

        form.addRow("Name", self.name_edit)
        form.addRow("API type", self.type_combo)
        form.addRow("Base URL", self.url_edit)
        form.addRow("Model", self.model_edit)
        form.addRow("API key", self.key_edit)
        form.addRow("", self.active_check)
        form.addRow("", self.autostart_check)
        form.addRow(hint)
        content.addWidget(right, 3)

        tts_group = QGroupBox("Text to speech")
        tts_form = QFormLayout(tts_group)
        self.tts_enabled_check = QCheckBox("Speak replies")

        # Radio buttons for provider selection
        self.milka_radio = QRadioButton("Milky TTS")
        self.groq_radio = QRadioButton("Groq")
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(self.milka_radio)
        provider_layout.addWidget(self.groq_radio)
        provider_layout.addStretch()
        provider_widget = QWidget()
        provider_widget.setLayout(provider_layout)

        self.milka_url_edit = QLineEdit()
        self.milka_url_edit.setPlaceholderText("http://<NUC-IP>:8765")
        self.milka_voice_edit = QLineEdit()
        self.milka_voice_edit.setPlaceholderText("sveta")
        self.milka_speed_spin = QDoubleSpinBox()
        self.milka_speed_spin.setRange(0.5, 2.0)
        self.milka_speed_spin.setSingleStep(0.1)
        self.milka_speed_spin.setDecimals(1)
        self.groq_key_edit = QLineEdit()
        self.groq_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.groq_model_edit = QLineEdit()
        self.groq_model_edit.setPlaceholderText("playai-tts")
        self.groq_voice_edit = QLineEdit()
        self.groq_voice_edit.setPlaceholderText("Fritz-PlayAI")
        self.tts_test_button = QPushButton("Test Milka TTS")
        self.tts_status = QLabel("")
        self.tts_status.setWordWrap(True)
        self.tts_status.setStyleSheet("color: #777;")

        tts_hint = QLabel(
            "Milka TTS runs on your NUC. Enter its local address, for example "
            "http://192.168.1.100:8765. The test button calls /health. "
            "Groq uses the OpenAI-compatible speech endpoint."
        )
        tts_hint.setWordWrap(True)
        tts_hint.setStyleSheet("color: #777;")

        tts_form.addRow(self.tts_enabled_check)
        tts_form.addRow("Provider", provider_widget)
        tts_form.addRow("Milka TTS URL", self.milka_url_edit)
        tts_form.addRow("Milka voice", self.milka_voice_edit)
        tts_form.addRow("Milka speed", self.milka_speed_spin)
        tts_form.addRow("Groq API key", self.groq_key_edit)
        tts_form.addRow("Groq model", self.groq_model_edit)
        tts_form.addRow("Groq voice", self.groq_voice_edit)
        tts_form.addRow("", self.tts_test_button)
        tts_form.addRow(self.tts_status)
        tts_form.addRow(tts_hint)
        general_root.addWidget(tts_group)

        vision_group = QGroupBox("Screen vision")
        vision_form = QFormLayout(vision_group)
        self.vision_enabled_check = QCheckBox(
            "Let Milky look at the screen when asked"
        )
        self.vision_provider_combo = QComboBox()
        self.vision_model_edit = QLineEdit()
        self.vision_model_edit.setPlaceholderText("qwen/qwen3.8-27b")
        vision_hint = QLabel(
            "Use a multimodal model that accepts images; a text-only model "
            "cannot see the screenshot. On Groq, <b>qwen/qwen3.8-27b</b> is "
            "available, but if it returns empty or incorrect descriptions, "
            "switch to a stronger vision model such as Baseten DeepSeek V4.1 "
            "Flash, Gemini, GPT-4o-mini, or a local Ollama "
            "<code>qwen3-vl:8b</code>.\n"
            "A screenshot is captured only when you ask about the screen or "
            "choose <b>Look at screen</b> in the menu. Milky first asks what "
            "to look for, then sends the screenshot to the vision endpoint "
            "and does not keep it. On Wayland, the desktop screenshot portal "
            "is used over D-Bus."
        )
        vision_hint.setWordWrap(True)
        vision_hint.setTextFormat(Qt.TextFormat.RichText)
        vision_hint.setStyleSheet("color: #777;")

        vision_form.addRow(self.vision_enabled_check)
        vision_form.addRow("Vision endpoint", self.vision_provider_combo)
        vision_form.addRow("Vision model", self.vision_model_edit)
        vision_form.addRow(vision_hint)
        general_root.addWidget(vision_group)

        drawing_group = QGroupBox("Drawings")
        drawing_form = QFormLayout(drawing_group)
        self.drawing_provider_combo = QComboBox()
        for value, label in DRAWING_PROVIDERS:
            self.drawing_provider_combo.addItem(label, value)

        self.cloudflare_account_edit = QLineEdit()
        self.cloudflare_account_edit.setPlaceholderText(
            "Cloudflare account ID"
        )
        self.cloudflare_token_edit = QLineEdit()
        self.cloudflare_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.cloudflare_token_edit.setPlaceholderText(
            "API token with Workers AI access"
        )
        self.cloudflare_model_edit = QLineEdit()
        self.cloudflare_model_edit.setPlaceholderText(
            "@cf/black-forest-labs/flux-1-schnell"
        )
        self.cloudflare_test_button = QPushButton("Test Cloudflare")
        self.cloudflare_status = QLabel("")
        self.cloudflare_status.setWordWrap(True)
        self.cloudflare_status.setStyleSheet("color: #777;")

        drawing_hint = QLabel(
            "Cloudflare Workers AI renders a polished JPEG with FLUX.1 schnell. "
            "The free plan includes 10,000 Neurons per day, roughly 170 images "
            "at the default 4 steps, and resets daily at 00:00 UTC. The "
            "drawing gallery keeps both SVG and JPEG/PNG drawings.\n"
            "Open <a href=\"https://dash.cloudflare.com/?to=/:account/ai/"
            "workers-ai\">Workers AI</a>, select <b>Use REST API</b>, then "
            "select <b>Create a Workers AI API Token</b> and copy both the "
            "token and the <b>Account ID</b>. The token secret is shown only "
            "once. The test button renders one small image and uses a few "
            "free Neurons. If Cloudflare is unavailable, Milky falls back to "
            "her SVG drawing path."
        )
        drawing_hint.setWordWrap(True)
        drawing_hint.setTextFormat(Qt.TextFormat.RichText)
        drawing_hint.setOpenExternalLinks(True)
        drawing_hint.setStyleSheet("color: #777;")

        drawing_form.addRow("Drawing engine", self.drawing_provider_combo)
        drawing_form.addRow(
            "Cloudflare account ID", self.cloudflare_account_edit
        )
        drawing_form.addRow(
            "Cloudflare API token", self.cloudflare_token_edit
        )
        drawing_form.addRow(
            "Cloudflare model", self.cloudflare_model_edit
        )
        drawing_form.addRow("", self.cloudflare_test_button)
        drawing_form.addRow(self.cloudflare_status)
        drawing_form.addRow(drawing_hint)
        general_root.addWidget(drawing_group)

        life_group = QGroupBox("Life cycle")
        life_form = QFormLayout(life_group)
        self.life_enabled_check = QCheckBox(
            "Let Milky do little things on her own"
        )
        self.life_outfit_check = QCheckBox(
            "Sometimes suggest a new outfit"
        )
        self.life_draw_check = QCheckBox(
            "Sometimes draw something for fun"
        )
        self.life_min_spin = QSpinBox()
        self.life_min_spin.setRange(1, 1440)
        self.life_min_spin.setSuffix(" min")
        self.life_max_spin = QSpinBox()
        self.life_max_spin.setRange(1, 1440)
        self.life_max_spin.setSuffix(" min")
        life_interval = QHBoxLayout()
        life_interval.addWidget(QLabel("Between"))
        life_interval.addWidget(self.life_min_spin)
        life_interval.addWidget(QLabel("and"))
        life_interval.addWidget(self.life_max_spin)
        life_interval.addStretch()
        life_interval_widget = QWidget()
        life_interval_widget.setLayout(life_interval)

        life_hint = QLabel(
            "When the interval passes, Milky may ask whether she should put "
            "on a random accessory or she may sketch a small picture and add "
            "it to the drawing gallery. She waits while you are chatting, "
            "typing, or when the window is hidden. Turn this off to keep her "
            "completely quiet between conversations."
        )
        life_hint.setWordWrap(True)
        life_hint.setStyleSheet("color: #777;")

        life_form.addRow(self.life_enabled_check)
        life_form.addRow(self.life_outfit_check)
        life_form.addRow(self.life_draw_check)
        life_form.addRow("Interval", life_interval_widget)
        life_form.addRow(life_hint)
        general_root.addWidget(life_group)

        outfit_tab = QWidget()
        outfit_layout = QVBoxLayout(outfit_tab)
        outfit_hint = QLabel(
            "Clothing and accessories Milky is wearing. Items stay on her "
            "between sessions until you remove them here.\n"
            "Ask her, for example, «одень шапку» or «надень очки». "
            "Changes apply when you click Save."
        )
        outfit_hint.setWordWrap(True)
        outfit_hint.setStyleSheet("color: #777;")
        outfit_layout.addWidget(outfit_hint)

        self.outfit_list = QListWidget()
        self.outfit_list.setIconSize(QSize(44, 44))
        self.outfit_list.itemSelectionChanged.connect(
            self._update_outfit_buttons
        )
        self.outfit_list.itemDoubleClicked.connect(
            lambda _item: self._remove_outfit_item()
        )
        outfit_layout.addWidget(self.outfit_list, 1)

        self.outfit_empty = QLabel("Milky is not wearing anything yet.")
        self.outfit_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.outfit_empty.setStyleSheet("color: #888;")
        outfit_layout.addWidget(self.outfit_empty)

        outfit_buttons = QHBoxLayout()
        self.outfit_remove_button = QPushButton("Remove selected")
        self.outfit_remove_button.clicked.connect(self._remove_outfit_item)
        self.outfit_clear_button = QPushButton("Remove all")
        self.outfit_clear_button.clicked.connect(self._clear_outfit)
        outfit_buttons.addWidget(self.outfit_remove_button)
        outfit_buttons.addWidget(self.outfit_clear_button)
        outfit_buttons.addStretch()
        outfit_layout.addLayout(outfit_buttons)
        tabs.addTab(outfit_tab, "Outfit")

        search_scroll = QScrollArea()
        search_scroll.setWidgetResizable(True)
        search_scroll.setFrameShape(QFrame.Shape.NoFrame)
        search_page = QWidget()
        search_root = QVBoxLayout(search_page)
        search_scroll.setWidget(search_page)
        tabs.addTab(search_scroll, "Search and history")

        search_group = QGroupBox("Web search")
        search_form = QFormLayout(search_group)
        self.search_enabled_check = QCheckBox(
            "Allow Milky to search the web and YouTube"
        )
        self.search_max_spin = QSpinBox()
        self.search_max_spin.setRange(1, 10)
        self.search_region_edit = QLineEdit()
        self.search_region_edit.setPlaceholderText("ru-ru")
        self.search_safesearch_combo = QComboBox()
        for value, label in (
            ("on", "On"),
            ("moderate", "Moderate"),
            ("off", "Off"),
        ):
            self.search_safesearch_combo.addItem(label, value)
        self.search_google_check = QCheckBox(
            "Try Google as a last-resort source"
        )
        self.search_youtube_check = QCheckBox("Search YouTube for videos")
        search_hint = QLabel(
            "Results come from DuckDuckGo, Google and YouTube; no API key is "
            "needed. Milky reads the titles, links and snippets, then answers "
            "from them instead of only opening a search page. Found links "
            "open in the browser and are never read aloud."
        )
        search_hint.setWordWrap(True)
        search_hint.setStyleSheet("color: #777;")
        search_form.addRow(self.search_enabled_check)
        search_form.addRow("Results per search", self.search_max_spin)
        search_form.addRow("Region", self.search_region_edit)
        search_form.addRow("Safe search", self.search_safesearch_combo)
        search_form.addRow(self.search_google_check)
        search_form.addRow(self.search_youtube_check)
        search_form.addRow(search_hint)
        search_root.addWidget(search_group)

        history_group = QGroupBox("Conversation history")
        history_form = QFormLayout(history_group)
        self.history_limit_spin = QSpinBox()
        self.history_limit_spin.setRange(2, 100)
        self.history_keep_spin = QSpinBox()
        self.history_keep_spin.setRange(2, 20)
        history_hint = QLabel(
            "Ask Milky <b>«сожми историю»</b> or <b>«прибери лишнее»</b> to "
            "compact the dialog: the last messages stay verbatim and older "
            "ones become a short local summary. No model tokens are used. "
            "<b>«очисти историю»</b> clears the dialog; saved facts in "
            "memory.json are kept."
        )
        history_hint.setWordWrap(True)
        history_hint.setTextFormat(Qt.TextFormat.RichText)
        history_hint.setStyleSheet("color: #777;")
        history_form.addRow(
            "Messages sent to the model", self.history_limit_spin
        )
        history_form.addRow(
            "Messages kept when compacting", self.history_keep_spin
        )
        history_form.addRow(history_hint)
        search_root.addWidget(history_group)
        search_root.addStretch()

        addons_scroll = QScrollArea()
        addons_scroll.setWidgetResizable(True)
        addons_scroll.setFrameShape(QFrame.Shape.NoFrame)
        addons_tab = QWidget()
        addons_layout = QVBoxLayout(addons_tab)
        addons_scroll.setWidget(addons_tab)
        addons_hint = QLabel(
            "Skills are small addons that give Milky extra tools. Each skill "
            "is a folder with addon.json, a Python entry file and optional "
            "files in an assets folder. Skills run inside Milky with the same "
            "permissions, so only install code you trust."
        )
        addons_hint.setWordWrap(True)
        addons_hint.setStyleSheet("color: #777;")
        addons_layout.addWidget(addons_hint)

        installed_group = QGroupBox("Installed skills")
        installed_layout = QVBoxLayout(installed_group)
        self.addons_list = QListWidget()
        self.addons_list.setMinimumHeight(170)
        self.addons_list.setIconSize(QSize(32, 32))
        self.addons_list.itemChanged.connect(self._addon_toggled)
        self.addons_list.currentItemChanged.connect(self._show_addon_settings)
        installed_layout.addWidget(self.addons_list)

        self.addons_empty = QLabel("No skills installed yet.")
        self.addons_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.addons_empty.setStyleSheet("color: #888;")
        installed_layout.addWidget(self.addons_empty)

        self.addons_path = QLabel()
        self.addons_path.setWordWrap(True)
        self.addons_path.setStyleSheet("color: #777;")
        installed_layout.addWidget(self.addons_path)

        addons_save_hint = QLabel(
            "Select a skill to edit its settings. Toggle it to enable or "
            "disable it. Changes apply when you click Save; use Reload skills "
            "to load them immediately."
        )
        addons_save_hint.setWordWrap(True)
        addons_save_hint.setStyleSheet("color: #777;")
        installed_layout.addWidget(addons_save_hint)

        addons_buttons = QHBoxLayout()
        self.addons_reload_button = QPushButton("Reload skills")
        self.addons_reload_button.clicked.connect(self._reload_addons)
        self.addons_folder_button = QPushButton("Open skills folder")
        self.addons_folder_button.clicked.connect(self._open_addons_folder)
        addons_buttons.addWidget(self.addons_reload_button)
        addons_buttons.addWidget(self.addons_folder_button)
        addons_buttons.addStretch()
        installed_layout.addLayout(addons_buttons)
        addons_layout.addWidget(installed_group)

        settings_group = QGroupBox("Skill settings")
        settings_layout = QVBoxLayout(settings_group)
        self.addon_settings_title = QLabel("Select a skill to configure it.")
        self.addon_settings_title.setStyleSheet("font-weight: 600;")
        settings_layout.addWidget(self.addon_settings_title)

        self.addon_settings_description = QLabel(
            "Skills can declare visual settings in addon.json. Values are "
            "passed to the skill as ctx.settings and stored in settings.json "
            "under addons.settings.<id>."
        )
        self.addon_settings_description.setWordWrap(True)
        self.addon_settings_description.setStyleSheet("color: #777;")
        settings_layout.addWidget(self.addon_settings_description)

        self.addon_settings_scroll = QScrollArea()
        self.addon_settings_scroll.setWidgetResizable(True)
        self.addon_settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.addon_settings_scroll.setMinimumHeight(150)
        self.addon_settings_content = QWidget()
        self.addon_settings_layout = QVBoxLayout(self.addon_settings_content)
        self.addon_settings_layout.setContentsMargins(0, 0, 0, 0)
        self.addon_settings_scroll.setWidget(self.addon_settings_content)
        settings_layout.addWidget(self.addon_settings_scroll)

        self.addon_settings_status = QLabel()
        self.addon_settings_status.setWordWrap(True)
        self.addon_settings_status.setStyleSheet("color: #777;")
        settings_layout.addWidget(self.addon_settings_status)

        settings_buttons = QHBoxLayout()
        self.addon_settings_reset_button = QPushButton("Reset to defaults")
        self.addon_settings_reset_button.setEnabled(False)
        self.addon_settings_reset_button.clicked.connect(
            self._reset_addon_settings
        )
        settings_buttons.addWidget(self.addon_settings_reset_button)
        settings_buttons.addStretch()
        settings_layout.addLayout(settings_buttons)
        addons_layout.addWidget(settings_group)

        github_group = QGroupBox("Install from GitHub")
        github_layout = QVBoxLayout(github_group)
        github_layout.addWidget(QLabel("Repository or folder URL"))
        self.skill_url_edit = QLineEdit()
        self.skill_url_edit.setPlaceholderText(
            "https://github.com/owner/repo"
        )
        self.skill_url_edit.returnPressed.connect(self._install_skill)
        github_layout.addWidget(self.skill_url_edit)

        self.skill_install_button = QPushButton("Install skill")
        self.skill_install_button.clicked.connect(self._install_skill)
        github_layout.addWidget(self.skill_install_button)

        self.skill_status = QLabel()
        self.skill_status.setWordWrap(True)
        self.skill_status.setTextFormat(Qt.TextFormat.PlainText)
        github_layout.addWidget(self.skill_status)

        github_hint = QLabel(
            "Public repositories only. The repository can be the skill "
            "itself or contain one or more skill folders. You can also "
            "point to a folder:\n"
            "https://github.com/owner/repo/tree/main/path/to/skill\n"
            "Installing replaces a skill with the same id."
        )
        github_hint.setWordWrap(True)
        github_hint.setStyleSheet("color: #777;")
        github_layout.addWidget(github_hint)
        addons_layout.addWidget(github_group)
        addons_layout.addStretch()
        tabs.addTab(addons_scroll, "Skills")

        shop_scroll = QScrollArea()
        shop_scroll.setWidgetResizable(True)
        shop_scroll.setFrameShape(QFrame.Shape.NoFrame)
        shop_page = QWidget()
        self.shop_layout = QVBoxLayout(shop_page)
        shop_scroll.setWidget(shop_page)
        shop_hint = QLabel(
            "Browse extensions from the Milky catalog. Cards show an icon, "
            "preview, author, version and description."
        )
        shop_hint.setWordWrap(True)
        shop_hint.setStyleSheet("color: #777;")
        self.shop_layout.addWidget(shop_hint)
        shop_buttons = QHBoxLayout()
        self.shop_refresh_button = QPushButton("Refresh catalog")
        self.shop_refresh_button.clicked.connect(self._refresh_shop)
        shop_buttons.addWidget(self.shop_refresh_button)
        self.shop_status = QLabel("Catalog is not loaded yet.")
        self.shop_status.setStyleSheet("color: #777;")
        shop_buttons.addWidget(self.shop_status, 1)
        self.shop_layout.addLayout(shop_buttons)
        self.shop_cards = QVBoxLayout()
        self.shop_layout.addLayout(self.shop_cards)
        self.shop_layout.addStretch()
        self._shop_worker = None
        tabs.addTab(shop_scroll, "Extension Store")

        # Connect UI elements
        self.name_edit.textChanged.connect(self._store_current)
        self.type_combo.currentIndexChanged.connect(self._store_current)
        self.url_edit.textChanged.connect(self._store_current)
        self.model_edit.textChanged.connect(self._store_current)
        self.key_edit.textChanged.connect(self._store_current)
        self.active_check.toggled.connect(self._set_active)

        self.tts_enabled_check.toggled.connect(self._tts_changed)
        self.milka_radio.toggled.connect(self._tts_changed)
        self.groq_radio.toggled.connect(self._tts_changed)
        self.milka_url_edit.textChanged.connect(self._tts_changed)
        self.milka_voice_edit.textChanged.connect(self._tts_changed)
        self.milka_speed_spin.valueChanged.connect(self._tts_changed)
        self.groq_key_edit.textChanged.connect(self._tts_changed)
        self.groq_model_edit.textChanged.connect(self._tts_changed)
        self.groq_voice_edit.textChanged.connect(self._tts_changed)
        self.tts_test_button.clicked.connect(self._test_milka_tts)

        self.vision_enabled_check.toggled.connect(self._vision_changed)
        self.vision_provider_combo.currentIndexChanged.connect(
            self._vision_provider_changed
        )
        self.vision_model_edit.textChanged.connect(self._vision_changed)

        self.drawing_provider_combo.currentIndexChanged.connect(
            self._drawing_changed
        )
        self.cloudflare_account_edit.textChanged.connect(
            self._drawing_changed
        )
        self.cloudflare_token_edit.textChanged.connect(self._drawing_changed)
        self.cloudflare_model_edit.textChanged.connect(self._drawing_changed)
        self.cloudflare_test_button.clicked.connect(self._test_cloudflare)

        self.life_enabled_check.toggled.connect(self._life_changed)
        self.life_outfit_check.toggled.connect(self._life_changed)
        self.life_draw_check.toggled.connect(self._life_changed)
        self.life_min_spin.valueChanged.connect(self._life_changed)
        self.life_max_spin.valueChanged.connect(self._life_changed)

        self.search_enabled_check.toggled.connect(self._search_changed)
        self.search_max_spin.valueChanged.connect(self._search_changed)
        self.search_region_edit.textChanged.connect(self._search_changed)
        self.search_safesearch_combo.currentIndexChanged.connect(
            self._search_changed
        )
        self.search_google_check.toggled.connect(self._search_changed)
        self.search_youtube_check.toggled.connect(self._search_changed)
        self.history_limit_spin.valueChanged.connect(self._history_changed)
        self.history_keep_spin.valueChanged.connect(self._history_changed)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        box.button(QDialogButtonBox.StandardButton.Save).setText("Save")
        box.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancel")
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        root.addWidget(box)

    def _active_row(self):
        active = self._settings.get("active")
        for index, provider in enumerate(self._providers):
            if provider["name"] == active:
                return index
        return 0

    def _refresh_list(self, row):
        self._loading = True
        self.provider_list.clear()
        for provider in self._providers:
            self.provider_list.addItem(provider["name"] or "(unnamed)")
        self._loading = False
        if self._providers:
            self.provider_list.setCurrentRow(max(0, min(row, len(self._providers) - 1)))
        self._refresh_vision_providers()

    def _load_provider(self, row):
        if self._loading or not (0 <= row < len(self._providers)):
            return
        provider = self._providers[row]
        self._loading = True
        self.name_edit.setText(provider["name"])
        index = self.type_combo.findData(provider["type"])
        self.type_combo.setCurrentIndex(index if index >= 0 else 0)
        self.url_edit.setText(provider["base_url"])
        self.model_edit.setText(provider["model"])
        self.key_edit.setText(provider["api_key"])
        self.active_check.setChecked(
            self._settings.get("active") == provider["name"]
        )
        self._loading = False

    def _load_tts(self):
        self._loading = True
        self.tts_enabled_check.setChecked(bool(self._tts.get("enabled", True)))
        provider = self._tts.get("provider", "milka")
        if provider == "milka":
            self.milka_radio.setChecked(True)
        else:
            self.groq_radio.setChecked(True)
        self.milka_url_edit.setText(self._tts.get("milka_url", ""))
        self.milka_voice_edit.setText(self._tts.get("milka_voice", "sveta"))
        self.milka_speed_spin.setValue(
            float(self._tts.get("milka_speed", 1.0))
        )
        self.groq_key_edit.setText(self._tts.get("groq_api_key", ""))
        self.groq_model_edit.setText(
            self._tts.get("groq_model", "playai-tts")
        )
        self.groq_voice_edit.setText(
            self._tts.get("groq_voice", "Fritz-PlayAI")
        )
        self._loading = False
        self._update_tts_state()

    def _tts_changed(self):
        self._store_tts()
        self._update_tts_state()

    def _store_tts(self):
        if self._loading:
            return
        provider = "milka" if self.milka_radio.isChecked() else "groq"
        self._tts = {
            "enabled": self.tts_enabled_check.isChecked(),
            "provider": provider,
            "milka_url": self.milka_url_edit.text().strip().rstrip("/"),
            "milka_voice": self.milka_voice_edit.text().strip() or "sveta",
            "milka_speed": round(self.milka_speed_spin.value(), 1),
            "groq_api_key": self.groq_key_edit.text().strip(),
            "groq_model": self.groq_model_edit.text().strip()
            or "canopylabs/orpheus-v1-english",
            "groq_voice": self.groq_voice_edit.text().strip()
            or "hannah",
        }
        self._settings["tts"] = dict(self._tts)

    def _update_tts_state(self):
        enabled = self.tts_enabled_check.isChecked()
        provider = "milka" if self.milka_radio.isChecked() else "groq"
        self.milka_radio.setEnabled(enabled)
        self.groq_radio.setEnabled(enabled)
        for widget in (
            self.milka_url_edit,
            self.milka_voice_edit,
            self.milka_speed_spin,
        ):
            widget.setEnabled(enabled and provider == "milka")
        for widget in (
            self.groq_key_edit,
            self.groq_model_edit,
            self.groq_voice_edit,
        ):
            widget.setEnabled(enabled and provider == "groq")
        self.tts_test_button.setEnabled(enabled and provider == "milka")

    def _refresh_vision_providers(self):
        if not hasattr(self, "vision_provider_combo"):
            return
        current = self.vision_provider_combo.currentData()
        names = {provider["name"] for provider in self._providers}
        if current not in names:
            current = self._vision.get("provider")
        previous_loading = self._loading
        self._loading = True
        self.vision_provider_combo.clear()
        for provider in self._providers:
            self.vision_provider_combo.addItem(
                provider["name"], provider["name"]
            )
        index = self.vision_provider_combo.findData(current)
        if index < 0:
            index = 0
        if self.vision_provider_combo.count():
            self.vision_provider_combo.setCurrentIndex(index)
            self._vision["provider"] = self.vision_provider_combo.currentData()
        else:
            self._vision["provider"] = ""
        self._loading = previous_loading

    def _load_vision(self):
        self._loading = True
        self._refresh_vision_providers()
        self.vision_enabled_check.setChecked(
            bool(self._vision.get("enabled", True))
        )
        self.vision_model_edit.setText(
            self._vision.get("model", "qwen/qwen3.8-27b")
        )
        self._loading = False
        self._update_vision_state()

    def _vision_provider_changed(self):
        if not self._loading:
            name = self.vision_provider_combo.currentData()
            provider = next(
                (
                    item
                    for item in self._providers
                    if item["name"] == name
                ),
                None,
            )
            model = self.vision_model_edit.text().strip()
            suggested = None
            if provider is not None:
                if (
                    provider["type"] == "ollama"
                    and model == "qwen/qwen3.8-27b"
                ):
                    suggested = "qwen3-vl:8b"
                elif (
                    "groq" in provider["base_url"].lower()
                    and model in ("", "qwen3-vl:8b")
                ):
                    suggested = "qwen/qwen3.8-27b"
            if suggested:
                self._loading = True
                self.vision_model_edit.setText(suggested)
                self._loading = False
        self._vision_changed()

    def _vision_changed(self):
        self._store_vision()
        self._update_vision_state()

    def _store_vision(self):
        if self._loading:
            return
        provider = self.vision_provider_combo.currentData() or ""
        model = self.vision_model_edit.text().strip()
        self._vision = {
            "enabled": self.vision_enabled_check.isChecked(),
            "provider": provider,
            "model": model or "qwen/qwen3.8-27b",
            "max_width": int(self._vision.get("max_width", 1600)),
            "jpeg_quality": int(self._vision.get("jpeg_quality", 82)),
        }
        self._settings["vision"] = dict(self._vision)

    def _update_vision_state(self):
        enabled = self.vision_enabled_check.isChecked()
        self.vision_provider_combo.setEnabled(enabled)
        self.vision_model_edit.setEnabled(enabled)

    def _load_drawing(self):
        self._loading = True
        provider = self._drawing.get("provider", "model")
        index = self.drawing_provider_combo.findData(provider)
        self.drawing_provider_combo.setCurrentIndex(index if index >= 0 else 0)
        self.cloudflare_account_edit.setText(
            self._drawing.get("cloudflare_account_id", "")
        )
        self.cloudflare_token_edit.setText(
            self._drawing.get("cloudflare_api_token", "")
        )
        self.cloudflare_model_edit.setText(
            self._drawing.get(
                "cloudflare_model",
                "@cf/black-forest-labs/flux-1-schnell",
            )
        )
        self._loading = False
        self._update_drawing_state()

    def _drawing_changed(self):
        self._store_drawing()
        if not self._cloudflare_testing:
            self.cloudflare_status.setText("")
        self._update_drawing_state()

    def _store_drawing(self):
        if self._loading:
            return
        provider = self.drawing_provider_combo.currentData() or "model"
        api_token = self.cloudflare_token_edit.text().strip()
        if api_token.lower().startswith("bearer "):
            api_token = api_token[7:].strip()
        try:
            steps = int(self._drawing.get("cloudflare_steps", 4))
        except (TypeError, ValueError):
            steps = 4
        self._drawing = {
            "provider": provider,
            "cloudflare_account_id": self.cloudflare_account_edit.text().strip(),
            "cloudflare_api_token": api_token,
            "cloudflare_model": self.cloudflare_model_edit.text().strip()
            or "@cf/black-forest-labs/flux-1-schnell",
            "cloudflare_steps": max(1, min(8, steps)),
        }
        self._settings["drawing"] = dict(self._drawing)

    def _update_drawing_state(self):
        cloudflare = (
            (self.drawing_provider_combo.currentData() or "model")
            == "cloudflare"
        )
        for widget in (
            self.cloudflare_account_edit,
            self.cloudflare_token_edit,
            self.cloudflare_model_edit,
        ):
            widget.setEnabled(cloudflare)
        self.cloudflare_test_button.setEnabled(
            cloudflare and not self._cloudflare_testing
        )

    def _test_cloudflare(self):
        self._store_drawing()
        drawing = self._drawing
        account_id = drawing.get("cloudflare_account_id", "").strip()
        api_token = drawing.get("cloudflare_api_token", "").strip()
        if api_token.lower().startswith("bearer "):
            api_token = api_token[7:].strip()
        if not account_id or not api_token:
            self.cloudflare_status.setText(
                "Enter the Cloudflare account ID and API token first."
            )
            return

        if self._cloudflare_reply is not None:
            self._cloudflare_reply.abort()
            self._cloudflare_reply.deleteLater()
            self._cloudflare_reply = None

        model = drawing.get(
            "cloudflare_model", "@cf/black-forest-labs/flux-1-schnell"
        ).strip() or "@cf/black-forest-labs/flux-1-schnell"
        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{quote(account_id, safe='')}/ai/run/"
            f"{quote(model, safe='@/')}"
        )
        payload = {
            "prompt": (
                "A small red apple on a wooden table, warm storybook "
                "illustration, simple background"
            ),
            "steps": 4,
        }
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(
            b"Authorization", f"Bearer {api_token}".encode("utf-8")
        )
        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader,
            "application/json",
        )
        request.setTransferTimeout(120000)

        self._cloudflare_testing = True
        self.cloudflare_status.setText("Generating a test image...")
        self._update_drawing_state()
        reply = self._network.post(
            request,
            QByteArray(json.dumps(payload).encode("utf-8")),
        )
        self._cloudflare_reply = reply
        reply.finished.connect(lambda r=reply: self._on_cloudflare_reply(r))

    def _on_cloudflare_reply(self, reply):
        if reply is not self._cloudflare_reply:
            reply.deleteLater()
            return
        self._cloudflare_reply = None
        self._cloudflare_testing = False

        status = reply.attribute(
            QNetworkRequest.Attribute.HttpStatusCodeAttribute
        )
        body = bytes(reply.readAll()).decode("utf-8", "replace").strip()
        data = None
        try:
            data = json.loads(body) if body else None
        except ValueError:
            data = None

        error = None
        if reply.error() != QNetworkReply.NetworkError.NoError:
            error = reply.errorString()
        if status != 200:
            detail = ""
            if isinstance(data, dict):
                parts = []
                for item in data.get("errors") or []:
                    if isinstance(item, dict):
                        parts.append(str(item.get("message") or ""))
                    elif item:
                        parts.append(str(item))
                detail = "; ".join(part for part in parts if part)
            detail = detail or body
            detail = " ".join(detail.split())
            if len(detail) > 220:
                detail = detail[:217] + "..."
            error = error or f"HTTP {status}"
            if detail:
                error += f": {detail}"
        elif not isinstance(data, dict) or data.get("success") is False:
            error = "Cloudflare returned an error response."
        else:
            result = data.get("result")
            image = result.get("image") if isinstance(result, dict) else None
            if (
                not isinstance(image, str)
                or len(image) < 100
                or not image.startswith(
                    ("/9j/", "iVBOR", "UklGR", "data:image")
                )
            ):
                error = "Cloudflare returned no image data."

        if error:
            self.cloudflare_status.setText(f"Cloudflare error: {error}")
        else:
            self.cloudflare_status.setText(
                "Cloudflare is ready: FLUX returned a JPEG image."
            )
        reply.deleteLater()
        self._update_drawing_state()

    def _load_life(self):
        self._loading = True
        self.life_enabled_check.setChecked(
            bool(self._life.get("enabled", True))
        )
        self.life_outfit_check.setChecked(
            bool(self._life.get("suggest_outfit", True))
        )
        self.life_draw_check.setChecked(bool(self._life.get("draw", True)))
        self.life_min_spin.setValue(int(self._life.get("min_minutes", 10)))
        self.life_max_spin.setValue(int(self._life.get("max_minutes", 30)))
        self._loading = False
        self._update_life_state()

    def _life_changed(self):
        self._store_life()
        self._update_life_state()

    def _store_life(self):
        if self._loading:
            return
        minimum = int(self.life_min_spin.value())
        maximum = int(self.life_max_spin.value())
        if maximum < minimum:
            maximum = minimum
            self._loading = True
            self.life_max_spin.setValue(maximum)
            self._loading = False
        self._life = {
            "enabled": self.life_enabled_check.isChecked(),
            "suggest_outfit": self.life_outfit_check.isChecked(),
            "draw": self.life_draw_check.isChecked(),
            "min_minutes": minimum,
            "max_minutes": maximum,
        }
        self._settings["life"] = dict(self._life)

    def _update_life_state(self):
        enabled = self.life_enabled_check.isChecked()
        self.life_outfit_check.setEnabled(enabled)
        self.life_draw_check.setEnabled(enabled)
        interval_enabled = enabled and (
            self.life_outfit_check.isChecked()
            or self.life_draw_check.isChecked()
        )
        self.life_min_spin.setEnabled(interval_enabled)
        self.life_max_spin.setEnabled(interval_enabled)

    def _load_search(self):
        self._loading = True
        self.search_enabled_check.setChecked(self._search["enabled"])
        self.search_max_spin.setValue(self._search["max_results"])
        self.search_region_edit.setText(self._search["region"])
        index = self.search_safesearch_combo.findData(
            self._search["safesearch"]
        )
        self.search_safesearch_combo.setCurrentIndex(
            index if index >= 0 else 0
        )
        self.search_google_check.setChecked(self._search["google"])
        self.search_youtube_check.setChecked(self._search["youtube"])
        self._loading = False
        self._update_search_state()

    def _search_changed(self):
        self._store_search()
        self._update_search_state()

    def _store_search(self):
        if self._loading:
            return
        region = self.search_region_edit.text().strip() or "ru-ru"
        self._search = {
            "enabled": self.search_enabled_check.isChecked(),
            "max_results": max(1, min(10, self.search_max_spin.value())),
            "region": region,
            "safesearch": (
                self.search_safesearch_combo.currentData() or "moderate"
            ),
            "google": self.search_google_check.isChecked(),
            "youtube": self.search_youtube_check.isChecked(),
        }
        self._settings["search"] = dict(self._search)

    def _update_search_state(self):
        enabled = self.search_enabled_check.isChecked()
        for widget in (
            self.search_max_spin,
            self.search_region_edit,
            self.search_safesearch_combo,
            self.search_google_check,
            self.search_youtube_check,
        ):
            widget.setEnabled(enabled)

    def _load_history(self):
        self._loading = True
        self.history_limit_spin.setValue(self._history["limit"])
        self.history_keep_spin.setValue(self._history["keep_recent"])
        self._loading = False
        self._update_history_state()

    def _history_changed(self):
        self._store_history()
        self._update_history_state()

    def _store_history(self):
        if self._loading:
            return
        limit = max(2, min(100, self.history_limit_spin.value()))
        keep = max(2, min(20, self.history_keep_spin.value()))
        self._history = {"limit": limit, "keep_recent": keep}
        self._settings["history"] = dict(self._history)

    def _update_history_state(self):
        limit = max(2, self.history_limit_spin.value())
        self.history_keep_spin.setMaximum(min(20, max(2, limit - 1)))
        if not self._loading:
            self._store_history()

    def _load_addons(self):
        current = self.addons_list.currentItem()
        selected_id = (
            current.data(Qt.ItemDataRole.UserRole) if current else ""
        )
        was_loading = self._loading
        self._loading = True
        self.addons_list.blockSignals(True)
        self.addons_list.clear()
        records = addon_records()
        disabled = set(self._addons.get("disabled") or [])
        selected_row = -1
        for row, record in enumerate(records):
            addon_id = record["id"]
            label = f"{record['name']} ({addon_id})"
            if record.get("version"):
                label += f"  v{record['version']}"
            icon = QIcon()
            if record.get("icon"):
                icon = self._addon_icon(record["icon"])
            item = QListWidgetItem(icon, label)
            item.setData(Qt.ItemDataRole.UserRole, addon_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Unchecked
                if addon_id in disabled
                else Qt.CheckState.Checked
            )
            details = []
            if record.get("description"):
                details.append(record["description"])
            if record.get("assets"):
                count = record["assets"]
                details.append(
                    f"Assets: {count} file" + ("" if count == 1 else "s")
                )
            if record.get("tools"):
                details.append("Tools: " + ", ".join(record["tools"]))
            if record.get("settings_schema"):
                details.append(
                    f"Settings: {len(record['settings_schema'])} field"
                    + ("" if len(record["settings_schema"]) == 1 else "s")
                )
            if record.get("error"):
                details.append("Error: " + record["error"])
            if details:
                item.setToolTip("\n".join(details))
            if addon_id == selected_id:
                selected_row = row
            self.addons_list.addItem(item)
        self.addons_list.blockSignals(False)
        self._loading = was_loading
        has_items = bool(records)
        self.addons_list.setVisible(has_items)
        self.addons_empty.setVisible(not has_items)
        if has_items:
            if selected_row < 0:
                selected_row = 0
            self.addons_list.setCurrentRow(selected_row)
        self._show_addon_settings()
        try:
            folder = addons_directory()
        except OSError as error:
            self.addons_path.setText(
                f"Skills folder is not writable: {error}"
            )
        else:
            self.addons_path.setText(f"Skills folder: {folder}")

    def _refresh_shop(self):
        if self._shop_worker is not None:
            return
        self.shop_refresh_button.setEnabled(False)
        self.shop_status.setText("Loading catalog...")
        worker = _ShopCatalogWorker(self)
        self._shop_worker = worker
        worker.completed.connect(self._shop_loaded)
        worker.finished.connect(self._shop_finished)
        worker.start()

    def _shop_finished(self):
        worker = self._shop_worker
        self._shop_worker = None
        self.shop_refresh_button.setEnabled(True)
        if worker is not None:
            worker.deleteLater()

    def _shop_loaded(self, catalog, error):
        while self.shop_cards.count():
            item = self.shop_cards.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if error:
            self.shop_status.setText(f"Could not load catalog: {error}")
            self.shop_status.setStyleSheet("color: #b3261e;")
            return
        extensions = extensions_from_catalog(catalog)
        self.shop_status.setText(f"{len(extensions)} extension(s) available")
        self.shop_status.setStyleSheet("color: #777;")
        if not extensions:
            self.shop_cards.addWidget(QLabel("No extensions are published yet."))
            return
        installed_records = {record["id"]: record for record in addon_records()}
        for extension in extensions:
            self.shop_cards.addWidget(
                self._shop_card(
                    extension,
                    installed_records.get(extension.get("id")),
                )
            )

    def _shop_card(self, extension, installed_record=None):
        card = QGroupBox()
        layout = QHBoxLayout(card)
        icon = QLabel()
        icon.setFixedSize(72, 72)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_url = extension.get("icon") or extension.get("preview")
        if icon_url:
            icon.setText("🧩")
            self._load_shop_image(icon, str(icon_url))
        else:
            icon.setText("🧩")
        layout.addWidget(icon)
        details = QVBoxLayout()
        title = QLabel(
            f"{extension.get('name') or extension.get('id', '')}"
            f"  v{extension.get('version') or 'unknown'}"
        )
        title.setStyleSheet("font-weight: 600; font-size: 14px;")
        details.addWidget(title)
        meta = str(extension.get("author") or "")
        if meta:
            label = QLabel(meta)
            label.setStyleSheet("color: #777;")
            details.addWidget(label)
        description = QLabel(str(extension.get("description") or "No description."))
        description.setWordWrap(True)
        details.addWidget(description)
        preview = str(extension.get("preview") or "")
        if preview and preview != str(extension.get("icon") or ""):
            preview_label = QLabel()
            preview_label.setMaximumHeight(120)
            details.addWidget(preview_label)
            self._load_shop_image(preview_label, preview)
        buttons = QHBoxLayout()
        repo = str(extension.get("repo") or "")
        installed = installed_record is not None
        install = QPushButton("Installed" if installed else "Install")
        install.setEnabled(bool(repo) and not installed)
        if installed:
            install.setToolTip("This extension is already installed.")
        install.clicked.connect(
            lambda _checked=False, repo=repo: self._install_shop_extension(repo)
        )
        buttons.addWidget(install)
        if installed:
            remove = QPushButton("Remove")
            remove.clicked.connect(
                lambda _checked=False, record=installed_record:
                self._remove_shop_extension(record)
            )
            buttons.addWidget(remove)
        buttons.addStretch()
        details.addLayout(buttons)
        layout.addLayout(details, 1)
        return card

    def _load_shop_image(self, label, url):
        request = QNetworkRequest(QUrl(url))
        reply = self._network.get(request)
        reply.finished.connect(
            lambda reply=reply, target=label: self._shop_image_finished(reply, target)
        )

    def _shop_image_finished(self, reply, label):
        if reply.error() == QNetworkReply.NetworkError.NoError:
            pixmap = QPixmap()
            pixmap.loadFromData(reply.readAll())
            if not pixmap.isNull():
                label.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        reply.deleteLater()

    def _install_shop_extension(self, repo):
        if not repo:
            return
        self.skill_url_edit.setText(repo)
        self._install_skill()

    def _remove_shop_extension(self, record):
        addon_id = str(record.get("id") or "")
        addon_name = str(record.get("name") or addon_id)
        if not addon_id or not record.get("path"):
            return
        answer = QMessageBox.question(
            self,
            "Remove extension",
            f"Remove {addon_name} ({addon_id}) from Milky?\n\n"
            "Its addon files will be deleted. Saved settings are kept in "
            "case you install it again.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            addon_path = Path(record["path"]).resolve()
            addons_root = Path(addons_directory()).resolve()
            addon_path.relative_to(addons_root)
            if addon_path == addons_root or not addon_path.is_dir():
                raise ValueError("Invalid addon folder")
            configure_addons(self._settings.get("addons") or {})
            shutil.rmtree(addon_path)
            configure_addons(self._settings.get("addons") or {})
        except Exception as error:
            QMessageBox.warning(
                self,
                "Remove extension",
                f"Could not remove {addon_name}:\n{error}",
            )
            return
        self._load_addons()
        self._refresh_shop()

    def _addon_toggled(self, item):
        if self._loading:
            return
        addon_id = item.data(Qt.ItemDataRole.UserRole)
        if not addon_id:
            return
        disabled = set(self._addons.get("disabled") or [])
        if item.checkState() == Qt.CheckState.Checked:
            disabled.discard(addon_id)
        else:
            disabled.add(addon_id)
        self._addons["disabled"] = sorted(disabled)
        self._settings["addons"] = copy.deepcopy(self._addons)
        self._show_addon_settings()

    def _show_addon_settings(self, current=None, previous=None):
        item = current or self.addons_list.currentItem()
        addon_id = (
            item.data(Qt.ItemDataRole.UserRole) if item is not None else ""
        )
        record = next(
            (
                entry
                for entry in addon_records()
                if entry["id"] == addon_id
            ),
            None,
        )

        was_loading = self._loading
        self._loading = True
        old = self.addon_settings_scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.addon_settings_content = content
        self.addon_settings_layout = layout
        self.addon_settings_scroll.setWidget(content)
        self.addon_settings_scroll.setVisible(True)
        self._addon_setting_widgets = {}

        if record is None:
            self._addon_settings_id = ""
            self._addon_settings_schema = []
            self.addon_settings_title.setText(
                "Select a skill to configure it."
            )
            self.addon_settings_description.setText(
                "Skills can declare visual settings in addon.json. Values "
                "are passed to the skill as ctx.settings and stored in "
                "settings.json."
            )
            self.addon_settings_status.setText("")
            self.addon_settings_reset_button.setEnabled(False)
            self.addon_settings_scroll.setVisible(False)
            layout.addStretch()
            self._loading = was_loading
            return

        self._addon_settings_id = addon_id
        self._addon_settings_schema = record.get("settings_schema") or []
        self.addon_settings_title.setText(f"{record['name']} settings")
        self.addon_settings_description.setText(
            "Values are stored under addons.settings."
            f"{addon_id} in settings.json and passed to the skill as "
            "ctx.settings. Changes apply when you click Save."
        )
        disabled = set(self._addons.get("disabled") or [])
        status = ""
        status_color = "#777"
        if record.get("error"):
            status = "This skill failed to load: " + record["error"]
            status_color = "#b3261e"
        elif addon_id in disabled:
            status = (
                "This skill is disabled. Its settings are kept and will "
                "apply when you enable it."
            )
        if not self._addon_settings_schema:
            if not status:
                status = "This skill does not declare any visual settings."
            self.addon_settings_status.setText(status)
            self.addon_settings_status.setStyleSheet(
                f"color: {status_color};"
            )
            self.addon_settings_reset_button.setEnabled(False)
            self.addon_settings_scroll.setVisible(False)
            layout.addStretch()
            self._loading = was_loading
            return

        values = dict(record.get("settings") or {})
        saved = (self._addons.get("settings") or {}).get(addon_id)
        if isinstance(saved, dict):
            values.update(saved)
        for field in self._addon_settings_schema:
            key = field.get("key")
            if not key:
                continue
            value = values.get(key, field.get("default"))
            value = coerce_addon_setting(field, value)
            self._add_addon_setting_field(field, value)
        layout.addStretch()
        self.addon_settings_status.setText(status)
        self.addon_settings_status.setStyleSheet(f"color: {status_color};")
        self.addon_settings_reset_button.setEnabled(True)
        self._loading = was_loading

    def _add_addon_setting_field(self, field, value):
        key = field["key"]
        label_text = field.get("label") or key
        field_type = field.get("type")
        if field_type == "bool":
            control = QCheckBox(label_text)
            control.setChecked(bool(value))
            control.toggled.connect(
                lambda checked, name=key: self._store_addon_setting(
                    name, bool(checked)
                )
            )
            self._addon_setting_widgets[key] = control
            self.addon_settings_layout.addWidget(control)
        else:
            label = QLabel(label_text)
            label.setStyleSheet("font-weight: 600;")
            self.addon_settings_layout.addWidget(label)
            control = self._addon_setting_control(field, value)
            self._addon_setting_widgets[key] = control
            self.addon_settings_layout.addWidget(control)

        description = field.get("description") or ""
        if description:
            hint = QLabel(description)
            hint.setWordWrap(True)
            hint.setStyleSheet("color: #777; font-size: 11px;")
            self.addon_settings_layout.addWidget(hint)

    def _addon_setting_control(self, field, value):
        key = field["key"]
        field_type = field.get("type")
        placeholder = field.get("placeholder") or ""
        if field_type == "int":
            control = QSpinBox()
            minimum = field.get("min")
            maximum = field.get("max")
            control.setRange(
                int(minimum) if minimum is not None else -2147483648,
                int(maximum) if maximum is not None else 2147483647,
            )
            control.setSingleStep(int(field.get("step") or 1))
            control.setSuffix(field.get("suffix") or "")
            control.setValue(int(value or 0))
            control.valueChanged.connect(
                lambda number, name=key: self._store_addon_setting(
                    name, int(number)
                )
            )
            return control
        if field_type == "number":
            control = QDoubleSpinBox()
            minimum = field.get("min")
            maximum = field.get("max")
            decimals = field.get("decimals")
            control.setDecimals(int(2 if decimals is None else decimals))
            control.setRange(
                float(minimum) if minimum is not None else -1.0e9,
                float(maximum) if maximum is not None else 1.0e9,
            )
            control.setSingleStep(float(field.get("step") or 0.1))
            control.setSuffix(field.get("suffix") or "")
            control.setValue(float(value or 0.0))
            control.valueChanged.connect(
                lambda number, name=key: self._store_addon_setting(
                    name, round(float(number), 6)
                )
            )
            return control
        if field_type == "select":
            control = QComboBox()
            for option in field.get("options") or []:
                control.addItem(option["label"], option["value"])
            index = control.findData(str(value if value is not None else ""))
            control.setCurrentIndex(index if index >= 0 else 0)
            control.currentIndexChanged.connect(
                lambda index, name=key, widget=control: (
                    self._store_addon_setting(
                        name, widget.itemData(index)
                    )
                )
            )
            return control
        if field_type == "path":
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            edit = QLineEdit(str(value or ""))
            edit.setPlaceholderText(placeholder)
            edit.textChanged.connect(
                lambda text, name=key: self._store_addon_setting(
                    name, text.strip()
                )
            )
            browse = QPushButton("Browse...")
            browse.clicked.connect(
                lambda _checked=False, target=edit, spec=field: (
                    self._browse_addon_path(target, spec)
                )
            )
            row_layout.addWidget(edit, 1)
            row_layout.addWidget(browse)
            return row
        if field.get("multiline"):
            control = QPlainTextEdit()
            control.setPlaceholderText(placeholder)
            control.setPlainText(str(value or ""))
            control.setFixedHeight(76)
            control.textChanged.connect(
                lambda name=key, widget=control: (
                    self._store_addon_setting(
                        name, widget.toPlainText().strip()
                    )
                )
            )
            return control

        control = QLineEdit(str(value or ""))
        control.setPlaceholderText(placeholder)
        if field.get("secret"):
            control.setEchoMode(QLineEdit.EchoMode.Password)
        control.textChanged.connect(
            lambda text, name=key: self._store_addon_setting(
                name, text.strip()
            )
        )
        return control

    def _browse_addon_path(self, edit, field):
        initial = edit.text().strip()
        if field.get("pick") == "file":
            value, _selected = QFileDialog.getOpenFileName(
                self, "Select file", initial
            )
        else:
            value = QFileDialog.getExistingDirectory(
                self, "Select folder", initial
            )
        if value:
            edit.setText(value)

    def _store_addon_setting(self, key, value):
        if self._loading or not self._addon_settings_id or not key:
            return
        per_addon = self._addons.get("settings")
        if not isinstance(per_addon, dict):
            per_addon = {}
            self._addons["settings"] = per_addon
        values = per_addon.get(self._addon_settings_id)
        if not isinstance(values, dict):
            values = {}
        values[key] = value
        per_addon[self._addon_settings_id] = values
        self._settings["addons"] = copy.deepcopy(self._addons)

    def _reset_addon_settings(self):
        if not self._addon_settings_id:
            return
        per_addon = self._addons.get("settings")
        if isinstance(per_addon, dict):
            per_addon.pop(self._addon_settings_id, None)
        self._settings["addons"] = copy.deepcopy(self._addons)
        self._show_addon_settings()

    def _store_addons(self):
        known = {record["id"] for record in addon_records()}
        disabled = [
            addon_id
            for addon_id in (self._addons.get("disabled") or [])
            if addon_id in known
        ]
        self._addons["disabled"] = sorted(disabled)
        self._settings["addons"] = copy.deepcopy(self._addons)

    def _open_addons_folder(self):
        try:
            folder = addons_directory()
        except OSError as error:
            QMessageBox.warning(
                self, "Skills", f"Could not open the skills folder:\n{error}"
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _reload_addons(self):
        self._store_addons()
        self._addons_applied = True
        try:
            configure_addons(self._settings.get("addons") or {})
        except Exception as error:
            QMessageBox.warning(
                self, "Skills", f"Could not reload skills:\n{error}"
            )
        self._load_addons()

    def _restore_addons(self):
        if not self._addons_applied or self._addons_restored:
            return
        self._addons_restored = True
        try:
            configure_addons(self._initial_addons)
        except Exception as error:
            print(f"[addons] could not restore addons: {error}", flush=True)

    def _installing(self):
        return self._install_worker is not None

    def _set_skill_status(self, text, kind="info"):
        colors = {"info": "#777", "ok": "#1a7f37", "error": "#b3261e"}
        self.skill_status.setStyleSheet(
            f"color: {colors.get(kind, colors['info'])};"
        )
        self.skill_status.setText(text)

    def _install_skill(self):
        if self._installing():
            return
        url = self.skill_url_edit.text().strip()
        if not url:
            self._set_skill_status(
                "Enter a GitHub repository URL.", "error"
            )
            return
        try:
            parse_github_url(url)
        except SkillInstallError as error:
            self._set_skill_status(str(error), "error")
            return
        answer = QMessageBox.question(
            self,
            "Install skill",
            "Milky will download and run Python code from:\n\n"
            f"{url}\n\n"
            "Skills run with Milky's permissions and can read files, use "
            "the network and control the computer. Only install repositories "
            "you trust.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._set_skill_status("Downloading and installing the skill...")
        self.skill_install_button.setEnabled(False)
        self.skill_url_edit.setEnabled(False)
        worker = _SkillInstallWorker(url, self)
        self._install_worker = worker
        worker.completed.connect(self._on_skill_installed)
        worker.finished.connect(self._install_finished)
        try:
            worker.start()
        except Exception as error:
            self._install_worker = None
            worker.deleteLater()
            self.skill_install_button.setEnabled(True)
            self.skill_url_edit.setEnabled(True)
            self._set_skill_status(
                f"Could not start the installer: {error}", "error"
            )

    def _on_skill_installed(self, result):
        if result.get("error"):
            self._set_skill_status(
                f"Could not install: {result['error']}", "error"
            )
            return

        installed = result.get("installed") or []
        known_before = {record["id"] for record in addon_records()}
        disabled = set(self._addons.get("disabled") or [])
        for item in installed:
            addon_id = item.get("id")
            if addon_id not in known_before:
                disabled.discard(addon_id)
        self._addons["disabled"] = sorted(disabled)
        self._settings["addons"] = copy.deepcopy(self._addons)
        self._addons_applied = True
        try:
            configure_addons(self._settings.get("addons") or {})
        except Exception as error:
            self._set_skill_status(
                f"The skill was downloaded but could not be loaded: {error}",
                "error",
            )
            self._load_addons()
            return

        self._load_addons()
        self._refresh_shop()
        if not installed:
            self._set_skill_status("No skills were installed.", "error")
            return

        names = ", ".join(
            f"{item.get('name') or item.get('id')} ({item.get('id')})"
            for item in installed
        )
        installed_ids = {item.get("id") for item in installed}
        tool_count = 0
        failed = []
        for record in addon_records():
            if record["id"] not in installed_ids:
                continue
            tool_count += len(record.get("tools") or [])
            if record.get("error"):
                failed.append(record["name"])
        source = result.get("source") or "GitHub"
        message = (
            f"Installed {names} from {source}. "
            f"{tool_count} tool(s) available. Click Save to keep the settings."
        )
        if failed:
            message += " Load errors: " + ", ".join(failed) + "."
        self._set_skill_status(message, "error" if failed else "ok")

    def _install_finished(self):
        worker = self._install_worker
        self._install_worker = None
        if worker is not None:
            worker.deleteLater()
        self.skill_install_button.setEnabled(True)
        self.skill_url_edit.setEnabled(True)

    def reject(self):
        if self._installing():
            QMessageBox.information(
                self,
                "Skills",
                "Wait for the skill installation to finish.",
            )
            return
        self._stop_shop_worker()
        super().reject()
        self._restore_addons()

    def _stop_shop_worker(self):
        worker = self._shop_worker
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            worker.wait(5000)
        self._shop_worker = None

    def closeEvent(self, event):
        if self._installing():
            QMessageBox.information(
                self,
                "Skills",
                "Wait for the skill installation to finish.",
            )
            event.ignore()
            return
        self._stop_shop_worker()
        super().closeEvent(event)
        self._restore_addons()

    def _addon_icon(self, path):
        side = 32
        try:
            data = Path(path).read_bytes()
        except OSError:
            return QIcon()
        renderer = QSvgRenderer(QByteArray(data))
        if renderer.isValid():
            pixmap = QPixmap(side * 2, side * 2)
            pixmap.setDevicePixelRatio(2.0)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            renderer.render(painter, QRectF(0, 0, side, side))
            painter.end()
            return QIcon(pixmap)
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return QIcon()
        pixmap = pixmap.scaled(
            side * 2,
            side * 2,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        pixmap.setDevicePixelRatio(2.0)
        return QIcon(pixmap)

    def _outfit_icon(self, svg):
        side = 44
        pixmap = QPixmap(side * 2, side * 2)
        pixmap.setDevicePixelRatio(2.0)
        pixmap.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(QByteArray(str(svg).encode("utf-8")))
        if renderer.isValid():
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            renderer.render(painter, QRectF(0, 0, side, side))
            painter.end()
        return QIcon(pixmap)

    def _refresh_outfit_list(self):
        self.outfit_list.clear()
        for item in self._outfit:
            slot = SLOT_LABELS.get(item["slot"], "Other")
            entry = QListWidgetItem(
                self._outfit_icon(item["svg"]),
                f"{item['name']}  ·  {slot}",
            )
            entry.setData(Qt.ItemDataRole.UserRole, item["id"])
            entry.setToolTip(f"{item['name']} ({slot})")
            self.outfit_list.addItem(entry)
        has_items = bool(self._outfit)
        self.outfit_list.setVisible(has_items)
        self.outfit_empty.setVisible(not has_items)
        self._update_outfit_buttons()

    def _update_outfit_buttons(self):
        has_items = bool(self._outfit)
        row = self.outfit_list.currentRow()
        self.outfit_remove_button.setEnabled(
            has_items and 0 <= row < len(self._outfit)
        )
        self.outfit_clear_button.setEnabled(has_items)

    def _remove_outfit_item(self):
        row = self.outfit_list.currentRow()
        if not (0 <= row < len(self._outfit)):
            return
        del self._outfit[row]
        self._refresh_outfit_list()
        if self._outfit:
            self.outfit_list.setCurrentRow(min(row, len(self._outfit) - 1))

    def _clear_outfit(self):
        if not self._outfit:
            return
        answer = QMessageBox.question(
            self,
            "Remove all clothing",
            "Remove everything Milky is wearing?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._outfit = []
        self._refresh_outfit_list()

    def _test_milka_tts(self):
        self._store_tts()
        base = self._tts.get("milka_url", "").strip().rstrip("/")
        if not base:
            self.tts_status.setText("Enter the Milka TTS URL first.")
            return
        if not base.lower().startswith(("http://", "https://")):
            self.tts_status.setText(
                "The Milka TTS URL must start with http:// or https://."
            )
            return
        if self._health_reply is not None:
            self._health_reply.abort()
            self._health_reply.deleteLater()
            self._health_reply = None
        self.tts_status.setText("Checking Milka TTS...")
        self.tts_test_button.setEnabled(False)
        request = QNetworkRequest(QUrl(base + "/health"))
        request.setTransferTimeout(5000)
        reply = self._network.get(request)
        self._health_reply = reply
        reply.finished.connect(lambda r=reply: self._on_health_reply(r))

    def _on_health_reply(self, reply):
        if reply is not self._health_reply:
            reply.deleteLater()
            return
        self._health_reply = None
        status = reply.attribute(
            QNetworkRequest.Attribute.HttpStatusCodeAttribute
        )
        body = bytes(reply.readAll()).decode("utf-8", "replace").strip()
        if reply.error() != QNetworkReply.NetworkError.NoError or status != 200:
            detail = " ".join(body.split()) or reply.errorString()
            if len(detail) > 180:
                detail = detail[:177] + "..."
            self.tts_status.setText(f"Error: {detail}")
        else:
            detail = " ".join(body.split())
            if len(detail) > 120:
                detail = detail[:117] + "..."
            suffix = f": {detail}" if detail else ""
            self.tts_status.setText(f"Milka TTS is reachable ({status}){suffix}.")
        reply.deleteLater()
        self._update_tts_state()

    def _store_current(self):
        if self._loading:
            return
        row = self.provider_list.currentRow()
        if not (0 <= row < len(self._providers)):
            return
        provider = self._providers[row]
        old_name = provider["name"]
        name = self.name_edit.text().strip()
        provider["name"] = name
        provider["type"] = self.type_combo.currentData() or "openai"
        provider["base_url"] = self.url_edit.text().strip()
        provider["model"] = self.model_edit.text().strip()
        provider["api_key"] = self.key_edit.text().strip()
        if name and self._settings.get("active") == old_name:
            self._settings["active"] = name
        if name and self._vision.get("provider") == old_name:
            self._vision["provider"] = name
            self._settings["vision"] = dict(self._vision)
        item = self.provider_list.item(row)
        if item is not None:
            item.setText(name or "(unnamed)")
        self._refresh_vision_providers()

    def _set_active(self, checked):
        if self._loading:
            return
        row = self.provider_list.currentRow()
        if not (0 <= row < len(self._providers)):
            return
        provider = self._providers[row]
        if checked:
            self._settings["active"] = provider["name"]
            return
        if self._settings.get("active") == provider["name"]:
            self._loading = True
            self.active_check.setChecked(True)
            self._loading = False

    def _add_provider(self):
        self._store_current()
        number = len(self._providers) + 1
        names = {provider["name"] for provider in self._providers}
        name = f"Endpoint {number}"
        while name in names:
            number += 1
            name = f"Endpoint {number}"
        self._providers.append(
            {
                "name": name,
                "type": "openai",
                "base_url": "https://openrouter.ai/api/v1",
                "model": "openai/gpt-4o-mini",
                "api_key": "",
            }
        )
        self._refresh_list(len(self._providers) - 1)

    def _remove_provider(self):
        self._store_current()
        if len(self._providers) <= 1:
            return
        row = self.provider_list.currentRow()
        removed = self._providers.pop(row)
        if self._settings.get("active") == removed["name"]:
            self._settings["active"] = self._providers[0]["name"]
        self._refresh_list(min(row, len(self._providers) - 1))

    def accept(self):
        if self._installing():
            QMessageBox.information(
                self,
                "Skills",
                "Wait for the skill installation to finish.",
            )
            return
        self._store_current()
        self._store_tts()
        self._store_drawing()
        self._store_vision()
        self._store_life()
        self._store_search()
        self._store_history()
        self._store_addons()
        names = [provider["name"] for provider in self._providers]
        if any(not name for name in names):
            QMessageBox.warning(self, "Settings", "Every endpoint must have a name.")
            return
        if len(set(names)) != len(names):
            QMessageBox.warning(self, "Settings", "Endpoint names must be unique.")
            return
        for provider in self._providers:
            if not provider["base_url"] or not provider["model"]:
                QMessageBox.warning(
                    self,
                    "Settings",
                    f"Fill in the URL and model for \"{provider['name']}\".",
                )
                return
        if self._settings.get("active") not in names:
            self._settings["active"] = names[0]
        vision = self._settings.get("vision") or {}
        if vision.get("enabled"):
            if vision.get("provider") not in names:
                QMessageBox.warning(
                    self,
                    "Screen vision",
                    "Choose an existing endpoint for screen vision.",
                )
                return
            if not vision.get("model"):
                QMessageBox.warning(
                    self,
                    "Screen vision",
                    "Enter a vision model, for example qwen/qwen3.8-27b "
                    "or qwen3-vl:8b.",
                )
                return
        tts = self._settings.get("tts") or {}
        if tts.get("enabled"):
            if tts.get("provider") == "milka":
                url = tts.get("milka_url", "")
                if not url:
                    QMessageBox.warning(
                        self,
                        "Text to speech",
                        "Enter the Milka TTS URL, for example "
                        "http://192.168.1.100:8765.",
                    )
                    return
                if not url.lower().startswith(("http://", "https://")):
                    QMessageBox.warning(
                        self,
                        "Text to speech",
                        "The Milka TTS URL must start with http:// or https://.",
                    )
                    return
            elif tts.get("provider") == "groq" and not tts.get(
                "groq_api_key"
            ):
                QMessageBox.warning(
                    self,
                    "Text to speech",
                    "Enter the Groq API key or set GROQ_API_KEY in .env.",
                )
                return
        drawing = self._settings.get("drawing") or {}
        if drawing.get("provider") == "cloudflare":
            if not drawing.get("cloudflare_account_id"):
                QMessageBox.warning(
                    self,
                    "Drawings",
                    "Enter the Cloudflare account ID, or select the SVG "
                    "drawing engine.",
                )
                return
            if not drawing.get("cloudflare_api_token"):
                QMessageBox.warning(
                    self,
                    "Drawings",
                    "Enter the Cloudflare API token, or select the SVG "
                    "drawing engine.",
                )
                return
        autostart = self.autostart_check.isChecked()
        try:
            set_autostart(autostart)
        except Exception as error:
            QMessageBox.warning(
                self,
                "Autostart",
                f"Could not change autostart:\n{error}",
            )
            return
        self._settings["autostart"] = autostart
        self._settings["providers"] = self._providers
        try:
            self._outfit = save_outfit(self._outfit)
        except OSError as error:
            QMessageBox.warning(
                self,
                "Outfit",
                f"Could not save Milky's outfit:\n{error}",
            )
            return
        save_settings(self._settings)
        super().accept()
