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
        self.rulet_ctx = app_commands.ContextMenu(
            name='Retar a la rulet',
            callback=self.rulet_command,
        )
        self.bot.tree.add_command(self.rulet_ctx)


    @app_commands.command(name="rulet", description="Retar a alguien a la rulet")
    @app_commands.describe(objetivo="La persona a la que retaras a la rulet")
    @Utility.cooldown_check()
    async def rulet(self, interaction: discord.Interaction, objetivo: discord.Member):
        message, timeout_task = await self.tirar_rulet(interaction, objetivo)
        ephemeral = timeout_task is None
        formated_message = Utility.format_message(message, author=interaction.user, target=objetivo)
        await interaction.response.send_message(formated_message, ephemeral=ephemeral)
        if timeout_task is not None:
            await timeout_task

    @Utility.cooldown_check()
    async def rulet_command(self, interaction: discord.Interaction, objetivo: discord.Member):
        message, timeout_task = await self.tirar_rulet(interaction, objetivo)
        ephemeral = isinstance(timeout_task, asyncio.Task)
        formated_message = Utility.format_message(message, author=interaction.user, target=objetivo)
        await interaction.response.send_message(formated_message, ephemeral=ephemeral)
        if timeout_task is not None:
            await timeout_task

    async def tirar_rulet(self, interaction: discord.Interaction, target: discord.Member) -> tuple[str, asyncio.Task | None]:
        db = await database.get_from_database(interaction.guild.id)

        if interaction.user.id == target.id or target.bot:
            task = await self.timeout(interaction, user=interaction.user, db=db, multiplier=5)
            return db.wrong_target, task

        higher_role = target.top_role > interaction.guild.self_role
        if (target.guild_permissions.administrator or higher_role) and not db.annoy_admins:
            return f"{target.display_name} es un administrador y no le puedes retar", None

        if bool(randint(0, 1)):
            multiplier = 0.5 if db.half_lose_timeout else 1
            task = await self.timeout(interaction, target, db, multiplier)
            return db.win_message, task

        if target.voice and not interaction.user.voice:
            task = await self.timeout(interaction, user=interaction.user, db=db, multiplier=3)
            await self.set_user_cooldown(interaction, db=db, multiplier=5)
            return db.lose_penalty_message, task

        task = await self.timeout(interaction, interaction.user, db=db)
        await self.set_user_cooldown(interaction, db=db)

        return db.lose_message, task

    @staticmethod
    async def timeout(interaction: discord.Interaction, user: discord.Member, db: database.GuildConfig, multiplier: int = 1) -> asyncio.Task:
        timeout_impossible: bool = user.top_role >= interaction.guild.me.top_role or user.guild_permissions.administrator
        seconds: int = db.timeout_seconds

        key: tuple[int, int] = (user.guild.id, user.id)
        if key not in Utility.users_status:
            Utility.users_status[key] = {}

        if timeout_impossible or seconds == 0:
            new_value = max(Utility.users_status[key].get("timeout_until", 0), int(time()))
            Utility.users_status[key]["timeout_until"] = new_value + (seconds * multiplier)
            task = asyncio.create_task(user.move_to(channel=None, reason="Ha perdido"))
            return task

        timeout_time: timedelta | datetime = timedelta(seconds=seconds * multiplier)
        Utility.users_status[key]["timeout_until"] = int(time()) + (seconds * multiplier)

        if user.timed_out_until is not None and user.timed_out_until > datetime.now(UTC):
            timeout_time = timeout_time + user.timed_out_until
            Utility.users_status[key]["timeout_until"] = int(timeout_time.timestamp())

        task = asyncio.create_task(user.timeout(timeout_time, reason="Ha perdido"))
        return task

    @staticmethod
    async def set_user_cooldown(interaction: discord.Interaction, db: database.GuildConfig, multiplier: int = 1) -> None:
        key: tuple[int, int] = (interaction.guild_id, interaction.user.id)
        total_time: int = db.timeout_seconds + (db.lose_cooldown * multiplier)
        available_on: int = int(total_time + time())

        if key not in Utility.users_status:
            Utility.users_status[key] = {}
        Utility.users_status[key]["cooldown_until"] = available_on


async def setup(bot: commands.bot):
    await bot.add_cog(Rulet(bot))