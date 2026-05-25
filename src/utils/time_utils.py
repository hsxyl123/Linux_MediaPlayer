"""
Time formatting utilities
"""


def format_time(ms: int) -> str:
    """
    Format milliseconds to MM:SS format
    
    Args:
        ms: Time in milliseconds
        
    Returns:
        Formatted time string (MM:SS)
    """
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def format_time_short(seconds: float) -> str:
    """
    Format seconds to human-readable short format
    
    Args:
        seconds: Time in seconds (float)
        
    Returns:
        Formatted time string
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds) // 60
        secs = int(seconds) % 60
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds) // 3600
        minutes = (int(seconds) % 3600) // 60
        return f"{hours}h {minutes}m"


def format_duration(total_seconds: float) -> str:
    """
    Format total duration in HH:MM:SS or MM:SS
    
    Args:
        total_seconds: Total duration in seconds
        
    Returns:
        Formatted duration string
    """
    hours = int(total_seconds) // 3600
    minutes = (int(total_seconds) % 3600) // 60
    seconds = int(total_seconds) % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"
