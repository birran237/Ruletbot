import discord
from discord import app_commands
from discord.ext import commands
import database
import asyncio
from time import time
from utility import Utility
from typing import Optional

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    admin_group = app_commands.Group(name="set", description="...")

    @admin_group.command(name="disable", description="Deshabilita el bot durante los minutos especificados")
    @Utility.admin_checks()
    @app_commands.describe(minutes="Cantidad de minutos (deja en 0 para habilitar el bot instantaniamente)")
    async def disable(self, interaction: discord.Interaction, minutes: Optional[app_commands.Range[float, 0, 10080]]):
        if minutes == 0:
            Utility.disabled_servers.pop(interaction.guild_id, None)
            await interaction.response.send_message(f"El bot vuelve a funcionar correctamente", ephemeral=True)
            return

        expire_at = int(time() + (minutes * 60))
        Utility.disabled_servers[interaction.guild_id] = expire_at
        await interaction.response.send_message(f"El bot no funcionará hasta dentro de **{Utility.format_seconds(int(minutes * 60))}**", ephemeral=True)

        async def enable():
            await asyncio.sleep(minutes * 60)
            if Utility.disabled_servers.get(interaction.guild_id) == expire_at:
                del Utility.disabled_servers[interaction.guild_id]

        asyncio.create_task(enable())

    @admin_group.command(name="timeout", description="Configura los minutos de timeout de la rulet (deja en blanco para ver ajustes actuales)")
    @Utility.admin_checks()
    @app_commands.describe(seconds="Cantidad de segundos (1–600), dejar a 0 solo para expulsar de vc")
    async def set_timeout(self, interaction: discord.Interaction, seconds: Optional[app_commands.Range[int, 0, 600]] = None):
        db = await database.get_from_database(guild_id=interaction.guild_id)
        if seconds is None:
            await interaction.response.send_message(f"Ahora mismo la rulet está configurada para {Utility.format_seconds(db['timeout_seconds'])}", ephemeral=True)
            return

        await database.save_to_database(guild_id=interaction.guild_id, field="timeout_seconds", data=seconds)
        await interaction.response.send_message(f"Tiempo de rulet configurado a {Utility.format_seconds(seconds)}", ephemeral=True)

    @admin_group.command(name="annoy_admins", description="Elige si afecta o no a los roles superiores al del bot (deja en blanco para ver ajustes actuales)")
    @Utility.admin_checks()
    async def set_annoy_admins(self, interaction: discord.Interaction, affect_admins: Optional[bool] = None):
        if affect_admins is None:
            db = await database.get_from_database(guild_id=interaction.guild_id)
            message_mod = "también" if db['annoy_admins'] else "no"
            await interaction.response.send_message(f"La ruleta {message_mod} afecta a los roles superiores al mio y a los administradores", ephemeral=True)
            return

        await database.save_to_database(guild_id=interaction.guild_id, field="annoy_admins", data=affect_admins)
        message_mod = "también" if affect_admins else "ya no"
        await interaction.response.send_message(f"A partir de ahora la ruleta {message_mod} afectará a los roles superiores al mio o a administradores",ephemeral=True)

async def setup(bot: commands.bot):
    await bot.add_cog(Admin(bot))