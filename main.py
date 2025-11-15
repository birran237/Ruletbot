from time import time
import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
import signal
import sys
import json
from dotenv import load_dotenv
from utility import Utility
import database
from collections import OrderedDict

log = logging.getLogger(__name__)

load_dotenv()
token = os.getenv('DISCORD_TOKEN')
if token is None:
    raise ValueError('DISCORD_TOKEN is not set')

def load_temp_dicts():
    if not os.path.isfile('temp.json'):
        return OrderedDict(), {}, {}, {}
    def str_keys_to_int(d: dict) -> dict:
        out: dict = {}
        for k, v in d.items():
            try:
                ik = int(k)
            except (ValueError, TypeError): continue
            out[ik] = v
        return out

    with open('temp.json', 'r') as f:
        data = json.load(f)
        return (
            OrderedDict(data.get("local_db",{})),
            str_keys_to_int(data.get("disabled_servers",{})),
            str_keys_to_int(data.get("disabled_users",{})),
            str_keys_to_int(data.get("timeouted_admins", {}))
        )

database.local_db,Utility.disabled_servers,Utility.disabled_users, Utility.timeouted_admins = load_temp_dicts()

def save_temp_dicts(signum, frame):
    data = {"local_db":database.local_db,"disabled_servers":Utility.disabled_servers,"disabled_users":Utility.disabled_users, "timeouted_admins":Utility.timeouted_admins}
    with open('temp.json', 'w') as f:
        json.dump(data, f)
    sys.exit(0)

signal.signal(signal.SIGTERM, save_temp_dicts)
signal.signal(signal.SIGINT, save_temp_dicts)


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix='!', intents=intents)
        self.help_command = None
        self.activity = discord.CustomActivity(name="Pegando escopetazos")
        self.director_guild = None


    async def setup_hook(self):
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                log.info(f'Loaded cog {filename[:-3]}')


    async def on_ready(self):
        log.info(f'Logged in as {self.user.name} (ID: {self.user.id})')

        try:
            director_guild_id: int | None = int(os.getenv('DIRECTOR_GUILD'))
        except TypeError:
            director_guild_id = None

        if director_guild_id is None:
            return

        self.director_guild = self.get_guild(director_guild_id)
        if self.director_guild is None:
            await self.tree.sync()
            log.info(f'Synced global commands')
            return

        self.tree.add_command(sync_tree, guild=self.director_guild)
        await self.tree.sync(guild=self.director_guild)
        log.info(f'Guild {self.director_guild.name} has been synced')
        await self.director_guild.system_channel.send(f"The bot successfully reloaded/updated with {len(database.local_db)} local server(s), {len(Utility.disabled_servers)} disabled server(s), {len(Utility.disabled_users)} disabled user(s) and {len(Utility.timeouted_admins)} timeouted admin(s).")
        Utility.director_guild = self.director_guild

    @staticmethod
    async def on_guild_remove(guild):
        await database.del_guild_database(guild.id)
        log.debug(f'Guild {guild.name} has been deleted')

    @staticmethod
    async def on_voice_state_update(member, before, after):
        if before.channel is not None:
            return

        key: tuple[int, int] = (member.guild.id, member.id)
        if key not in Utility.timeouted_admins:
            return

        remaining: float = Utility.timeouted_admins.get(key, 0) - time()
        if remaining <= 0:
            Utility.timeouted_admins.pop(key)
            return
        await member.move_to(channel=None, reason="Ha perdido")

async def error_handler(interaction: discord.Interaction, error: app_commands.errors) -> None:
    if isinstance(error, Utility.AdminError):
        await interaction.response.send_message("Para ejectuar este comando necesitas permisos de administrador", ephemeral=True)
        return

    if isinstance(error, Utility.GuildCooldown):
        time = Utility.format_seconds(error.retry_after)
        await interaction.response.send_message(f"He sido deshabilitado por los administradores hasta dentro de **{time}**", ephemeral=True)
        return

    if isinstance(error, Utility.UserCooldown):
        time = Utility.format_seconds(error.retry_after)
        await interaction.response.send_message(f"Has retado a alguien recientemente y has perdido, no podras usar la rulet hasta dentro de **{time}**", ephemeral=True)
        return

    if interaction is None:
        return
    def param_string(parameter, namespace: discord.Interaction.namespace) -> str:
        if namespace is None:
            return f'{parameter}: Unknown'
        return f"{parameter}: {getattr(namespace, parameter)}"

    try:
        await interaction.response.send_message("Ha ocurrido un error inesperado, vuelve a intentarlo más tarde",ephemeral=True)
        parameters = [param_string(i.name, interaction.namespace) for i in interaction.command.parameters] if hasattr(interaction.command, 'parameters') else []
    except Exception as mssg_error:
        message = f"There was an error and in its handling this error ocurred: **{mssg_error}**"
    else:
        message = f"There was an error in guild **{interaction.guild}({interaction.guild_id})** by user **{interaction.user.display_name}({interaction.user.id})** with command /{interaction.command.qualified_name} {', '.join(parameters)}: **{error}**"

    log.error(message)
    if bot.director_guild is not None:
        await bot.director_guild.system_channel.send(message)


bot = Bot()
bot.tree.on_error = error_handler

@app_commands.command(description="Sincronizar el arbol de comandos global")
async def sync_tree(interaction: discord.Interaction):
    synced = await bot.tree.sync()
    await interaction.response.send_message(f"Successfully synced {len(synced)} commands")


if __name__ == "__main__":
    bot.run(token)