"""
Abstract base class for all player backends
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Callable


class PlayerState(Enum):
    """Player state enumeration"""
    STOPPED = 0
    PLAYING = 1
    PAUSED = 2
    ERROR = 3


class PlayerBackend(ABC):
    """Abstract base class defining the interface for all media players"""
    
    def __init__(self):
        self._state = PlayerState.STOPPED
        self._volume: int = 70
        self._position: int = 0
        self._duration: int = 0
        self._on_state_changed: Optional[Callable] = None
        self._on_position_changed: Optional[Callable] = None
    
    @property
    def state(self) -> PlayerState:
        return self._state
    
    @property
    def volume(self) -> int:
        return self._volume
    
    @property
    def position(self) -> int:
        return self._position
    
    @property
    def duration(self) -> int:
        return self._duration
    
    @abstractmethod
    def load(self, file_path: str) -> bool:
        """Load a media file"""
        pass
    
    @abstractmethod
    def play(self) -> None:
        """Start or resume playback"""
        pass
    
    @abstractmethod
    def pause(self) -> None:
        """Pause playback"""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop playback"""
        pass
    
    @abstractmethod
    def set_position(self, position: int) -> None:
        """Seek to position in milliseconds"""
        pass
    
    @abstractmethod
    def set_volume(self, volume: int) -> None:
        """Set volume (0-100)"""
        pass
    
    @abstractmethod
    def set_video_output(self, widget) -> None:
        """Set video output widget"""
        pass
    
    def connect_state_changed(self, callback: Callable) -> None:
        """Connect state change callback"""
        self._on_state_changed = callback
    
    def connect_position_changed(self, callback: Callable) -> None:
        """Connect position change callback"""
        self._on_position_changed = callback
    
    def _emit_state_changed(self):
        if self._on_state_changed:
            self._on_state_changed(self._state)
    
    def _emit_position_changed(self):
        if self._on_position_changed:
            self._on_position_changed(self._position, self._duration)
    
    @staticmethod
    @abstractmethod
    def is_available() -> bool:
        """Check if this backend is available on the system"""
        pass
    
    @staticmethod
    @abstractmethod
    def get_backend_name() -> str:
        """Get backend name for display"""
        pass
