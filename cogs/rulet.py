import discord
from discord import app_commands
from discord.ext import commands
import database
from random import randint
from datetime import timedelta, datetime, UTC
from time import time
from utility import Utility
import logging
import asyncio

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
        message, ephemeral, timeout_task = await self.tirar_rulet(interaction, objetivo)
        formated_message = Utility.format_message(message, author=interaction.user, target=objetivo)
        await interaction.response.send_message(formated_message, ephemeral=ephemeral)
        if timeout_task is not None:
            await timeout_task

    @Utility.cooldown_check()
    async def rulet_context(self, interaction: discord.Interaction, objetivo: discord.Member):
        message, ephemeral, timeout_task = await self.tirar_rulet(interaction, objetivo)
        formated_message = Utility.format_message(message, author=interaction.user, target=objetivo)
        await interaction.response.send_message(formated_message, ephemeral=ephemeral)
        if timeout_task is not None:
            await timeout_task

    async def tirar_rulet(self, interaction: discord.Interaction, target: discord.Member) -> tuple[str, bool, asyncio.Task | None]:
        db = await database.get_from_database(interaction.guild.id)

        if interaction.user.id == target.id or target.bot:
            task = asyncio.create_task(self.timeout(interaction, user=interaction.user, db=db, multiplier=5))
            return db.wrong_target, False, task

        higher_role = target.top_role > interaction.guild.self_role
        if (target.guild_permissions.administrator or higher_role) and not db.annoy_admins:
            return f"{target.display_name} es un administrador y no le puedes retar", True, None

        if bool(randint(0, 1)):
            multiplier = 0.5 if db.half_lose_timeout else 1
            task = asyncio.create_task(self.timeout(interaction, target, db, multiplier))
            return db.win_message, False, task

        if target.voice and not interaction.user.voice:
            task = asyncio.create_task(self.timeout(interaction, user=interaction.user, db=db, multiplier=3))
            await self.set_user_cooldown(interaction, db=db, multiplier=5)
            return db.lose_penalty_message, False, task

        task = asyncio.create_task(self.timeout(interaction, interaction.user, db=db))
        await self.set_user_cooldown(interaction, db=db)

        return db.lose_message, True, task

    @staticmethod
    async def timeout(interaction: discord.Interaction, user: discord.Member, db: database.GuildConfig, multiplier: int = 1) -> None:
        timeout_impossible: bool = user.top_role >= interaction.guild.me.top_role or user.guild_permissions.administrator
        seconds: int = db.timeout_seconds

        if timeout_impossible or seconds == 0:
            await user.move_to(channel=None, reason="Ha perdido")
            return

        timeout_time: timedelta | datetime = timedelta(seconds=seconds * multiplier)
        if user.timed_out_until is not None and user.timed_out_until > datetime.now(UTC):
            timeout_time = timeout_time + user.timed_out_until
        await user.timeout(timeout_time, reason="Ha perdido")
        return

    @staticmethod
    async def set_user_cooldown(interaction: discord.Interaction, db: database.GuildConfig, multiplier: int = 1) -> None:
        key: tuple[int, int] = (interaction.guild_id, interaction.user.id)
        total_time: int = (db.timeout_seconds + db.lose_cooldown) * multiplier
        available_on: int = int(total_time + time())

        if interaction.user.guild_permissions.administrator:
            return

        Utility.disabled_users[key] = available_on


async def setup(bot: commands.bot):
    await bot.add_cog(Rulet(bot))