import discord
from discord import app_commands
from logging.handlers import RotatingFileHandler
import logging
from typing import Dict, Optional, Tuple
from time import time

formatter = logging.Formatter(fmt="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",datefmt="%Y-%m-%d %H:%M:%S")

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

file_handler = RotatingFileHandler("discord.log", maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.handlers.clear()
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)


class Utility:
    director_guild = None
    disabled_servers: Dict[int, int] = {}
    disabled_users: Dict[Tuple[int, int], int] = {}

    class AdminError(app_commands.CheckFailure): pass
    class GuildCooldown(app_commands.CheckFailure):
        def __init__(self, retry_after: float) -> None:
            self.retry_after: float = retry_after
    class UserCooldown(app_commands.CheckFailure):
        def __init__(self, retry_after: float) -> None:
            self.retry_after: float = retry_after

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
        parts.append(f"{seconds}s")

        return ' '.join(parts)

    @classmethod
    def get_admin_permissions(cls, member: discord.Member) -> bool:
        if member.resolved_permissions.administrator:
            return True

        if cls.director_guild is None:
            return False
        if member.id == cls.director_guild.owner_id:
            return True
        return False
    @classmethod
    def admin_check(cls):
        def predicate(interaction: discord.Interaction) -> bool:
            admin = cls.get_admin_permissions(interaction.user)
            if admin:
                return True
            raise cls.AdminError

        return app_commands.check(predicate)

    @classmethod
    def cooldown_check(cls):
        def predicate (interaction: discord.Interaction) -> bool:
            remaining = get_guild_status(interaction.user)
            if remaining is not None:
                raise cls.GuildCooldown(retry_after=remaining)

            remaining = get_user_status(interaction.user)
            if remaining is not None:
                raise cls.UserCooldown(retry_after=remaining)
            return True


        def get_guild_status(member: discord.Member) -> Optional[float]:
            if cls.get_admin_permissions(member):
                return None

            expire_at = cls.disabled_servers.get(member.guild.id)
            if not expire_at:
                return None
            remaining = expire_at - time()
            if remaining <= 0:
                cls.disabled_servers.pop(member.guild.id)
                return None
            return remaining

        def get_user_status(member: discord.Member) -> Optional[float]:
            key: Tuple[int, int] = (member.guild.id, member.id)
            if cls.get_admin_permissions(member):
                cls.disabled_users.pop(key)
                return None

            expire_at = cls.disabled_users.get(key)
            if not expire_at:
                return None
            remaining = expire_at - time()
            if remaining <= 0:
                cls.disabled_users.pop(key)
                return None
            return remaining

        return app_commands.check(predicate)