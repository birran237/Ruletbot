import discord
from discord import app_commands
from logging.handlers import RotatingFileHandler
import logging
from time import time
from string import Template

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

log = logging.getLogger(__name__)
class Utility:
    director_guild = None
    disabled_servers: dict[int, int] = {} #guild_id -> disabled until
    disabled_users: dict[tuple[int, int], int] = {} #(guild_id, member_id) -> cooldown until
    timeouted_admins: dict[tuple[int, int], int] = {} #(guild_id, member_id) -> timeout until

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
    def admin_check(cls):
        def predicate(interaction: discord.Interaction):
            if interaction.user.guild_permissions.administrator:
                return True

            if cls.director_guild is None:
                raise Utility.AdminError
            if interaction.user.id == cls.director_guild.owner_id:
                return True
            raise cls.AdminError

        return app_commands.check(predicate)

    @classmethod
    def cooldown_check(cls):
        def predicate (interaction: discord.Interaction) -> bool:
            expire_at = get_guild_status(interaction.user)
            if expire_at is not None:
                raise cls.GuildCooldown(retry_after=expire_at)

            expire_at = get_user_status(interaction.user)
            if expire_at is not None:
                raise cls.UserCooldown(retry_after=expire_at)
            return True

        def get_guild_status(member: discord.Member) -> float | None:
            if member.guild_permissions.administrator:
                return None

            expire_at = cls.disabled_servers.get(member.guild.id)
            if expire_at is None:
                return None
            remaining = expire_at - time()
            if remaining <= 0:
                cls.disabled_servers.pop(member.guild.id)
                return None
            return remaining

        def get_user_status(member: discord.Member) -> float | None:
            key: tuple[int, int] = (member.guild.id, member.id)
            expire_at = cls.disabled_users.get(key)
            if expire_at is None:
                return None

            if member.guild_permissions.administrator:
                cls.disabled_users.pop(key)
                return None

            remaining = expire_at - time()
            if remaining <= 0:
                cls.disabled_users.pop(key)
                return None
            return remaining

        return app_commands.check(predicate)

    @staticmethod
    def format_message(message: str, author: discord.User | discord.Member | None = None, target: discord.User | discord.Member | None = None) -> str:
        mapper = {"k": "*autor*", "u": "*objetivo*"}

        if author is not None:
            mapper["k"] = author.display_name
        if target is not None:
            mapper["u"] = target.mention

        return Template(message).safe_substitute(mapper)
