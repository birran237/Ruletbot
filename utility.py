import discord
from discord import app_commands
from logging.handlers import RotatingFileHandler
import logging
from time import time
import signal, sys, os, pickle
from collections import OrderedDict
from string import Template
import database
from typing import Literal
import asyncio


# Track running cleanup tasks to prevent duplicates
_cleanup_tasks: dict[tuple, asyncio.Task] = {}


def create_logger():
    formatter = logging.Formatter(fmt="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
                                  datefmt="%Y-%m-%d %H:%M:%S")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    file_handler = RotatingFileHandler("discord.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

class Utility:
    disabled_servers: dict[int, int] = {} #guild_id -> disabled until
    users_status: dict[tuple[int, int], dict[Literal["cooldown_until","timeout_until","streak_expiates","streak"],int]] = {} #(guild_id, member_id) -> {}

    class GuildCooldown(app_commands.CheckFailure):
        def __init__(self, expire_at: int) -> None:
            self.expire_at: int = expire_at
    class UserCooldown(app_commands.CheckFailure):
        def __init__(self, expire_at: int, extra_cooldown: bool) -> None:
            self.expire_at: int = expire_at
            self.extra_cooldown: bool = extra_cooldown

    class MissingPerms(app_commands.CheckFailure):
        def __init__(self, missing_perms: list[str]) -> None:
            self.missing_perms: list[str] = missing_perms
    class GuildCheckFailure(app_commands.CheckFailure):
        pass

    @staticmethod
    def format_seconds(seconds: int | float) -> str:
        seconds = int(seconds)
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
        if seconds or not parts:
            parts.append(f"{seconds}s")

        return ' '.join(parts)

    @staticmethod
    def format_message(message: str, author: discord.User | discord.Member | None = None, target: discord.User | discord.Member | None = None, victim: discord.User | discord.Member | None = None) -> str:
        mapper = {'k': "*autor*", 'u': "*objetivo*", 't': "*x minutos*", 'r':"*n*"}

        if author is not None:
            mapper['k'] = author.display_name
            key: tuple[int, int] = (author.guild.id, author.id)
            try:
                mapper['r'] = str(Utility.users_status[key].get("streak",0))
            except KeyError:
                mapper['r'] = "0"
        if target is not None:
            mapper['u'] = target.mention
        if victim is not None:
            key: tuple[int, int] = (victim.guild.id, victim.id)
            try:
                timeout_until = Utility.users_status[key].get("timeout_until",time())
            except KeyError:
                timeout_until = time()
            mapper['t'] = f"<t:{timeout_until}:R>"


        return Template(message).safe_substitute(mapper)

    @classmethod
    def check_valid_perms(cls):
        def predicate(interaction: discord.Interaction) -> bool:
            bot_member = interaction.guild.me
            bot_permissions = bot_member.guild_permissions
            missing_perms = []

            if not bot_permissions.moderate_members:
                missing_perms.append("timeout members")
            if not bot_permissions.send_messages:
                missing_perms.append("send texts")
            if not bot_permissions.move_members:
                missing_perms.append("move users")

            # If any permissions are missing, send an ephemeral message and return False
            if missing_perms:
                raise cls.MissingPerms(missing_perms)
            return True
        return app_commands.check(predicate)
    @classmethod
    async def delete_expired_disabled_server(cls, guild_id: int) -> None:
        """Wait until the disabled time for a guild has passed, then remove the entry.
        This function ensures only one cleanup task runs per guild_id at a time."""
        task_key = ('disabled_server', guild_id)
        if task_key in _cleanup_tasks:
            existing_task = _cleanup_tasks[task_key]
            if not existing_task.done():
                existing_task.cancel()

        task = asyncio.create_task(cls._delete_expired_disabled_server_internal(guild_id))
        _cleanup_tasks[task_key] = task
        try:
            await task
        finally:
            await _cleanup_tasks.pop(task_key, None)

    @staticmethod
    async def _delete_expired_disabled_server_internal(guild_id: int) -> None:
        """Internal implementation that waits for expiration and cleans up."""
        while True:
            disabled_until = Utility.disabled_servers.get(guild_id)
            if disabled_until is None:
                # The entry has been removed by another task or manually
                return
            now = time()
            if disabled_until <= now:
                # The disabled time has passed, remove the entry
                Utility.disabled_servers.pop(guild_id, None)
                return
            wait_time = disabled_until - now
            await asyncio.sleep(wait_time)


    @classmethod
    async def delete_expired_user(cls, guild_id: int, member_id: int) -> None:
        """Wait until all expiration times for a user have passed, then remove the entry.
        This function ensures only one cleanup task runs per user at a time."""
        key = (guild_id, member_id)
        task_key = ('user', key)

        # Cancel any existing task for this user
        if task_key in _cleanup_tasks:
            existing_task = _cleanup_tasks[task_key]
            if not existing_task.done():
                existing_task.cancel()

        # Create and store the new task
        task = asyncio.create_task(cls._delete_expired_user_internal(guild_id, member_id))
        _cleanup_tasks[task_key] = task

        try:
            await task
        finally:
            # Clean up the task reference when done
            await _cleanup_tasks.pop(task_key, None)

    @staticmethod
    async def _delete_expired_user_internal(guild_id: int, member_id: int) -> None:
        """Internal implementation that waits for expiration and cleans up."""
        key = (guild_id, member_id)
        while True:
            user_dict = Utility.users_status.get(key)
            if user_dict is None:
                return
            if not user_dict:
                Utility.users_status.pop(key, None)
                return
            # Find the maximum expiration time in the user dictionary
            try:
                max_expiration = max(user_dict.values())
            except ValueError:
                # This happens if user_dict is empty, but we already checked for empty
                Utility.users_status.pop(key, None)
                return

            now = time()
            if max_expiration <= now:
                # All expiration times have passed, remove the entry
                Utility.users_status.pop(key, None)
                return

            wait_time = max_expiration - now
            await asyncio.sleep(wait_time)

    @classmethod
    def cooldown_check(cls):
        def predicate(interaction: discord.Interaction) -> bool:
            cls._get_guild_status(interaction)
            cls._get_user_status(interaction.user)
            return True

        return app_commands.check(predicate)

    @classmethod
    def _get_guild_status(cls, interaction: discord.Interaction) -> None:
        """Check if the guild is disabled and handle cooldown logic."""
        guild = interaction.guild
        expire_at = cls.disabled_servers.get(guild.id)
        timed_out_until = interaction.guild.me.timed_out_until

        # If neither source indicates a timeout, nothing to do
        if expire_at is None and timed_out_until is None:
            return

        # Calculate the expiration time from available sources
        times = []
        if expire_at is not None:
            times.append(expire_at)
        if timed_out_until is not None:
            times.append(timed_out_until.timestamp())

        if not times:
            return

        time_value = max(times)
        if time_value > time():
            raise cls.GuildCooldown(expire_at=int(time_value))

        # Clean up expired entry
        cls.disabled_servers.pop(guild.id, None)

    @classmethod
    def _get_user_status(cls, member: discord.Member) -> None:
        """Check if the user is on cooldown/timeout and handle cooldown logic."""
        key: tuple[int, int] = (member.guild.id, member.id)
        if key not in cls.users_status:
            return

        cooldown_until = cls.users_status[key].get("cooldown_until", 0)
        timeout_until = cls.users_status[key].get("timeout_until", 0)
        extra_cooldown: bool = cooldown_until > timeout_until
        disabled_until = max(cooldown_until, timeout_until)

        # If neither cooldown nor timeout is active, nothing to do
        if disabled_until == 0:
            return

        if disabled_until > time():
            raise cls.UserCooldown(expire_at=int(disabled_until), extra_cooldown=extra_cooldown)

        # Clean up expired cooldown/timeout values
        cls.users_status[key].pop('cooldown_until', None)
        cls.users_status[key].pop('timeout_until', None)

class Loader:
    state_path = "state.pkl"
    tmp_path = "state.pkl.tmp"

    @staticmethod
    async def cleanup_expired_entries():
        tasks = []
        # We make a copy of the keys to avoid dictionary changed size during iteration
        for key in list(Utility.users_status.keys()):
            tasks.append(Utility.delete_expired_user(*key))
        for key in list(Utility.disabled_servers.keys()):
            tasks.append(Utility.delete_expired_disabled_server(key))
        if tasks:
            await asyncio.gather(*tasks)

    @classmethod
    def _process_temp_dicts(cls):
        if not os.path.isfile(cls.state_path):
            return OrderedDict(), {}, {}

        with open(cls.state_path, 'rb') as f:
            try:
                data = pickle.load(f)
            except EOFError:
                return OrderedDict(), {}, {}

            return (
                data.get("local_db",OrderedDict()),
                data.get("disabled_servers", {}),
                data.get("users_status", {})
            )

    @classmethod
    def load_temp_dicts(cls) -> None:
        database.local_db,Utility.disabled_servers,Utility.users_status = cls._process_temp_dicts()
        return

    @classmethod
    def save_temp_dicts(cls, signum, frame) -> None:
        # Mark unused parameters to satisfy linter
        _ = signum, frame
        data = {"local_db":database.local_db,"disabled_servers":Utility.disabled_servers,"users_status":Utility.users_status}
        with open(cls.tmp_path, 'wb') as f:
            pickle.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(cls.tmp_path, cls.state_path)
        sys.exit(0)


signal.signal(signal.SIGTERM, Loader.save_temp_dicts)
signal.signal(signal.SIGINT, Loader.save_temp_dicts)
Loader.load_temp_dicts()
create_logger()