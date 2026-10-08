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
EMOJI_SKIP = "⏭️"
EMOJI_STOP = "⏹️"
EMOJI_QUEUE = "📜"
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

# yt-dlp Yapılandırması
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
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
            'player_client': ['android', 'web']
        }
    }
}

# Çerez kontrolü (Railway'de YTDLP_COOKIES değişkeni veya projedeki cookies.txt)
cookie_content = os.getenv("YTDLP_COOKIES")
if cookie_content:
    if "\\n" in cookie_content and "\n" not in cookie_content:
        cookie_content = cookie_content.replace("\\n", "\n")
    # Eski IP'ye bağlı abuse exemption satırlarını temizle
    lines = [
        line for line in cookie_content.splitlines()
        if "GOOGLE_ABUSE_EXEMPTION" not in line
    ]
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip())
    YTDL_OPTIONS['cookiefile'] = "cookies.txt"
elif os.path.exists("cookies.txt") and os.path.getsize("cookies.txt") > 0:
    YTDL_OPTIONS['cookiefile'] = "cookies.txt"

# Eğer çerez tanımlandıysa standart istemcileri kullanarak tam yetkiyle çalıştır
if 'cookiefile' in YTDL_OPTIONS:
    YTDL_OPTIONS['extractor_args'] = {
        'youtube': {
            'player_client': ['web', 'mweb', 'android']
        }
    }


