"""
Floating Controls - Modern Minimalist Design
"""

from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
                             QSlider, QLabel)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QRect
from PyQt5.QtGui import QFont, QLinearGradient, QPalette, QPainter, QColor


class FloatingControls(QWidget):
    """Modern minimalist floating control bar"""
    
    play_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    open_clicked = pyqtSignal()
    position_changed = pyqtSignal(int)
    volume_changed = pyqtSignal(int)
    fullscreen_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(False)
        self._init_ui()
        self._apply_style()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor(15, 15, 15, 255))
        gradient.setColorAt(0.45, QColor(10, 10, 10, 255))
        gradient.setColorAt(1.0, QColor(5, 5, 5, 255))
        painter.fillRect(event.rect(), gradient)
        painter.end()
        super().paintEvent(event)
    
    def _init_ui(self):
        self.setFixedHeight(120)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 12, 25, 18)
        main_layout.setSpacing(10)
        
        controls_row = QWidget()
        controls_layout = QHBoxLayout(controls_row)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(10)
        
        backward_btn = self._create_button("⏪")
        backward_btn.clicked.connect(lambda: self.position_changed.emit(
            max(0, self.position_slider.value() - 5000)))
        
        self.play_btn = self._create_button("⏸")
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self._toggle_play)
        
        forward_btn = self._create_button("⏩")
        forward_btn.clicked.connect(lambda: self.position_changed.emit(
            min(self.position_slider.maximum(), self.position_slider.value() + 5000)))
        
        volume_icon = self._create_button("🔊")
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(90)
        self.volume_slider.valueChanged.connect(
            lambda vol: self.volume_changed.emit(vol))
        
        controls_layout.addWidget(backward_btn)
        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(forward_btn)
        controls_layout.addWidget(volume_icon)
        controls_layout.addWidget(self.volume_slider)
        
        controls_layout.addStretch()
        
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("""
            color: #ffffff;
            font-family: 'Helvetica Neue', 'Arial', sans-serif;
            font-size: 14px;
            font-weight: 500;
            background-color: rgba(30, 30, 30, 255);
            padding: 6px 16px;
            border-radius: 8px;
        """)
        
        controls_layout.addWidget(self.time_label)
        controls_layout.addStretch()
        
        fullscreen_btn = self._create_button("⛶")
        fullscreen_btn.clicked.connect(lambda: self.fullscreen_clicked.emit())
        

        settings_btn = self._create_button("⚙")
        
        controls_layout.addWidget(settings_btn)
        controls_layout.addWidget(fullscreen_btn)
        
        main_layout.addWidget(controls_row)
        
        progress_row = QWidget()
        progress_layout = QHBoxLayout(progress_row)
        progress_layout.setContentsMargins(0, 5, 0, 0)
        
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(
            lambda pos: self.position_changed.emit(pos))
        
        self.remaining_label = QLabel("-0:00 | 0:00")
        self.remaining_label.setStyleSheet("""
            color: rgba(255,255,255,0.7);
            font-family: 'Helvetica Neue', 'Arial', sans-serif;
            font-size: 13px;
            background: transparent;
        """)
        
        progress_layout.addWidget(self.position_slider, stretch=1)
        progress_layout.addWidget(self.remaining_label)
        
        main_layout.addWidget(progress_row)
    
    def _create_button(self, icon_text):
        btn = QPushButton(icon_text)
        btn.setFixedSize(44, 44)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                font-size: 20px;
                border-radius: 22px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.08);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.12);
            }
            QPushButton:disabled {
                color: rgba(255, 255, 255, 0.3);
            }
        """)
        return btn
    
    def _apply_style(self):
        self.setStyleSheet("""
            FloatingControls {
                background: transparent;
                border: none;
            }
            
            QSlider::groove:horizontal {
                height: 4px;
                background: rgba(255, 255, 255, 0.18);
                border-radius: 2px;
            }
            
            QSlider::sub-page:horizontal {
                background: #ffffff;
                border-radius: 2px;
            }
            
            QSlider::handle:horizontal {
                width: 18px;
                height: 18px;
                margin: -7px 0;
                background: #ffffff;
                border-radius: 9px;
            }
            
            QSlider::handle:horizontal:hover {
                background: #ffffff;
            }
            
            QSlider[objectName='volumeSlider']::groove:horizontal {
                height: 3px;
                background: rgba(255, 255, 255, 0.2);
            }
            
            QSlider[objectName='volumeSlider']::sub-page:horizontal {
                background: #ffffff;
            }
            
            QSlider[objectName='volumeSlider']::handle:horizontal {
                width: 14px;
                height: 14px;
                margin: -5.5px 0;
                background: #ffffff;
                border-radius: 7px;
            }
        """)
        
        self.volume_slider.setObjectName("volumeSlider")
    
    def _toggle_play(self):
        if self.play_btn.text() in ["▶", "Play"]:
            self.play_clicked.emit()
        else:
            self.pause_clicked.emit()
    
    def set_play_enabled(self, enabled: bool):
        self.play_btn.setEnabled(enabled)
    
    def update_play_button(self, is_playing: bool):
        if is_playing:
            self.play_btn.setText("⏸")
        else:
            self.play_btn.setText("▶")
    
    def update_position_range(self, duration: int):
        self.position_slider.setRange(0, duration)
    
    def update_position(self, position: int):
        self.position_slider.blockSignals(True)
        self.position_slider.setValue(position)
        self.position_slider.blockSignals(False)
    
    def update_time_display(self, current: int, duration: int):
        current_str = self._format_time(current)
        duration_str = self._format_time(duration)
        
        self.time_label.setText(f"{current_str} / {duration_str}")
        
        remaining = max(0, duration - current)
        remaining_str = self._format_time(remaining)
        self.remaining_label.setText(f"-{remaining_str} | {duration_str}")
    
    def show_temp_message(self, text: str, color: str = "#ffffff", duration_ms=2000):
        pass
    
    @staticmethod
    def _format_time(ms: int) -> str:
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"
