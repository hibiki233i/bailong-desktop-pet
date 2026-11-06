"""A small window that shows both agents and controls both pets."""
import sys

from PySide6.QtCore import QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSlider,
                               QVBoxLayout, QWidget)

import claude_limits
from platform_support import UI_FONT

STATES = {'busy': ('工作中', '#d9822b'), 'waiting': ('等你确认', '#d64545'), 'idle': ('空闲', '#3f9c5f'), 'offline': ('未检测到', '#8a8a8a')}
THUMB = 112


def describe(status):
    """Plain text for the rows under the status line."""
    rows = status['sessions']
    if not rows:
        return '没有进行中的任务' if status['state'] == 'idle' else '这台电脑上没有找到它的记录'
    lines = [('· ' + row['title'])[:30] + (f"（{row['detail']}）" if row.get('detail') else '') for row in rows[:3]]
    if len(rows) > 3:
        lines.append(f'还有 {len(rows) - 3} 项')
    return '\n'.join(lines)


class PetCard(QFrame):
    def __init__(self, pet, parent=None):
        super().__init__(parent)
        self.pet = pet
        self.setObjectName('card')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(12)
        self.thumb = QLabel()
        self.thumb.setFixedSize(THUMB, THUMB)
        heading = QVBoxLayout()
        heading.setSpacing(3)
        name = QLabel(pet.character.agent)
        name.setObjectName('name')
        self.state = QLabel()
        self.state.setObjectName('state')
        self.detail = QLabel()
        self.detail.setObjectName('detail')
        self.detail.setWordWrap(True)
        self.detail.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        heading.addWidget(name)
        heading.addWidget(self.state)
        heading.addWidget(self.detail, 1)
        top.addWidget(self.thumb)
        top.addLayout(heading, 1)
        layout.addLayout(top)

        self.show_box = QCheckBox('显示这只桌宠')
        self.show_box.toggled.connect(lambda checked: pet.set_manual_hidden(not checked))
        self.walk = QCheckBox('自己走动')
        self.walk.toggled.connect(lambda checked: pet.set_auto_movement_disabled(not checked))
        self.bubbles = QCheckBox('任务气泡提醒')
        self.bubbles.toggled.connect(lambda checked: pet.set_task_bubbles_disabled(not checked))
        self.sound = QCheckBox('音效')
        self.sound.toggled.connect(lambda checked: pet.set_sound_disabled(not checked))
        switches = QGridLayout()
        switches.setHorizontalSpacing(14)
        switches.setVerticalSpacing(4)
        for index, box in enumerate((self.show_box, self.walk, self.bubbles, self.sound)):
            switches.addWidget(box, index // 2, index % 2)
        self.limits = None
        if pet.character.real_limits and claude_limits.SUPPORTED:
            self.limits = QCheckBox('读取真实额度')
            self.limits.setToolTip('在 Claude Code 设置里加一个状态栏，用它接收账户额度。')
            self.limits.toggled.connect(self.set_limits)
            switches.addWidget(self.limits, 2, 0)
        layout.addLayout(switches)

        size_row = QHBoxLayout()
        self.size_text = QLabel()
        self.size_text.setMinimumWidth(66)
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(50, 200)
        self.size_slider.setAccessibleName(pet.character.agent + ' 桌宠大小')
        self.size_slider.valueChanged.connect(self.resize_pet)
        size_row.addWidget(self.size_text)
        size_row.addWidget(self.size_slider, 1)
        layout.addLayout(size_row)

        buttons = QHBoxLayout()
        self.quota = QPushButton('查额度')
        self.quota.clicked.connect(pet.quota)
        buttons.addWidget(self.quota)
        if pet.character.chat:
            self.chat = QPushButton('对话')
            self.chat.clicked.connect(pet.toggle_chat)
            buttons.addWidget(self.chat)
        layout.addLayout(buttons)

    def set_limits(self, checked):
        try:
            (claude_limits.enable if checked else claude_limits.disable)()
        except (OSError, RuntimeError) as error:
            QMessageBox.warning(self, '没有修改', str(error))
        with QSignalBlocker(self.limits):
            self.limits.setChecked(claude_limits.enabled())

    def resize_pet(self, value):
        self.pet.set_size_percent(value)
        self.size_text.setText(f'大小 {value}%')

    def refresh(self):
        """Follow the pet: its right-click menu can change these same settings."""
        pet = self.pet
        for box, value in ((self.show_box, not pet.manual_hidden), (self.walk, not pet.auto_movement_disabled),
                           (self.bubbles, not pet.task_bubbles_disabled), (self.sound, not pet.sound_disabled)):
            with QSignalBlocker(box):
                box.setChecked(value)
        if self.limits:
            with QSignalBlocker(self.limits):
                self.limits.setChecked(claude_limits.enabled())
        with QSignalBlocker(self.size_slider):
            self.size_slider.setValue(pet.size_percent)
        self.size_text.setText(f'大小 {pet.size_percent}%')
        self.quota.setEnabled(not pet.desktop_hidden())
        status = pet.desktop_sync.status()
        label, colour = STATES.get(status['state'], STATES['offline'])
        count = len(status['sessions'])
        self.state.setText(f'<span style="color:{colour}">●</span> {label}' + (f' · {count} 项' if count else ''))
        self.detail.setText(describe(status))

    def refresh_thumb(self):
        frame = self.pet.visible_frame()
        if frame is None:
            return
        ratio = self.devicePixelRatioF()
        side = round(THUMB * ratio)
        pixmap = QPixmap.fromImage(frame).scaled(side, side, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        pixmap.setDevicePixelRatio(ratio)
        self.thumb.setPixmap(pixmap)


class ControlPanel(QWidget):
    def __init__(self, hub):
        super().__init__(None, Qt.WindowType.Window)
        self.hub = hub
        self.setWindowTitle('AI 桌宠控制面板')
        self.setStyleSheet('QWidget {font-family:' + UI_FONT + ';font-size:13px;}'
                           '#card {border:1px solid palette(mid);border-radius:10px;}'
                           '#name {font-size:17px;font-weight:600;} #state {font-size:13px;} #detail {font-size:12px;color:palette(placeholder-text);}')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.cards = [PetCard(pet, self) for pet in hub.pets]
        for card in self.cards:
            card.setMinimumWidth(310)
            row.addWidget(card, 1)
        layout.addLayout(row)

        footer = QHBoxLayout()
        self.fullscreen = QCheckBox('全屏时自动隐藏')
        self.fullscreen.toggled.connect(hub.set_auto_hide_fullscreen)
        footer.addWidget(self.fullscreen)
        self.startup = None
        if sys.platform == 'darwin':
            self.startup = QCheckBox('随 ChatGPT 或 Claude 自动启动')
            self.startup.toggled.connect(self.set_startup)
            footer.addWidget(self.startup)
        footer.addStretch(1)
        leave = QPushButton('退出桌宠')
        leave.clicked.connect(hub.quit)
        footer.addWidget(leave)
        layout.addLayout(footer)

        self.status_timer = QTimer(self)
        self.status_timer.setInterval(1000)
        self.status_timer.timeout.connect(self.refresh)
        self.thumb_timer = QTimer(self)
        self.thumb_timer.setInterval(200)
        self.thumb_timer.timeout.connect(self.refresh_thumbs)
        self.refresh()
        self.refresh_thumbs()

    def set_startup(self, enabled):
        from mac_autostart import disable, enable
        try:
            (enable if enabled else disable)()
        except Exception as error:
            QMessageBox.warning(self, 'AI 桌宠', '无法修改自动启动：' + str(error))
            self.refresh()

    def refresh(self):
        for card in self.cards:
            card.refresh()
        with QSignalBlocker(self.fullscreen):
            self.fullscreen.setChecked(all(pet.auto_hide_fullscreen for pet in self.hub.pets))
        if self.startup:
            from mac_autostart import is_enabled
            with QSignalBlocker(self.startup):
                self.startup.setChecked(is_enabled())

    def refresh_thumbs(self):
        for card in self.cards:
            card.refresh_thumb()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
        self.status_timer.start()
        self.thumb_timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.status_timer.stop()
        self.thumb_timer.stop()
