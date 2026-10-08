import re
import config

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


def clean_title_noise(text: str) -> str:
    """Başlıktaki (Official Video), [Official Audio] gibi kalıpları temizler."""
    if not text:
        return ""
    pattern = r'\s*[\(\[\{](?:official|video|audio|klip|lyric|lyrics|hd|4k|remastered|visualizer|feat|ft\.)[^\)\]\}]*[\)\]\}]\s*'
    cleaned = re.sub(pattern, '', text, flags=re.IGNORECASE)
    # Çift boşlukları ve baştaki/sondaki tırnak/boşlukları temizle
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' "\'[](){}-–—')
    return cleaned or text


def parse_song_and_artist(raw_title: str, uploader: str | None = None, data_artist: str | None = None, data_track: str | None = None) -> tuple[str, str]:
    """
    Şarkı başlığından temiz [Şarkı Adı] ve [Sanatçı] ayrımı yapar.
    Örn: 'Noldu Böyle - Asil Gök (Official Video)' -> ('Noldu Böyle', 'Asil Gök')
    """
    if data_track and data_artist:
        return clean_title_noise(data_track), clean_title_noise(data_artist)

    cleaned = clean_title_noise(raw_title)

    for sep in [' - ', ' – ', ' — ', ' | ']:
        if sep in cleaned:
            parts = cleaned.split(sep, 1)
            p1 = clean_title_noise(parts[0])
            p2 = clean_title_noise(parts[1])

            if uploader:
                u_lower = uploader.lower()
                # Eğer ilk parça kanal/sanatçı ismi ise: Sanatçı - Şarkı -> Şarkı, Sanatçı
                if u_lower in p1.lower() or p1.lower() in u_lower:
                    return p2, p1
                # Eğer ikinci parça kanal/sanatçı ismi ise: Şarkı - Sanatçı
                elif u_lower in p2.lower() or p2.lower() in u_lower:
                    return p1, p2

            # Eşleşme yoksa varsayılan olarak [p1, p2] al
            return p1, p2

    artist = data_artist or uploader or "Bilinmiyor"
    return cleaned, clean_title_noise(artist)


def create_emoji_progress_bar(current_seconds: float, total_seconds: float | None, length: int = 6) -> str:
    """
    Sunucuya özel emojilerle interaktif bir müzik ilerleme çubuğu oluşturur.
    Dolgu: <:1545483634905976975:1557813129310638150>
    Düğme: <:1545483638974578818:1557810173207253084>
    Boş:   <:1545483637602910219:1557810153636634775>
    """
    if not total_seconds or total_seconds <= 0:
        return config.EMOJI_BAR_KNOB + (config.EMOJI_BAR_EMPTY * (length - 1))

    progress = min(1.0, max(0.0, current_seconds / total_seconds))
    pos = int(progress * (length - 1))

    return (config.EMOJI_BAR_FILLED * pos) + config.EMOJI_BAR_KNOB + (config.EMOJI_BAR_EMPTY * (length - 1 - pos))
