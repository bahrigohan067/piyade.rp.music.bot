import asyncio
import discord
from typing import Optional, List
import config
from core.ytdl import Song, YTDLSource
from core.views import MusicControlView
from utils.helpers import format_duration

class GuildMusicPlayer:
    """Her sunucu için ayrı müzik kuyruğunu ve oynatma durumunu yönetir."""
    def __init__(self, bot, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.queue: List[Song] = []
        self.current_song: Optional[Song] = None
        self.current_source: Optional[discord.PCMVolumeTransformer] = None
        self.text_channel: Optional[discord.TextChannel] = None
        self.panel_message: Optional[discord.Message] = None
        self.panel_view: Optional[MusicControlView] = None
        
        self.loop_mode: str = "off"  # "off", "song", "queue"
        self.volume: float = 0.8
        self.is_paused: bool = False
        self.skip_loop_once: bool = False
        
        self.lock = asyncio.Lock()
        self.disconnect_task: Optional[asyncio.Task] = None

    @property
    def voice_client(self) -> Optional[discord.VoiceClient]:
        return self.guild.voice_client

    def set_volume(self, volume: float):
        self.volume = max(0.0, min(1.5, volume))
        if self.current_source:
            self.current_source.volume = self.volume

    def cancel_disconnect_timer(self):
        if self.disconnect_task and not self.disconnect_task.done():
            self.disconnect_task.cancel()
            self.disconnect_task = None

    def start_disconnect_timer(self):
        """Kanal boş kaldığında 3 dakika sonra otomatik bağlantıyı keser."""
        self.cancel_disconnect_timer()
        async def disconnect_after_delay():
            await asyncio.sleep(180)  # 3 dakika
            if self.voice_client and not self.voice_client.is_playing() and not self.queue:
                if self.text_channel:
                    try:
                        embed = discord.Embed(
                            title="💤 Boşta Kalma Zaman Aşımı",
                            description="Sırada şarkı bulunmadığı için bot ses kanalından otomatik olarak ayrıldı.",
                            color=config.COLOR_DEFAULT
                        )
                        await self.text_channel.send(embed=embed)
                    except Exception:
                        pass
                await self.stop()

        self.disconnect_task = self.bot.loop.create_task(disconnect_after_delay())

    async def add_to_queue(self, song: Song, text_channel: discord.TextChannel) -> Optional[int]:
        """
        Şarkıyı kuyruğa ekler.
        Eğer müzik çalmıyorsa başlatır ve None döner.
        Eğer zaten müzik çalıyorsa sıraya ekler ve sıra numarasını döner.
        """
        self.text_channel = text_channel
        self.cancel_disconnect_timer()

        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused() or self.current_song):
            self.queue.append(song)
            await self.update_panel_message()
            return len(self.queue)
        else:
            self.queue.append(song)
            await self.process_next()
            return None

    async def process_next(self):
        """Kuyruktaki sıradaki parçayı oynatır."""
        async with self.lock:
            # Döngü mantığı kontrolü
            if self.current_song and not self.skip_loop_once:
                if self.loop_mode == "song":
                    # Tek şarkı döngüsü: mevcut şarkıyı tekrar başa koy
                    self.queue.insert(0, self.current_song)
                elif self.loop_mode == "queue":
                    # Kuyruk döngüsü: mevcut şarkıyı kuyruğun sonuna ekle
                    self.queue.append(self.current_song)

            self.skip_loop_once = False

            if not self.queue:
                self.current_song = None
                self.is_paused = False
                await self.show_queue_finished_panel()
                self.start_disconnect_timer()
                return

            self.current_song = self.queue.pop(0)

            try:
                source = await YTDLSource.create_source(self.current_song, volume=self.volume)
                self.current_source = source
            except Exception as e:
                print(f"[Player Error] Şarkı kaynağı oluşturulamadı: {e}")
                if self.text_channel:
                    err_embed = discord.Embed(
                        title="❌ Şarkı Oynatılamadı",
                        description=f"**{self.current_song.title}** parçası yüklenirken bir sorun oluştu, sıradaki parçaya geçiliyor.",
                        color=config.COLOR_ERROR
                    )
                    await self.text_channel.send(embed=err_embed)
                # Hata durumunda sıradakine geç
                return await self.process_next()

            def after_playing(error):
                if error:
                    print(f"[Playback Error] {error}")
                # Asenkron sonraki şarkı çağrısı
                coro = self.process_next()
                fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
                try:
                    fut.result()
                except Exception as exc:
                    print(f"[After Callback Error] {exc}")

            if self.voice_client and self.voice_client.is_connected():
                self.voice_client.play(source, after=after_playing)
                self.is_paused = False
                await self.send_or_update_panel()
            else:
                self.current_song = None

    def skip(self):
        """Mevcut şarkıyı atlar."""
        if self.loop_mode == "song":
            self.skip_loop_once = True
            
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()

    async def stop(self):
        """Müziği tamamen durdurur, kuyruğu temizler ve kanaldan ayrılır."""
        self.queue.clear()
        self.current_song = None
        self.is_paused = False
        self.cancel_disconnect_timer()

        if self.panel_message and self.panel_view:
            for item in self.panel_view.children:
                item.disabled = True
            try:
                await self.panel_message.edit(view=self.panel_view)
            except Exception:
                pass

        if self.voice_client:
            if self.voice_client.is_playing() or self.voice_client.is_paused():
                self.voice_client.stop()
            if self.voice_client.is_connected():
                await self.voice_client.disconnect()

    def build_panel_embed(self) -> discord.Embed:
        """Şarkı kontrol paneli için güncel embed oluşturur."""
        if not self.current_song:
            return discord.Embed(
                title="🎵 Müzik Paneli",
                description="Şu anda çalan şarkı yok.",
                color=config.COLOR_DEFAULT
            )

        title_text = "⏸️ Duraklatıldı" if self.is_paused else "🎶 Şu Anda Çalıyor"
        embed_color = config.COLOR_PAUSED if self.is_paused else config.COLOR_PLAYING

        embed = discord.Embed(
            title=title_text,
            description=f"[{self.current_song.title}]({self.current_song.webpage_url})",
            color=embed_color
        )

        embed.add_field(
            name="⏱️ Süre / Boyut",
            value=f"`{self.current_song.formatted_duration}`",
            inline=True
        )
        embed.add_field(
            name="👤 İsteyen",
            value=self.current_song.requester.mention,
            inline=True
        )

        loop_labels = {
            "off": "❌ Kapalı",
            "song": "🔂 Tek Şarkı",
            "queue": "🔁 Tüm Liste"
        }
        embed.add_field(
            name="🔄 Döngü Modu",
            value=f"`{loop_labels.get(self.loop_mode, 'Kapalı')}`",
            inline=True
        )

        embed.add_field(
            name="📜 Sıradaki Parça",
            value=f"`{len(self.queue)} şarkı`",
            inline=True
        )
        embed.add_field(
            name="🔊 Ses Seviyesi",
            value=f"`%{int(self.volume * 100)}`",
            inline=True
        )
        embed.add_field(
            name="📻 Kanal",
            value=f"<#{self.voice_client.channel.id}>" if self.voice_client and self.voice_client.channel else "`Bilinmiyor`",
            inline=True
        )

        if self.current_song.thumbnail:
            embed.set_thumbnail(url=self.current_song.thumbnail)

        embed.set_footer(
            text=f"Piyade RP Müzik Sistemi • Yetkili Rol: @| Müzik Açma İzni"
        )
        return embed

    async def send_or_update_panel(self):
        """Panel mesajını kanala gönderir veya günceller."""
        if not self.text_channel:
            return

        embed = self.build_panel_embed()
        self.panel_view = MusicControlView(self)

        # Eski paneli güncellemeye çalış, olmazsa yeni mesaj yolla
        if self.panel_message:
            try:
                await self.panel_message.edit(embed=embed, view=self.panel_view)
                return
            except discord.NotFound:
                self.panel_message = None
            except Exception:
                pass

        try:
            self.panel_message = await self.text_channel.send(embed=embed, view=self.panel_view)
        except Exception as e:
            print(f"[Panel Send Error] {e}")

    async def update_panel_message(self):
        """Mevcut panel mesajının içeriğini yeniler."""
        if self.panel_message:
            embed = self.build_panel_embed()
            try:
                await self.panel_message.edit(embed=embed, view=self.panel_view)
            except Exception:
                pass

    async def show_queue_finished_panel(self):
        """Sıra bittiğinde paneli sonlandırılmış olarak gösterir."""
        if self.panel_message:
            embed = discord.Embed(
                title="✅ Çalma Sırası Tamamlandı",
                description="Sıradaki tüm parçalar çalındı. Yeni şarkı eklemek için `/oynat` veya `/dosya-oynat` komutunu kullanabilirsiniz.",
                color=config.COLOR_DEFAULT
            )
            embed.set_footer(text="3 dakika içinde yeni şarkı gelmezse bot kanaldan ayrılacaktır.")
            if self.panel_view:
                for item in self.panel_view.children:
                    item.disabled = True
            try:
                await self.panel_message.edit(embed=embed, view=self.panel_view)
            except Exception:
                pass

    def create_queue_embed(self) -> discord.Embed:
        """Kullanıcıya gösterilecek kuyruk embed'ini oluşturur."""
        embed = discord.Embed(
            title="📜 Güncel Müzik Sırası",
            color=config.COLOR_QUEUE
        )

        if self.current_song:
            embed.add_field(
                name="▶️ Şu Anda Çalan",
                value=f"**[{self.current_song.title}]({self.current_song.webpage_url})** (`{self.current_song.formatted_duration}`) - {self.current_song.requester.mention}",
                inline=False
            )

        if not self.queue:
            embed.description = "Sırada başka şarkı bulunmuyor."
        else:
            lines = []
            for i, song in enumerate(self.queue[:10], start=1):
                lines.append(f"`{i}.` **[{song.title}]({song.webpage_url})** (`{song.formatted_duration}`) - {song.requester.mention}")
            
            if len(self.queue) > 10:
                lines.append(f"\n*...ve {len(self.queue) - 10} şarkı daha*")

            embed.description = "\n".join(lines)

        embed.set_footer(text=f"Toplam Sıradaki Şarkı: {len(self.queue)} | Döngü: {self.loop_mode.capitalize()}")
        return embed
