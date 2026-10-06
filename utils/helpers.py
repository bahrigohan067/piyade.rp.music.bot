def format_duration(seconds: int | float | None) -> str:
    """Saniyeyi DD:SS veya SS:DD:SS formatına çevirir."""
    if seconds is None or seconds <= 0:
        return "Canlı Yayın / Belirsiz"
    
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_bytes(size: int | float | None) -> str:
    """Bayt miktarını okunabilir boyuta dönüştürür."""
    if not size:
        return "Bilinmiyor"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"
