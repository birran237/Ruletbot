from utility import Utility, Loader, PageView, CLEANUP_TASKS
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

    async def setup_hook(self):
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                log.info(f'Loaded cog {filename[:-3]}')


    async def on_ready(self):
        log.info(f'Logged in as {self.user.name} (ID: {self.user.id})')
        asyncio.create_task(Loader.cleanup_expired_entries())

        try:
            director_guild_id: int | None = int(os.getenv('DIRECTOR_GUILD'))
        except TypeError:
            director_guild_id = None

        if director_guild_id is None:
            return

        self.director_guild = self.get_guild(director_guild_id)
        if self.director_guild is None:
            await self.fetch_guild(director_guild_id)
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
            if after.channel is None:
                await handle_leave_vc(member)
            return

        key: tuple[int, int] = (member.guild.id, member.id)
        if key not in Utility.users_status:
            Utility.users_status[key] = {}

        if await check_force_timeout(member):
            await member.move_to(channel=None, reason="Ha perdido")
            return

        if 'vc_rulet_available' not in Utility.users_status[key]:
            #user will be able to use the rulet in 5 minutes after joining vc
            Utility.users_status[key]['vc_rulet_available'] = int(time() + 5*60)

async def handle_leave_vc(member: discord.Member) -> None:
    key: tuple[int, int] = (member.guild.id, member.id)
    if key not in Utility.users_status[key]:
        return
    user_status = Utility.users_status[key]
    if "vc_rulet_available" not in user_status or user_status.get("vc_rulet_available", 0) < time():
        return
    db = await database.get_from_database(member.guild.id)

    task_key = ("vc_hold", key)
    if task_key in CLEANUP_TASKS:
        existing_task = CLEANUP_TASKS[task_key]
        if not existing_task.done():
            existing_task.cancel()

    # Create and store the new task
    hold_time = db["timeout_seconds"] + 60
    Utility.users_status[key]["vc_rulet_hold"] = int(hold_time + time())
    task = asyncio.create_task(_handle_leave_vc_internal(member, hold_time))
    CLEANUP_TASKS[task_key] = task

async def _handle_leave_vc_internal(member: discord.Member, hold_time: int) -> None:
    key: tuple[int,int] = (member.guild.id, member.id)
    while True:
        await asyncio.sleep(hold_time)
        if key not in Utility.users_status[key]:
            return
        if Utility.users_status[key].get("vc_rulet_hold", 0) < time() + hold_time:
            Utility.users_status[key].pop("vc_rulet_hold", 0)
            Utility.users_status[key].pop("vc_rulet_available", 0)
            return
        hold_time = int(Utility.users_status[key].get("vc_rulet_hold", 0) - time())

async def check_force_timeout(member: discord.Member) -> bool:
    if not member.guild_permissions.administrator and member.top_role < member.guild.me.top_role and member != member.guild.owner:
        return False

    key: tuple[int, int] = (member.guild.id, member.id)
    if "timeout_until" not in Utility.users_status[key]:
        return False
    remaining: float = Utility.users_status[key].get("timeout_until", 0) - time()
    if remaining <= 0:
        Utility.users_status[key].pop("timeout_until", 0)
        return False
    db = await database.get_from_database(member.guild.id)
    if db['annoy_admins'] == 0:
        Utility.users_status[key].pop("timeout_until", 0)
        return False
    return True

async def error_handler(interaction: discord.Interaction, error: app_commands.errors) -> None:
    if isinstance(error, Utility.GuildCooldown):
        await interaction.response.send_message(f"He sido deshabilitado por los administradores hasta <t:{error.expire_at}:R>", ephemeral=True)
        return

    if isinstance(error, Utility.UserCooldown):
        message = f"Has retado a alguien recientemente y has perdido, no podras usar la rulet hasta <t:{error.expire_at}:R>"
        if error.expire_at:
            message += " (cooldown extra por retar a una persona y perder)"
        await interaction.response.send_message(message, ephemeral=True)
        return

    if isinstance(error, app_commands.TransformerError):
        await interaction.response.send_message("Este usuario no esta en el servidor (que coño habeis hecho)",ephemeral=True)
        return

    if isinstance(error, Utility.GuildCheckFailure):
        await interaction.response.send_message("Este comando solo puede usarse en servidores", ephemeral=True)
        return

    if isinstance(error, Utility.MissingPerms):
        missing_list = ", ".join(error.missing_perms)
        await interaction.response.send_message(f"Necesito estos permisos como mínimo para funcionar correctamente: {missing_list}", ephemeral=True)

    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("Para ejecutar este comando necesitas permisos de administrador", ephemeral=True)
        return

    error_message = await get_command_error(interaction, error)
    log.error(error_message)
    if bot.director_guild is not None:
        await bot.director_guild.system_channel.send(error_message)

async def get_command_error(interaction: discord.Interaction | None, error: app_commands.errors) -> str:
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
        if isinstance(interaction.guild, discord.Guild) and isinstance(interaction.user, discord.abc.User):
            return f"There was an error in guild **{interaction.guild}({interaction.guild.id})** by user **{interaction.user.display_name}({interaction.user.id})**: **{error}**"
        return f"There was an error and in its handling this error ocurred: **{mssg_error}**"

    return f"There was an error in guild **{interaction.guild}({interaction.guild_id})** by user **{interaction.user.display_name}({interaction.user.id})** with command /{interaction.command.qualified_name} {', '.join(parameters)}: **{error}**"

async def interaction_check(interaction: discord.Interaction) -> bool:
    # Check if we're in a guild
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        raise Utility.GuildCheckFailure()
    return True

bot = Bot()
bot.tree.on_error = error_handler
bot.tree.interaction_check = interaction_check

@app_commands.command(description="Sincronizar el arbol de comandos global")
async def sync_tree(interaction: discord.Interaction):
    synced = await bot.tree.sync()
    await interaction.response.send_message(f"Successfully synced {len(synced)} commands")

@app_commands.command(description="Borrar la base de datos local")
@app_commands.describe(variable="Variable a eliminar")
async def erase_local_variables(interaction: discord.Interaction, variable: Literal["local_db","disabled_servers","disabled_users", "all", "none"]):
    match variable:
        case "none":
            await interaction.response.send_message(f"Hay {len(database.local_db)} elementos de la base de datos local, {len(Utility.disabled_servers)} elementos de los servidores deshabilitados y {len(Utility.users_status)} elementos de los usuarios deshabilitados")
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
    pages = [
        discord.Embed(title="General", color=discord.Color.blue(),description=(
                "Al usar el comando `/rulet` con un usuario, hay un 50% de que pierdas, y un 50% de que ganes. "
                f"Al ganador no le pasará nada, pero el perdedor será aislado temporalmente por *{Utility.format_seconds(db['timeout_seconds'])}*. "
                "La configuración puede ser modificada por miembros con permiso de administrador."
            ),
        ), discord.Embed(title="Rulet", color=discord.Color.blue(), description=(
                "Al retar a alguien con `/rulet`, si tienes suerte y ganas el objetivo recibirá un timeout, mientras que tú podrás seguir escribiendo, hablando sin ningún problema e incluso hacer más rulets. "
                f"En caso de que pierdas, recibirás un timeout de *{Utility.format_seconds(db['timeout_seconds'])}*, y no podrás hacer rulet hasta que pasen *{Utility.format_seconds(db['lose_cooldown'])}* de cooldown. "
                "Si te retan a ti y pierdes recibirás el timeout igual, pero ningún cooldown del comando"
            ),
        ),
        ]
    if not interaction.user.resolved_permissions.administrator:
        await interaction.response.send_message(embed=pages[0], view=PageView(pages), ephemeral=True)
        return
    pages.extend([
        discord.Embed(title="Moderación - general", color=discord.Color.red(), description=(
                "Puedes modificar los ajustes del bot usando `/set ...` para modificar los ajustes como el tiempo de timeout o el cooldown tras perder un duelo, y el comando `/customize ...` para personalizar los mensajes del bot. "
                "También se puede usar el comando `/disable (minutos)` para desactivar el bot por un cierto tiempo (máximo 1 mes). "
                "Para restablecer el bot a los ajustes por defecto usa `/set default`."
                "Esos tres comandos y las pestañas de moderación del comando `/help` solo lo podrán ver los usuarios que tengan el permiso de administrador.\n \n"
                "**Importante:** Por defecto solo podrán usar el bot los miembros que su rol máximo esté por encima del rol propio del bot `Rulet bot`. "
                "Modificando la jerarquía del rol `Rulet bot` puedes configurar que personas serán afectadas y cuales no (más información en la siguiente pestaña)."
            ),
        ), discord.Embed(title="Moderación - /set annoy_admins", color=discord.Color.red(), description=(
                "Con `/set annoy_admins 0/1/2`, puedes modificar quien podrá retar a alguien a un duelo.\n"
                "- **0 →** Las personas por encima del rol `Rulet bot` no seran afectados por la ruleta (por defecto)\n "
                "- **1 →** Solo se podrá retar a las personas por debajo de tu rol máximo (o todo el mundo que esté por debajo del rol `Rulet bot` sin importar la jerarquía). Todos los perdedores recibirán un timeout\n"
                "- **2 →** Todo el mundo podrá ser victima de la ruleta, sin importar la jerarquía"
            ),
        ), discord.Embed(title="Moderación - /customize", color=discord.Color.red(), description=(
                "Puedes modificar los mensajes que envia el bot para customizarlos como quieras. "
                "Cierta información como los nombres de los involucrados se pueden inserir como parametros. "
                "Por ejemplo, $k se sustituirá por el nombre del autor, y $u por el del objetivo (no es necesario usarlos todos). "
                "Si añades un link de una imagen o de un gif al final ese también se mostrará. "
            ),
        ),
    ])
    await interaction.response.send_message(embed=pages[0], view=PageView(pages), ephemeral=True)

if __name__ == "__main__":
    bot.run(token)