import discord
from discord import app_commands
from discord.ext import commands
from typing import Dict, Optional
import config
from core.player import GuildMusicPlayer
from core.ytdl import YTDLSource, is_playlist_url
from utils.checks import user_has_music_role, check_voice_state, get_required_role_mention

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
                description=f"Bu komutu kullanabilmek için {get_required_role_mention(interaction.guild)} rolüne sahip olmalısınız.",
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

        # 4. YouTube'dan şarkıyı veya çalma listesini ara / getir
        if is_playlist_url(sarki):
            songs, error_detail, playlist_title = await YTDLSource.from_playlist(sarki, interaction.user)
            if not songs:
                if error_detail == "BOT_CHECK":
                    err_embed = discord.Embed(
                        title="⚠️ YouTube Bot Koruması (Railway IP Engeli)",
                        description=(
                            "YouTube, çalma listesini çekerken veri merkezi IP adresini engelledi.\n\n"
                            "💡 **Çözüm:** Railway Variables sekmesinde `YTDLP_COOKIES` değişkenine güncel YouTube cookies ekleyin."
                        ),
                        color=config.COLOR_ERROR
                    )
                else:
                    err_embed = discord.Embed(
                        title="❌ Çalma Listesi Yüklenemedi",
                        description=f"Çalma listesi bulunamadı veya liste gizli olabilir.\n`{error_detail or 'Bilinmeyen hata'}`",
                        color=config.COLOR_ERROR
                    )
                return await interaction.followup.send(embed=err_embed)

            player = self.get_player(interaction.guild)
            started_now, queue_pos = await player.add_playlist_to_queue(songs, interaction.channel)

            p_title = playlist_title or "YouTube Çalma Listesi"
            first_song = songs[0]

            if started_now:
                embed = discord.Embed(
                    title=f"{config.EMOJI_CD} Çalma Listesi Başlatıldı!",
                    description=(
                        f"📂 **[{p_title}]({sarki})**\n\n"
                        f"▶️ **Şu Anda Çalıyor:** [{first_song.song_name}]({first_song.webpage_url})\n"
                        f"📊 **Toplam Eklenen:** `{len(songs)}` adet parça\n"
                        f"📻 Kanal: <#{interaction.user.voice.channel.id}>\n"
                        f"✨ Ses kanalı durumu ayarlandı ve kontrol paneli gönderildi!"
                    ),
                    color=config.COLOR_PLAYING
                )
                if first_song.thumbnail:
                    embed.set_thumbnail(url=first_song.thumbnail)
                embed.set_footer(text=f"Sıradaki parça sayısı: {len(player.queue)} | İsteyen: {interaction.user.display_name}")
                await interaction.followup.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="📥 Çalma Listesi Sıraya Eklendi",
                    description=(
                        f"📂 **[{p_title}]({sarki})**\n\n"
                        f"📊 **Eklenen Parça:** `{len(songs)}` adet\n"
                        f"🔢 **Kuyruktaki Başlangıç Sırası:** `#{queue_pos}`"
                    ),
                    color=config.COLOR_QUEUE
                )
                if first_song.thumbnail:
                    embed.set_thumbnail(url=first_song.thumbnail)
                embed.set_footer(text=f"Şu anda toplam sırada {len(player.queue)} parça var. | İsteyen: {interaction.user.display_name}")
                await interaction.followup.send(embed=embed)
            return

        # Tekil şarkı arama
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
                title=f"{config.EMOJI_CD} Şarkı Başlatılıyor...",
                description=f"**[{song.song_name}]({song.webpage_url})** — `{song.artist_name}`\n\n📻 Kanal: <#{interaction.user.voice.channel.id}>\n✨ Ses kanalı durumu ayarlandı ve kontrol paneli gönderildi!",
                color=config.COLOR_PLAYING
            )
            await interaction.followup.send(embed=embed)
        else:
            # Sıraya eklendi
            queued_embed = discord.Embed(
                title="📥 Sıraya Eklendi",
                description=f"**[{song.song_name}]({song.webpage_url})** — `{song.artist_name}`",
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
        name="liste-oynat",
        description="YouTube veya YouTube Music çalma listesini (playlist) topluca sıraya ekler."
    )
    @app_commands.describe(liste_url="YouTube veya YouTube Music çalma listesi bağlantısı")
    async def liste_oynat(self, interaction: discord.Interaction, liste_url: str):
        # 1. Rol Yetkisi Kontrolü
        if not user_has_music_role(interaction.user):
            embed = discord.Embed(
                title="⛔ Yetkisiz İşlem",
                description=f"Bu komutu kullanabilmek için {get_required_role_mention(interaction.guild)} rolüne sahip olmalısınız.",
                color=config.COLOR_ERROR
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # 2. Ses Durumu ve Kanal Kilitleme Kontrolü
        is_ok, err_msg = check_voice_state(interaction)
        if not is_ok:
            return await interaction.response.send_message(err_msg, ephemeral=True)

        await interaction.response.defer(ephemeral=False)

        # 3. Ses kanalına bağlan
        voice_client = await self.ensure_voice_connection(interaction)
        if not voice_client:
            return await interaction.followup.send(
                "❌ Bot şu anda başka bir ses kanalında kilitli durumdadır!",
                ephemeral=True
            )

        songs, error_detail, playlist_title = await YTDLSource.from_playlist(liste_url, interaction.user)
        if not songs:
            if error_detail == "BOT_CHECK":
                err_embed = discord.Embed(
                    title="⚠️ YouTube Bot Koruması (Railway IP Engeli)",
                    description=(
                        "YouTube, çalma listesini çekerken veri merkezi IP adresini engelledi.\n\n"
                        "💡 **Çözüm:** Railway Variables sekmesinde `YTDLP_COOKIES` değişkenine güncel YouTube cookies ekleyin."
                    ),
                    color=config.COLOR_ERROR
                )
            else:
                err_embed = discord.Embed(
                    title="❌ Çalma Listesi Yüklenemedi",
                    description=f"Çalma listesi bulunamadı veya liste gizli olabilir.\n`{error_detail or 'Bilinmeyen hata'}`",
                    color=config.COLOR_ERROR
                )
            return await interaction.followup.send(embed=err_embed)

        player = self.get_player(interaction.guild)
        started_now, queue_pos = await player.add_playlist_to_queue(songs, interaction.channel)

        p_title = playlist_title or "YouTube Çalma Listesi"
        first_song = songs[0]

        if started_now:
            embed = discord.Embed(
                title=f"{config.EMOJI_CD} Çalma Listesi Başlatıldı!",
                description=(
                    f"📂 **[{p_title}]({liste_url})**\n\n"
                    f"▶️ **Şu Anda Çalıyor:** [{first_song.song_name}]({first_song.webpage_url})\n"
                    f"📊 **Toplam Eklenen:** `{len(songs)}` adet parça\n"
                    f"📻 Kanal: <#{interaction.user.voice.channel.id}>\n"
                    f"✨ Ses kanalı durumu ayarlandı ve kontrol paneli gönderildi!"
                ),
                color=config.COLOR_PLAYING
            )
            if first_song.thumbnail:
                embed.set_thumbnail(url=first_song.thumbnail)
            embed.set_footer(text=f"Sıradaki parça sayısı: {len(player.queue)} | İsteyen: {interaction.user.display_name}")
            await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(
                title="📥 Çalma Listesi Sıraya Eklendi",
                description=(
                    f"📂 **[{p_title}]({liste_url})**\n\n"
                    f"📊 **Eklenen Parça:** `{len(songs)}` adet\n"
                    f"🔢 **Kuyruktaki Başlangıç Sırası:** `#{queue_pos}`"
                ),
                color=config.COLOR_QUEUE
            )
            if first_song.thumbnail:
                embed.set_thumbnail(url=first_song.thumbnail)
            embed.set_footer(text=f"Şu anda toplam sırada {len(player.queue)} parça var. | İsteyen: {interaction.user.display_name}")
            await interaction.followup.send(embed=embed)

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
                description=f"Bu komutu kullanabilmek için {get_required_role_mention(interaction.guild)} rolüne sahip olmalısınız.",
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
                title=f"{config.EMOJI_CD} Ses Dosyası Oynatılıyor...",
                description=f"**{song.song_name}**\n\n📻 Kanal: <#{interaction.user.voice.channel.id}>\n✨ Ses kanalı durumu ayarlandı!",
                color=config.COLOR_PLAYING
            )
            await interaction.followup.send(embed=embed)
        else:
            queued_embed = discord.Embed(
                title="📁 Ses Dosyası Sıraya Eklendi",
                description=f"**{song.song_name}**",
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
                f"⛔ Bu komutu kullanabilmek için {get_required_role_mention(interaction.guild)} rolüne sahip olmalısınız.",
                ephemeral=True
            )

        player = self.get_player(interaction.guild)
        embed = player.create_queue_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="gecmis",
        description="Son çalınan şarkıların geçmişini listeler."
    )
    async def gecmis(self, interaction: discord.Interaction):
        if not user_has_music_role(interaction.user):
            return await interaction.response.send_message(
                f"⛔ Bu komutu kullanabilmek için {get_required_role_mention(interaction.guild)} rolüne sahip olmalısınız.",
                ephemeral=True
            )

        player = self.get_player(interaction.guild)
        embed = player.create_history_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="onceki",
        description="Geçmişte çalınan bir önceki şarkıya geri döner."
    )
    async def onceki(self, interaction: discord.Interaction):
        if not user_has_music_role(interaction.user):
            return await interaction.response.send_message(
                f"⛔ Bu komutu kullanabilmek için {get_required_role_mention(interaction.guild)} rolüne sahip olmalısınız.",
                ephemeral=True
            )

        is_ok, err_msg = check_voice_state(interaction)
        if not is_ok:
            return await interaction.response.send_message(err_msg, ephemeral=True)

        player = self.get_player(interaction.guild)
        success, msg = await player.previous()
        if success:
            await interaction.response.send_message(f"⏮️ {msg}", ephemeral=False)
        else:
            await interaction.response.send_message(f"⚠️ {msg}", ephemeral=True)

    @app_commands.command(
        name="atla",
        description="Şu anda çalan şarkıyı atlayarak sıradakine geçer."
    )
    async def atla(self, interaction: discord.Interaction):
        if not user_has_music_role(interaction.user):
            return await interaction.response.send_message(
                f"⛔ Bu komutu kullanabilmek için {get_required_role_mention(interaction.guild)} rolüne sahip olmalısınız.",
                ephemeral=True
            )

        is_ok, err_msg = check_voice_state(interaction)
        if not is_ok:
            return await interaction.response.send_message(err_msg, ephemeral=True)

        player = self.get_player(interaction.guild)
        if not player.current_song:
            return await interaction.response.send_message("⚠️ Şu anda çalan bir parça bulunmuyor.", ephemeral=True)

        title = player.current_song.song_name
        player.skip()
        await interaction.response.send_message(f"⏭️ **{title}** parçası atlandı.", ephemeral=False)

    @app_commands.command(
        name="durdur",
        description="Müziği durdurur, kuyruğu temizler ve bot ses kanalından ayrılır."
    )
    async def durdur(self, interaction: discord.Interaction):
        if not user_has_music_role(interaction.user):
            return await interaction.response.send_message(
                f"⛔ Bu komutu kullanabilmek için {get_required_role_mention(interaction.guild)} rolüne sahip olmalısınız.",
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
                f"⛔ Bu komutu kullanabilmek için {get_required_role_mention(interaction.guild)} rolüne sahip olmalısınız.",
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
                f"⛔ Bu komutu kullanabilmek için {get_required_role_mention(interaction.guild)} rolüne sahip olmalısınız.",
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
                f"⛔ Bu komutu kullanabilmek için {get_required_role_mention(interaction.guild)} rolüne sahip olmalısınız.",
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
                f"⛔ Bu komutu kullanabilmek için {get_required_role_mention(interaction.guild)} rolüne sahip olmalısınız.",
                ephemeral=True
            )

        is_ok, err_msg = check_voice_state(interaction)
        if not is_ok:
            return await interaction.response.send_message(err_msg, ephemeral=True)

        player = self.get_player(interaction.guild)
        player.set_volume(seviye / 100.0)
        await player.update_panel_message()
        await interaction.response.send_message(f"🔊 Ses düzeyi **%{seviye}** olarak ayarlandı.", ephemeral=False)

    # --- KLASİK METİN (PREFIX) KOMUTLARI (!oynat, !atla vb.) ---
    # Discord slash komutlarının görünmediği veya önbelleğe takıldığı durumlarda
    # kullanıcıların doğrudan metin kanalından müzik açabilmesini sağlar.

    @commands.command(name="oynat", aliases=["play", "p"])
    async def prefix_oynat(self, ctx: commands.Context, *, sarki: str = None):
        """Prefix ile şarkı çalma: !oynat <şarkı adı veya link>"""
        if not sarki:
            return await ctx.reply("❌ Lütfen bir şarkı adı veya YouTube linki girin: `!oynat <şarkı>`")

        # 1. Rol Yetkisi Kontrolü
        if not user_has_music_role(ctx.author):
            role_text = get_required_role_mention(ctx.guild)
            return await ctx.reply(f"⛔ **Yetkiniz Bulunmuyor!** Bu komutu kullanabilmek için {role_text} rolüne sahip olmalısınız.")

        # 2. Ses Durumu Kontrolü
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.reply("⚠️ Bu komutu kullanabilmek için bir **ses kanalında** bulunmalısınız!")

        bot_voice = ctx.guild.voice_client
        if bot_voice and bot_voice.channel and bot_voice.channel.id != ctx.author.voice.channel.id:
            return await ctx.reply(f"🔒 Bot şu anda <#{bot_voice.channel.id}> kanalında hizmet veriyor!")

        # 3. Ses kanalına bağlan
        if bot_voice is None:
            voice_client = await ctx.author.voice.channel.connect(self_deaf=True)
        else:
            voice_client = bot_voice

        # 4. Şarkıyı yükle ve kuyruğa ekle
        msg = await ctx.reply("🔍 Şarkı aranıyor, lütfen bekleyin...")
        if is_playlist_url(sarki):
            songs, error_detail, playlist_title = await YTDLSource.from_playlist(sarki, ctx.author)
            if not songs:
                return await msg.edit(content=f"❌ Çalma listesi yüklenemedi: `{error_detail or 'Bilinmeyen hata'}`")
            player = self.get_player(ctx.guild)
            started_now, queue_pos = await player.add_playlist_to_queue(songs, ctx.channel)
            p_title = playlist_title or "YouTube Çalma Listesi"
            if started_now:
                await msg.edit(content=f"🎶 **{p_title}** başlatıldı! ({len(songs)} parça)")
            else:
                await msg.edit(content=f"📜 **{p_title}** sıraya eklendi! ({len(songs)} parça, Sıra: #{queue_pos})")
        else:
            song, error_detail = await YTDLSource.from_query(sarki, ctx.author)
            if not song:
                return await msg.edit(content=f"❌ Şarkı bulunamadı veya yüklenemedi: `{error_detail or 'Bilinmeyen hata'}`")
            player = self.get_player(ctx.guild)
            queue_pos = await player.add_to_queue(song, ctx.channel)
            if queue_pos is None:
                await msg.edit(content=f"▶️ **{song.title}** çalınıyor...")
            else:
                await msg.edit(content=f"📜 **{song.title}** sıraya eklendi! (Sıra: #{queue_pos})")

    @commands.command(name="atla", aliases=["skip", "s"])
    async def prefix_atla(self, ctx: commands.Context):
        if not user_has_music_role(ctx.author):
            return await ctx.reply("⛔ Bu komutu kullanmaya yetkiniz yok!")
        player = self.get_player(ctx.guild)
        if not player.current_song:
            return await ctx.reply("⚠️ Şu anda çalan bir şarkı bulunmuyor.")
        title = player.current_song.title
        player.skip()
        await ctx.reply(f"⏭️ **{title}** parçası atlandı.")

    @commands.command(name="durdur", aliases=["stop"])
    async def prefix_durdur(self, ctx: commands.Context):
        if not user_has_music_role(ctx.author):
            return await ctx.reply("⛔ Bu komutu kullanmaya yetkiniz yok!")
        player = self.get_player(ctx.guild)
        await player.stop()
        await ctx.reply("⏹️ Müzik durduruldu ve kanaldan ayrılındı.")

    @commands.command(name="duraklat", aliases=["pause"])
    async def prefix_duraklat(self, ctx: commands.Context):
        if not user_has_music_role(ctx.author):
            return await ctx.reply("⛔ Bu komutu kullanmaya yetkiniz yok!")
        player = self.get_player(ctx.guild)
        await player.pause()
        await ctx.reply("⏸️ Müzik duraklatıldı.")

    @commands.command(name="devam", aliases=["resume"])
    async def prefix_devam(self, ctx: commands.Context):
        if not user_has_music_role(ctx.author):
            return await ctx.reply("⛔ Bu komutu kullanmaya yetkiniz yok!")
        player = self.get_player(ctx.guild)
        await player.resume()
        await ctx.reply("▶️ Müzik devam ettiriliyor.")

    @commands.command(name="kuyruk", aliases=["queue", "q"])
    async def prefix_kuyruk(self, ctx: commands.Context):
        player = self.get_player(ctx.guild)
        if not player.queue:
            return await ctx.reply("📜 Şu anda kuyrukta bekleyen şarkı yok.")
        lines = [f"`{idx}.` **{s.title}** ({s.formatted_duration})" for idx, s in enumerate(player.queue[:10], 1)]
        await ctx.reply("📜 **Sıradaki Parçalar:**\n" + "\n".join(lines))

    @commands.command(name="panel")
    async def prefix_panel(self, ctx: commands.Context):
        player = self.get_player(ctx.guild)
        if not player.current_song:
            return await ctx.reply("⚠️ Şu anda çalan aktif bir şarkı bulunmuyor.")
        player.text_channel = ctx.channel
        await player.send_or_update_panel()
        await ctx.reply("🎛️ Kontrol paneli gönderildi.")

async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))
