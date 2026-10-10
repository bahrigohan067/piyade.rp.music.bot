import discord
from discord import ui
import random
import config
from utils.checks import user_has_music_role

class MusicControlView(ui.View):
    """
    Şarkı kontrol paneli için interaktif Discord butonları.
    Sadece yetkili role sahip ve botla aynı kanalda olan üyeler tarafından tıklanabilir.
    """
    def __init__(self, player):
        super().__init__(timeout=None)  # Panel aktif kaldığı sürece butonlar çalışır
        self.player = player

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # 1. Rol Yetkisi Kontrolü
        if not user_has_music_role(interaction.user):
            await interaction.response.send_message(
                f"⛔ **Yetkiniz Yok!**\nBu kontrol panelini yalnızca <@&{config.MUSIC_ROLE_ID}> rolüne sahip üyeler kullanabilir.",
                ephemeral=True
            )
            return False

        # 2. Ses Kanalı Kontrolü (Bot bir kanalda aktifken sadece o kanaldakiler yönetebilir)
        bot_voice = interaction.guild.voice_client if interaction.guild else None
        user_voice = interaction.user.voice.channel if interaction.user.voice else None

        if not user_voice:
            await interaction.response.send_message(
                "⚠️ Bu işlemi yapabilmek için bir ses kanalında olmalısınız!",
                ephemeral=True
            )
            return False

        if bot_voice and bot_voice.channel and bot_voice.channel.id != user_voice.id:
            await interaction.response.send_message(
                f"🔒 **Erişim Engellendi!**\nBot şu anda <#{bot_voice.channel.id}> kanalında aktif. "
                "Yalnızca botla aynı ses kanalında olanlar kontrol panelini kullanabilir.",
                ephemeral=True
            )
            return False

        return True

    @ui.button(label="Önceki", style=discord.ButtonStyle.secondary, emoji=config.EMOJI_PREVIOUS, row=0)
    async def previous_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.player.voice_client or not self.player.voice_client.is_connected():
            return await interaction.response.send_message("❌ Bot şu anda bağlı değil.", ephemeral=True)

        success, msg = await self.player.previous()
        if success:
            await interaction.response.send_message(f"⏮️ {msg}", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ {msg}", ephemeral=True)

    @ui.button(label="Duraklat / Devam", style=discord.ButtonStyle.primary, emoji=config.EMOJI_PAUSE, row=0)
    async def pause_resume_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.player.voice_client or not self.player.voice_client.is_connected():
            return await interaction.response.send_message("❌ Bot şu anda bağlı değil.", ephemeral=True)

        if self.player.voice_client.is_playing():
            await self.player.pause()
            button.emoji = config.EMOJI_PLAY
            button.label = "Devam Et"
            await interaction.response.send_message("⏸️ Müzik duraklatıldı.", ephemeral=True)
        elif self.player.voice_client.is_paused():
            await self.player.resume()
            button.emoji = config.EMOJI_PAUSE
            button.label = "Duraklat"
            await interaction.response.send_message("▶️ Müzik devam ettiriliyor.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Şu anda çalan bir parça bulunmuyor.", ephemeral=True)

    @ui.button(label="Atla", style=discord.ButtonStyle.secondary, emoji=config.EMOJI_SKIP, row=0)
    async def skip_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.player.voice_client or not self.player.voice_client.is_connected():
            return await interaction.response.send_message("❌ Bot bağlı değil.", ephemeral=True)

        current_title = self.player.current_song.title if self.player.current_song else "Bilinmeyen"
        await interaction.response.send_message(f"⏭️ **{current_title}** parçası atlandı.", ephemeral=True)
        self.player.skip()

    @ui.button(label="Döngü", style=discord.ButtonStyle.secondary, emoji=config.EMOJI_LOOP, row=0)
    async def loop_button(self, interaction: discord.Interaction, button: ui.Button):
        # Döngü modu geçişi: off -> song -> queue -> off
        if self.player.loop_mode == "off":
            self.player.loop_mode = "song"
            status = "🔂 Tek Şarkı Döngüsü"
        elif self.player.loop_mode == "song":
            self.player.loop_mode = "queue"
            status = "🔁 Tüm Sıra Döngüsü"
        else:
            self.player.loop_mode = "off"
            status = "➡️ Döngü Kapalı"

        await self.player.update_panel_message()
        await interaction.response.send_message(f"🔄 Döngü Modu: **{status}** olarak ayarlandı.", ephemeral=True)

    @ui.button(label="Durdur & Ayrıl", style=discord.ButtonStyle.danger, emoji=config.EMOJI_STOP, row=0)
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("⏹️ Oynatma sonlandırıldı ve bot kanaldan ayrıldı.", ephemeral=True)
        await self.player.stop()

    @ui.button(label="Kuyruk", style=discord.ButtonStyle.secondary, emoji=config.EMOJI_QUEUE, row=1)
    async def queue_button(self, interaction: discord.Interaction, button: ui.Button):
        embed = self.player.create_queue_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="Geçmiş", style=discord.ButtonStyle.secondary, emoji=config.EMOJI_HISTORY, row=1)
    async def history_button(self, interaction: discord.Interaction, button: ui.Button):
        embed = self.player.create_history_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="Karıştır", style=discord.ButtonStyle.secondary, emoji=config.EMOJI_SHUFFLE, row=1)
    async def shuffle_button(self, interaction: discord.Interaction, button: ui.Button):
        if len(self.player.queue) < 2:
            return await interaction.response.send_message("⚠️ Sırayı karıştırmak için en az 2 şarkı olmalı!", ephemeral=True)

        random.shuffle(self.player.queue)
        await self.player.update_panel_message()
        await interaction.response.send_message("🔀 Çalma sırası başarıyla karıştırıldı!", ephemeral=True)

    @ui.button(label="Ses -", style=discord.ButtonStyle.secondary, emoji=config.EMOJI_VOL_DOWN, row=1)
    async def vol_down_button(self, interaction: discord.Interaction, button: ui.Button):
        new_vol = max(0.1, round(self.player.volume - 0.1, 1))
        self.player.set_volume(new_vol)
        await self.player.update_panel_message()
        await interaction.response.send_message(f"🔉 Ses düzeyi: **%{int(new_vol * 100)}**", ephemeral=True)

    @ui.button(label="Ses +", style=discord.ButtonStyle.secondary, emoji=config.EMOJI_VOL_UP, row=1)
    async def vol_up_button(self, interaction: discord.Interaction, button: ui.Button):
        new_vol = min(1.0, round(self.player.volume + 0.1, 1))
        self.player.set_volume(new_vol)
        await self.player.update_panel_message()
        await interaction.response.send_message(f"🔊 Ses düzeyi: **%{int(new_vol * 100)}**", ephemeral=True)
