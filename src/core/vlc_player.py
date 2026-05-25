"""
VLC Player Backend Implementation
"""

import sys
from .player_base import PlayerBackend, PlayerState

try:
    import vlc
    VLC_AVAILABLE = True
except ImportError:
    VLC_AVAILABLE = False


class VLCPlayer(PlayerBackend):
    """VLC media player backend implementation"""
    
    def __init__(self):
        super().__init__()
        if not VLC_AVAILABLE:
            raise RuntimeError("VLC is not available. Install with: pip install python3-vlc")
        
        self._instance = vlc.Instance('--no-xlib')
        self._player = self.instance.media_player_new()
        self._video_widget = None
        self._is_playing_internal = False
    
    @property
    def instance(self):
        return self._instance
    
    @property
    def player(self):
        return self._player
    
    @staticmethod
    def is_available() -> bool:
        return VLC_AVAILABLE
    
    @staticmethod
    def get_backend_name() -> str:
        return "VLC"
    
    def load(self, file_path: str) -> bool:
        try:
            media = self._instance.media_new(file_path)
            self._player.set_media(media)
            
            if self._video_widget:
                win_id = int(self._video_widget.winId())
                if sys.platform == 'win32':
                    self._player.set_hwnd(win_id)
                else:
                    self._player.set_xwindow(win_id)
            
            self._state = PlayerState.STOPPED
            return True
        except Exception as e:
            print(f"Error loading file: {e}")
            self._state = PlayerState.ERROR
            return False
    
    def play(self) -> None:
        self._player.play()
        self._is_playing_internal = True
        self._state = PlayerState.PLAYING
        self._emit_state_changed()
    
    def pause(self) -> None:
        self._player.pause()
        self._is_playing_internal = False
        self._state = PlayerState.PAUSED
        self._emit_state_changed()
    
    def stop(self) -> None:
        self._player.stop()
        self._is_playing_internal = False
        self._state = PlayerState.STOPPED
        self._emit_state_changed()
    
    def set_position(self, position: int) -> None:
        if self._player.get_length() > 0:
            self._player.set_time(position)
    
    def set_volume(self, volume: int) -> None:
        self._volume = max(0, min(100, volume))
        self._player.audio_set_volume(self._volume)
    
    def set_video_output(self, widget) -> None:
        self._video_widget = widget
    
    def update_status(self) -> None:
        """Update internal state from player"""
        try:
            current_pos = self._player.get_time()
            total_len = self._player.get_length()
            
            if total_len > 0:
                self._position = current_pos
                self._duration = total_len
                
                state = self._player.get_state()
                if state in [vlc.State.Ended]:
                    self._state = PlayerState.STOPPED
                    self._is_playing_internal = False
                    self._emit_state_changed()
                
                self._emit_position_changed()
        except Exception:
            pass
    
    def toggle_play_pause(self) -> None:
        """Toggle between play and pause states"""
        if self._is_playing_internal:
            self.pause()
        else:
            self.play()
