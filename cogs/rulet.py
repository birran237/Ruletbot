import discord
from discord import app_commands
from discord.ext import commands
import database
from random import randint
from datetime import timedelta, datetime, UTC
from time import time
from utility import Utility
from typing import Tuple
import logging

log = logging.getLogger(__name__)
class Rulet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(
            name='Retar a la rulet',
            callback=self.rulet_context,
        )
        self.bot.tree.add_command(self.ctx_menu)


    @app_commands.command(name="rulet", description="Retar a alguien a la rulet")
    @app_commands.describe(objetivo="La persona a la que retaras a la rulet")
    @Utility.cooldown_check()
    async def rulet(self, interaction: discord.Interaction, objetivo: discord.Member):
        message, ephemeral = await self.tirar_rulet(interaction, objetivo)
        formated_message = Utility.format_message(message, author=interaction.user, target=objetivo)
        await interaction.response.send_message(formated_message, ephemeral=ephemeral)

    @Utility.cooldown_check()
    async def rulet_context(self, interaction: discord.Interaction, objetivo: discord.Member):
        message, ephemeral = await self.tirar_rulet(interaction, objetivo)
        formated_message = Utility.format_message(message, author=interaction.user, target=objetivo)
        await interaction.response.send_message(formated_message, ephemeral=ephemeral)


    async def tirar_rulet(self, interaction: discord.Interaction, target:discord.Member) -> (str, bool):
        db = await database.get_from_database(guild_id=interaction.guild.id)
        if interaction.user.id == target.id or target.bot:
            await self.timeout(interaction=interaction, user=target, db=db, multiplier=5)
            return f"{interaction.user.display_name} creo que te amamantaron con RedBull", False

        higher_role: bool = target.top_role > interaction.guild.self_role

        if (target.guild_permissions.administrator or higher_role) and not db["annoy_admins"]:
            return f"{target.display_name} es un administrador y no le puedes retar", True


        if bool(randint(0, 1)):
            multiplayer = 0.5 if db["half_lose_timeout"] else 1
            await self.timeout(interaction=interaction, user=target, db=db, multiplier=multiplayer)
            return db["win_message"], False

        if target.voice is not None and interaction.user.voice is None:
            await self.timeout(interaction=interaction, user=interaction.user, db=db, multiplier=3)
            await self.set_user_cooldown(interaction=interaction, db=db, multiplier=5)
            return db["lose_penalty_message"], False

        await self.timeout(interaction=interaction, user=interaction.user, db=db)
        await self.set_user_cooldown(interaction=interaction, db=db)
        return db["lose_message"], False

    @staticmethod
    async def timeout(interaction: discord.Interaction, user: discord.Member, db:dict, multiplier: int = 1) -> None:
        timeout_impossible: bool = user.top_role >= interaction.guild.me.top_role or user.guild_permissions.administrator
        seconds: int = db["timeout_seconds"]

        if timeout_impossible:
            await user.move_to(channel=None, reason="Ha perdido")
            log.debug(f"{user.display_name}({user.id}) has been kicked of vc in guild {interaction.guild}({interaction.guild.id})")
            return

        if seconds == 0:
            await user.move_to(channel=None, reason="Ha perdido")
            log.debug(f"{user.display_name}({user.id}) has been kicked of vc in guild {interaction.guild}({interaction.guild.id})")
            return

        timeout_time: timedelta | datetime = timedelta(seconds=seconds * multiplier)
        if user.timed_out_until is not None and user.timed_out_until > datetime.now(UTC):
            timeout_time = timeout_time + user.timed_out_until
        await user.timeout(timeout_time, reason="Ha perdido")
        log.debug(f"{user.display_name}({user.id}) has been timeouted for {seconds * multiplier} seconds in guild {interaction.guild}({interaction.guild.id})")
        return

    @staticmethod
    async def set_user_cooldown(interaction: discord.Interaction, db: dict, multiplier: int = 1) -> None:
        key: Tuple[int, int] = (interaction.guild_id, interaction.user.id)
        total_time: int = (db["timeout_seconds"] + db["lose_cooldown"]) * multiplier
        available_on: int = int(total_time + time())

        if interaction.user.guild_permissions.administrator:
            return

        Utility.disabled_users[key] = available_on


async def setup(bot: commands.bot):
    await bot.add_cog(Rulet(bot))