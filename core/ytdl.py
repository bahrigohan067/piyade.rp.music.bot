import asyncio
import re
import discord
import yt_dlp
from typing import Optional, Dict, Any, List
import config
from utils.helpers import format_duration, format_bytes, parse_song_and_artist, clean_title_noise

# yt-dlp örneği
ytdl = yt_dlp.YoutubeDL(config.YTDL_OPTIONS)

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
        artist_name: Optional[str] = None
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


class YTDLSource:
    """YouTube ve dosya ses kaynaklarını yöneten yardımcı sınıf."""

    @classmethod
    async def create_source(cls, song: Song, volume: float = 0.8) -> discord.PCMVolumeTransformer:
        """Şarkıdan FFmpeg ses kaynağı üretir."""
        stream_url = song.stream_url
        
        if not song.is_file and not stream_url:
            fresh_song, error_detail = await cls.from_query(song.webpage_url, song.requester)
            if fresh_song and fresh_song.stream_url:
                stream_url = fresh_song.stream_url
                if fresh_song.duration and not song.duration:
                    song.duration = fresh_song.duration
                if fresh_song.thumbnail and not song.thumbnail:
                    song.thumbnail = fresh_song.thumbnail
                if fresh_song.song_name:
                    song.song_name = fresh_song.song_name
                if fresh_song.artist_name:
                    song.artist_name = fresh_song.artist_name
            else:
                # YouTube veri merkezi IP engeline karşı otomatik SoundCloud yedeği
                print(f"[YTDL] YouTube akışı alınamadı ({error_detail}). Otomatik SoundCloud yedeği deneniyor: {song.title}")
                sc_song, sc_err = await cls.from_soundcloud(song.title, song.requester)
                if sc_song and sc_song.stream_url:
                    stream_url = sc_song.stream_url
                    if not song.duration:
                        song.duration = sc_song.duration
                    if not song.thumbnail:
                        song.thumbnail = sc_song.thumbnail
                    print(f"[YTDL] SoundCloud yedeği başarıyla bağlandı: {sc_song.title}")
                else:
                    raise RuntimeError(f"Şarkı akış linki alınamadı: {error_detail or 'Bilinmeyen hata'}")

        audio = discord.FFmpegPCMAudio(
            stream_url,
            before_options=config.FFMPEG_BEFORE_OPTIONS,
            options=config.FFMPEG_OPTIONS
        )
        return discord.PCMVolumeTransformer(audio, volume=volume)

    @classmethod
    async def from_soundcloud(cls, search_query: str, requester: discord.Member) -> tuple[Optional[Song], Optional[str]]:
        """SoundCloud üzerinden şarkıyı arar ve bulur (IP engeline takılmaz)."""
        loop = asyncio.get_event_loop()
        clean_title = clean_title_noise(search_query)
        sc_query = f"scsearch5:{clean_title}"

        error_detail = None
        opts = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 6,
            'retries': 1,
            'default_search': 'scsearch',
        }

        def extract():
            nonlocal error_detail
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(sc_query, download=False)
            except Exception as e:
                err_str = str(e)
                print(f"[SoundCloud Error] {err_str}")
                error_detail = err_str
                return None

        data = await loop.run_in_executor(None, extract)
        if not data:
            return None, error_detail

        entries = data.get('entries') if 'entries' in data else [data]
        if not entries:
            return None, error_detail or "Arama sonucu bulunamadı"

        valid_entry = None
        for entry in entries:
            if not entry:
                continue
            # Akış URL'si olan ilk geçerli (DRM'siz) kaydı seç
            if entry.get('url'):
                valid_entry = entry
                break

        if not valid_entry:
            return None, error_detail or "Geçerli ses akışı bulunamadı (DRM korumalı veya silinmiş olabilir)"

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
            song_name=valid_entry.get('track') or clean_title
        )
        return song, None

    @classmethod
    async def from_query(cls, query: str, requester: discord.Member) -> tuple[Optional[Song], Optional[str]]:
        """Arama terimi veya YouTube URL'sinden (Song, error_type) döndürür."""
        loop = asyncio.get_event_loop()
        
        query = clean_youtube_query(query)
        search_query = query if query.startswith(('http://', 'https://')) else f"ytsearch1:{query}"

        error_detail = None

        def extract():
            nonlocal error_detail
            try:
                # Güncel YTDL_OPTIONS ile çalıştır (çerez sonradan eklense bile anında okur)
                with yt_dlp.YoutubeDL(config.YTDL_OPTIONS) as ydl:
                    return ydl.extract_info(search_query, download=False)
            except Exception as e:
                err_str = str(e)
                print(f"[YTDL Error] {err_str}")
                if "Sign in to confirm you" in err_str:
                    error_detail = "BOT_CHECK"
                else:
                    error_detail = err_str
                return None

        # Ana döngüyü kilitlememesi için thread içinde çalıştır
        data = await loop.run_in_executor(None, extract)
        if not data:
            if error_detail == "BOT_CHECK":
                print(f"[YTDL] YouTube bot engeli nedeniyle SoundCloud deneniyor: {query}")
                sc_song, sc_err = await cls.from_soundcloud(query, requester)
                if sc_song:
                    return sc_song, None
            return None, error_detail

        # Arama sonucu liste ise ilk elemanı al
        if 'entries' in data:
            if not data['entries']:
                return None, error_detail
            data = data['entries'][0]

        song = Song(
            title=data.get('title', 'Bilinmeyen Şarkı'),
            stream_url=data.get('url', ''),
            webpage_url=data.get('webpage_url', query),
            duration=data.get('duration'),
            thumbnail=data.get('thumbnail'),
            requester=requester,
            is_file=False,
            uploader=data.get('uploader'),
            artist_name=data.get('artist') or data.get('creator'),
            song_name=data.get('track')
        )
        return song, None

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

        error_detail = None

        playlist_opts = {
            **config.YTDL_OPTIONS,
            'noplaylist': False,
            'extract_flat': 'in_playlist',
            'playlistend': max_songs,
            'ignoreerrors': True,
        }

        def extract():
            nonlocal error_detail
            try:
                with yt_dlp.YoutubeDL(playlist_opts) as ydl:
                    return ydl.extract_info(clean_url, download=False)
            except Exception as e:
                err_str = str(e)
                print(f"[YTDL Playlist Error] {err_str}")
                if "Sign in to confirm you" in err_str:
                    error_detail = "BOT_CHECK"
                else:
                    error_detail = err_str
                return None

        data = await loop.run_in_executor(None, extract)
        if not data:
            return [], error_detail, None

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
