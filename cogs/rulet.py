import discord
from discord import app_commands
from discord.ext import commands
import database
from random import randint
from datetime import timedelta
from time import time


def format_seconds(seconds:int)-> str:
     days, remainder = divmod(seconds, 60*60*24)
     hours, remainder = divmod(remainder, 60*60)
     minutes = remainder // 60
     parts = []
     if days:
        parts.append(f"{days}d")
        parts.append(f"{hours}h")
     elif hours:
        parts.append(f"{hours}h")
     parts.append(f"{minutes}m")

     return ' '.join(parts)


async def timeout(interaction: discord.Interaction, user:discord.Member, multiplier:int = 1):
    timeout_impossible:bool = user.top_role >= interaction.guild.me.top_role or user.resolved_permissions.administrator
    minutes: int = await database.get_from_database(guild_id=interaction.guild_id,field="timeout_minutes")

    if timeout_impossible:
        await user.move_to(channel=None, reason="Ha perdido")
        return

    if minutes == 0:
        await user.move_to(channel=None, reason="Ha perdido")
        return

    await user.timeout(timedelta(minutes=minutes*multiplier), reason="Ha perdido")
    return

class Rulet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.disabled_servers = {}

    @app_commands.command(name="rulet", description="Retar a alguien a la rulet")
    @app_commands.describe(persona="La persona a la que retaras a la rulet")
    async def rulet(self, interaction: discord.Interaction, persona: discord.Member):
        message, ephemeral = await self.tirar_rulet(interaction, persona)
        await interaction.response.send_message(message, ephemeral=ephemeral)

    @app_commands.context_menu(name="Retar a la rulet")
    async def rulet_context(self, interaction: discord.Interaction, persona: discord.Member):
        message, ephemeral = await self.tirar_rulet(interaction, persona)
        await interaction.response.send_message(message, ephemeral=ephemeral)

    async def tirar_rulet(self, interaction: discord.Interaction, user:discord.Member) -> (str, bool):
        if interaction.user.id == user.id or user.bot:
            await timeout(interaction=interaction, user=user, multiplier=6)
            return f"{interaction.user.display_name} creo que te amamantaron con RedBull"

        disabled_time = self.get_disabled_status(interaction.guild_id)
        if disabled_time is not None:
            return f"{interaction.user.mention} he sido deshabilitado por los administradores hasta dentro de **{format_seconds(int(disabled_time))} {round(disabled_time%60)}s**.", True

        affect_admins = await database.get_from_database(guild_id=interaction.guild_id,field="annoy_admins")
        higher_role: bool = user.top_role > interaction.guild.self_role

        if (user.resolved_permissions.administrator or higher_role) and not affect_admins:
            return f"{user.display_name} es un administrador y no le puedes retar", True

        if bool(randint(0, 1)):
            await timeout(interaction=interaction, user=user)
            message: str = await database.get_from_database(guild_id=interaction.guild_id,field="win_message")
            return message.replace("{k}",interaction.user.display_name).replace("{u}",user.mention), False

        if user.voice is not None and interaction.user.voice is None:
            await timeout(interaction=interaction, user=interaction.user, multiplier=5)
            message: str = await database.get_from_database(guild_id=interaction.guild_id, field="lose_penalty_message")
            return message.replace("{k}",interaction.user.display_name).replace("{u}",user.mention), False

        await timeout(interaction=interaction, user=interaction.user)
        message: str = await database.get_from_database(guild_id=interaction.guild_id, field="lose_message")
        return message.replace("{k}", interaction.user.display_name).replace("{u}", user.mention), False


    def get_disabled_status(self, guild_id: int) -> float | None:
        expire_at = self.disabled_servers.get(guild_id)
        if not expire_at:
            return None
        remaining = expire_at - time()
        if remaining <= 0:
            self.disabled_servers.pop(guild_id, None)
            return None
        return remaining

async def setup(bot: commands.bot):
    await bot.add_cog(Rulet(bot))