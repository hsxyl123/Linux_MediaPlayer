"""
Application entry point
"""

import sys
from PyQt5.QtWidgets import QApplication

from .core import QtPlayer
from .ui import MainWindow
from .config.settings import Config


def main():
    """Main application entry point"""
    print("=" * 60)
    print("🎬 Simple Video Player v1.0.0")
    print("=" * 60)

    app = QApplication(sys.argv)
    app.setApplicationName("Simple Video Player")
    app.setOrganizationName("YourOrg")

    config = Config()

    if not QtPlayer.is_available():
        print("\n❌ Error: Qt Multimedia backend is not available!")
        print("\nPlease install:")
        print("  • pip install PyQt5")
        print("  • On Linux also: sudo apt install python3-pyqt5.qtmultimedia")
        print("")
        sys.exit(1)

    backend = QtPlayer()

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
