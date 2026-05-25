"""
Main window - Modern Minimalist Design
"""

import os
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QFileDialog, QLabel, QPushButton, QFrame)
from PyQt5.QtCore import Qt, QTimer, QRect
from PyQt5.QtGui import QFont

from .video_widget import VideoWidget
from .controls.floating_controls import FloatingControls

from ..core.player_base import PlayerState


class MainWindow(QMainWindow):
    """Modern minimalist main window with clean design"""
    
    def __init__(self, backend=None):
        super().__init__()
        self.backend = backend
        
        self._init_ui()
        self._apply_style()
        self._connect_signals()
        self._setup_timer()
        
        # 延迟调整控制栏位置（等窗口完全加载后）
        QTimer.singleShot(100, self._adjust_controls_position)
        
        # 窗口大小改变时重新定位控制栏
        self.resizeEvent = self._on_resize
    
    def _init_ui(self):
        self.setWindowTitle("🎬 Video Player")
        self.setGeometry(100, 100, 1000, 700)
        self.setMinimumSize(800, 500)
        
        # 主容器 - 无边框，全屏体验
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 1️⃣ 顶部标题栏（半透明）
        self.title_bar = self._create_title_bar()
        main_layout.addWidget(self.title_bar)
        
        # 2️⃣ 视频播放区域（作为容器）
        self.video_container = QWidget()
        video_container_layout = QVBoxLayout(self.video_container)
        video_container_layout.setContentsMargins(0, 0, 0, 0)
        video_container_layout.setSpacing(0)
        
        self.video_widget = VideoWidget()
        video_container_layout.addWidget(self.video_widget)
        
        main_layout.addWidget(self.video_container, stretch=1)
        
        # 3️⃣ 底部浮动控制栏（极简风格）- 使用绝对定位
        self.controls = FloatingControls(self.video_container)
        self.controls.show()
        
        if self.backend:
            self.backend.set_video_output(self.video_widget)
            backend_name = self.backend.get_backend_name()
            self.setWindowTitle(f"🎬 Video Player - {backend_name}")
    
    def _adjust_controls_position(self):
        """调整控制栏位置到视频底部"""
        if hasattr(self, 'video_container') and hasattr(self, 'controls'):
            container_width = self.video_container.width()
            container_height = self.video_container.height()
            
            # 控制栏固定在底部，宽度填满容器
            controls_height = self.controls.height()
            
            self.controls.setGeometry(
                0,  # x: 左边对齐
                container_height - controls_height,  # y: 底部对齐
                container_width,  # width: 容器宽度
                controls_height  # height: 控制栏高度
            )
            self.controls.raise_()
    
    def _on_resize(self, event):
        """窗口大小改变时重新定位"""
        QMainWindow.resizeEvent(self, event)
        self._adjust_controls_position()
    
    def _create_title_bar(self):
        """创建顶部标题栏"""
        title_bar = QFrame()
        title_bar.setFixedHeight(45)
        title_bar.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.5);
                border: none;
            }
        """)
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(12)
        
        # 左侧: Open按钮
        open_btn = QPushButton("Open")
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                font-family: 'Helvetica Neue', 'Arial', sans-serif;
                font-size: 14px;
                font-weight: 500;
                padding: 6px 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.08);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.12);
            }
        """)
        open_btn.clicked.connect(self._open_file)
        
        # 左侧箭头（Open旁边的下拉箭头）
        arrow_label = QLabel("▼")
        arrow_label.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 10px;")
        arrow_label.setAlignment(Qt.AlignLeft)
        
        # 中间: 标题
        title_label = QLabel("Video Player")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            color: #ffffff;
            font-family: 'Helvetica Neue', 'Arial', sans-serif;
            font-size: 15px;
            font-weight: 600;
            letter-spacing: 2px;
        """)
        
        # 右侧: 菜单按钮
        menu_btn = QPushButton("☰")
        menu_btn.setFixedSize(36, 36)
        menu_btn.setCursor(Qt.PointingHandCursor)
        menu_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                font-size: 20px;
                border-radius: 18px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.08);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.12);
            }
        """)
        
        # 右侧: 关闭按钮
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(36, 36)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                font-size: 16px;
                border-radius: 18px;
            }
            QPushButton:hover {
                background-color: rgba(255, 100, 100, 0.3);
            }
            QPushButton:pressed {
                background-color: rgba(255, 100, 100, 0.5);
            }
        """)
        close_btn.clicked.connect(self.close)
        
        # 组装布局
        left_group = QWidget()
        left_layout = QHBoxLayout(left_group)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        left_layout.addWidget(open_btn)
        left_layout.addWidget(arrow_label)
        
        right_group = QWidget()
        right_layout = QHBoxLayout(right_group)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)
        right_layout.addWidget(menu_btn)
        right_layout.addWidget(close_btn)
        
        layout.addWidget(left_group)
        layout.addStretch()
        layout.addWidget(title_label, stretch=1)
        layout.addStretch()
        layout.addWidget(right_group)
        
        return title_bar
    
    def _apply_style(self):
        """应用深色主题样式"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #000000;
            }
            QWidget {
                font-family: 'Helvetica Neue', 'Arial', sans-serif;
            }
        """)
    
    def _connect_signals(self):
        self.controls.play_clicked.connect(self._play)
        self.controls.pause_clicked.connect(self._pause)
        self.controls.stop_clicked.connect(self._stop)
        self.controls.position_changed.connect(self._seek)
        self.controls.volume_changed.connect(self._set_volume)
        self.controls.fullscreen_clicked.connect(self._toggle_fullscreen)
        self.controls.open_clicked.connect(self._open_file)
        
        if self.backend:
            self.backend.connect_state_changed(self._on_state_changed)
            self.backend.connect_position_changed(self._on_position_changed)
    
    def _setup_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_ui)
        self.timer.start(50)
    
    def _update_ui(self):
        if not self.backend:
            return
        
        if hasattr(self.backend, 'update_status'):
            self.backend.update_status()
        elif hasattr(self.backend, 'request_update'):
            self.backend.request_update()
    
    def _open_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select Video File",
            "",
            "Video Files (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm);;All Files (*)"
        )
        if file_name and self.backend:
            self._load_and_play(file_path=file_name)
    
    def _load_and_play(self, file_path):
        success = self.backend.load(file_path)
        if success:
            base_name = os.path.basename(file_path)
            
            # 更新中间标题为文件名
            for i in range(self.title_bar.layout().count()):
                item = self.title_bar.layout().itemAt(i)
                if isinstance(item.widget(), QLabel) and item.widget().text() in ["Video Player", base_name]:
                    item.widget().setText(base_name)
                    break
            
            self.controls.set_play_enabled(True)
            
            # ✨ 自动播放
            QTimer.singleShot(150, self._auto_play)
        else:
            self.controls.show_temp_message("❌ Error", "#ff4444")
    
    def _auto_play(self):
        if self.backend:
            self.backend.play()
    
    def _play(self):
        if self.backend:
            self.backend.play()
    
    def _pause(self):
        if self.backend:
            self.backend.pause()
    
    def _stop(self):
        if self.backend:
            self.backend.stop()
    
    def _seek(self, position):
        if self.backend:
            self.backend.set_position(position)
    
    def _set_volume(self, volume):
        if self.backend:
            self.backend.set_volume(volume)
    
    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.title_bar.show()
        else:
            self.showFullScreen()
            self.title_bar.hide()
        # 全屏切换后重新定位
        QTimer.singleShot(50, self._adjust_controls_position)
    
    def _on_state_changed(self, state):
        is_playing = state == PlayerState.PLAYING
        self.controls.update_play_button(is_playing)
        
        status_map = {
            PlayerState.STOPPED: ("Stopped", "#888888"),
            PlayerState.PLAYING: ("▶ Playing", "#00ff88"),
            PlayerState.PAUSED: ("⏸ Paused", "#ffaa00"),
            PlayerState.ERROR: ("❌ Error", "#ff4444"),
        }
        text, color = status_map.get(state, ("", "#ffffff"))
        if text:
            self.controls.show_temp_message(text, color)
    
    def _on_position_changed(self, position, duration):
        self.controls.update_position(position)
        self.controls.update_position_range(duration)
        self.controls.update_time_display(position, duration)
    
    def keyPressEvent(self, event):
        key_handlers = {
            Qt.Key_Space: self._handle_space,
            Qt.Key_F: self._toggle_fullscreen,
            Qt.Key_Escape: lambda: self.showNormal() if self.isFullScreen() else None,
            Qt.Key_Left: lambda: self._seek_relative(-5000),
            Qt.Key_Right: lambda: self._seek_relative(5000),
            Qt.Key_Up: lambda: self._volume_relative(10),
            Qt.Key_Down: lambda: self._volume_relative(-10),
        }
        
        handler = key_handlers.get(event.key())
        if handler:
            handler()
        else:
            super().keyPressEvent(event)
    
    def _handle_space(self):
        if self.backend and hasattr(self.backend, 'toggle_play_pause'):
            self.backend.toggle_play_pause()
    
    def _seek_relative(self, delta_ms):
        if self.backend:
            new_pos = max(0, self.backend.position + delta_ms)
            new_pos = min(new_pos, self.backend.duration) if self.backend.duration > 0 else new_pos
            self.backend.set_position(new_pos)
    
    def _volume_relative(self, delta):
        new_vol = max(0, min(100, self.controls.volume_slider.value() + delta))
        self.controls.volume_slider.setValue(new_vol)
