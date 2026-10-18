"""The bot itself: startup, registering the slash commands, logging and errors."""

import logging
from logging.handlers import RotatingFileHandler

import discord
from discord import app_commands

from procbot import config
from procbot.commands import COMMANDS

log = logging.getLogger("procbot")


def setup_logging() -> None:
    """Log to the terminal (so journalctl works) and, if it can be opened, a rolling log file."""
    formatter = logging.Formatter("[{asctime}] [{levelname:<7}] {name}: {message}", "%Y-%m-%d %H:%M:%S", style="{")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)
    try:
        config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(config.LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    except OSError as error:
        log.warning("Couldn't open log file %s, logging to the terminal only: %s", config.LOG_FILE, error)
        return
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


class ProcBot(discord.Client):
    """Slash commands only, so it needs no privileged intents: it never reads anyone's messages."""

    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
        for command in COMMANDS:
            self.tree.add_command(command)
        self.tree.on_error = self.on_app_command_error

    async def setup_hook(self):
        if config.GUILD_IDS:
            # Server-only commands update instantly; global ones can take up to an hour to reach everyone.
            for guild_id in config.GUILD_IDS:
                guild = discord.Object(id=guild_id)
                self.tree.copy_global_to(guild=guild)
                try:
                    synced = await self.tree.sync(guild=guild)
                except discord.Forbidden:
                    log.warning("Couldn't add slash commands to server %s: is the bot in it, invited with the "
                                "applications.commands scope? Skipping it.", guild_id)
                    continue
                log.info("Synced %d slash commands to server %s", len(synced), guild_id)
        else:
            synced = await self.tree.sync()
            log.info("Synced %d global slash commands", len(synced))

    async def on_ready(self):
        log.info("Logged in as %s (ID: %s), in %d servers", self.user, self.user.id, len(self.guilds))

    async def on_app_command_completion(self, interaction: discord.Interaction, command):
        # Which command ran, and in which server: never who ran it, or what they searched for.
        log.info("[%s] /%s", interaction.guild_id or "DM", command.qualified_name)

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            message = str(error) or "You can't use that here."
        else:
            log.exception("/%s failed", interaction.command.qualified_name if interaction.command else "?",
                          exc_info=error)
            message = "Something went wrong. Treason, presumably."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


def main():
    if not config.DISCORD_TOKEN:
        raise SystemExit(f"DISCORD_TOKEN is not set. Copy .env.example to {config.ENV_FILE} and add your token.")
    setup_logging()
    ProcBot().run(config.DISCORD_TOKEN, log_handler=None)
