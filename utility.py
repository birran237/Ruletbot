import discord
from discord import app_commands

class AdminError(app_commands.CheckFailure): pass

def format_seconds(seconds: int) -> str:
    days, remainder = divmod(seconds, 60 * 60 * 24)
    hours, remainder = divmod(remainder, 60 * 60)
    minutes = remainder // 60
    parts = []
    if days:
        parts.append(f"{days}d")
        parts.append(f"{hours}h")
    elif hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")

    return ' '.join(parts)

def admin_checks():
    def predicate(interaction: discord.Interaction):
        if interaction.user.resolved_permissions.administrator:
            return True

        director_guild = interaction.client.director_guild
        if director_guild is None:
            raise AdminError
        if interaction.user.id == director_guild.owner.id:
            return True
        raise AdminError

    return app_commands.check(predicate)