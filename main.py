import discord
from discord import app_commands
from discord.ext import commands
import logging
import random
import asyncio
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

@bot.tree.command(name="rulet", description="Retar a alguine a la rulet")
@app_commands.describe(persona="La persona a la que retaras a la rulet")
async def rulet(interaction: discord.Interaction, persona: discord.Member):
    await interaction.response.send_message(f"{interaction.user.display_name} ha retado a la rulet a {persona.mention}")
    await asyncio.sleep(2)

    if interaction.user.id == persona.id or persona.bot or persona.resolved_permissions.moderate_members:
        await interaction.followup.send(f"{interaction.user.display_name} eres sumamente imbécil")
        return

    if random.randint(0,1) == 1:
        await interaction.followup.send(f"Ha perdido {persona.display_name}")
        await persona.timeout(timedelta(minutes=5), reason="Ha perdido")
    else:
        await interaction.followup.send(f"Ha perdido {interaction.user.display_name}")
        await interaction.user.timeout(timedelta(minutes=5), reason="Ha perdido")

webserver.keep_alive()
bot.run(token, log_handler=handler, log_level=logging.DEBUG)
#https://discord.com/oauth2/authorize?client_id=1391344171452727398&permissions=1099780065280&integration_type=0&scope=bot+applications.commands