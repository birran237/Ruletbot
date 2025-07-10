import discord
from discord import app_commands
from discord.ext import commands
import logging
import random
from datetime import timedelta
from dotenv import load_dotenv
import os
import webserver
import database

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()

bot = commands.Bot(command_prefix='!', intents=intents)

async def timeout(interaction: discord.Interaction,user:discord.Member):
    minutes: int = await database.get_from_database(guild_id=interaction.guild_id, field="timeout_minutes", default=5)
    affect_admins: bool = await database.get_from_database(guild_id=interaction.guild_id, field="annoy_admins", default=True)
    higher_role: bool = user.top_role >= interaction.guild.me.top_role
    if not user.resolved_permissions.administrator and not higher_role:
        await user.timeout(timedelta(minutes=minutes), reason="Ha perdido")
        return
    if higher_role and affect_admins:
        return
    await user.move_to(channel=None, reason="Ha perdido")


async def tirar_rulet(interaction: discord.Interaction, user:discord.Member):
    if interaction.user.id == user.id or user.bot:
        await interaction.response.send_message(f"{interaction.user.display_name} eres sumamente imbécil")
        await user.timeout(timedelta(minutes=10), reason="Es minguito el pobre")
        return

    if bool(random.randint(0, 1)):
        await interaction.response.send_message(f"{interaction.user.display_name} ha retado a un duelo a {user.mention} y ha ganado")
        await timeout(interaction, user)
    else:
        await interaction.response.send_message(f"{interaction.user.display_name} ha retado a un duelo a {user.mention} y ha perdido")
        await timeout(interaction, interaction.user)


@bot.event
async def on_ready():
    print(f"We are ready to go in, {bot.user.name}")
    await bot.change_presence(activity=discord.CustomActivity(name="Pegando escopetazos"))
    bot.tree.add_command(SetGroup(name="set",description="Configuración del bot"))
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} commands")

@bot.event
async def on_guild_remove(guild:discord.Guild):
    await database.del_guild_database(guild.id)

@bot.tree.command(name="rulet", description="Retar a alguien a la rulet")
@app_commands.describe(persona="La persona a la que retaras a la rulet")
async def rulet(interaction: discord.Interaction, persona: discord.Member):
    await tirar_rulet(interaction, persona)

@bot.tree.context_menu(name="Retar a la rulet")
async def rulet_context(interaction: discord.Interaction, persona: discord.Member):
    await tirar_rulet(interaction, persona)

class SetGroup(app_commands.Group):
    @app_commands.command(name="timeout", description="Configura los minutos de timeout de la rulet")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(minutes="Cantidad de minutos (1–60)")
    async def set_timeout(self, interaction: discord.Interaction, minutes: int):
        if minutes < 1 or minutes > 60:
            await interaction.response.send_message("Debe estar entre 1 y 60 minutos.", ephemeral=True)
            return
        await database.save_to_database(guild_id=interaction.guild_id,field="timeout_minutes", data=minutes)
        await interaction.response.send_message(f"Tiempo de rulet configurado a {minutes} minutos", ephemeral=True)

    @app_commands.command(name="annoy_admins", description="Elige si afecta o no a los roles superiores")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_annoy_admins(self, interaction: discord.Interaction, affect_admins: bool):
        await database.save_to_database(guild_id=interaction.guild_id, field="annoy_admins", data=affect_admins)
        if affect_admins:
            await interaction.response.send_message(f"A partir de ahora la ruleta tambien afectará a los roles superiores", ephemeral=True)
        else:
            await interaction.response.send_message(f"A partir de ahora la ruleta ya no afectará a los roles superiores", ephemeral=True)


webserver.keep_alive()
bot.run(token, log_handler=handler, log_level=logging.DEBUG)
#https://discord.com/oauth2/authorize?client_id=1391344171452727398&permissions=1099528407040&integration_type=0&scope=applications.commands+bot