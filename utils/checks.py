import discord
from discord import app_commands
import config

class MusicPermissionError(app_commands.AppCommandError):
    """Kullanıcının müzik açma rolü olmadığında fırlatılır."""
    pass

class VoiceChannelError(app_commands.AppCommandError):
    """Kullanıcı ses kanalında olmadığında veya kanal kilitli olduğunda fırlatılır."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

def user_has_music_role(user: discord.Member) -> bool:
    """Kullanıcının belirtilen müzik rolüne veya yönetici yetkisine sahip olup olmadığını kontrol eder."""
    if not isinstance(user, discord.Member):
        return False
    
    # Sunucu yöneticileri her zaman yetkilidir
    if user.guild_permissions.administrator:
        return True
    
    # Rol kontrolü
    return any(role.id == config.MUSIC_ROLE_ID for role in user.roles)

def check_voice_state(interaction: discord.Interaction) -> tuple[bool, str | None]:
    """
    Kullanıcının ses durumunu ve botun mevcut kanalını doğrular.
    Kural: Bot bir kanalda aktifken başka kanaldaki biri çağıramaz veya kontrol edemez.
    """
    guild = interaction.guild
    if not guild:
        return False, "Bu komut yalnızca sunucularda kullanılabilir."

    user = interaction.user
    if not isinstance(user, discord.Member) or not user.voice or not user.voice.channel:
        return False, "⚠️ Bu komutu kullanabilmek için bir **ses kanalında** bulunmalısınız!"

    bot_voice = guild.voice_client
    if bot_voice and bot_voice.channel:
        if bot_voice.channel.id != user.voice.channel.id:
            return False, (
                f"🔒 **Bot Başka Bir Kanalda Aktif!**\n"
                f"Müzik botu şu anda <#{bot_voice.channel.id}> kanalında hizmet veriyor. "
                f"Kanalda müzik çalarken bot başka bir kanala çağrılamaz veya oradan yönetilemez!"
            )

    return True, None
