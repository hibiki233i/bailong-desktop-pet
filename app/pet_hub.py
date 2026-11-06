"""Run several pets in one process, with one menu bar icon and one control panel."""
from PySide6.QtCore import QObject, QSettings, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from characters import CHARACTERS
from platform_support import activate_mac_app, configure_mac_window, on_mac_reopen, resource_root


class PetHub(QObject):
    def __init__(self, pet_class, server=None, characters=CHARACTERS):
        """pet_class is passed in because pet.py runs as __main__, and importing it would load a second copy."""
        super().__init__()
        self.settings = QSettings('BailongPet', 'DesktopPet')
        self.tray = QSystemTrayIcon(self)
        self.tray_menu = QMenu()
        self.panel = None
        self.closing = False
        self.pets = []
        root = resource_root()
        available = [character for character in characters if (root / character.assets / '素材清单.json').is_file()]
        if not available:
            raise RuntimeError('没有找到桌宠素材，请把素材放到 outputs 文件夹。')
        for character in available:
            pet = pet_class(character, self)
            self.pets.append(pet)
            if self.saved_hidden(pet):
                pet.manual_hidden = True
                pet.apply_visibility()
            else:
                pet.show()
            configure_mac_window(pet)
            configure_mac_window(pet.bubble)
        self.setup_tray()
        if server is not None:
            self.server = server
            server.newConnection.connect(self.reveal)
            # NSApplication installs its own reopen handler as the event loop starts, so register after that.
            QTimer.singleShot(0, self.listen_for_reopen)

    def setup_tray(self):
        self.tray.setIcon(QIcon(self.pets[0].resting_pixmap()))
        self.tray.setToolTip('AI 桌宠')
        self.tray.setContextMenu(self.tray_menu)
        self.tray_menu.aboutToShow.connect(self.refresh_tray_menu)
        self.tray.activated.connect(self.tray_activated)
        self.refresh_tray_menu()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def refresh_tray_menu(self):
        self.tray_menu.clear()
        self.tray_menu.addAction('控制面板…', self.show_panel)
        self.tray_menu.addSeparator()
        for pet in self.pets:
            action = self.tray_menu.addAction('显示 ' + pet.character.agent + ' 桌宠')
            action.setCheckable(True)
            action.setChecked(not pet.manual_hidden)
            action.toggled.connect(lambda checked, p=pet: p.set_manual_hidden(not checked))
        self.tray_menu.addSeparator()
        self.tray_menu.addAction('退出桌宠', self.quit)

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_panel()

    def saved_hidden(self, pet):
        return self.settings.value(f'{pet.character.id}Hidden', False, type=bool)

    def remember_visibility(self, pet):
        self.settings.setValue(f'{pet.character.id}Hidden', pet.manual_hidden)
        if self.panel:
            self.panel.refresh()

    def set_auto_hide_fullscreen(self, enabled):
        for pet in self.pets:
            pet.set_auto_hide_fullscreen(enabled)

    def show_panel(self):
        if self.panel is None:
            from control_panel import ControlPanel
            self.panel = ControlPanel(self)
        activate_mac_app()
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    def listen_for_reopen(self):
        self.reopen_handler = on_mac_reopen(self.reveal)

    def reveal(self):
        """A second launch means the user is looking for the app, so bring it forward."""
        while self.server.hasPendingConnections():
            connection = self.server.nextPendingConnection()
            connection.disconnectFromServer()
            connection.deleteLater()
        for pet in self.pets:
            pet.ensure_on_screen()
            if not pet.desktop_hidden():
                pet.raise_()
        self.show_panel()

    def quit(self):
        self.closing = True
        if self.panel:
            self.panel.hide()
        for pet in list(self.pets):
            pet.close()

    def pet_closed(self, pet):
        if pet in self.pets:
            self.pets.remove(pet)
        if not self.pets:
            self.tray.hide()
            QApplication.quit()
