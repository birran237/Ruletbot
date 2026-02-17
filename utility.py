import discord
from discord import app_commands
from logging.handlers import RotatingFileHandler
import logging
from time import time
import signal, sys, os, pickle
from collections import OrderedDict
from string import Template
import database
from typing import Literal, Any


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
    director_guild = None
    disabled_servers: dict[int, int] = {} #guild_id -> disabled until
    users_status: dict[tuple[int, int], dict[Literal["cooldown_until","timeout_until"],int]] = {} #(guild_id, member_id) -> {}

    class AdminError(app_commands.CheckFailure): pass
    class GuildCooldown(app_commands.CheckFailure):
        def __init__(self, expire_at: float) -> None:
            self.expire_at: float = expire_at
    class UserCooldown(app_commands.CheckFailure):
        def __init__(self, expire_at: float) -> None:
            self.expire_at: float = expire_at

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
                raise cls.GuildCooldown(expire_at=expire_at)

            expire_at = get_user_status(interaction.user)
            if expire_at is not None:
                raise cls.UserCooldown(expire_at=expire_at)
            return True

        def get_guild_status(member: discord.Member) -> float | None:
            expire_at = cls.disabled_servers.get(member.guild.id)
            if expire_at is None:
                return None
            if expire_at <= time():
                cls.disabled_servers.pop(member.guild.id)
                return None
            return expire_at

        def get_user_status(member: discord.Member) -> float | None:
            key: tuple[int, int] = (member.guild.id, member.id)
            if key not in cls.users_status:
                return None
            cooldown_until = cls.users_status[key].get("cooldown_until")
            if cooldown_until is None:
                return None

            if cooldown_until <= time():
                del cls.users_status[key]["cooldown_until"]
                return None
            return cooldown_until

        return app_commands.check(predicate)

    @staticmethod
    def format_message(message: str, author: discord.User | discord.Member | None = None, target: discord.User | discord.Member | None = None) -> str:
        mapper = {"k": "*autor*", "u": "*objetivo*"}

        if author is not None:
            mapper["k"] = author.display_name
        if target is not None:
            mapper["u"] = target.mention

        return Template(message).safe_substitute(mapper)

class Loader:
    state_path = "state.pkl"
    tmp_path = "state.pkl.tmp"

    @staticmethod
    async def purge_expired_entries(d: dict) -> dict:
        out: dict = {}
        current_time = time()
        for key, value in d.items():
            if value > current_time:
                out[key] = value
        return out

    @staticmethod
    async def purge_expired_nested_entries(d: dict[Any, dict]) -> dict:
        out: dict = {}
        current_time = time()
        for key, nested_dict in d.items():
            max_value = max(nested_dict.values())
            if max_value > current_time:
                out[key] = nested_dict
        return out

    @classmethod
    async def process_temp_dicts(cls):
        if not os.path.isfile(cls.state_path):
            return OrderedDict(), {}, {}

        with open(cls.state_path, 'rb') as f:
            try:
                data = pickle.load(f)
            except EOFError:
                return OrderedDict(), {}, {}

            return (
                data.get("local_db",OrderedDict()),
                await cls.purge_expired_entries(data.get("disabled_servers", {})),
                await cls.purge_expired_nested_entries(data.get("users_status", {}))
            )

    @classmethod
    async def load_temp_dicts(cls) -> None:
        database.local_db,Utility.disabled_servers,Utility.users_status = await cls.process_temp_dicts()
        return

    @classmethod
    def save_temp_dicts(cls, signum, frame) -> None:
        data = {"local_db":database.local_db,"disabled_servers":Utility.disabled_servers,"users_status":Utility.users_status}
        with open(cls.tmp_path, 'wb') as f:
            pickle.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(cls.tmp_path, cls.state_path)
        sys.exit(0)


signal.signal(signal.SIGTERM, Loader.save_temp_dicts)
signal.signal(signal.SIGINT, Loader.save_temp_dicts)
create_logger()