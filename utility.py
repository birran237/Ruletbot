import discord
from discord import app_commands

class Utility:
    director_guild = None
    class AdminError(app_commands.CheckFailure): pass

    @staticmethod
    def format_seconds(seconds: int) -> str:
        days, remainder = divmod(seconds, 60 * 60 * 24)
        hours, remainder = divmod(remainder, 60 * 60)
        minutes, remainder = divmod(remainder, 60)
        seconds = remainder//1
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")

        return ' '.join(parts)

    @staticmethod
    def admin_checks():
        def predicate(interaction: discord.Interaction):
            if interaction.user.resolved_permissions.administrator:
                return True

            if Utility.director_guild is None:
                raise Utility.AdminError
            if interaction.user.id == Utility.director_guild.owner_id:
                return True
            raise Utility.AdminError

        return app_commands.check(predicate)