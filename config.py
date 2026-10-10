import os
from dotenv import load_dotenv

load_dotenv()

# Discord Bot Token (Railway'deki MUSIC_TOKEN değişkenini okur)
DISCORD_TOKEN = os.getenv("MUSIC_TOKEN") or os.getenv("DISCORD_TOKEN", "")

# Müzik Açma İzni Rol ID'si (Varsayılan: 1547589732937240627)
MUSIC_ROLE_ID = int(os.getenv("MUSIC_ROLE_ID", "1547589732937240627"))

# Çalma Listesi Maksimum Şarkı Limiti (Varsayılan: 100 parça)
MAX_PLAYLIST_SONGS = int(os.getenv("MAX_PLAYLIST_SONGS", "100"))

# Belirli bir sunucuya anında slash komutu senkronizasyonu için opsiyonel Guild ID
# Boş bırakılırsa tüm sunucularda global senkronize olur (global senkronizasyon birkaç dakika sürebilir)
GUILD_ID = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") and os.getenv("GUILD_ID").isdigit() else None

# Bot Prefix (opsiyonel klasik kullanım için)
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")

# Renk Paleti (Discord Embed Tasarımları)
COLOR_DEFAULT = 0x5865F2    # Discord Blurple
COLOR_PLAYING = 0x57F287    # Yeşil (Çalıyor)
COLOR_PAUSED = 0xFEE75C     # Sarı (Duraklatıldı)
COLOR_ERROR = 0xED4245      # Kırmızı (Hata)
COLOR_QUEUE = 0xEB459E      # Pembe (Kuyruk)

# Emojiler
EMOJI_PLAY = "▶️"
EMOJI_PAUSE = "⏸️"
EMOJI_PREVIOUS = "⏮️"
EMOJI_SKIP = "⏭️"
EMOJI_STOP = "⏹️"
EMOJI_QUEUE = "📜"
EMOJI_HISTORY = "🕰️"
EMOJI_LOOP = "🔁"
EMOJI_SHUFFLE = "🔀"
EMOJI_VOL_UP = "🔊"
EMOJI_VOL_DOWN = "🔉"
EMOJI_MUSIC = "🎵"
EMOJI_LOCK = "🔒"

# Özel İlerleme Çubuğu ve CD Emojileri (Sunucunuzdaki Emojiler)
EMOJI_CD = os.getenv("EMOJI_CD", "<a:60263cd:1557833161508003871>")
EMOJI_BAR_FILLED = os.getenv("EMOJI_BAR_FILLED", "<:1545483634905976975:1557825590562652350>")
EMOJI_BAR_KNOB = os.getenv("EMOJI_BAR_KNOB", "<:1545483638974578818:1557825653074559096>")
EMOJI_BAR_EMPTY = os.getenv("EMOJI_BAR_EMPTY", "<:1545483637602910219:1557825718782795827>")

# FFmpeg Akış Yapılandırması (Kopmaları ve gecikmeleri önleyici parametreler)
FFMPEG_BEFORE_OPTIONS = (
    "-reconnect 1 "
    "-reconnect_streamed 1 "
    "-reconnect_delay_max 5 "
    "-nostdin"
)

FFMPEG_OPTIONS = "-vn"

# yt-dlp Yapılandırması (En yüksek ses kalitesi ve Discord uyumluluğu)
YTDL_OPTIONS = {
    'format': 'bestaudio[acodec=opus]/bestaudio[ext=webm]/bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'socket_timeout': 6,
    'retries': 1,
    'extractor_retries': 0,
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'ios']
        }
    }
}

# Çerez Token Kontrolü (Railway Variables: YTDLP_TOKEN veya YTDLP_COOKIES)
cookie_token = os.getenv("YTDLP_TOKEN") or os.getenv("YTDLP_COOKIES")
if cookie_token:
    import base64
    import tempfile
    cookie_str = cookie_token.strip()
    # Base64 formatındaki token'ı otomatik çöz
    if cookie_str.startswith("IyBO") or len(cookie_str) > 100:
        try:
            decoded = base64.b64decode(cookie_str).decode('utf-8')
            if "Netscape" in decoded or "\t" in decoded:
                cookie_str = decoded
        except Exception:
            pass
    elif "\\n" in cookie_str and "\n" not in cookie_str:
        cookie_str = cookie_str.replace("\\n", "\n")

    # Eski IP'ye bağlı abuse exemption satırlarını temizle
    lines = [
        line for line in cookie_str.splitlines()
        if "GOOGLE_ABUSE_EXEMPTION" not in line and line.strip()
    ]
    # Proje dizininde kalıcı dosya oluşturmak yerine sistem geçici dizininde oluştur
    temp_cookie_path = os.path.join(tempfile.gettempdir(), "yt_cookie_token.txt")
    with open(temp_cookie_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    YTDL_OPTIONS['cookiefile'] = temp_cookie_path

# Mobil istemcileri kullan (Sunucu/Veri merkezi IP bot engeline takılmaz)
if 'cookiefile' in YTDL_OPTIONS:
    YTDL_OPTIONS['extractor_args'] = {
        'youtube': {
            'player_client': ['android', 'ios', 'mweb']
        }
    }


