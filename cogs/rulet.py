import discord
from discord import app_commands
from discord._types import ClientT
from discord.ext import commands
import database
from random import randint
from datetime import timedelta, datetime, UTC
from time import time
from utility import Utility
import logging
import asyncio
from typing import Coroutine, cast

log = logging.getLogger(__name__)
class Rulet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rulet_ctx = app_commands.ContextMenu(
            name='Retar a la rulet',
            callback=self.rulet_command,
        )
        self.bot.tree.add_command(self.rulet_ctx)

        self.rulet_app = app_commands.Command(
            name='rulet',
            description='Retar a alguien a la rulet',
            callback = self.rulet_command
        )
        self.bot.tree.add_command(self.rulet_app)


    @app_commands.guild_only()
    @app_commands.describe(objetivo="La persona a la que retaras a la rulet")
    @Utility.cooldown_check()
    @Utility.check_valid_perms()
    async def rulet_command(self, interaction: discord.Interaction, objetivo: discord.Member):

        try: #checks if the user is in the server
            _ = await interaction.guild.fetch_member(objetivo.id)
        except discord.NotFound:
            raise app_commands.TransformerError

        message, loser, timeout_coro = await self.tirar_rulet(interaction, objetivo)
        ephemeral = loser is None
        formated_message = Utility.format_message(message, author=interaction.user, target=objetivo, victim=loser)
        async with asyncio.TaskGroup() as tg:
            tg.create_task(interaction.response.send_message(formated_message, ephemeral=ephemeral))
            if timeout_coro is not None:
                tg.create_task(timeout_coro)
            tg.create_task(Utility.delete_expired_user(guild_id=interaction.guild.id, member_id=interaction.user.id))
            tg.create_task(Utility.delete_expired_user(guild_id=interaction.guild.id, member_id=objetivo.id))

    async def tirar_rulet(self, interaction: discord.Interaction, target: discord.Member) -> tuple[str, discord.Member | None, Coroutine | None]:
        assert isinstance(interaction.user, discord.Member); assert isinstance(interaction.guild, discord.Guild)
        db = await database.get_from_database(interaction.guild.id)
        key: tuple[int, int] = (interaction.guild.id, interaction.user.id)
        if key not in Utility.users_status:
            Utility.users_status[key] = {}

        if target.voice and not interaction.user.voice:
            message = "No puedes retar a una persona en un chat de voz sin tu estar en ninguno"
            return message, None, None

        user_status = Utility.users_status[key]

        if "vc_rulet_available" in user_status and user_status.get("vc_rulet_available", 0) < time() and target.voice:
            message = f'Llevas demasiado poco tiempo en un chat de voz, podrás retar a alguien en un vc en <t:{user_status.get("vc_rulet_available", time()+ 5*60)}:R>'
            return message, None, None

        if interaction.user.id == target.id or target.bot:
            coro = await self.timeout(interaction, user=interaction.user, db=db, multiplier=5)
            return str(db['wrong_target']), interaction.user, coro

        if db['annoy_admins'] < 2:
            message = await self.check_valid_rulet(interaction, target)
            if message is not None: return message, None, None


        if user_status.get("streak_expiates",0) < time():
            user_status["streak"] = 0

        extra_chance:float = min(user_status.get("streak", 0) * 0.05, 0.4)
        if randint(0, 1) + extra_chance > 0.5:
            user_status["streak"] = user_status.get("streak", 0) + 1
            user_status["streak_expiates"] = int(time()) + 300
            message = db['win_message'] if extra_chance < 0.1 else db['win_streak_message']
            coro = await self.timeout(interaction, target, db)
            return str(message), target, coro

        coro = await self.timeout(interaction, interaction.user, db=db)
        await self.set_user_cooldown(interaction, db=db)

        return str(db['lose_message']), interaction.user, coro

    @staticmethod
    async def check_valid_rulet(interaction: discord.Interaction, target: discord.Member) -> str | None:
        higher_role_than_bot: bool = target.top_role > interaction.guild.self_role or target.id == interaction.guild.owner_id
        higher_role_than_author: bool = target.top_role > interaction.user.top_role or target.id == interaction.guild.owner_id

        if not (higher_role_than_bot and higher_role_than_author):
            return None #Only allow rulet if the target is able to be timedout by the bot or if the author has a higher role than the target
        return f"{target.display_name} tiene un rol superior al tuyo y al rol `rulet bot` y no le puedes retar"

    @staticmethod
    async def timeout(interaction: discord.Interaction, user: discord.Member, db: database.db_dict, multiplier: int = 1) -> Coroutine | None:
        # Handle timing out a user (either voice kick or Discord timeout).
        # Check if timeout is impossible (user has higher/equal role or is admin)
        timeout_impossible: bool = bool(user.top_role >= interaction.guild.me.top_role or user.id == interaction.guild.owner_id or user.resolved_permissions.administrator)
        seconds: int = int(db['timeout_seconds'])

        # Ensure user entry exists in status tracking
        key: tuple[int, int] = (user.guild.id, user.id)
        if key not in Utility.users_status:
            Utility.users_status[key] = {}

        # Clear streak data when applying timeout
        try:
            del Utility.users_status[key]["streak_expiates"]
            del Utility.users_status[key]["streak"]
        except KeyError:
            pass

        # Calculate total timeout duration
        timeout_duration = seconds * multiplier

        # If timeout is impossible or duration is zero, use voice kick
        if timeout_impossible or timeout_duration == 0:
            if db['annoy_admins'] == 0:
                return None
            # Set the timeout_until to the maximum of current time and existing timeout
            current_timeout_until = Utility.users_status[key].get("timeout_until", 0)
            new_timeout_until = max(current_timeout_until, int(time())) + timeout_duration
            Utility.users_status[key]["timeout_until"] = new_timeout_until
            return user.move_to(channel=None, reason="Ha perdido")

        # Use Discord's timeout feature
        # Calculate new timeout time
        new_timeout_until = int(time()) + timeout_duration

        # If user is already timed out, extend the timeout
        if user.timed_out_until is not None and user.timed_out_until > datetime.now(UTC):
            # Add existing timeout to new timeout (extend duration)
            extension = user.timed_out_until - datetime.now(UTC)
            new_timeout_until += int(extension.total_seconds())

        Utility.users_status[key]["timeout_until"] = new_timeout_until

        # Apply the timeout
        timeout_duration = timedelta(seconds=new_timeout_until - time())
        return user.timeout(timeout_duration, reason="Ha perdido")

    @staticmethod
    async def set_user_cooldown(interaction: discord.Interaction, db: database.db_dict, multiplier: int = 1) -> None:
        key: tuple[int, int] = (interaction.guild.id, interaction.user.id)
        total_time: int = int(db['timeout_seconds'] + (int(db['lose_cooldown']) * multiplier))
        available_on: int = int(total_time + time())

        if key not in Utility.users_status:
            Utility.users_status[key] = {}
        Utility.users_status[key]["cooldown_until"] = available_on


async def setup(bot: commands.bot):
    await bot.add_cog(Rulet(bot))