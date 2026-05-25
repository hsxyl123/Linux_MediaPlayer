"""
Video display widget - Cine-style Minimalist Design
"""

from PyQt5.QtWidgets import QWidget, QSizePolicy
from PyQt5.QtCore import Qt


class VideoWidget(QWidget):
    """Cine-style video display widget with pure black background"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(640, 480)
        
        # Cine风格：纯黑色背景
        self.setStyleSheet("""
            VideoWidget {
                background-color: #000000;
                border: none;
            }
        """)
    
    def get_win_id(self) -> int:
        """Get window ID for embedding player"""
        return int(self.winId())
