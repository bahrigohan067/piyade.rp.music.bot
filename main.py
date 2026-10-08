import asyncio
import os
import sys
import logging
import discord
from discord.ext import commands
import config

# Log formatı
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("PiyadeMusicBot")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

class PiyadeMusicBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=config.BOT_PREFIX,
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        """Cog'ları yükler ve slash komutlarını senkronize eder."""
        # Music cog'unu yükle
        try:
            await self.load_extension("cogs.music")
            logger.info("✅ 'cogs.music' başarıyla yüklendi.")
        except Exception as e:
            logger.error(f"❌ 'cogs.music' yüklenirken hata oluştu: {e}")

        # Komutları senkronize et
        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(f"⚡ Komutlar sunucuya (Guild ID: {config.GUILD_ID}) anında senkronize edildi ({len(synced)} komut).")
        else:
            synced = await self.tree.sync()
            logger.info(f"🌍 Komutlar global olarak senkronize edildi ({len(synced)} komut).")

    async def on_ready(self):
        logger.info(f"==================================================")
        logger.info(f"🤖 Bot Aktif: {self.user.name} (ID: {self.user.id})")
        logger.info(f"👑 Müzik Yetki Rolü ID: {config.MUSIC_ROLE_ID}")
        logger.info(f"🌐 Bağlı Sunucu Sayısı: {len(self.guilds)}")
        logger.info(f"==================================================")

        for guild in self.guilds:
            logger.info(f"Sunucu [{guild.name}] (ID: {guild.id}) - {len(guild.emojis)} adet emoji:")
            for e in guild.emojis:
                logger.info(f"  • {e.name} (ID: {e.id}, Animasyonlu: {e.animated}) -> {str(e)}")

        # Durum mesajı
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name="/oynat | Piyade RP Müzik"
        )
        await self.change_presence(status=discord.Status.online, activity=activity)

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Eğer bot ses kanalında yalnız kalırsa otomatik olarak ayrılır."""
        voice_client = member.guild.voice_client
        if not voice_client or not voice_client.channel:
            return

        # Botun olduğu kanalda yalnızca bot kaldıysa
        channel = voice_client.channel
        non_bot_members = [m for m in channel.members if not m.bot]
        if len(non_bot_members) == 0:
            logger.info(f"Kanalda kimse kalmadığı için bot ayrılıyor: {channel.name} ({member.guild.name})")
            cog = self.get_cog("Müzik")
            if cog and member.guild.id in cog.players:
                await cog.players[member.guild.id].stop()
            else:
                if voice_client.is_playing() or voice_client.is_paused():
                    voice_client.stop()
                await voice_client.disconnect()


async def main():
    if not config.DISCORD_TOKEN:
        logger.error("❌ HATA: MUSIC_TOKEN bulunamadı! Lütfen Railway ortam değişkenlerini kontrol edin.")
        sys.exit(1)

    bot = PiyadeMusicBot()
    async with bot:
        await bot.start(config.DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot manuel olarak kapatıldı.")
