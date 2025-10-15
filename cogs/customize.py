import discord
from discord import app_commands
from discord.ext import commands

import utility
from utility import Utility
from typing import Optional
import database


class Customize(commands.GroupCog, name="customize"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="win",description="Cambia el mensaje de victoria de la ruleta (deja en blanco para ver ajustes actuales)")
    @app_commands.describe(message="Mensaje de victoria ($k será el nombre del autor y $u del objetivo)")
    @Utility.admin_check()
    async def win(self, interaction: discord.Interaction, message: Optional[str] = None):
        if message is None:
            db = await database.get_from_database(guild_id=interaction.guild.id)
            db_message = db["win_message"]
            db_message = Utility.format_message(message=db_message)
            await interaction.response.send_message(f"El mensaje actual es: {db_message}", ephemeral=True)
            return

        formated_message = Utility.format_message(message=message)
        await interaction.response.send_message(f"El nuevo mensaje será: {formated_message}", ephemeral=True)
        await database.save_to_database(guild_id=interaction.guild_id, field="win_message", data=message)

    @app_commands.command(name="lose",description="Cambia el mensaje de derrota de la ruleta")
    @app_commands.describe(message="Mensaje de derrota ($k será el nombre del autor y $u del objetivo)")
    @Utility.admin_check()
    async def lose(self, interaction: discord.Interaction, message: Optional[str] = None):
        if message is None:
            db = await database.get_from_database(guild_id=interaction.guild.id)
            db_message = db["lose_message"]
            db_message = Utility.format_message(message=db_message)
            await interaction.response.send_message(f"El mensaje actual es: {db_message}", ephemeral=True)
            return

        formated_message = Utility.format_message(message=message)
        await interaction.response.send_message(f"El nuevo mensaje será: {formated_message}", ephemeral=True)
        await database.save_to_database(guild_id=interaction.guild_id, field="lose_message", data=message)

    @app_commands.command(name="lose_with_penalty",description="Cambia el mensaje de derrota con penalización")
    @app_commands.describe(message="Mensaje de derrota con penalización ($k será el nombre del autor y $u del objetivo)")
    @Utility.admin_check()
    async def lose_penalty(self, interaction: discord.Interaction, message: Optional[str] = None):
        if message is None:
            db = await database.get_from_database(guild_id=interaction.guild.id)
            db_message = db["lose_penalty_message"]
            db_message = Utility.format_message(message=db_message)
            await interaction.response.send_message(f"El mensaje actual es: {db_message}", ephemeral=True)
            return

        formated_message = Utility.format_message(message=message)
        await interaction.response.send_message(f"El nuevo mensaje será: {formated_message}", ephemeral=True)
        await database.save_to_database(guild_id=interaction.guild_id, field="lose_penalty_message", data=message)

    @app_commands.command(name="wrong_target",description="Cambia el mensaje de cuando un usuario haga rulet a si mismo o a un bot")
    @app_commands.describe(message="Mensaje destinatario incorrecto ($k será el nombre del autor)")
    @Utility.admin_check()
    async def wrong_target(self, interaction: discord.Interaction, message: Optional[str] = None):
        if message is None:
            db = await database.get_from_database(guild_id=interaction.guild.id)
            db_message = db["wrong_target"]
            db_message = Utility.format_message(message=db_message)
            await interaction.response.send_message(f"El mensaje actual es: {db_message}", ephemeral=True)
            return

        formated_message = Utility.format_message(message=message)
        await interaction.response.send_message(f"El nuevo mensaje será: {formated_message}", ephemeral=True)
        await database.save_to_database(guild_id=interaction.guild_id, field="wrong_target", data=message)

    @app_commands.command(name="reset", description="Restableze las frases a los valores por defecto")
    @Utility.admin_check()
    async def reset(self, interaction: discord.Interaction):
        guild: int = interaction.guild_id
        if database.local_db.get(guild) is None:
            return

        delete_list = ["win_message", "lose_message", "lose_penalty_message", "wrong_target"]
        for field in delete_list:
            await database.del_guild_database_field(guild_id=guild, field=field)

        await interaction.response.send_message(f"Se han reseteado los mensajes del bot", ephemeral=True)


async def setup(bot: commands.bot):
    await bot.add_cog(Customize(bot))
