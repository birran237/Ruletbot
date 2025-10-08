import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
from dotenv import load_dotenv
from utility import Utility

log = logging.getLogger(__name__)

database_error = None
try:
    import database
except Exception as e:
    database_error = e


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
        self.director_guild = None


    async def setup_hook(self):
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                log.info(f'Loaded cog {filename[:-3]}')



    async def on_ready(self):
        log.info(f'Logged in as {self.user.name} (ID: {self.user.id})')

        global database_error
        if database_error is not None:
            raise SystemExit(f"The database failed with error: {database_error}")

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
        await self.director_guild.system_channel.send(f"The bot successfully reloaded/updated")
        Utility.director_guild = self.director_guild

    @staticmethod
    async def on_guild_remove(guild):
        await database.del_guild_database(guild.id)
        log.debug(f'Guild {guild.name} has been deleted')


async def error_handler(interaction: discord.Interaction, error: app_commands.errors) -> None:
    if isinstance(error, Utility.AdminError):
        await interaction.response.send_message("Para ejectuar este comando necesitas permisos de administrador",ephemeral=True)
        return

    log.error(f"There was an error with command {interaction.command}: {error}")

bot = Bot()
bot.tree.on_error = error_handler

@app_commands.command(description="Sincronizar el arbol de comandos global")
async def sync_tree(interaction: discord.Interaction):
    synced = await bot.tree.sync()
    await interaction.response.send_message(f"Successfully synced {len(synced)} commands")


if __name__ == "__main__":
    bot.run(token)