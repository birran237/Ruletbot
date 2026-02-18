import discord
from discord import app_commands
from discord.ext import commands
from utility import Utility
import database


class Customize(commands.GroupCog, name="customize"):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def message_customization(message: str, guild_id: int, field: database.db_fields) -> str:
        if message is None:
            db = await database.get_from_database(guild_id=guild_id)
            db_message = Utility.format_message(message=db[field])
            return f"El mensaje actual es: {db_message}"

        formated_message = Utility.format_message(message=message)
        await database.save_to_database(guild_id=guild_id, field=field, data=message)
        return f"El nuevo mensaje será: {formated_message}"

    @app_commands.command(name="win",description="Cambia el mensaje de victoria de la ruleta (deja en blanco para ver ajustes actuales)")
    @app_commands.describe(message="$k será el nombre del autor, $u del objetivo y $t el tiempo de timeout")
    @Utility.admin_check()
    async def win(self, interaction: discord.Interaction, message: str | None = None):
        return_message = await self.message_customization(message=message, guild_id=interaction.guild.id, field="win_message")
        await interaction.response.send_message(return_message, ephemeral=True)

    @app_commands.command(name="win_with_streak",description="Cambia el mensaje de victoria con una racha de 3 o más")
    @app_commands.describe(message="$k será el nombre del autor, $u del objetivo, $t el tiempo de timeout y $r la racha de victorias")
    @Utility.admin_check()
    async def win_streak(self, interaction: discord.Interaction, message: str | None = None):
        return_message = await self.message_customization(message=message, guild_id=interaction.guild.id, field="win_streak_message")
        await interaction.response.send_message(return_message, ephemeral=True)
    @app_commands.command(name="lose",description="Cambia el mensaje de derrota de la ruleta (deja en blanco para ver ajustes actuales)")
    @app_commands.describe(message="$k será el nombre del autor, $u del objetivo y $t el tiempo de timeout")
    @Utility.admin_check()
    async def lose(self, interaction: discord.Interaction, message: str | None = None):
        return_message = await self.message_customization(message=message, guild_id=interaction.guild.id,field="lose_message")
        await interaction.response.send_message(return_message, ephemeral=True)

    @app_commands.command(name="lose_with_penalty",description="Cambia el mensaje de derrota con penalización (deja en blanco para ver ajustes actuales)")
    @app_commands.describe(message="$k será el nombre del autor, $u del objetivo y $t el tiempo de timeout")
    @Utility.admin_check()
    async def lose_penalty(self, interaction: discord.Interaction, message: str | None = None):
        return_message = await self.message_customization(message=message, guild_id=interaction.guild.id,field="lose_penalty_message")
        await interaction.response.send_message(return_message, ephemeral=True)

    @app_commands.command(name="wrong_target",description="Cambia el mensaje de cuando un usuario haga rulet a si mismo o a un bot")
    @app_commands.describe(message="$k será el nombre del autor y $t el tiempo de timeout")
    @Utility.admin_check()
    async def wrong_target(self, interaction: discord.Interaction, message: str | None = None):
        return_message = await self.message_customization(message=message, guild_id=interaction.guild.id,field="wrong_target")
        await interaction.response.send_message(return_message, ephemeral=True)

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
