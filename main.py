import discord
from discord import app_commands
from discord.ext import commands
import logging
import random
from datetime import timedelta
from dotenv import load_dotenv
import os
import webserver

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f"We are ready to go in, {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)

@bot.tree.command(name="rulet", description="Retar a alguien a la rulet")
@app_commands.describe(persona="La persona a la que retaras a la rulet")
async def rulet(interaction: discord.Interaction, persona: discord.Member):
    if interaction.user.id == persona.id or persona.bot:
        await interaction.response.send_message(f"{interaction.user.display_name} eres sumamente imbécil")
        return

    if bool(random.randint(0, 1)):
        await interaction.response.send_message(f"{interaction.user.display_name} ha retado a un duelo a {persona.mention} y ha ganado")
        await persona.timeout(timedelta(minutes=5), reason="Ha perdido")
    else:
        await interaction.response.send_message(f"{interaction.user.display_name} ha retado a un duelo a {persona.mention} y ha ganado")
        await interaction.user.timeout(timedelta(minutes=5), reason="Ha perdido")
    await interaction.response.send_message(f"XD")
webserver.keep_alive()
bot.run(token, log_handler=handler, log_level=logging.DEBUG)
#https://discord.com/oauth2/authorize?client_id=1391344171452727398&permissions=1099780065280&integration_type=0&scope=bot+applications.commands