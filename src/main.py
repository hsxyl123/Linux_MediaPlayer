"""
Application entry point
"""

import sys
from PyQt5.QtWidgets import QApplication

from .core import VLCPlayer, MPVPlayer, QtPlayer
from .ui import MainWindow
from .config.settings import Config


def create_backend(preferred: str = None):
    """
    Create and return the best available player backend
    
    Args:
        preferred: Preferred backend name ('vlc', 'mpv', 'qt')
        
    Returns:
        PlayerBackend instance or None if no backend available
    """
    backends = []
    
    if preferred:
        backend_map = {
            'vlc': VLCPlayer,
            'mpv': MPVPlayer,
            'qt': QtPlayer
        }
        
        if preferred.lower() in backend_map:
            backend_class = backend_map[preferred.lower()]
            if backend_class.is_available():
                try:
                    return backend_class()
                except Exception as e:
                    print(f"Failed to initialize {preferred} backend: {e}")
    
    if VLCPlayer.is_available():
        try:
            return VLCPlayer()
        except Exception as e:
            print(f"Failed to initialize VLC: {e}")
    
    if MPVPlayer.is_available():
        return MPVPlayer()
    
    if QtPlayer.is_available():
        return QtPlayer()
    
    return None


def main():
    """Main application entry point"""
    print("=" * 60)
    print("🎬 Simple Video Player v1.0.0")
    print("=" * 60)
    
    app = QApplication(sys.argv)
    app.setApplicationName("Simple Video Player")
    app.setOrganizationName("YourOrg")
    
    config = Config()
    
    backend = create_backend(config.preferred_backend)
    
    if backend is None:
        print("\n❌ Error: No suitable media player backend found!")
        print("\nPlease install one of the following:")
        print("  • VLC:     sudo apt install vlc python3-vlc")
        print("  • MPV:     sudo apt install mpv")
        print("  • Qt:      sudo apt install python3-pyqt5.qtmultimedia")
        print("")
        sys.exit(1)
    
    print(f"\n✅ Using {backend.get_backend_name()} backend")
    
    window = MainWindow(backend)
    window.resize(config.window_width, config.window_height)
    window.show()
    
    print("\n✅ Player started successfully!")
    print("   Shortcuts: Space=Play/Pause, F=Fullscreen, ←→=Seek, ↑↓=Volume\n")
    
    exit_code = app.exec_()
    
    config.set('window.width', window.width())
    config.set('window.height', window.height())
    config.save()
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
