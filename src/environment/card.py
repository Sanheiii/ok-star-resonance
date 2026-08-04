from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    FluentIcon,
    MessageBox,
    PrimaryPushButton,
)

from ok import Config, Logger, og
from ok.gui.widget.Card import Card
from src.environment.checker import (
    PACKAGE_INDEXES,
    EnvironmentReport,
    PythonEnvironmentChecker,
)
from src.environment.update import EnvironmentUpdateLauncher


logger = Logger.get_logger(__name__)


class PythonEnvironmentCard(Card):
    def __init__(self, parent=None):
        requirements_path = Path.cwd() / "requirements.txt"
        self._checker = PythonEnvironmentChecker(requirements_path)
        self._update_launcher = EnvironmentUpdateLauncher(Path.cwd())
        self._report = EnvironmentReport(())
        self._config = Config("python_environment", {"package_index": "Default"})

        content = QWidget(parent)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.status_label = BodyLabel(
            og.app.tr("Checking the runtime environment..."), content
        )
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.controls_widget = QWidget(content)
        controls = QHBoxLayout(self.controls_widget)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(
            BodyLabel(og.app.tr("Download source"), self.controls_widget)
        )

        self.index_combo = ComboBox(self.controls_widget)
        self._index_by_label = {}
        for name in PACKAGE_INDEXES:
            label = og.app.tr(name)
            self._index_by_label[label] = name
            self.index_combo.addItem(label)
        saved_index = self._config.get("package_index")
        saved_label = (
            og.app.tr(saved_index)
            if saved_index in PACKAGE_INDEXES
            else og.app.tr("Default")
        )
        self.index_combo.setCurrentIndex(
            max(self.index_combo.findText(saved_label), 0)
        )
        self.index_combo.currentTextChanged.connect(self._save_package_index)
        controls.addWidget(self.index_combo)
        controls.addStretch(1)

        self.install_button = PrimaryPushButton(
            FluentIcon.DOWNLOAD,
            og.app.tr("Repair and restart"),
            self.controls_widget,
        )
        self.install_button.clicked.connect(self._confirm_update)
        controls.addWidget(self.install_button, 0, Qt.AlignRight)
        self.controls_widget.setVisible(False)
        layout.addWidget(self.controls_widget)

        super().__init__(og.app.tr("Environment Check"), content, parent=parent)
        QTimer.singleShot(0, self.check_environment)

    def _save_package_index(self, label):
        self._config["package_index"] = self._index_by_label.get(label, "Default")

    def check_environment(self):
        try:
            self._report = self._checker.check()
        except FileNotFoundError:
            self._show_error(
                og.app.tr(
                    "The environment configuration file is missing. "
                    "Please download or extract the app again."
                )
            )
            return
        except Exception as exc:
            logger.error("Failed to check Python requirements", exc)
            self._show_error(
                og.app.tr(
                    "The environment check failed. Please restart the app and "
                    "try again. Details: {error}"
                ).format(error=exc)
            )
            return

        if self._report.is_healthy:
            self.status_label.setText(
                og.app.tr("All dependencies are installed correctly.")
            )
            self.controls_widget.setVisible(False)
            return

        messages = []
        if self._report.missing:
            messages.append(
                og.app.tr("Missing dependencies: {packages}.").format(
                    packages=", ".join(
                        str(issue.requirement) for issue in self._report.missing
                    )
                )
            )
        if self._report.outdated:
            descriptions = [
                f"{issue.requirement} ({og.app.tr('current version')}: "
                f"{issue.installed_version})"
                for issue in self._report.outdated
            ]
            messages.append(
                og.app.tr(
                    "Dependencies requiring an update: {packages}."
                ).format(packages=", ".join(descriptions))
            )
        messages.append(
            og.app.tr(
                "Choose a download source, then repair the environment. "
                "The app will restart automatically."
            )
        )
        self.status_label.setText("\n".join(messages))
        self.controls_widget.setVisible(True)
        self.install_button.setEnabled(True)
        self.index_combo.setEnabled(True)

    def _show_error(self, message):
        self.status_label.setText(message)
        self.controls_widget.setVisible(False)

    def _confirm_update(self):
        if self._report.is_healthy:
            self.check_environment()
            return

        confirm = MessageBox(
            og.app.tr("Repair runtime environment"),
            og.app.tr(
                "The app will close before repairing the environment and restart "
                "automatically when the repair succeeds."
            ),
            self.window(),
        )
        confirm.yesButton.setText(og.app.tr("Repair and restart"))
        confirm.cancelButton.setText(og.app.tr("Cancel"))
        if not confirm.exec():
            return

        source_name = self._index_by_label.get(
            self.index_combo.currentText(), "Default"
        )
        try:
            self._update_launcher.launch(
                self._report.requirements_to_install,
                PACKAGE_INDEXES[source_name],
            )
        except Exception as exc:
            logger.error("Failed to start environment updater", exc)
            self.status_label.setText(
                og.app.tr("The updater could not be started. Please try again.")
            )
            return

        self.install_button.setEnabled(False)
        self.index_combo.setEnabled(False)
        self.status_label.setText(
            og.app.tr("Closing the app and preparing the repair...")
        )
        og.app.quit()
