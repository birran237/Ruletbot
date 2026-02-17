from utility import Utility, Loader
import database
import discord
from discord.ext import commands
from discord import app_commands
from time import time
import logging, os, asyncio
from dotenv import load_dotenv
from typing import Literal
from collections import OrderedDict

log = logging.getLogger(__name__)

load_dotenv()
token = os.getenv('DISCORD_TOKEN')
if token is None:
    raise ValueError('DISCORD_TOKEN is not set')


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix='!', intents=intents)
        self.help_command = None
        self.activity = discord.CustomActivity(name="Pegando escopetazos")
        self.director_guild: discord.Guild | None = None
        self.loader_coro: asyncio.Task | None = None

    def run(self, func_token:str, reconnect:bool = True, *args, **kwargs) -> None:
        async def runner():
            self.loader_coro = asyncio.create_task(Loader.load_temp_dicts())
            async with self:
                await self.start(func_token, reconnect=reconnect)

        asyncio.run(runner())

    async def setup_hook(self):
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                log.info(f'Loaded cog {filename[:-3]}')


    async def on_ready(self):
        log.info(f'Logged in as {self.user.name} (ID: {self.user.id})')
        await self.loader_coro

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
        self.tree.add_command(erase_local_variables, guild=self.director_guild)
        await self.tree.sync(guild=self.director_guild)
        log.info(f'Guild {self.director_guild.name} has been synced')
        await self.director_guild.system_channel.send(f"The bot successfully reloaded/updated with {len(database.local_db)} local server(s), {len(Utility.disabled_servers)} disabled server(s) and {len(Utility.users_status)} disabled user(s)")
        Utility.director_guild = self.director_guild

    @staticmethod
    async def on_guild_remove(guild):
        await database.del_guild_database(guild.id)
        log.debug(f'Guild {guild.name} has been deleted')

    @staticmethod
    async def on_voice_state_update(member, before, after):
        if before.channel is not None:
            return

        if not member.guild_permissions.administrator or member.top_role < member.guild.me.top_role:
            return

        key: tuple[int, int] = (member.guild.id, member.id)
        if key not in Utility.users_status:
            return

        remaining: float = Utility.users_status[key].get("timeout_until", 0) - time()
        if remaining <= 0:
            del Utility.users_status[key]["timeout_until"]
            return
        await member.move_to(channel=None, reason="Ha perdido")

async def error_handler(interaction: discord.Interaction, error: app_commands.errors) -> None:
    if isinstance(error, Utility.AdminError):
        await interaction.response.send_message("Para ejectuar este comando necesitas permisos de administrador", ephemeral=True)
        return

    if isinstance(error, Utility.GuildCooldown):
        await interaction.response.send_message(f"He sido deshabilitado por los administradores hasta <t:{error.expire_at}:R>", ephemeral=True)
        return

    if isinstance(error, Utility.UserCooldown):
        await interaction.response.send_message(f"Has retado a alguien recientemente y has perdido, no podras usar la rulet hasta <t:{error.expire_at}:R>", ephemeral=True)
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

@app_commands.command(description="Borrar la base de datos local")
@app_commands.describe(variable="Variable a eliminar")
async def erase_local_variables(interaction: discord.Interaction, variable: Literal["local_db","disabled_servers","disabled_users", "all"]):
    match variable:
        case "all":
            database.local_db, Utility.disabled_servers, Utility.users_status = OrderedDict(), {}, {}
            await interaction.response.send_message(f"Se ha reseteado toda la base de datos local")
        case "local_db":
            await interaction.response.send_message(f"Se han eliminado {len(database.local_db)} elementos de la base de datos local")
            database.local_db = OrderedDict()
        case "disabled_servers":
            await interaction.response.send_message(f"Se han eliminado {len(Utility.disabled_servers)} elementos de los servidores deshabilitados")
            Utility.disabled_servers = {}
        case "disabled_users":
            await interaction.response.send_message(f"Se han eliminado {len(Utility.users_status)} elementos de los usuarios deshabilitados")
            Utility.users_status = {}


if __name__ == "__main__":
    bot.run(token)