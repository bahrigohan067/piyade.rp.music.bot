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


class YTDLSource:
    """YouTube ve dosya ses kaynaklarını yöneten yardımcı sınıf."""

    @classmethod
    async def create_source(cls, song: Song, volume: float = 0.8) -> discord.PCMVolumeTransformer:
        """Şarkıdan FFmpeg ses kaynağı üretir."""
        # Eğer YouTube URL'sinin stream linki zaman aşımına uğramışsa yenileme ihtimali
        stream_url = song.stream_url
        
        # Eğer YouTube linkiyse ve stream URL güncellenmesi gerekebiliyorsa
        if not song.is_file and not stream_url:
            fresh_song = await cls.from_query(song.webpage_url, song.requester)
            if fresh_song:
                stream_url = fresh_song.stream_url

        audio = discord.FFmpegPCMAudio(
            stream_url,
            before_options=config.FFMPEG_BEFORE_OPTIONS,
            options=config.FFMPEG_OPTIONS
        )
        return discord.PCMVolumeTransformer(audio, volume=volume)

    @classmethod
    async def from_query(cls, query: str, requester: discord.Member) -> Optional[Song]:
        """Arama terimi veya YouTube URL'sinden Song nesnesi oluşturur."""
        loop = asyncio.get_event_loop()
        
        # Eğer direkt link değilse arama yap
        if not query.startswith(('http://', 'https://')):
            query = f"ytsearch1:{query}"

        def extract():
            try:
                return ytdl.extract_info(query, download=False)
            except Exception as e:
                print(f"[YTDL Error] {e}")
                return None

        # Ana döngüyü kilitlememesi için thread içinde çalıştır
        data = await loop.run_in_executor(None, extract)
        if not data:
            return None

        # Arama sonucu liste ise ilk elemanı al
        if 'entries' in data:
            if not data['entries']:
                return None
            data = data['entries'][0]

        return Song(
            title=data.get('title', 'Bilinmeyen Şarkı'),
            stream_url=data.get('url', ''),
            webpage_url=data.get('webpage_url', query),
            duration=data.get('duration'),
            thumbnail=data.get('thumbnail'),
            requester=requester,
            is_file=False,
            uploader=data.get('uploader')
        )

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
