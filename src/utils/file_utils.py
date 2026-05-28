"""
File utility functions
"""

import os


VIDEO_EXTENSIONS = {
    '.mp4', '.avi', '.mkv', '.mov', '.wmv', 
    '.flv', '.webm', '.m4v', '.mpg', '.mpeg',
    '.3gp', '.ts', '.mts', '.m2ts','.m4a'
}


def get_video_extensions() -> list:
    """Get list of supported video file extensions"""
    return sorted(VIDEO_EXTENSIONS)


def is_video_file(file_path: str) -> bool:
    """
    Check if a file is a video based on extension
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if file has video extension, False otherwise
    """
    _, ext = os.path.splitext(file_path)
    return ext.lower() in VIDEO_EXTENSIONS


def get_file_filter() -> str:
    """
    Get file dialog filter string for video files
    
    Returns:
        Filter string for QFileDialog
    """
    extensions_str = " ".join(f"*{ext}" for ext in sorted(VIDEO_EXTENSIONS))
    return f"Video Files ({extensions_str});;All Files (*)"


def get_file_size_mb(file_path: str) -> float:
    """
    Get file size in megabytes
    
    Args:
        file_path: Path to the file
        
    Returns:
        File size in MB
    """
    try:
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    except OSError:
        return 0.0


def ensure_directory_exists(dir_path: str) -> bool:
    """
    Ensure directory exists, create if necessary
    
    Args:
        dir_path: Path to directory
        
    Returns:
        True if directory exists or was created successfully
    """
    try:
        os.makedirs(dir_path, exist_ok=True)
        return True
    except OSError:
        return False
