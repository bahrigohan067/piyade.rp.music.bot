import re
import discord
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
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' "\'[](){}-–—')
    return cleaned or text


def parse_song_and_artist(raw_title: str, uploader: str | None = None, data_artist: str | None = None, data_track: str | None = None) -> tuple[str, str]:
    """
    Şarkı başlığından temiz [Şarkı Adı] ve [Sanatçı] ayrımı yapar.
    YouTube başlıkları genellikle 'Sanatçı - Şarkı Adı' formatındadır.
    Örn: 'Bora Duran - Döndüm' -> Şarkı Adı: 'Döndüm', Sanatçı: 'Bora Duran'
    """
    if data_track and data_artist:
        return clean_title_noise(data_track), clean_title_noise(data_artist)

    cleaned = clean_title_noise(raw_title)

    for sep in [' - ', ' – ', ' — ', ' | ']:
        if sep in cleaned:
            parts = cleaned.split(sep, 1)
            p1 = clean_title_noise(parts[0])  # Genellikle Sanatçı
            p2 = clean_title_noise(parts[1])  # Genellikle Şarkı Adı

            # Eğer uploader p2 içinde geçiyorsa (Ters yazılmış: Şarkı - Sanatçı):
            if uploader:
                u_lower = uploader.lower()
                if u_lower in p2.lower() or p2.lower() in u_lower:
                    return p1, p2  # Şarkı Adı = p1, Sanatçı = p2

            # Standart YouTube kuralı (Bora Duran - Döndüm):
            # p1 = Sanatçı, p2 = Şarkı Adı -> return (Şarkı Adı, Sanatçı)
            return p2, p1

    artist = data_artist or uploader or "Bilinmiyor"
    return cleaned, clean_title_noise(artist)


def resolve_discord_emoji(bot, guild, emoji_id: int, emoji_name: str, fallback: str) -> str:
    """
    Sunucu veya bot önbelleğindeki özel emojiyi arar.
    Animasyonlu ise otomatik <a:name:id>, statik ise <:name:id> üretir.
    Eğer emoji bulunamazsa veya erişilemiyorsa bozuk metin yazmak yerine temiz fallback döner.
    """
    # 1. Sunucu emojilerinden ID veya isimle ara
    if guild:
        for e in guild.emojis:
            if e.id == emoji_id or (emoji_name and e.name.lower() == emoji_name.lower()):
                return str(e)

    # 2. Botun tüm sunucularındaki emojilerde ara
    if bot:
        for e in bot.emojis:
            if e.id == emoji_id or (emoji_name and e.name.lower() == emoji_name.lower()):
                return str(e)

    # 3. Eğer bot emojiyi göremiyorsa bozuk metin (:isim:) yerine temiz fallback döner
    return fallback


def create_emoji_progress_bar(player, current_seconds: float, total_seconds: float | None, length: int = 8) -> str:
    """
    Sunucu emojileriyle (veya güvenli fallback ile) ilerleme çubuğu oluşturur.
    Asla bozuk :sayı: metni göstermez.
    """
    guild = player.guild if player else None
    bot = player.bot if player else None

    # Emojileri dinamik çöz (Öncelik: sunucu/bot önbelleği -> Fallback: doğrudan kullanıcının özel emojisi)
    filled = resolve_discord_emoji(bot, guild, 1557825590562652350, "1545483634905976975", fallback=config.EMOJI_BAR_FILLED)
    knob = resolve_discord_emoji(bot, guild, 1557825653074559096, "1545483638974578818", fallback=config.EMOJI_BAR_KNOB)
    empty = resolve_discord_emoji(bot, guild, 1557825718782795827, "1545483637602910219", fallback=config.EMOJI_BAR_EMPTY)

    if not total_seconds or total_seconds <= 0:
        return knob + (empty * (length - 1))

    progress = min(1.0, max(0.0, current_seconds / total_seconds))
    pos = int(progress * (length - 1))

    return (filled * pos) + knob + (empty * (length - 1 - pos))
