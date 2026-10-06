import os
from dotenv import load_dotenv

load_dotenv()

# Discord Bot Token (Railway'deki MUSIC_TOKEN değişkenini okur)
DISCORD_TOKEN = os.getenv("MUSIC_TOKEN") or os.getenv("DISCORD_TOKEN", "")

# Müzik Açma İzni Rol ID'si (Varsayılan: 1547589732937240627)
MUSIC_ROLE_ID = int(os.getenv("MUSIC_ROLE_ID", "1547589732937240627"))

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

# FFmpeg Akış Yapılandırması (Kopmaları ve gecikmeleri önleyici parametreler)
FFMPEG_BEFORE_OPTIONS = (
    "-reconnect 1 "
    "-reconnect_streamed 1 "
    "-reconnect_delay_max 5 "
    "-nostdin"
)

FFMPEG_OPTIONS = "-vn"

# yt-dlp Yapılandırması (YouTube IP ban/datacenter koruması için ios/android istemcileri kullanılır)
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
    'extractor_args': {
        'youtube': {
            'player_client': ['ios', 'android', 'web_creator', 'mweb'],
        }
    }
}

# Çerez kontrolü (Eğer projede cookies.txt varsa yt-dlp'ye aktar)
if os.path.exists("cookies.txt"):
    YTDL_OPTIONS['cookiefile'] = "cookies.txt"
elif os.getenv("YTDLP_COOKIES"):
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write(os.getenv("YTDLP_COOKIES"))
    YTDL_OPTIONS['cookiefile'] = "cookies.txt"
