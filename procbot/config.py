"""Settings from .env (or .env.dev with --dev). Relative paths are from the repo root."""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Run with --dev ("python bot.py --dev") to use a separate test bot's settings from .env.dev.
DEV = "--dev" in sys.argv
ENV_FILE = ".env.dev" if DEV else ".env"
if not os.getenv("PROCBOT_NO_DOTENV"):  # The tests set this so they never read a real .env.
    load_dotenv(BASE_DIR / ENV_FILE)


def parse_ids(name: str) -> list[int]:
    """Comma-separated IDs from an env var. Skips (and warns about) anything that isn't a number."""
    ids = []
    for item in (os.getenv(name) or "").replace(" ", "").split(","):
        if item.isdigit():
            ids.append(int(item))
        elif item:
            logging.getLogger("procbot").warning("Ignoring %r in %s: server IDs are numbers only.", item, name)
    return ids


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
# Optional: servers to register the slash commands to directly, so changes show up instantly (handy while testing).
# Leave empty for a public bot: commands are registered globally, for every server it's in.
GUILD_IDS = parse_ids("GUILD_IDS")
DB_PATH = str(BASE_DIR / os.getenv("DB_PATH", "procbot.db"))
LOG_FILE = BASE_DIR / os.getenv("LOG_FILE", "logs/procbot-dev.log" if DEV else "logs/procbot.log")
