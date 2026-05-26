"""
Qt Multimedia Player Backend Implementation
"""

import sys
import subprocess

try:
    from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
    from PyQt5.QtMultimediaWidgets import QVideoWidget
    from PyQt5.QtCore import QUrl
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

from .player_base import PlayerBackend, PlayerState


class QtPlayer(PlayerBackend):
    """Qt Multimedia backend implementation"""
    
    def __init__(self):
        super().__init__()
        self._media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self._video_widget: Optional[QVideoWidget] = None
        self._media_player.stateChanged.connect(self._on_qt_state_changed)
        self._media_player.positionChanged.connect(self._on_qt_position_changed)
        self._media_player.durationChanged.connect(self._on_qt_duration_changed)
        self._media_player.error.connect(self._on_error)
    
    @property
    def media_player(self):
        return self._media_player
    
    @staticmethod
    def is_available() -> bool:
        if not QT_AVAILABLE:
            return False
        if sys.platform == 'linux':
            try:
                result = subprocess.run(
                    ['gst-inspect-1.0', 'playback'],
                    capture_output=True, text=True, timeout=3
                )
                if result.returncode != 0:
                    print("Warning: GStreamer playback plugin not found.")
                    print("  Install with: sudo apt install gstreamer1.0-plugins-base")
                    return False
            except FileNotFoundError:
                print("Warning: gst-inspect-1.0 not found, GStreamer may not be installed.")
                print("  Install with: sudo apt install gstreamer1.0-plugins-base gstreamer1.0-plugins-good")
                print("                gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav")
                return False
            except subprocess.TimeoutExpired:
                return False
        return True
    
    @staticmethod
    def get_backend_name() -> str:
        return "Qt Multimedia"
    
    def load(self, file_path: str) -> bool:
        try:
            self._media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
            self._state = PlayerState.STOPPED
            return True
        except Exception as e:
            print(f"Error loading file: {e}")
            self._state = PlayerState.ERROR
            return False
    
    def play(self) -> None:
        self._media_player.play()
    
    def pause(self) -> None:
        self._media_player.pause()
    
    def stop(self) -> None:
        self._media_player.stop()
    
    def set_position(self, position: int) -> None:
        self._media_player.setPosition(position)
    
    def set_volume(self, volume: int) -> None:
        self._volume = max(0, min(100, volume))
        self._media_player.setVolume(self._volume)
    
    def set_video_output(self, widget) -> None:
        self._video_widget = widget
        self._media_player.setVideoOutput(widget)
    
    def _on_qt_state_changed(self, state):
        state_map = {
            QMediaPlayer.StoppedState: PlayerState.STOPPED,
            QMediaPlayer.PlayingState: PlayerState.PLAYING,
            QMediaPlayer.PausedState: PlayerState.PAUSED,
        }
        self._state = state_map.get(state, PlayerState.STOPPED)
        self._emit_state_changed()
    
    def _on_qt_position_changed(self, position):
        self._position = position
        self._emit_position_changed()
    
    def _on_qt_duration_changed(self, duration):
        self._duration = duration
        self._emit_position_changed()
    
    def _on_error(self, error):
        if error != QMediaPlayer.NoError:
            self._state = PlayerState.ERROR
            error_msg = self._media_player.errorString()
            print(f"Qt Media Error ({error}): {error_msg}")
            self._emit_state_changed()
    
    def toggle_play_pause(self) -> None:
        """Toggle between play and pause states"""
        if self._state == PlayerState.PLAYING:
            self.pause()
        else:
            self.play()
