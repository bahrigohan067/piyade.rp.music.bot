import asyncio
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import discord
import yt_dlp
from typing import Optional, Dict, Any, List, Tuple
import config
from utils.helpers import format_duration, format_bytes, parse_song_and_artist, clean_title_noise


class Song:
    """Müzik veya ses dosyası verilerini temsil eden sınıf."""
    def __init__(
        self,
        title: str,
        stream_url: str,
        webpage_url: str,
        duration: Optional[int],
        thumbnail: Optional[str],
        requester: discord.Member,
        is_file: bool = False,
        file_name: Optional[str] = None,
        uploader: Optional[str] = None,
        file_size: Optional[int] = None,
        song_name: Optional[str] = None,
        artist_name: Optional[str] = None,
        http_headers: Optional[Dict[str, str]] = None
    ):
        self.title = title
        self.stream_url = stream_url
        self.webpage_url = webpage_url
        self.duration = duration
        self.thumbnail = thumbnail
        self.requester = requester
        self.is_file = is_file
        self.file_name = file_name
        self.uploader = uploader or ("Dosya Yüklemesi" if is_file else "Bilinmiyor")
        self.file_size = file_size
        # Akış adresine erişirken FFmpeg'in göndermesi gereken HTTP başlıkları (User-Agent vb.)
        self.http_headers: Dict[str, str] = dict(http_headers or {})
        # Erken kopma durumunda yeniden deneme bilgileri
        self.retry_count: int = 0
        self.force_pipe: bool = False

        if is_file:
            self.song_name = file_name or clean_title_noise(title)
            self.artist_name = "Dosya Yüklemesi"
        else:
            s_name, a_name = parse_song_and_artist(title, self.uploader, artist_name, song_name)
            self.song_name = s_name
            self.artist_name = a_name

    @property
    def formatted_duration(self) -> str:
        if self.is_file:
            return f"Dosya ({format_bytes(self.file_size)})" if self.file_size else "Ses Dosyası"
        return format_duration(self.duration)


def is_playlist_url(query: str) -> bool:
    """URL'in bir YouTube veya YouTube Music çalma listesi/albümü olup olmadığını kontrol eder."""
    q = query.strip().lower()
    if not (q.startswith("http://") or q.startswith("https://")):
        return False
    if "youtube.com" not in q and "youtu.be" not in q:
        return False
    # playlist?list= kontrolü
    if "playlist?list=" in q or "/playlist?" in q:
        return True
    # watch?v=...&list=PL... veya list=OLAK... veya list=UU...
    if "list=pl" in q or "list=olak" in q or "list=uu" in q or "list=fl" in q:
        return True
    return False


def normalize_playlist_url(query: str) -> str:
    """Çalma listesi URL'sini standart YouTube playlist URL formatına çevirir."""
    query = query.strip()
    match = re.search(r'[?&]list=([^&]+)', query)
    if match:
        playlist_id = match.group(1)
        return f"https://www.youtube.com/playlist?list={playlist_id}"
    return query.replace("music.youtube.com", "www.youtube.com")


def clean_youtube_query(query: str) -> str:
    """YouTube Music ve kişisel radyo/mix parametrelerini temizler."""
    query = query.strip()
    query = query.replace("music.youtube.com", "www.youtube.com")
    
    # Eğer doğrudan bir video linkiyse (watch?v=), kişisel playlist &list=LM veya RD parametrelerini kaldır
    if "watch?" in query and "v=" in query:
        query = re.sub(r'&list=(?:LM|RD|UL|LL)[^&]*', '', query)
        query = re.sub(r'&index=[^&]+', '', query)
        query = re.sub(r'&start_radio=[^&]+', '', query)
    return query


def is_youtube_url(url: Optional[str]) -> bool:
    if not url:
        return False
    u = url.lower()
    return "youtube.com" in u or "youtu.be" in u


def extract_title_from_youtube_url(url: str) -> Optional[str]:
    """YouTube URL'sinden oEmbed veya HTML üzerinden video başlığını çıkarır."""
    try:
        import urllib.request
        import urllib.parse
        import json
        oembed_url = f"https://www.youtube.com/oembed?url={urllib.parse.quote(url, safe='')}&format=json"
        req = urllib.request.Request(oembed_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get('title')
    except Exception:
        pass
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8', errors='ignore')
            m = re.search(r'<title>(.*?)</title>', html)
            if m:
                title = m.group(1).replace(" - YouTube", "").strip()
                return title or None
    except Exception:
        pass
    return None


def resolve_spotify_query(query: str) -> Optional[str]:
    """
    Spotify şarkı URL'sini (open.spotify.com/track/...) analiz eder ve
    YouTube araması için 'Sanatçı - Şarkı Adı' formatında temiz arama terimi döner.
    Bu sayede Spotify DRM kısıtlamasına (30 saniyelik önizleme) takılmadan
    YouTube üzerinden TAM parça dinlenir.
    """
    if "spotify.com" not in query.lower() or "/track/" not in query.lower():
        return None

    try:
        import urllib.request
        req = urllib.request.Request(
            query,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8', errors='ignore')

        og_title = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        og_desc = re.search(r'<meta property="og:description" content="([^"]+)"', html)

        track_name = og_title.group(1).strip() if og_title else None
        artist_name = None

        if og_desc:
            desc_text = og_desc.group(1)
            parts = re.split(r'\s*[·•\-]\s*', desc_text)
            if parts and parts[0].strip():
                artist_name = parts[0].strip()

        if not artist_name:
            title_tag = re.search(r'<title>([^<]+)</title>', html)
            if title_tag:
                m = re.search(r'by\s+(.*?)\s*\|\s*Spotify', title_tag.group(1), re.IGNORECASE)
                if m:
                    artist_name = m.group(1).strip()

        if track_name and artist_name:
            clean_track = clean_title_noise(track_name)
            clean_art = clean_title_noise(artist_name)
            return f"{clean_art} - {clean_track}"
        elif track_name:
            return clean_title_noise(track_name)
    except Exception as e:
        print(f"[Spotify Resolver Error] {e}")

    return None


# --- yt-dlp YARDIMCI FONKSİYONLARI ---

# Bu hatalar kalıcıdır; farklı istemcilerle tekrar denemek anlamsızdır
_PERMANENT_ERROR_MARKERS = (
    'private video',
    'has been removed',
    'account associated with this video has been terminated',
    'copyright claim',
    'unsupported url',
    'is not a valid url',
    'no video results',
)


def _is_bot_check(err: Optional[str]) -> bool:
    if not err:
        return False
    e = err.lower()
    return "sign in to confirm" in e or "not a bot" in e


def _cookie_copy() -> Optional[str]:
    """
    Ana çerez dosyasının geçici bir kopyasını oluşturur.
    yt-dlp kapanırken çerez dosyasının üzerine yazdığı için, eşzamanlı işlemler ana dosyayı bozmasın diye
    her işlem kendi kopyasını kullanır.
    """
    src = getattr(config, 'YTDL_COOKIEFILE', None)
    if not src or not os.path.exists(src):
        return None
    try:
        fd, path = tempfile.mkstemp(prefix="ytc_", suffix=".txt")
        os.close(fd)
        shutil.copyfile(src, path)
        return path
    except Exception:
        return None


def _safe_remove(path: Optional[str]):
    if path:
        try:
            os.remove(path)
        except Exception:
            pass


def _run_ytdl(opts: Dict[str, Any], target: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """yt-dlp'yi verilen ayarlarla senkron olarak çalıştırır. (data, hata_metni) döner."""
    opts = dict(opts)
    tmp_cookie = None
    if opts.get('cookiefile'):
        tmp_cookie = _cookie_copy()
        if tmp_cookie:
            opts['cookiefile'] = tmp_cookie
        else:
            opts.pop('cookiefile', None)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(target, download=False), None
    except Exception as e:
        return None, str(e)
    finally:
        _safe_remove(tmp_cookie)


def _extraction_variants() -> List[Tuple[str, Dict[str, Any]]]:
    """
    Sırasıyla denenecek yt-dlp yapılandırmaları:
    1) Varsayılan istemciler (+ çerez varsa çerezli) — Deno ile en güvenilir yol
    2) Çerezsiz android_vr/tv/web_safari — PO token gerektirmeyen yedek istemciler
    3) Çerezli tv/web_safari/mweb/web — son çare
    """
    base = dict(config.YTDL_OPTIONS)
    base.pop('extractor_args', None)
    no_cookie = {k: v for k, v in base.items() if k != 'cookiefile'}

    variants: List[Tuple[str, Dict[str, Any]]] = [("varsayılan", base)]
    variants.append((
        "android_vr",
        {**no_cookie, 'extractor_args': {'youtube': {'player_client': ['android_vr', 'tv', 'web_safari']}}}
    ))
    if base.get('cookiefile'):
        variants.append((
            "tv/web",
            {**base, 'extractor_args': {'youtube': {'player_client': ['tv', 'web_safari', 'mweb', 'web']}}}
        ))
    return variants


def _pick_stream(info: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, str]]:
    """Seçilen formatın akış adresini ve gerekli HTTP başlıklarını döner."""
    if not info:
        return None, {}
    if info.get('url'):
        return info['url'], dict(info.get('http_headers') or {})
    for fmt in info.get('requested_formats') or []:
        if fmt.get('url') and fmt.get('acodec') not in (None, 'none'):
            return fmt['url'], dict(fmt.get('http_headers') or {})
    return None, {}


def _extract_stream_sync(url: str) -> Tuple[Optional[Dict[str, Any]], Optional[str], bool]:
    """
    Tek bir video için akış bilgisini birden fazla istemci stratejisiyle çeker.
    Döner: (info, son_hata, tüm_hatalar_bot_engeli_mi)
    """
    last_err: Optional[str] = None
    errors: List[str] = []

    for name, opts in _extraction_variants():
        data, err = _run_ytdl(opts, url)
        if data and 'entries' in data:
            entries = [e for e in (data.get('entries') or []) if e]
            data = entries[0] if entries else None
            if not data and not err:
                err = "Sonuç bulunamadı"

        if data:
            stream_url, _ = _pick_stream(data)
            if stream_url:
                if name != "varsayılan":
                    print(f"[YTDL] Akış '{name}' stratejisiyle alındı: {data.get('title')}")
                return data, None, False
            err = err or "Oynatılabilir ses formatı bulunamadı"

        last_err = err or "Bilinmeyen hata"
        errors.append(last_err)
        print(f"[YTDL] '{name}' stratejisi başarısız: {last_err[:200]}")

        if any(m in last_err.lower() for m in _PERMANENT_ERROR_MARKERS):
            break

    all_bot = bool(errors) and all(_is_bot_check(e) for e in errors)
    return None, last_err, all_bot


def _search_sync(query: str, limit: int = 5) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """YouTube'da hızlı (flat) arama yaparak aday videoları döner."""
    base = dict(config.YTDL_OPTIONS)
    base.pop('extractor_args', None)
    search_opts = {**base, 'extract_flat': 'in_playlist', 'noplaylist': False}
    attempts = [search_opts]
    if search_opts.get('cookiefile'):
        attempts.append({k: v for k, v in search_opts.items() if k != 'cookiefile'})

    last_err = None
    for opts in attempts:
        data, err = _run_ytdl(opts, f"ytsearch{limit}:{query}")
        if data:
            entries = [e for e in (data.get('entries') or []) if e and (e.get('id') or e.get('url'))]
            if entries:
                return entries, None
            err = err or "Arama sonucu bulunamadı"
        last_err = err
        print(f"[YTDL Search] Arama başarısız: {(err or '')[:200]}")
    return [], last_err


def _ffmpeg_before_options(headers: Optional[Dict[str, str]]) -> str:
    """
    FFmpeg giriş seçeneklerini oluşturur. yt-dlp'nin akışı aldığı istemcinin User-Agent ve
    başlıkları FFmpeg'e de iletilir; aksi halde YouTube akışı birkaç saniye içinde 403 ile keser.
    """
    opts = config.FFMPEG_BEFORE_OPTIONS
    if not headers:
        return opts

    parts = [opts]
    user_agent = headers.get('User-Agent') or headers.get('user-agent')
    if user_agent:
        parts.append("-user_agent " + shlex.quote(user_agent))

    crlf = "\r\n"
    extra = ""
    for key, value in headers.items():
        if not value or key.lower() in ('user-agent', 'cookie'):
            continue
        extra += f"{key}: {value}" + crlf
    if extra:
        parts.append("-headers " + shlex.quote(extra))
    return " ".join(parts)


class YTDLPipeAudio(discord.FFmpegPCMAudio):
    """
    Yedek oynatma modu: Sesi yt-dlp'nin kendisi indirip FFmpeg'e boru (pipe) ile aktarır.
    Doğrudan akış adresi erken koptuğunda (403/kısıtlama) kullanılır; yt-dlp tüm başlık,
    çerez ve parça (fragment) yönetimini kendisi üstlenir.
    """
    def __init__(self, url: str):
        self._ytdlp_proc: Optional[subprocess.Popen] = None
        self._cookie_tmp: Optional[str] = _cookie_copy()

        cmd = [
            sys.executable, '-m', 'yt_dlp',
            '--no-playlist', '--quiet', '--no-warnings', '--no-part',
            '-f', 'bestaudio/best',
            '-o', '-',
        ]
        if self._cookie_tmp:
            cmd += ['--cookies', self._cookie_tmp]
        cmd.append(url)

        self._ytdlp_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            super().__init__(self._ytdlp_proc.stdout, pipe=True, options=config.FFMPEG_OPTIONS)
        except Exception:
            self._kill_ytdlp()
            raise

    def _kill_ytdlp(self):
        proc = getattr(self, '_ytdlp_proc', None)
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=3)
            except Exception:
                pass
            try:
                if proc.stdout:
                    proc.stdout.close()
            except Exception:
                pass
        self._ytdlp_proc = None
        _safe_remove(getattr(self, '_cookie_tmp', None))
        self._cookie_tmp = None

    def cleanup(self) -> None:
        try:
            super().cleanup()
        finally:
            self._kill_ytdlp()


def _is_preview_entry(entry: Dict[str, Any]) -> bool:
    """SoundCloud Go+ 30 saniyelik önizleme kaydı olup olmadığını kontrol eder."""
    dur = entry.get('duration') or 0
    if 0 < dur <= 35:
        return True
    fmt_url = (entry.get('url') or '').lower()
    if '/preview/' in fmt_url:
        return True
    note = f"{entry.get('format_id') or ''} {entry.get('format_note') or ''}".lower()
    return 'preview' in note


class YTDLSource:
    """YouTube ve dosya ses kaynaklarını yöneten yardımcı sınıf."""

    @classmethod
    async def create_source(cls, song: Song, volume: float = 0.8) -> discord.PCMVolumeTransformer:
        """Şarkıdan FFmpeg ses kaynağı üretir."""
        # Dosya yüklemeleri doğrudan oynatılır
        if song.is_file:
            audio = discord.FFmpegPCMAudio(
                song.stream_url,
                before_options=config.FFMPEG_BEFORE_OPTIONS,
                options=config.FFMPEG_OPTIONS
            )
            return discord.PCMVolumeTransformer(audio, volume=volume)

        # Yedek mod: Doğrudan akış erken koptuysa sesi yt-dlp üzerinden boru ile aktar
        if song.force_pipe and is_youtube_url(song.webpage_url):
            print(f"[YTDL] Pipe modu ile yeniden oynatılıyor: {song.title}")
            audio = YTDLPipeAudio(song.webpage_url)
            return discord.PCMVolumeTransformer(audio, volume=volume)

        stream_url = song.stream_url
        headers = song.http_headers

        if not stream_url:
            fresh_song, error_detail = await cls.from_query(song.webpage_url, song.requester)
            if not fresh_song or not fresh_song.stream_url:
                raise RuntimeError(f"Şarkı akış linki alınamadı: {error_detail or 'Bilinmeyen hata'}")

            stream_url = fresh_song.stream_url
            headers = fresh_song.http_headers
            song.http_headers = headers
            if fresh_song.duration and not song.duration:
                song.duration = fresh_song.duration
            if fresh_song.thumbnail and not song.thumbnail:
                song.thumbnail = fresh_song.thumbnail
            # Meta verileri yalnızca aynı kaynaktan (YouTube) geldiyse güncelle
            if is_youtube_url(fresh_song.webpage_url):
                if fresh_song.song_name:
                    song.song_name = fresh_song.song_name
                if fresh_song.artist_name:
                    song.artist_name = fresh_song.artist_name

        audio = discord.FFmpegPCMAudio(
            stream_url,
            before_options=_ffmpeg_before_options(headers),
            options=config.FFMPEG_OPTIONS
        )
        return discord.PCMVolumeTransformer(audio, volume=volume)

    @classmethod
    async def from_soundcloud(cls, search_query: str, requester: discord.Member) -> tuple[Optional[Song], Optional[str]]:
        """SoundCloud üzerinden şarkıyı arar ve bulur (IP engeline takılmaz)."""
        loop = asyncio.get_event_loop()
        
        # Eğer bir YouTube linki doğrudan yedek olarak düştüyse, başlığı çekip SoundCloud'da arat
        if is_youtube_url(search_query):
            yt_title = await loop.run_in_executor(None, extract_title_from_youtube_url, search_query)
            if not yt_title:
                return None, "YouTube video başlığı alınamadı"
            print(f"[SoundCloud] YouTube URL başlığı çözümlendi: '{yt_title}' -> SoundCloud'da aranıyor.")
            search_query = yt_title

        clean_title = clean_title_noise(search_query)
        sc_query = f"scsearch5:{clean_title}"

        opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 10,
            'retries': 2,
        }

        data, error_detail = await loop.run_in_executor(None, _run_ytdl, opts, sc_query)
        if error_detail:
            print(f"[SoundCloud Error] {error_detail}")
        if not data:
            return None, error_detail or "SoundCloud araması başarısız"

        entries = data.get('entries') if 'entries' in data else [data]
        entries = [e for e in (entries or []) if e and e.get('url')]
        if not entries:
            return None, error_detail or "Arama sonucu bulunamadı"

        is_user_requesting_slowed = "slowed" in search_query.lower()

        valid_entry = None
        # Bası patlak / earrape / bozuk remix, istenmeyen slowed ve 30 saniyelik Go+ önizlemeleri ele
        for entry in entries:
            if _is_preview_entry(entry):
                continue
            e_title = (entry.get('title') or '').lower()
            if not is_user_requesting_slowed and any(bad in e_title for bad in ['slowed', 'deep slowed', 'reverb', 'speed up', 'nightcore', 'chipmunk']):
                continue
            if any(bad in e_title for bad in ['bass boosted', 'earrape', 'distorted', '8d audio']):
                continue
            valid_entry = entry
            break

        # Temiz bulunamadıysa önizleme olmayan ilk kaydı al
        if not valid_entry:
            for entry in entries:
                if not _is_preview_entry(entry):
                    valid_entry = entry
                    break

        if not valid_entry:
            return None, "Yalnızca 30 saniyelik önizleme bulundu (tam sürüm yok)"

        song = Song(
            title=valid_entry.get('title', clean_title),
            stream_url=valid_entry.get('url', ''),
            webpage_url=valid_entry.get('webpage_url', ''),
            duration=valid_entry.get('duration'),
            thumbnail=valid_entry.get('thumbnail'),
            requester=requester,
            is_file=False,
            uploader=valid_entry.get('uploader') or "SoundCloud",
            artist_name=valid_entry.get('artist') or valid_entry.get('uploader'),
            song_name=valid_entry.get('track') or clean_title,
            http_headers=valid_entry.get('http_headers')
        )
        return song, None

    @staticmethod
    def _song_from_info(info: Dict[str, Any], requester: discord.Member, fallback_url: str,
                        fallback_title: Optional[str] = None) -> Song:
        stream_url, headers = _pick_stream(info)
        return Song(
            title=info.get('title') or fallback_title or 'Bilinmeyen Şarkı',
            stream_url=stream_url or '',
            webpage_url=info.get('webpage_url') or fallback_url,
            duration=info.get('duration'),
            thumbnail=info.get('thumbnail'),
            requester=requester,
            is_file=False,
            uploader=info.get('uploader') or info.get('channel'),
            artist_name=info.get('artist') or info.get('creator'),
            song_name=info.get('track'),
            http_headers=headers
        )

    @classmethod
    async def from_query(cls, query: str, requester: discord.Member) -> tuple[Optional[Song], Optional[str]]:
        """Arama terimi veya URL'den (Song, hata_detayı) döndürür."""
        loop = asyncio.get_event_loop()
        query = (query or "").strip()
        if not query:
            return None, "Boş arama"

        # Spotify şarkı linki kontrolü (30 saniyelik önizleme yerine tam parça için YouTube'a yönlendir)
        if "spotify.com" in query.lower() and "/track/" in query.lower():
            spotify_resolved = await loop.run_in_executor(None, resolve_spotify_query, query)
            if spotify_resolved:
                print(f"[Spotify] Spotify parçası çözümlendi: '{spotify_resolved}' -> YouTube'da tam sürüm aranıyor.")
                query = spotify_resolved
            else:
                return None, "Spotify parça bilgisi alınamadı"

        query = clean_youtube_query(query)
        is_url = query.startswith(('http://', 'https://'))

        last_err: Optional[str] = None
        bot_blocked = False

        if is_url:
            info, err, all_bot = await loop.run_in_executor(None, _extract_stream_sync, query)
            if info:
                return cls._song_from_info(info, requester, query), None
            last_err, bot_blocked = err, all_bot
            if not is_youtube_url(query):
                return None, last_err
        else:
            entries, search_err = await loop.run_in_executor(None, _search_sync, query, 5)
            if not entries:
                last_err = search_err or "Arama sonucu bulunamadı"
                bot_blocked = _is_bot_check(search_err)
            else:
                # Shorts/kısa klipleri sona at, tam parçaları öne al
                full_tracks = [e for e in entries if not (0 < (e.get('duration') or 0) <= 35)]
                short_clips = [e for e in entries if 0 < (e.get('duration') or 0) <= 35]
                candidates = (full_tracks + short_clips)[:3]

                for entry in candidates:
                    entry_url = entry.get('url') or ''
                    if not entry_url.startswith('http'):
                        entry_url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                    info, err, all_bot = await loop.run_in_executor(None, _extract_stream_sync, entry_url)
                    if info:
                        return cls._song_from_info(info, requester, entry_url, entry.get('title')), None
                    last_err = err
                    bot_blocked = all_bot
                    # Bot engeli tüm istemcilerde varsa diğer adayları denemek boşuna zaman kaybıdır
                    if all_bot:
                        break

        # Son çare: SoundCloud (30 saniyelik önizlemeler otomatik elenir)
        print(f"[YTDL] YouTube'dan alınamadı ({(last_err or '')[:150]}). SoundCloud yedeği deneniyor: {query}")
        sc_song, sc_err = await cls.from_soundcloud(query, requester)
        if sc_song:
            print(f"[YTDL] SoundCloud yedeği bağlandı: {sc_song.title}")
            return sc_song, None

        if bot_blocked:
            return None, "BOT_CHECK"
        return None, last_err or sc_err or "Bilinmeyen hata"

    @classmethod
    def from_attachment(cls, attachment: discord.Attachment, requester: discord.Member) -> Song:
        """Kullanıcının yüklediği Discord ses dosyasından Song nesnesi oluşturur."""
        return Song(
            title=attachment.filename,
            stream_url=attachment.url,
            webpage_url=attachment.url,
            duration=None,
            thumbnail="https://cdn-icons-png.flankapp.com/512/3844/3844724.png",
            requester=requester,
            is_file=True,
            file_name=attachment.filename,
            file_size=attachment.size
        )

    @classmethod
    async def from_playlist(
        cls,
        query: str,
        requester: discord.Member,
        max_songs: int = config.MAX_PLAYLIST_SONGS
    ) -> tuple[List[Song], Optional[str], Optional[str]]:
        """
        YouTube veya YouTube Music çalma listesindeki tüm şarkıları flat (hızlı) modda çeker.
        Döner: (songs_list, error_detail, playlist_title)
        """
        loop = asyncio.get_event_loop()
        clean_url = normalize_playlist_url(query)

        base = dict(config.YTDL_OPTIONS)
        base.pop('extractor_args', None)
        playlist_opts = {
            **base,
            'noplaylist': False,
            'extract_flat': 'in_playlist',
            'playlistend': max_songs,
            'ignoreerrors': True,
        }

        data, err = await loop.run_in_executor(None, _run_ytdl, playlist_opts, clean_url)
        if not data and playlist_opts.get('cookiefile'):
            # Çerezli deneme başarısızsa çerezsiz tekrar dene
            no_cookie_opts = {k: v for k, v in playlist_opts.items() if k != 'cookiefile'}
            data, err = await loop.run_in_executor(None, _run_ytdl, no_cookie_opts, clean_url)

        if not data:
            if err:
                print(f"[YTDL Playlist Error] {err}")
            return [], ("BOT_CHECK" if _is_bot_check(err) else err), None

        raw_entries = data.get('entries') or []
        if not isinstance(raw_entries, list):
            raw_entries = list(raw_entries)

        playlist_title = data.get('title') or "YouTube Çalma Listesi"
        songs: List[Song] = []

        for entry in raw_entries:
            if not entry:
                continue

            entry_title = (entry.get('title') or "").strip()
            if not entry_title:
                continue

            # Silinmiş, gizli veya kullanılamayan video başlıklarını listeye hiç ekleme
            lower_title = entry_title.lower()
            if any(term in lower_title for term in [
                'deleted video', 'private video', 'unavailable video',
                'silinen video', 'silinmiş video', 'gizli video', 'kullanılamayan video'
            ]):
                continue

            if entry.get('availability') in ['private', 'subscriber_only', 'needs_auth']:
                continue

            video_id = entry.get('id')
            entry_url = entry.get('url')
            if not entry_url or not entry_url.startswith('http'):
                if video_id:
                    webpage_url = f"https://www.youtube.com/watch?v={video_id}"
                else:
                    continue
            else:
                webpage_url = entry_url

            thumb = entry.get('thumbnail')
            if not thumb and entry.get('thumbnails'):
                thumb = entry['thumbnails'][-1].get('url')

            s = Song(
                title=entry_title,
                stream_url="",  # Oynatılacağı an lazy olarak create_source tarafından çekilecek
                webpage_url=webpage_url,
                duration=entry.get('duration'),
                thumbnail=thumb,
                requester=requester,
                is_file=False,
                uploader=entry.get('uploader') or entry.get('channel'),
                artist_name=entry.get('artist') or entry.get('creator'),
                song_name=entry.get('track')
            )
            songs.append(s)

        return songs, None, playlist_title
