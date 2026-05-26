"""
Video display widget - Cine-style Minimalist Design
"""

from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import QSizePolicy


class VideoWidget(QVideoWidget):
    """Cine-style video display widget with pure black background"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(640, 480)
        self.setStyleSheet("""
            VideoWidget {
                background-color: #000000;
                border: none;
            }
        """)
    
    def get_win_id(self) -> int:
        """Get window ID for embedding player"""
        return int(self.winId())
