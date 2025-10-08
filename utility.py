import discord
from discord import app_commands
from logging.handlers import RotatingFileHandler
import logging
from typing import Dict

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
    disabled_servers: Dict[int] = {}
    disabled_users: Dict[int] = {}

    class AdminError(app_commands.CheckFailure): pass

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
    def admin_checks(cls):
        def predicate(interaction: discord.Interaction):
            if interaction.user.resolved_permissions.administrator:
                return True

            if cls.director_guild is None:
                raise Utility.AdminError
            if interaction.user.id == cls.director_guild.owner_id:
                return True
            raise cls.AdminError

        return app_commands.check(predicate)

