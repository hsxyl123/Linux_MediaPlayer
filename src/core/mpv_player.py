"""
MPV Player Backend Implementation
"""

from PyQt5.QtCore import QProcess
from .player_base import PlayerBackend, PlayerState

import subprocess


class MPVPlayer(PlayerBackend):
    """MPV media player backend implementation using subprocess"""
    
    def __init__(self):
        super().__init__()
        self._process: Optional[QProcess] = None
        self._video_widget = None
        self._current_file: str = ""
        self._is_playing_internal = False
    
    @staticmethod
    def is_available() -> bool:
        try:
            result = subprocess.run(["which", "mpv"], capture_output=True, text=True)
            return result.returncode == 0
        except Exception:
            return False
    
    @staticmethod
    def get_backend_name() -> str:
        return "MPV"
    
    def load(self, file_path: str) -> bool:
        self._current_file = file_path
        self._state = PlayerState.STOPPED
        return True
    
    def _ensure_process(self):
        if self._process is None:
            self._process = QProcess()
            self._process.readyReadStandardOutput.connect(self._read_output)
    
    def _start_mpv(self):
        if not self._video_widget or not self._current_file:
            return
        
        self._ensure_process()
        
        if self._process.state() == QProcess.Running:
            self._process.write(b"quit\n")
            self._process.waitForFinished(1000)
        
        wid = str(int(self._video_widget.winId()))
        args = [
            '--wid', wid,
            '--keep-open', 'no',
            '--osc=no',
            '--input-default-bindings=no',
            '--no-input-cursor',
            '--title', '',
            self._current_file
        ]
        
        self._process.start('mpv', args)
    
    def play(self) -> None:
        if self._process and self._process.state() == QProcess.Running:
            self._process.write(b"cycle pause\n")
        else:
            self._start_mpv()
        
        self._is_playing_internal = True
        self._state = PlayerState.PLAYING
        self._emit_state_changed()
    
    def pause(self) -> None:
        if self._process and self._process.state() == QProcess.Running:
            self._process.write(b"cycle pause\n")
        
        self._is_playing_internal = False
        self._state = PlayerState.PAUSED
        self._emit_state_changed()
    
    def stop(self) -> None:
        if self._process and self._process.state() == QProcess.Running:
            self._process.write(b"quit\n")
            self._process.waitForFinished(1000)
        
        self._is_playing_internal = False
        self._state = PlayerState.STOPPED
        self._emit_state_changed()
    
    def set_position(self, position: int) -> None:
        if self._duration > 0 and self._process and self._process.state() == QProcess.Running:
            percent = position / (self._duration * 1000) if self._duration > 0 else 0
            self._process.write(f'seek {percent:.2%} absolute\n'.encode())
    
    def set_volume(self, volume: int) -> None:
        self._volume = max(0, min(100, volume))
        if self._process and self._process.state() == QProcess.Running:
            self._process.write(f'set volume {self._volume}\n'.encode())
    
    def set_video_output(self, widget) -> None:
        self._video_widget = widget
    
    def _read_output(self):
        if not self._process:
            return
        
        data = self._process.readAllStandardOutput().data().decode()
        for line in data.strip().split('\n'):
            if line.startswith('ANS_duration='):
                try:
                    self._duration = float(line.split('=')[1])
                except (ValueError, IndexError):
                    pass
            elif line.startswith('ANS_time_position='):
                try:
                    pos = float(line.split('=')[1])
                    self._position = int(pos * 1000)
                    self._emit_position_changed()
                except (ValueError, IndexError):
                    pass
    
    def request_update(self):
        """Request position/duration info from MPV"""
        if self._process and self._process.state() == QProcess.Running:
            self._process.write(b'{"command": ["get_property", "duration"]}\n')
            self._process.write(b'{"command": ["get_property", "time-pos"]}\n')
    
    def toggle_play_pause(self) -> None:
        """Toggle between play and pause states"""
        if self._is_playing_internal:
            self.pause()
        else:
            self.play()
