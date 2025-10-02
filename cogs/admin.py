import discord
from discord import app_commands
from discord.ext import commands
import database
import asyncio
from time import time
from rulet import format_seconds

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    admin_group = app_commands.Group(name="set", description="...")

    @admin_group.command(name="disable", description="Deshabilita el bot durante los minutos especificados")
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
        await interaction.response.send_message(
            f"El bot no funcionará hasta dentro de **{format_seconds(int(minutes * 60))}**", ephemeral=True)

        async def enable():
            await asyncio.sleep(minutes * 60)
            if disabled_servers.get(interaction.guild_id) == expire_at:
                del disabled_servers[interaction.guild_id]

        asyncio.create_task(enable())

    @admin_group.command(name="timeout", description="Configura los minutos de timeout de la rulet (deja en blanco para saber la configuración actual, poner a 0 para solo expulsar de vc)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(minutes="Cantidad de minutos (0–60)")
    async def set_timeout(self, interaction: discord.Interaction, minutes: app_commands.Range[int, 0, 60] = None):
        if minutes is None:
            db_minutes = await database.get_from_database(guild_id=interaction.guild_id, field="timeout_minutes")
            await interaction.response.send_message(f"Ahora mismo la rulet está configurada para {db_minutes} minutos", ephemeral=True)
            return

        await database.save_to_database(guild_id=interaction.guild_id,field="timeout_minutes", data=minutes)
        await interaction.response.send_message(f"Tiempo de rulet configurado a {minutes} minutos", ephemeral=True)

    @admin_group.command(name="annoy_admins", description="Elige si afecta o no a los roles superiores al del bot (deja en blanco para saber la configuración actual)")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_annoy_admins(self, interaction: discord.Interaction, affect_admins: bool | None = None):
        if affect_admins is None:
            db_affect_admins = await database.get_from_database(guild_id=interaction.guild_id,field="affect_admins")
            message_mod = "también" if db_affect_admins else "no"
            await interaction.response.send_message(f"La ruleta {message_mod} afecta a los roles superiores al mio y a los administradores", ephemeral=True)
            return

        await database.save_to_database(guild_id=interaction.guild_id, field="annoy_admins", data=affect_admins)
        message_mod = "también" if affect_admins else "ya no"
        await interaction.response.send_message(f"A partir de ahora la ruleta {message_mod} afectará a los roles superiores al mio ni a administradores",ephemeral=True)

async def setup(bot: commands.bot):
    await bot.add_cog(Admin(bot))