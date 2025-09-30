import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import logging
from random import randint
from datetime import timedelta
import os
from time import time

database_error = None
try:
    import database
except Exception as e:
    database_error = e

token = os.getenv('DISCORD_TOKEN')
if token is None:
    raise ValueError('DISCORD_TOKEN is not set')

intents = discord.Intents.default()
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
bot = commands.Bot(command_prefix='!', intents=intents)

director_guild_id:int = int(os.getenv('DIRECTOR_GUILD'))

async def tirar_rulet(interaction: discord.Interaction, user:discord.Member):
    if interaction.user.id == user.id or user.bot:
        await interaction.response.send_message(f"{interaction.user.display_name} creo que te amamantaron con RedBull")
        minutes = await database.get_from_database(guild_id=interaction.guild_id, field="timeout_minutes")
        await interaction.user.timeout(timedelta(minutes=minutes*5), reason="Es minguito el pobre")
        return

    disabled_time = get_disabled_status(interaction.guild_id)
    if disabled_time is not None:
        await interaction.response.send_message(f"{interaction.user.mention} he sido deshabilitado por los administradores hasta dentro de **{format_seconds(int(disabled_time))} {round(disabled_time%60)}s**.")
        return

    affect_admins = await database.get_from_database(guild_id=interaction.guild_id,field="annoy_admins")
    higher_role: bool = user.top_role >= interaction.guild.me.top_role

    if (user.resolved_permissions.administrator or higher_role) and not affect_admins:
        await interaction.response.send_message(f"{user.display_name} es un administrador y no le puedes retar", ephemeral=True)
        return

    if bool(randint(0, 1)):
        await timeout(interaction=interaction, user=user, higher_role=higher_role)
        await interaction.response.send_message(f"{interaction.user.display_name} ha retado a un duelo a {user.mention} y ha ganado")
        return

    await timeout(interaction=interaction, user=interaction.user, higher_role=higher_role)
    await interaction.response.send_message(f"{interaction.user.display_name} ha retado a un duelo a {user.mention} y ha perdido")
    return


async def timeout(interaction: discord.Interaction,user:discord.Member, higher_role:bool):
    minutes: int = await database.get_from_database(guild_id=interaction.guild_id,field="timeout_minutes")

    if user.resolved_permissions.administrator or higher_role:
        await user.move_to(channel=None, reason="Ha perdido")
        return

    if minutes == 0:
        await user.move_to(channel=None, reason="Ha perdido")
        return

    await user.timeout(timedelta(minutes=minutes), reason="Ha perdido")
    return

disabled_servers = {}
def get_disabled_status(guild_id: int) -> float | None:
    global disabled_servers
    expire_at = disabled_servers.get(guild_id)
    if not expire_at:
        return None
    remaining = expire_at - time()
    if remaining <= 0:
        disabled_servers.pop(guild_id, None)
        return None
    return remaining

def format_seconds(seconds:int)-> str:
     days, remainder = divmod(seconds, 60*60*24)
     hours, remainder = divmod(remainder, 60*60)
     minutes = remainder // 60
     parts = []
     if days:
        parts.append(f"{days}d")
        parts.append(f"{hours}h")
     elif hours:
        parts.append(f"{hours}h")
     parts.append(f"{minutes}m")

     return ' '.join(parts)


@bot.event
async def on_ready():
    director_guild = bot.get_guild(director_guild_id)
    if database_error is not None:
        await director_guild.system_channel.send(f"The database failed with error: {database_error}")
        print(f"The database failed with error: {database_error}")
        exit(1)
    await director_guild.system_channel.send(f"The bot successfully reloaded/updated")
    print(f"We are ready to go in, {bot.user.name}")
    await bot.tree.sync(guild=discord.Object(director_guild_id))

@bot.event
async def on_guild_remove(guild:discord.Guild):
    await database.del_guild_database(guild.id)

@bot.tree.command(guild=discord.Object(director_guild_id), description="Sincronizar el arbol de comandos global")
async def sync_tree(interaction: discord.Interaction):
    await bot.change_presence(activity=discord.CustomActivity(name="Pegando escopetazos"))
    bot.tree.add_command(SetGroup(name="set", description="Configuración del bot"))
    synced = await bot.tree.sync()
    await interaction.response.send_message(f"Succesfully synced {len(synced)} commands")

@bot.tree.command(name="rulet", description="Retar a alguien a la rulet")
@app_commands.describe(persona="La persona a la que retaras a la rulet")
async def rulet(interaction: discord.Interaction, persona: discord.Member):
    await tirar_rulet(interaction, persona)

@bot.tree.context_menu(name="Retar a la rulet")
async def rulet_context(interaction: discord.Interaction, persona: discord.Member):
    await tirar_rulet(interaction, persona)



@bot.tree.command(name="disable",description="Deshabilita el bot durante los minutos especificados")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(minutes="Cantidad de minutos (deja en 0 para habilitar el bot instantaniamente)")
async def disable(interaction: discord.Interaction, minutes: app_commands.Range[float, 0, 10080]):
    global disabled_servers
    if minutes == 0:
        disabled_servers.pop(interaction.guild_id, None)
        await interaction.response.send_message(f"El bot vuelve a funcionar correctamente", ephemeral=True)
        return
    expire_at = time() + (minutes * 60)
    disabled_servers[interaction.guild_id] = expire_at
    await interaction.response.send_message(f"El bot no funcionará hasta dentro de **{format_seconds(int(minutes*60))}**",ephemeral=True)

    async def enable():
        await asyncio.sleep(minutes*60)
        if disabled_servers.get(interaction.guild_id) == expire_at:
            del disabled_servers[interaction.guild_id]

    asyncio.create_task(enable())

class SetGroup(app_commands.Group):
    @app_commands.command(name="timeout", description="Configura los minutos de timeout de la rulet (deja en blanco para saber la configuración actual)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(minutes="Cantidad de minutos (1–60)")
    async def set_timeout(self, interaction: discord.Interaction, minutes: app_commands.Range[int, 0, 60] = None):
        if minutes is None:
            db_minutes = await database.get_from_database(guild_id=interaction.guild_id, field="timeout_minutes")
            await interaction.response.send_message(f"Ahora mismo la rulet está configurada para {db_minutes} minutos", ephemeral=True)
            return

        await database.save_to_database(guild_id=interaction.guild_id,field="timeout_minutes", data=minutes)
        await interaction.response.send_message(f"Tiempo de rulet configurado a {minutes} minutos", ephemeral=True)

    @app_commands.command(name="annoy_admins", description="Elige si afecta o no a los roles superiores (deja en blanco para saber la configuración actual)")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_annoy_admins(self, interaction: discord.Interaction, affect_admins: bool | None = None):
        if affect_admins is None:
            db_affect_admins = await database.get_from_database(guild_id=interaction.guild_id,field="affect_admins")
            message_mod = "también" if db_affect_admins else "no"
            await interaction.response.send_message(f"La ruleta {message_mod} afecta a los roles superiores y a los administradores", ephemeral=True)
            return

        await database.save_to_database(guild_id=interaction.guild_id, field="annoy_admins", data=affect_admins)
        message_mod = "también" if affect_admins else "ya no"
        await interaction.response.send_message(f"A partir de ahora la ruleta {message_mod} afectará a los roles superiores ni a administradores",ephemeral=True)

if __name__ == "__main__":
    bot.run(token, log_handler=handler, log_level=logging.DEBUG)