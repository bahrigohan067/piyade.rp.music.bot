import asyncio
import os
import sys
import logging
import discord
from discord.ext import commands
import config

# Log formatı (Railway'in tüm logları 'error' olarak algılamaması için stdout kullanılır)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)
logger = logging.getLogger("PiyadeMusicBot")


def ensure_opus_loaded() -> bool:
    """Linux/Docker ve Windows ortamlarında libopus kütüphanesini başlangıçta zorunlu olarak yükler."""
    if discord.opus.is_loaded():
        return True
    for lib_name in ("libopus.so.0", "libopus.so", "opus", "libopus-0.dll"):
        try:
            discord.opus.load_opus(lib_name)
            if discord.opus.is_loaded():
                logger.info(f"🔊 Opus ses kodlayıcısı yüklendi: {lib_name}")
                return True
        except Exception:
            continue
    try:
        discord.opus._load_default()
    except Exception:
        pass
    return discord.opus.is_loaded()


ensure_opus_loaded()

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

        # Komutları global olarak senkronize et (Tüm sunucularda geçerli)
        try:
            synced = await self.tree.sync()
            logger.info(f"🌍 Komutlar global olarak senkronize edildi ({len(synced)} komut).")
        except Exception as e:
            logger.error(f"❌ Global komut senkronizasyon hatası: {e}")

    async def on_guild_join(self, guild: discord.Guild):
        """Bot yeni bir sunucuya katıldığında komutları o sunucuya anında senkronize eder."""
        try:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"🎉 Yeni sunucuya ({guild.name}) komutlar anında senkronize edildi.")
        except Exception as e:
            logger.warning(f"⚠️ [{guild.name}] sunucusuna senkronizasyon uyarısı: {e}")

    async def on_ready(self):
        try:
            import davey
            dave_info = f"Aktif (v{davey.DAVE_PROTOCOL_VERSION})"
        except Exception:
            dave_info = "Yüklü Değil!"
        logger.info(f"==================================================")
        logger.info(f"🤖 Bot Aktif: {self.user.name} (ID: {self.user.id})")
        logger.info(f"📦 discord.py: v{discord.__version__} | DAVE E2EE: {dave_info} | Opus: {discord.opus.is_loaded()}")
        logger.info(f"👑 Müzik Yetki Rolü ID(leri): {config.MUSIC_ROLE_IDS}")
        logger.info(f"🌐 Bağlı Sunucu Sayısı: {len(self.guilds)}")
        if config.YTDL_OPTIONS.get('cookiefile'):
            logger.info("🍪 YouTube Çerez Durumu: Aktif (Çerez token'ı başarıyla yüklendi)")
        else:
            logger.warning("⚠️ YouTube Çerez Durumu: Çerez token'ı tanımlı değil (YTDLP_TOKEN veya YTDLP_COOKIES)")
        logger.info(f"==================================================")

        # Tüm bağlı sunuculara komutları anında senkronize et (Her sunucuda anında / komutları çıksın)
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                logger.info(f"⚡ [{guild.name}] (ID: {guild.id}) sunucusuna komutlar anında senkronize edildi.")
            except Exception as e:
                logger.warning(f"⚠️ [{guild.name}] senkronizasyon uyarısı: {e}")

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
        if member.bot:
            return

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
