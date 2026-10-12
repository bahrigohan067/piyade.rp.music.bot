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
# NOT: 'player_client' bilinçli olarak zorlanmıyor. yt-dlp (Deno JS çalıştırıcısı ile birlikte)
# çerezlerle uyumlu en sağlam istemcileri kendisi seçer. Eski android/ios istemcileri çerezi
# desteklemediği için atlanıyor ve aramaların başarısız olmasına neden oluyordu.
YTDL_OPTIONS = {
    # HLS (m3u8) dahil tüm akış türlerinde çalışan güvenli format seçici
    'format': 'bestaudio[acodec=opus]/bestaudio/best',
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
    'socket_timeout': 10,
    'retries': 3,
    'extractor_retries': 1,
}

# yt-dlp alt sürecinin (pipe modu) kullanacağı çerez dosyası yolu
YTDL_COOKIEFILE = None


def _sanitize_cookie_text(raw: str) -> str:
    """
    Railway arayüzünde bozulabilen çerez metnini onarır:
    - Base64 token'ı çözer
    - Sekme (Tab) yerine boşluk yapıştırılmış satırları düzeltir
    - Hatalı kopyalanmış çerez adlarını (W_Secure- -> __Secure-) onarır
    - IP'ye bağlı GOOGLE_ABUSE_EXEMPTION satırlarını temizler
    """
    import base64
    import binascii

    text = raw.strip().strip('"').strip("'").strip()

    # Base64 token kontrolü (tek satır, sekme/yeni satır içermiyorsa)
    if "\t" not in text and "\n" not in text and not text.startswith("#"):
        compact = "".join(text.split())
        try:
            decoded = base64.b64decode(compact + "=" * (-len(compact) % 4)).decode("utf-8")
            if "Netscape" in decoded or "\t" in decoded or ".youtube.com" in decoded:
                text = decoded
        except (binascii.Error, UnicodeDecodeError, ValueError):
            pass

    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n").replace("\\t", "\t")

    fixed_lines = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 7:
            parts = line.split(None, 6)
        if len(parts) != 7:
            continue
        domain, flag, path, secure, expiry, name, value = [p.strip() for p in parts]
        if name == "GOOGLE_ABUSE_EXEMPTION":
            continue
        if name.startswith("W_Secure-"):
            name = "__Secure-" + name[len("W_Secure-"):]
        elif name.startswith("_Secure-"):
            name = "_" + name
        flag = "TRUE" if domain.startswith(".") else flag.upper()
        secure = secure.upper()
        if not expiry.isdigit():
            expiry = "0"
        fixed_lines.append("\t".join([domain, flag, path, secure, expiry, name, value]))

    return "# Netscape HTTP Cookie File\n\n" + "\n".join(fixed_lines) + "\n", len(fixed_lines)


# Çerez Token Kontrolü (Railway Variables: YTDLP_TOKEN veya YTDLP_COOKIES)
cookie_token = os.getenv("YTDLP_TOKEN") or os.getenv("YTDLP_COOKIES")
if cookie_token:
    import tempfile
    try:
        cookie_content, cookie_count = _sanitize_cookie_text(cookie_token)
        if cookie_count > 0:
            # Proje dizininde kalıcı dosya oluşturmak yerine sistem geçici dizininde oluştur
            temp_cookie_path = os.path.join(tempfile.gettempdir(), "yt_cookie_token.txt")
            with open(temp_cookie_path, "w", encoding="utf-8") as f:
                f.write(cookie_content)
            YTDL_OPTIONS['cookiefile'] = temp_cookie_path
            YTDL_COOKIEFILE = temp_cookie_path
            print(f"[Config] YouTube çerezleri yüklendi ({cookie_count} adet).")
        else:
            print("[Config] UYARI: YTDLP_COOKIES okunamadı, çerezsiz devam ediliyor.")
    except Exception as e:
        print(f"[Config] UYARI: Çerezler işlenemedi ({e}), çerezsiz devam ediliyor.")
