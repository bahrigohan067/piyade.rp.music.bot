import asyncio
import discord
import yt_dlp
from typing import Optional, Dict, Any
import config
from utils.helpers import format_duration, format_bytes

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
        file_size: Optional[int] = None
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

    @property
    def formatted_duration(self) -> str:
        if self.is_file:
            return f"Dosya ({format_bytes(self.file_size)})" if self.file_size else "Ses Dosyası"
        return format_duration(self.duration)


import re

def clean_youtube_query(query: str) -> str:
    """YouTube Music ve kişisel çalma listesi (LM vb.) parametrelerini temizler."""
    query = query.strip()
    query = query.replace("music.youtube.com", "www.youtube.com")
    
    # Eğer doğrudan bir video linkiyse (watch?v=), kişisel playlist &list=LM parametrelerini kaldır
    if "watch?" in query and "v=" in query:
        query = re.sub(r'&list=[^&]+', '', query)
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
            fresh_song, _ = await cls.from_query(song.webpage_url, song.requester)
            if fresh_song:
                stream_url = fresh_song.stream_url

        audio = discord.FFmpegPCMAudio(
            stream_url,
            before_options=config.FFMPEG_BEFORE_OPTIONS,
            options=config.FFMPEG_OPTIONS
        )
        return discord.PCMVolumeTransformer(audio, volume=volume)

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
            uploader=data.get('uploader')
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
