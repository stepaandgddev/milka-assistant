import copy

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from autostart import (
    autostart_enabled,
    autostart_supported,
    set_autostart,
)
from settings_store import PROVIDER_TYPES, save_settings


class SettingsDialog(QDialog):

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Settings")
        self.resize(680, 400)

        self._settings = copy.deepcopy(settings)
        self._providers = self._settings["providers"]
        self._loading = False

        self._build_ui()
        self._refresh_list(self._active_row())

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

        self.name_edit.textChanged.connect(self._store_current)
        self.type_combo.currentIndexChanged.connect(self._store_current)
        self.url_edit.textChanged.connect(self._store_current)
        self.model_edit.textChanged.connect(self._store_current)
        self.key_edit.textChanged.connect(self._store_current)
        self.active_check.toggled.connect(self._set_active)

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
