import discord
from discord import app_commands
from discord.ext import commands
import database
from time import time
from utility import Utility

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    admin_group = app_commands.Group(name="set", description="...")

    @app_commands.command(name="disable", description="Deshabilita el bot durante los minutos especificados")
    @app_commands.describe(minutes="Cantidad de minutos (deja en 0 para habilitar el bot instantaniamente)")
    @Utility.admin_check()
    async def disable(self, interaction: discord.Interaction, minutes: app_commands.Range[float, 0, 10080] | None = None):
        timeouted_until = Utility.disabled_servers.get(interaction.guild.id, 0)
        remaining_time = Utility.disabled_servers.get(interaction.guild.id, 0) - time()
        if minutes is None:
            if remaining_time <= 0:
                await interaction.response.send_message(f"El bot está habilitado", ephemeral=True)
                return
            await interaction.response.send_message(f"El bot no funcionará hasta <t:{timeouted_until}:R>", ephemeral=True)
            return

        if minutes == 0:
            if remaining_time <= 0:
                await interaction.response.send_message(f"El bot ya estaba habilitado habilitado", ephemeral=True)
                return

            Utility.disabled_servers.pop(interaction.guild_id)
            await interaction.response.send_message(f"El bot vuelve a estar habilitado", ephemeral=True)
            return

        expire_at = int(time() + (minutes * 60))
        Utility.disabled_servers[interaction.guild_id] = expire_at
        await interaction.response.send_message(f"El bot no funcionará hasta <t:{expire_at}:R>", ephemeral=True)

    @app_commands.command(name="info", description="Mostrar toda la configuración actual")
    @Utility.admin_check()
    async def info(self, interaction: discord.Interaction):
        db = await database.get_from_database(interaction.guild.id)
        message: str = f"""Solo puede ser modificada por usuarios con permisos de administrador
**/set**
- **Tiempo de timeout:** {Utility.format_seconds(db['timeout_seconds'])}
- **Cooldown extra de derrota:** {Utility.format_seconds(db['lose_cooldown'])}
- **Afectar a administradores:** {"Sí" if db['annoy_admins'] else "No"}
- **Mitad de castigo para los que son retados:** {"Sí" if db['half_lose_timeout'] else "No"}
**/customize**
- **Mensaje de victoria:** {db['win_message']}
- **Mensaje de victoria con racha:** {db['win_streak_message']}
- **Mensaje de derrota:** {db['lose_message']}
- **Mensaje de derrota con penalización:** {db['lose_penalty_message']}
- **Mensaje de objetivo inválido:** {db['wrong_target']}"""
        embed = discord.Embed(title="Configuración actual",description=Utility.format_message(message),color=discord.Color.dark_blue())
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin_group.command(name="timeout", description="Configura los segundos de timeout de la rulet (deja en blanco para ver ajustes actuales)")
    @app_commands.describe(seconds="Cantidad de segundos (1–600), dejar a 0 solo para expulsar de vc")
    @Utility.admin_check()
    async def set_timeout(self, interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 600] | None = None):
        db = await database.get_from_database(guild_id=interaction.guild_id)
        if seconds is None:
            await interaction.response.send_message(f"Ahora mismo la rulet está configurada para {Utility.format_seconds(db.timeout_seconds)}", ephemeral=True)
            return

        await database.save_to_database(guild_id=interaction.guild_id, field="timeout_seconds", data=seconds)
        await interaction.response.send_message(f"Tiempo de rulet configurado a {Utility.format_seconds(seconds)}", ephemeral=True)

    @admin_group.command(name="lose_cooldown", description="Cooldown del comando para un usuario después de perder (deja en blanco para ver ajustes actuales)")
    @app_commands.describe(seconds="Cantidad de segundos (0–900), solo afectará al que reta cuando pierda, no al retado")
    @Utility.admin_check()
    async def set_lose_cooldown(self, interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 900] | None = None):
        db = await database.get_from_database(guild_id=interaction.guild_id)
        if seconds is None:
            await interaction.response.send_message(f"Ahora mismo el cooldown es de {Utility.format_seconds(db['lose_cooldown'])}", ephemeral=True)
            return

        await database.save_to_database(guild_id=interaction.guild_id, field="lose_cooldown", data=seconds)
        await interaction.response.send_message(f"Tiempo de cooldown configurado a {Utility.format_seconds(seconds)}", ephemeral=True)


    @admin_group.command(name="annoy_admins", description="Elige si afecta o no a los roles superiores al del bot (deja en blanco para ver ajustes actuales)")
    @Utility.admin_check()
    async def set_annoy_admins(self, interaction: discord.Interaction, affect_admins: bool | None = None):
        if affect_admins is None:
            db = await database.get_from_database(guild_id=interaction.guild_id)
            message_mod = "también" if db['annoy_admins'] else "no"
            await interaction.response.send_message(f"La ruleta {message_mod} afecta a los roles superiores al mio y a los administradores", ephemeral=True)
            return

        await database.save_to_database(guild_id=interaction.guild_id, field="annoy_admins", data=affect_admins)
        message_mod = "también" if affect_admins else "ya no"
        await interaction.response.send_message(f"A partir de ahora la ruleta {message_mod} afectará a los roles superiores al mio o a administradores",ephemeral=True)


    @admin_group.command(name="half_lose_timeout", description="Reducir a la mitad el tiempo de las derrotas (solo afecta a los retados)")
    @Utility.admin_check()
    async def set_half_lose_timeout(self, interaction: discord.Interaction, enable: bool | None = None):
        if enable is None:
            db = await database.get_from_database(guild_id=interaction.guild_id)
            message_mod = "la mitad de tiempo" if db['half_lose_timeout'] else "el timepo entero"
            await interaction.response.send_message(f"Los retados recibiran {message_mod} cuando pierdan", ephemeral=True)
            return

        await database.save_to_database(guild_id=interaction.guild_id, field="half_lose_timeout", data=enable)
        message_mod = "la mitad de tiempo" if enable else "el timepo entero"
        await interaction.response.send_message(f"A partir de ahora los retados recibiran {message_mod} cuando pierdan", ephemeral=True)

    @admin_group.command(name="default", description="Devuelve los ajustes del bot a valores por defecto")
    @Utility.admin_check()
    async def set_default(self, interaction: discord.Interaction):
        await database.del_guild_database(guild_id=interaction.guild_id)
        await interaction.response.send_message(f"Se han resetado los ajustes del bot", ephemeral=True)


async def setup(bot: commands.bot):
    await bot.add_cog(Admin(bot))