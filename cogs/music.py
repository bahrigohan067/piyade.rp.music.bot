import discord
from discord import app_commands
from discord.ext import commands
from typing import Dict, Optional
import config
from core.player import GuildMusicPlayer
from core.ytdl import YTDLSource
from utils.checks import user_has_music_role, check_voice_state

# İzin verilen ses dosyası uzantıları
ALLOWED_AUDIO_EXTENSIONS = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.opus', '.webm')

class MusicCog(commands.Cog, name="Müzik"):
    """Piyade RP Profesyonel Müzik Sistemi"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players: Dict[int, GuildMusicPlayer] = {}

    def get_player(self, guild: discord.Guild) -> GuildMusicPlayer:
        """Sunucuya ait müzik çaları getirir veya oluşturur."""
        if guild.id not in self.players:
            self.players[guild.id] = GuildMusicPlayer(self.bot, guild)
        return self.players[guild.id]

    async def ensure_voice_connection(self, interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
        """Kullanıcının kanalına bağlanır veya mevcut bağlantıyı döner."""
        user = interaction.user
        voice_channel = user.voice.channel
        voice_client = interaction.guild.voice_client

        if voice_client is None:
            return await voice_channel.connect(self_deaf=True)
        elif voice_client.channel.id != voice_channel.id:
            # check_voice_state zaten bunu filtreliyor ancak ek güvenlik
            return None
        return voice_client

    # --- SLASH KOMUTLARI ---

    @app_commands.command(
        name="oynat",
        description="YouTube üzerinden bir şarkı ismi aratın veya YouTube linki girerek çalın."
    )
    @app_commands.describe(sarki="Şarkı adı veya YouTube bağlantısı (URL)")
    async def oynat(self, interaction: discord.Interaction, sarki: str):
        # 1. Rol Yetkisi Kontrolü
        if not user_has_music_role(interaction.user):
            embed = discord.Embed(
                title="⛔ Yetkiniz Bulunmuyor!",
                description=f"Bu komutu kullanabilmek için <@&{config.MUSIC_ROLE_ID}> rolüne sahip olmalısınız.",
                color=config.COLOR_ERROR
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # 2. Ses Durumu ve Kanal Kilitleme Kontrolü
        is_ok, err_msg = check_voice_state(interaction)
        if not is_ok:
            return await interaction.response.send_message(err_msg, ephemeral=True)

        # İşlem uzun sürebileceği için defer
        await interaction.response.defer(ephemeral=False)

        # 3. Ses kanalına bağlan
        voice_client = await self.ensure_voice_connection(interaction)
        if not voice_client:
            return await interaction.followup.send(
                f"❌ Bot şu anda başka bir ses kanalında kilitli durumdadır!",
                ephemeral=True
            )

        # 4. YouTube'dan şarkıyı ara / getir
        song, error_detail = await YTDLSource.from_query(sarki, interaction.user)
        if not song:
            if error_detail == "BOT_CHECK":
                err_embed = discord.Embed(
                    title="⚠️ YouTube Bot Koruması (Railway IP Engeli)",
                    description=(
                        "YouTube, Railway veri merkezi IP adresini bot olarak algıladı ve erişimi engelledi.\n\n"
                        "💡 **Çözüm Seçenekleri:**\n"
                        "1. **Çerez Ekleme:** Tarayıcınızdan aldığınız YouTube `cookies.txt` içeriğini Railway Variables sekmesinde `YTDLP_COOKIES` değişkenine yapıştırın.\n"
                        "2. **Dosya Yükleme:** Şarkıyı `/dosya-oynat` komutunu kullanarak doğrudan bilgisayarınızdan/telefonunuzdan yükleyip kesintisiz dinleyebilirsiniz."
                    ),
                    color=config.COLOR_ERROR
                )
            else:
                err_embed = discord.Embed(
                    title="❌ Şarkı Bulunamadı",
                    description=f"**{sarki}** araması için YouTube'da sonuç bulunamadı veya video kısıtlı.",
                    color=config.COLOR_ERROR
                )
            return await interaction.followup.send(embed=err_embed)

        player = self.get_player(interaction.guild)
        queue_pos = await player.add_to_queue(song, interaction.channel)

        if queue_pos is None:
            # Hemen çalmaya başladı, panel gönderildi
            embed = discord.Embed(
                title="🎶 Şarkı Başlatılıyor...",
                description=f"**[{song.title}]({song.webpage_url})**\n\n📻 Kanal: <#{interaction.user.voice.channel.id}>\n🕹️ Şarkıyı aşağıdaki kontrol panelinden yönetebilirsiniz.",
                color=config.COLOR_PLAYING
            )
            await interaction.followup.send(embed=embed)
        else:
            # Sıraya eklendi
            queued_embed = discord.Embed(
                title="📥 Sıraya Eklendi",
                description=f"**[{song.title}]({song.webpage_url})**",
                color=config.COLOR_QUEUE
            )
            queued_embed.add_field(name="⏱️ Süre", value=f"`{song.formatted_duration}`", inline=True)
            queued_embed.add_field(name="🔢 Sıradaki Yeri", value=f"`#{queue_pos}`", inline=True)
            queued_embed.add_field(name="👤 İsteyen", value=interaction.user.mention, inline=True)
            if song.thumbnail:
                queued_embed.set_thumbnail(url=song.thumbnail)
            queued_embed.set_footer(text=f"Şu anda sırada {len(player.queue)} parça var.")
            await interaction.followup.send(embed=queued_embed)

    @app_commands.command(
        name="dosya-oynat",
        description="Cihazınızdan bir ses dosyası (MP3, WAV, OGG vb.) yükleyin ve çalın."
    )
    @app_commands.describe(dosya="Yüklenecek ses dosyası")
    async def dosya_oynat(self, interaction: discord.Interaction, dosya: discord.Attachment):
        # 1. Rol Yetkisi Kontrolü
        if not user_has_music_role(interaction.user):
            embed = discord.Embed(
                title="⛔ Yetkiniz Bulunmuyor!",
                description=f"Bu komutu kullanabilmek için <@&{config.MUSIC_ROLE_ID}> rolüne sahip olmalısınız.",
                color=config.COLOR_ERROR
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # 2. Dosya Uzantısı Kontrolü
        if not dosya.filename.lower().endswith(ALLOWED_AUDIO_EXTENSIONS):
            valid_formats = ", ".join(ext.upper().replace('.', '') for ext in ALLOWED_AUDIO_EXTENSIONS)
            embed = discord.Embed(
                title="⚠️ Desteklenmeyen Dosya Türü",
                description=f"Lütfen geçerli bir ses dosyası yükleyin.\n**Desteklenen formatlar:** `{valid_formats}`",
                color=config.COLOR_ERROR
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # 3. Ses Durumu ve Kanal Kilidi
        is_ok, err_msg = check_voice_state(interaction)
        if not is_ok:
            return await interaction.response.send_message(err_msg, ephemeral=True)

        await interaction.response.defer(ephemeral=False)

        voice_client = await self.ensure_voice_connection(interaction)
        if not voice_client:
            return await interaction.followup.send(
                f"❌ Bot şu anda başka bir ses kanalında kilitli durumdadır!",
                ephemeral=True
            )

        song = YTDLSource.from_attachment(dosya, interaction.user)
        player = self.get_player(interaction.guild)
        queue_pos = await player.add_to_queue(song, interaction.channel)

        if queue_pos is None:
            embed = discord.Embed(
                title="📁 Ses Dosyası Oynatılıyor...",
                description=f"**{song.title}**\n\n📻 Kanal: <#{interaction.user.voice.channel.id}>",
                color=config.COLOR_PLAYING
            )
            await interaction.followup.send(embed=embed)
        else:
            queued_embed = discord.Embed(
                title="📁 Ses Dosyası Sıraya Eklendi",
                description=f"**{song.title}**",
                color=config.COLOR_QUEUE
            )
            queued_embed.add_field(name="📦 Dosya Boyutu", value=f"`{song.formatted_duration}`", inline=True)
            queued_embed.add_field(name="🔢 Sıradaki Yeri", value=f"`#{queue_pos}`", inline=True)
            queued_embed.add_field(name="👤 İsteyen", value=interaction.user.mention, inline=True)
            await interaction.followup.send(embed=queued_embed)

    @app_commands.command(
        name="kuyruk",
        description="Mevcut müzik çalma sırasını listeler."
    )
    async def kuyruk(self, interaction: discord.Interaction):
        if not user_has_music_role(interaction.user):
            return await interaction.response.send_message(
                f"⛔ Bu komutu kullanabilmek için <@&{config.MUSIC_ROLE_ID}> rolüne sahip olmalısınız.",
                ephemeral=True
            )

        player = self.get_player(interaction.guild)
        embed = player.create_queue_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="atla",
        description="Şu anda çalan şarkıyı atlayarak sıradakine geçer."
    )
    async def atla(self, interaction: discord.Interaction):
        if not user_has_music_role(interaction.user):
            return await interaction.response.send_message(
                f"⛔ Bu komutu kullanabilmek için <@&{config.MUSIC_ROLE_ID}> rolüne sahip olmalısınız.",
                ephemeral=True
            )

        is_ok, err_msg = check_voice_state(interaction)
        if not is_ok:
            return await interaction.response.send_message(err_msg, ephemeral=True)

        player = self.get_player(interaction.guild)
        if not player.current_song:
            return await interaction.response.send_message("⚠️ Şu anda çalan bir parça bulunmuyor.", ephemeral=True)

        title = player.current_song.title
        player.skip()
        await interaction.response.send_message(f"⏭️ **{title}** parçası atlandı.", ephemeral=False)

    @app_commands.command(
        name="durdur",
        description="Müziği durdurur, kuyruğu temizler ve bot ses kanalından ayrılır."
    )
    async def durdur(self, interaction: discord.Interaction):
        if not user_has_music_role(interaction.user):
            return await interaction.response.send_message(
                f"⛔ Bu komutu kullanabilmek için <@&{config.MUSIC_ROLE_ID}> rolüne sahip olmalısınız.",
                ephemeral=True
            )

        is_ok, err_msg = check_voice_state(interaction)
        if not is_ok:
            return await interaction.response.send_message(err_msg, ephemeral=True)

        player = self.get_player(interaction.guild)
        await player.stop()
        await interaction.response.send_message("⏹️ Müzik durduruldu, sıra temizlendi ve kanaldan ayrılındı.", ephemeral=False)

    @app_commands.command(
        name="panel",
        description="Aktif şarkı kontrol panelini bu kanala yeniden gönderir."
    )
    async def panel(self, interaction: discord.Interaction):
        if not user_has_music_role(interaction.user):
            return await interaction.response.send_message(
                f"⛔ Bu komutu kullanabilmek için <@&{config.MUSIC_ROLE_ID}> rolüne sahip olmalısınız.",
                ephemeral=True
            )

        is_ok, err_msg = check_voice_state(interaction)
        if not is_ok:
            return await interaction.response.send_message(err_msg, ephemeral=True)

        player = self.get_player(interaction.guild)
        if not player.current_song:
            return await interaction.response.send_message("⚠️ Şu anda çalan aktif bir şarkı bulunmuyor.", ephemeral=True)

        player.text_channel = interaction.channel
        player.panel_message = None  # Yeni mesaj göndermesi için sıfırla
        await player.send_or_update_panel()
        await interaction.response.send_message("✅ Kontrol paneli bu kanala gönderildi.", ephemeral=True)

    @app_commands.command(
        name="karistir",
        description="Kuyruktaki şarkıları rastgele karıştırır."
    )
    async def karistir(self, interaction: discord.Interaction):
        if not user_has_music_role(interaction.user):
            return await interaction.response.send_message(
                f"⛔ Bu komutu kullanabilmek için <@&{config.MUSIC_ROLE_ID}> rolüne sahip olmalısınız.",
                ephemeral=True
            )

        is_ok, err_msg = check_voice_state(interaction)
        if not is_ok:
            return await interaction.response.send_message(err_msg, ephemeral=True)

        player = self.get_player(interaction.guild)
        if len(player.queue) < 2:
            return await interaction.response.send_message("⚠️ Sırayı karıştırmak için en az 2 şarkı olmalıdır.", ephemeral=True)

        import random
        random.shuffle(player.queue)
        await player.update_panel_message()
        await interaction.response.send_message(f"🔀 **{len(player.queue)}** şarkılık çalma sırası karıştırıldı!", ephemeral=False)

    @app_commands.command(
        name="dongu",
        description="Şarkı veya sıra döngü modunu ayarlar."
    )
    @app_commands.choices(mod=[
        app_commands.Choice(name="Kapalı", value="off"),
        app_commands.Choice(name="Tek Şarkı Döngüsü", value="song"),
        app_commands.Choice(name="Tüm Liste (Kuyruk) Döngüsü", value="queue")
    ])
    async def dongu(self, interaction: discord.Interaction, mod: app_commands.Choice[str]):
        if not user_has_music_role(interaction.user):
            return await interaction.response.send_message(
                f"⛔ Bu komutu kullanabilmek için <@&{config.MUSIC_ROLE_ID}> rolüne sahip olmalısınız.",
                ephemeral=True
            )

        is_ok, err_msg = check_voice_state(interaction)
        if not is_ok:
            return await interaction.response.send_message(err_msg, ephemeral=True)

        player = self.get_player(interaction.guild)
        player.loop_mode = mod.value
        await player.update_panel_message()
        await interaction.response.send_message(f"🔄 Döngü modu ayarlandı: **{mod.name}**", ephemeral=False)

    @app_commands.command(
        name="ses",
        description="Müzik ses seviyesini ayarlar (0 - 100)."
    )
    @app_commands.describe(seviye="Ses yüzdesi (1 ile 100 arası)")
    async def ses(self, interaction: discord.Interaction, seviye: app_commands.Range[int, 0, 100]):
        if not user_has_music_role(interaction.user):
            return await interaction.response.send_message(
                f"⛔ Bu komutu kullanabilmek için <@&{config.MUSIC_ROLE_ID}> rolüne sahip olmalısınız.",
                ephemeral=True
            )

        is_ok, err_msg = check_voice_state(interaction)
        if not is_ok:
            return await interaction.response.send_message(err_msg, ephemeral=True)

        player = self.get_player(interaction.guild)
        player.set_volume(seviye / 100.0)
        await player.update_panel_message()
        await interaction.response.send_message(f"🔊 Ses düzeyi **%{seviye}** olarak ayarlandı.", ephemeral=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))
