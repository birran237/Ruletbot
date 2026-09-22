import discord
from discord import app_commands
from discord.ext import commands
import database
from time import time
from utility import Utility
import asyncio

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator

    admin_group = app_commands.Group(name="set", description="Modificar ajustes del bot",default_permissions=discord.Permissions(administrator=True))

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="disable", description="Deshabilita el bot durante los minutos especificados")
    async def disable(self, interaction: discord.Interaction, minutos: app_commands.Range[float, -1, 60] = -1, horas: app_commands.Range[float, -1, 24] = 0, dias: app_commands.Range[float, -1, 30] = 0):
        # Get disable time from utility (returns None if not set, or timestamp if set)
        disabled_until = Utility.disabled_servers.get(interaction.guild.id)
        # Get bot timeout time (returns None if not timed out, or datetime if timed out)
        timed_out_until = interaction.guild.me.timed_out_until

        # Clean up expired disabled server entry if needed
        if disabled_until is not None and disabled_until < time():
            Utility.disabled_servers.pop(interaction.guild.id, None)
            disabled_until = None

        # Calculate remaining time if either disable or timeout is active
        remaining_time = 0
        if disabled_until is not None:
            remaining_time = max(remaining_time, disabled_until - time())
        if timed_out_until is not None:
            remaining_time = max(remaining_time, timed_out_until.timestamp() - time())

        # Handle status check (when user passes negative values)
        if minutos + horas + dias <= -3:
            if remaining_time <= 0:
                await interaction.response.send_message(f"El bot está habilitado", ephemeral=True)
                return
            await interaction.response.send_message(f"El bot no funcionará hasta <t:{int(time() + remaining_time)}:R>", ephemeral=True)
            return

        # Normalize input values
        minutos, horas, dias = max(minutos, 0), max(horas, 0), max(dias, 0)
        total_seconds = minutos * 60 + horas * 60 * 60 + dias * 60 * 60 * 24

        if total_seconds == 0:
            # User wants to enable the bot
            if remaining_time <= 0:
                await interaction.response.send_message(f"El bot ya estaba habilitado", ephemeral=True)
                return

            if timed_out_until is not None and timed_out_until.timestamp() < time():
                await interaction.response.send_message(f"El bot ha sido aislado temporalmente, desaislalo para que vuelva a funcionar", ephemeral=True)
                return

            # Remove disable setting if exists
            if interaction.guild.id in Utility.disabled_servers:
                Utility.disabled_servers.pop(interaction.guild.id)
            await interaction.response.send_message(f"El bot vuelve a estar habilitado", ephemeral=True)
            return

        # Set new disable time
        expire_at = int(time() + total_seconds)
        Utility.disabled_servers[interaction.guild.id] = expire_at
        await interaction.response.send_message(f"El bot no funcionará hasta <t:{expire_at}:R>", ephemeral=True)
        await Utility.delete_expired_disabled_server(guild_id=interaction.guild.id)

    @admin_group.command(name="timeout", description="Configura los segundos de timeout de la rulet (deja en blanco para ver ajustes actuales)")
    @app_commands.describe(seconds="Cantidad de segundos (0–600), dejar a 0 solo para expulsar de vc")
    async def set_timeout(self, interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 600] | None = None):
        db = await database.get_from_database(guild_id=interaction.guild_id)
        if seconds is None:
            await interaction.response.send_message(f"Ahora mismo la rulet está configurada para {Utility.format_seconds(db.timeout_seconds)}", ephemeral=True)
            return

        await database.save_to_database(guild_id=interaction.guild_id, field="timeout_seconds", data=seconds)
        await interaction.response.send_message(f"Tiempo de rulet configurado a {Utility.format_seconds(seconds)}", ephemeral=True)

    @admin_group.command(name="lose_cooldown", description="Cooldown extra del comando para un usuario después de perder")
    async def set_lose_cooldown(self, interaction: discord.Interaction, minutos: app_commands.Range[float, -1, 60] = -1, horas: app_commands.Range[float, 0, 24] = 0, dias: app_commands.Range[float, 0, 7] = 0):
        seconds = int(minutos*60 + horas*60*60 + dias*60*60*24)
        db = await database.get_from_database(guild_id=interaction.guild_id)
        if seconds < 0:
            await interaction.response.send_message(f"Ahora mismo el cooldown es de {Utility.format_seconds(db['lose_cooldown'])}", ephemeral=True)
            return
        if minutos < 0:
            seconds += 60

        await database.save_to_database(guild_id=interaction.guild_id, field="lose_cooldown", data=seconds)
        await interaction.response.send_message(f"Tiempo de cooldown configurado a {Utility.format_seconds(seconds)}", ephemeral=True)


    @admin_group.command(name="annoy_admins", description="Modifica el comportamiento del bot hacia los administradores")
    async def set_annoy_admins(self, interaction: discord.Interaction, level: int | None = None):
        message = [
            "- 0 → Las personas por encima del rol `Rulet bot` no seran afectados por la ruleta (por defecto)",
            "- 1 → Solo se podrá retar a las personas por debajo de tu rol máximo (o todo el mundo que esté por debajo del rol `Rulet bot` sin importar la jerarquía). Todos los perdedores recibirán un timeout",
            "- 2 → Todo el mundo podrá ser victima de la ruleta, sin importar la jerarquía"
        ]
        if level is None:
            db = await database.get_from_database(guild_id=interaction.guild_id)
            current_level = int(max(0, min(db['annoy_admins'],2)))
            message[current_level] = f"**{message[current_level]}**"
            await interaction.response.send_message('\n'.join(message), ephemeral=True)
            return

        await database.save_to_database(guild_id=interaction.guild_id, field="annoy_admins", data=level)
        message[level] = f"**{message[level]}**"
        await interaction.response.send_message('\n'.join(message), ephemeral=True)


    @admin_group.command(name="default", description="Devuelve los ajustes del bot a valores por defecto")
    async def set_default(self, interaction: discord.Interaction):
        await database.del_guild_database(guild_id=interaction.guild_id)
        await interaction.response.send_message(f"Se han resetado los ajustes del bot", ephemeral=True)


async def setup(bot: commands.bot):
    await bot.add_cog(Admin(bot))
