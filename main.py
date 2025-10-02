import discord
from discord.ext import commands
import logging
import os
from dotenv import load_dotenv

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

        try:
            director_guild_id: int = int(os.getenv('DIRECTOR_GUILD'))
        except TypeError:
            self.director_guild = None
        else:
            self.director_guild = self.get_guild(director_guild_id)


    async def setup_hook(self):
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                logging.info(f'Loaded cog {filename[:-3]}')


        if self.director_guild is not None:
            self.tree.copy_global_to(guild=self.director_guild)
            await self.tree.sync(guild=self.director_guild)

            logging.info(f'Guild {self.director_guild.name} has been synced')
        else:
            await self.tree.sync()
            logging.info(f'Synced global commands')

    async def on_ready(self):
        logging.info(f'Logged in as {self.user.name} (ID: {self.user.id})')

        if self.director_guild is None:
            return

        global database_error
        if database_error is not None:
            await self.director_guild.system_channel.send(f"The database failed with error: {database_error}")
            raise SystemExit(f"The database failed with error: {database_error}")
        await self.director_guild.system_channel.send(f"The bot successfully reloaded/updated")

    @staticmethod
    async def on_guild_remove(guild):
        await database.del_guild_database(guild.id)


bot = Bot()


@bot.tree.command(guild=bot.director_guild, description="Sincronizar el arbol de comandos global")
async def sync_tree(interaction: discord.Interaction):
    synced = await bot.tree.sync()
    await interaction.response.send_message(f"Succesfully synced {len(synced)} commands")


if __name__ == "__main__":
    handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
    bot.run(token, log_handler=handler, log_level=logging.DEBUG)