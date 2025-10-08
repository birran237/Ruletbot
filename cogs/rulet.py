import discord
from discord import app_commands
from discord.ext import commands
import database
from random import randint
from datetime import timedelta
from time import time
from utility import Utility

class Rulet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(
            name='Retar a la rulet',
            callback=self.rulet_context,
        )
        self.bot.tree.add_command(self.ctx_menu)


    @app_commands.command(name="rulet", description="Retar a alguien a la rulet")
    @app_commands.describe(persona="La persona a la que retaras a la rulet")
    async def rulet(self, interaction: discord.Interaction, persona: discord.Member):
        message, ephemeral = await self.tirar_rulet(interaction, persona)
        formated_message = message.replace("{k}",interaction.user.display_name).replace("{u}",persona.mention)
        await interaction.response.send_message(formated_message, ephemeral=ephemeral)

    async def rulet_context(self, interaction: discord.Interaction, persona: discord.Member):
        message, ephemeral = await self.tirar_rulet(interaction, persona)
        formated_message = message.replace("{k}", interaction.user.display_name).replace("{u}", persona.mention)
        await interaction.response.send_message(formated_message, ephemeral=ephemeral)


    async def tirar_rulet(self, interaction: discord.Interaction, person:discord.Member) -> (str, bool):
        db = await database.get_from_database(guild_id=interaction.guild.id)
        if interaction.user.id == person.id or person.bot:
            await self.timeout(interaction=interaction, user=person, db=db, multiplier=5)
            return f"{interaction.user.display_name} creo que te amamantaron con RedBull", False

        disabled_time = self.get_disabled_status(interaction.guild_id)
        if disabled_time is not None:
            return f"{interaction.user.mention} he sido deshabilitado por los administradores hasta dentro de **{Utility.format_seconds(disabled_time)}**.", True

        higher_role: bool = person.top_role > interaction.guild.self_role

        if (person.resolved_permissions.administrator or higher_role) and not db["annoy_admins"]:
            return f"{person.display_name} es un administrador y no le puedes retar", True


        if bool(randint(0, 1)):
            await self.timeout(interaction=interaction, user=person, db=db)
            return db["win_message"], False

        if person.voice is not None and interaction.user.voice is None:
            await self.timeout(interaction=interaction, user=interaction.user, db=db, multiplier=3)
            return db["lose_penalty_message"], False

        await self.timeout(interaction=interaction, user=interaction.user, db=db)
        return db["lose_message"], False

    @staticmethod
    async def timeout(interaction: discord.Interaction, user: discord.Member, db:dict, multiplier: int = 1):
        timeout_impossible: bool = user.top_role >= interaction.guild.me.top_role or user.resolved_permissions.administrator
        seconds: int = db["timeout_seconds"]

        if timeout_impossible:
            await user.move_to(channel=None, reason="Ha perdido")
            return

        if seconds == 0:
            await user.move_to(channel=None, reason="Ha perdido")
            return

        await user.timeout(timedelta(seconds=seconds * multiplier), reason="Ha perdido")
        return

    def get_disabled_status(self, guild_id: int) -> float | None:
        expire_at = Utility.disabled_servers.get(guild_id)
        if not expire_at:
            return None
        remaining = expire_at - time()
        if remaining <= 0:
            Utility.disabled_servers.pop(guild_id, None)
            return None
        return remaining

async def setup(bot: commands.bot):
    await bot.add_cog(Rulet(bot))