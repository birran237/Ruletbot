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
    minutes = await database.get_guild_timeout(interaction.guild_id)
    if user.resolved_permissions.administrator:
        await user.move_to(channel=None, reason="Ha perdido")
    else:
        await user.timeout(timedelta(minutes=minutes), reason="Ha perdido")

async def tirar_rulet(interaction: discord.Interaction,persona:discord.Member):
    if interaction.user.id == persona.id or persona.bot:
        await interaction.response.send_message(f"{interaction.user.display_name} eres sumamente imbécil")
        return

    if bool(random.randint(0, 1)):
        await interaction.response.send_message(f"{interaction.user.display_name} ha retado a un duelo a {persona.mention} y ha ganado")
        await timeout(interaction, persona)
    else:
        await interaction.response.send_message(f"{interaction.user.display_name} ha retado a un duelo a {persona.mention} y ha perdido")
        await timeout(interaction, interaction.user)


@bot.event
async def on_ready():
    print(f"We are ready to go in, {bot.user.name}")
    await bot.change_presence(activity=discord.CustomActivity(name="Pegando escopetazos"))
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

@bot.tree.command(name="set_timeout", description="Configura los minutos de timeout de la rulet")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(minutos="Cantidad de minutos (1–60)")
async def set_timeout(interaction: discord.Interaction, minutos: int):
    if minutos < 1 or minutos > 60:
        await interaction.response.send_message("Debe estar entre 1 y 60 minutos.", ephemeral=True)
        return
    await database.set_guild_timeout(interaction.guild_id, minutos)
    await interaction.response.send_message(f"Tiempo de rulet configurado a {minutos} minutos", ephemeral=True)


webserver.keep_alive()
bot.run(token, log_handler=handler, log_level=logging.DEBUG)
#https://discord.com/oauth2/authorize?client_id=1391344171452727398&permissions=1099780065280&integration_type=0&scope=bot+applications.commands
