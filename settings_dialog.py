import copy

from PySide6.QtCore import QUrl
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QRadioButton,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from autostart import (
    autostart_enabled,
    autostart_supported,
    set_autostart,
)
from settings_store import (
    PROVIDER_TYPES,
    default_tts,
    save_settings,
)


class SettingsDialog(QDialog):

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Settings")
        self.resize(720, 650)

        self._settings = copy.deepcopy(settings)
        self._providers = self._settings["providers"]
        self._tts = self._settings.get("tts") or default_tts()
        self._loading = False
        self._network = QNetworkAccessManager(self)
        self._health_reply = None

        self._build_ui()
        self._refresh_list(self._active_row())
        self._load_tts()

    def _build_ui(self):
        root = QVBoxLayout(self)

        content = QHBoxLayout()
        root.addLayout(content)

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
        content.addWidget(left, 2)

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
        root.addWidget(tts_group)

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
        item = self.provider_list.item(row)
        if item is not None:
            item.setText(name or "(unnamed)")

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
        self._store_current()
        self._store_tts()
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
        save_settings(self._settings)
        super().accept()
