from utility import Utility, Loader
import database
import discord
from discord.ext import commands, tasks
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
        if not purge_expired_variables.is_running():
            purge_expired_variables.start()

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

    @staticmethod
    async def on_guild_remove(guild):
        await database.del_guild_database(guild.id)
        if guild.id in Utility.disabled_servers:
            del Utility.disabled_servers[guild.id]
        log.debug(f'Guild {guild.name} has been deleted')

    @staticmethod
    async def on_voice_state_update(member, before, after):
        if before.channel is not None:
            return

        if not member.guild_permissions.administrator and member.top_role < member.guild.me.top_role:
            return

        key: tuple[int, int] = (member.guild.id, member.id)
        if key not in Utility.users_status:
            return
        if "timeout_until" not in Utility.users_status[key]:
            return
        remaining: float = Utility.users_status[key].get("timeout_until", 0) - time()
        if remaining <= 0:
            del Utility.users_status[key]["timeout_until"]
            return
        await member.move_to(channel=None, reason="Ha perdido")

async def error_handler(interaction: discord.Interaction, error: app_commands.errors) -> None:
    if isinstance(error, Utility.GuildCooldown):
        await interaction.response.send_message(f"He sido deshabilitado por los administradores hasta <t:{error.expire_at}:R>", ephemeral=True)
        return

    if isinstance(error, Utility.UserCooldown):
        message = f"Has retado a alguien recientemente y has perdido, no podras usar la rulet hasta <t:{error.expire_at}:R>"
        if error.expire_at:
            message += " (cooldown extra por retar a una persona y perder o por retar a alguien dentro de llamada estando fuera de un canal de voz)"
        await interaction.response.send_message(message, ephemeral=True)
        return

    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("Para ejectuar este comando necesitas poder aislar temporalmente a miembros", ephemeral=True)
        return

    error_message = await get_command_error(interaction, error)
    log.error(error_message)
    if bot.director_guild is not None:
        await bot.director_guild.system_channel.send(error_message)

async def get_command_error(interaction: discord.Interaction, error: app_commands.errors) -> str:
    if interaction is None:
        return f"There was an error without an interaction"
    def param_string(parameter, namespace: discord.Interaction.namespace) -> str:
        if namespace is None:
            return f'{parameter}: Unknown'
        return f"{parameter}: {getattr(namespace, parameter)}"

    try:
        await interaction.response.send_message("Ha ocurrido un error inesperado, vuelve a intentarlo más tarde",ephemeral=True)
        parameters = [param_string(i.name, interaction.namespace) for i in interaction.command.parameters] if hasattr(interaction.command, 'parameters') else []
    except Exception as mssg_error:
        return f"There was an error and in its handling this error ocurred: **{mssg_error}**"

    return f"There was an error in guild **{interaction.guild}({interaction.guild_id})** by user **{interaction.user.display_name}({interaction.user.id})** with command /{interaction.command.qualified_name} {', '.join(parameters)}: **{error}**"

async def check_bot_permissions(interaction: discord.Interaction) -> bool:
    perms = interaction.guild.me.resolved_permissions
    missing = []
    if not perms.send_messages:
        missing.append('Enviar mensajes')
    if not perms.moderate_members:
        missing.append('Aislar temporalmente a miembros')
    if not perms.move_members:
        missing.append('Mover miembros')
    if missing:
        await interaction.response.send_message(f"**No tengo suficientes permisos para funcionar correctamente,** pide a un administrador que me de los siguientes permisos:\n{', '.join(missing)}",ephemeral=True)
        raise Utility.MissingBotPermissions
    return True

bot = Bot()
bot.tree.on_error = error_handler
bot.tree.interaction_check = check_bot_permissions

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

@bot.tree.command(description="Explicación sobre el funcionamiento del bot", name="help")
async def help_command(interaction: discord.Interaction):
    db = await database.get_from_database(interaction.guild.id)
    message = f"Al usar el comando `/rulet` con un usuario, hay un 50% de que pierdas, y un 50% de que ganes. Al ganador no le pasará nada, pero el perdedor será aislado temporalmente por `{Utility.format_seconds(db['timeout_seconds'])}`. Si TÚ retas a alguien y pierdes, no podrás usar el bot por `{Utility.format_seconds(db['timeout_seconds'] + db['lose_cooldown'])}`. Se pueden aplicar penalizaciones extra por perder contra un usuario dentro de un chat de voz, estando tu fuera de uno. La configuración puede ser modificada por miembros con permiso de administrador"
    if interaction.user.resolved_permissions.administrator:
        message += f"\n \n**Información para administradores:** podeis modificar los ajustes del bot usando `/set ...` para modificar los ajustes como el tiempo de timeout o si la ruleta puede afectar a administradores (actualmente `{'si' if db['annoy_admins'] else 'no'}`) y el comando `/customize ...` para personalizar los mensajes del bot. Por ejemplo: `/customize win $k ha retado a $u y ha ganado` (más información en la descripción del comando). También se puede usar el comando `/disable (minutos)` para desactivar el bot por un cierto tiempo (màximo 1 mes)"
    if interaction.user.resolved_permissions.administrator and not db['annoy_admins']:
        message += f"\n \n**Importante:** ningun usuario podrá retar a alguien o con el permiso de administrador, o que en la jerarquía de roles esté por encima del rol propio del bot (no su rol màximo). Para que el bot afecte a todos use el comando `/set annoy_admins True`"
    await interaction.response.send_message(message, ephemeral=True)

@tasks.loop(hours=24)
async def purge_expired_variables():
    Utility.disabled_servers = await Loader.purge_expired_entries(Utility.disabled_servers)
    Utility.users_status = await Loader.purge_expired_nested_entries(Utility.users_status)

if __name__ == "__main__":
    bot.run(token)