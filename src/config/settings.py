"""
Application configuration management
"""

import json
import os
from typing import Any, Dict, Optional


class Config:
    """Configuration manager for application settings"""
    
    DEFAULT_CONFIG = {
        'window': {
            'width': 800,
            'height': 600,
            'x': 100,
            'y': 100,
            'fullscreen': False
        },
        'player': {
            'default_volume': 70,
            'auto_play': False,
            'remember_position': True,
            'preferred_backend': None
        },
        'recent_files': {
            'max_items': 10,
            'files': []
        }
    }
    
    def __init__(self, config_dir: str = None):
        if config_dir is None:
            config_dir = self._get_default_config_dir()
        
        self.config_dir = config_dir
        self.config_file = os.path.join(config_dir, 'config.json')
        self._config: Dict[str, Any] = {}
        
        self._load_config()
    
    def _get_default_config_dir(self) -> str:
        """Get default configuration directory path"""
        home = os.path.expanduser('~')
        return os.path.join(home, '.config', 'simple-video-player')
    
    def _load_config(self) -> None:
        """Load configuration from file or use defaults"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                self._config = self._deep_merge(self.DEFAULT_CONFIG, loaded)
            else:
                self._config = self.DEFAULT_CONFIG.copy()
                self.save()
        except Exception as e:
            print(f"Warning: Failed to load config: {e}")
            self._config = self.DEFAULT_CONFIG.copy()
    
    def save(self) -> bool:
        """Save current configuration to file"""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self._config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    @staticmethod
    def _deep_merge(base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Config._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated path
        
        Args:
            key_path: Dot-separated path (e.g., 'player.default_volume')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any) -> None:
        """
        Set configuration value by dot-separated path
        
        Args:
            key_path: Dot-separated path (e.g., 'player.default_volume')
            value: Value to set
        """
        keys = key_path.split('.')
        config = self._config
        
        for key in keys[:-1]:
            if key not in config or not isinstance(config[key], dict):
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
    
    @property
    def window_width(self) -> int:
        return self.get('window.width', 800)
    
    @property
    def window_height(self) -> int:
        return self.get('window.height', 600)
    
    @property
    def default_volume(self) -> int:
        return self.get('player.default_volume', 70)
    
    @property
    def preferred_backend(self) -> Optional[str]:
        return self.get('player.preferred_backend')
    
    def add_recent_file(self, file_path: str) -> None:
        """Add file to recent files list"""
        recent_files = self.get('recent_files.files', [])
        
        if file_path in recent_files:
            recent_files.remove(file_path)
        
        recent_files.insert(0, file_path)
        max_items = self.get('recent_files.max_items', 10)
        recent_files = recent_files[:max_items]
        
        self.set('recent_files.files', recent_files)
        self.save()
    
    def get_recent_files(self) -> list:
        """Get list of recent files"""
        return self.get('recent_files.files', [])
