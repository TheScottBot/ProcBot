"""The SQLite database: each server's filter levels, any channels' own levels, hidden proclamations, and where its
Proclamation of the Day goes.

Call init() once at startup (the tests call it with ":memory:"). A server with no rows has the default preset, and a
channel with no rows has its server's levels.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from procbot import content

conn: sqlite3.Connection = None  # type: ignore[assignment]  # Set by init().

SCHEMA = [
    # A server's level for one category, as chosen with /setup. Categories it hasn't set have the default's level.
    """
    CREATE TABLE IF NOT EXISTS filter_levels (
        guild_id INTEGER NOT NULL,
        category TEXT NOT NULL,     -- content.CATEGORIES key, e.g. "religion"
        level    INTEGER NOT NULL,  -- 0 off, 1 mild, 2 full
        PRIMARY KEY (guild_id, category)
    )
    """,
    # A channel's own level for one category (/setup here), over its server's. Categories it hasn't set follow the
    # server, so a server tightening up still tightens the channels for everything they haven't chosen themselves.
    """
    CREATE TABLE IF NOT EXISTS channel_levels (
        guild_id   INTEGER NOT NULL,
        channel_id INTEGER NOT NULL,  -- a thread uses its parent channel's
        category   TEXT NOT NULL,
        level      INTEGER NOT NULL,
        PRIMARY KEY (channel_id, category)
    )
    """,
    # Proclamations a server has hidden by hand (/setup hide), whatever its levels, in every channel.
    """
    CREATE TABLE IF NOT EXISTS hidden_proclamations (
        guild_id        INTEGER NOT NULL,
        proclamation_id TEXT NOT NULL,
        PRIMARY KEY (guild_id, proclamation_id)
    )
    """,
    # Where and when each server's Proclamation of the Day goes (/setup daily). At most one per server.
    """
    CREATE TABLE IF NOT EXISTS daily_posts (
        guild_id   INTEGER PRIMARY KEY,
        channel_id INTEGER NOT NULL,
        clock      TEXT NOT NULL,     -- "09:00", in config.BOT_TIMEZONE
        next_run   TEXT NOT NULL      -- UTC, ISO
    )
    """,
]


def init(path: str) -> None:
    global conn
    conn = sqlite3.connect(path)
    for statement in SCHEMA:
        conn.execute(statement)
    conn.commit()


def limits(guild_id: int | None, channel_id: int | None = None) -> dict[str, int]:
    """The highest level of each category allowed in this server, or this channel of it. DMs get the default."""
    out = dict(content.DEFAULT.limits)
    if guild_id is not None:
        rows = conn.execute("SELECT category, level FROM filter_levels WHERE guild_id = ?", (guild_id,))
        out.update({category: level for category, level in rows if category in content.BY_KEY})
    if guild_id is not None and channel_id is not None:
        out.update({c: level for c, level in channel_levels(channel_id).items() if c in content.BY_KEY})
    return out


def set_level(guild_id: int, category: str, level: int) -> None:
    set_limits(guild_id, {category: level})


def set_limits(guild_id: int, levels: dict[str, int]) -> None:
    with conn:
        for category, level in levels.items():
            conn.execute("INSERT INTO filter_levels (guild_id, category, level) VALUES (?, ?, ?) "
                         "ON CONFLICT (guild_id, category) DO UPDATE SET level = excluded.level",
                         (guild_id, category, level))


def channel_levels(channel_id: int) -> dict[str, int]:
    """Only what this channel has set itself (/setup here)."""
    rows = conn.execute("SELECT category, level FROM channel_levels WHERE channel_id = ?", (channel_id,))
    return dict(rows.fetchall())


def set_channel_limits(guild_id: int, channel_id: int, levels: dict[str, int]) -> None:
    with conn:
        for category, level in levels.items():
            conn.execute("INSERT INTO channel_levels (guild_id, channel_id, category, level) VALUES (?, ?, ?, ?) "
                         "ON CONFLICT (channel_id, category) DO UPDATE SET level = excluded.level",
                         (guild_id, channel_id, category, level))


def channels(guild_id: int) -> dict[int, dict[str, int]]:
    """Every channel in this server with levels of its own: channel ID -> what it has set."""
    out: dict[int, dict[str, int]] = {}
    for channel_id, category, level in conn.execute(
            "SELECT channel_id, category, level FROM channel_levels WHERE guild_id = ? ORDER BY channel_id",
            (guild_id,)):
        out.setdefault(channel_id, {})[category] = level
    return out


def forget_channel(channel_id: int) -> bool:
    """Back to following the server (/setup here reset, or the channel being deleted). False if it had nothing set."""
    cursor = conn.execute("DELETE FROM channel_levels WHERE channel_id = ?", (channel_id,))
    conn.commit()
    return cursor.rowcount > 0


def hidden(guild_id: int | None) -> set[str]:
    if guild_id is None:
        return set()
    rows = conn.execute("SELECT proclamation_id FROM hidden_proclamations WHERE guild_id = ?", (guild_id,))
    return {row[0] for row in rows}


def hide(guild_id: int, proclamation_id: str) -> bool:
    """Hide a proclamation in a server. False if it was already hidden."""
    cursor = conn.execute("INSERT OR IGNORE INTO hidden_proclamations (guild_id, proclamation_id) VALUES (?, ?)",
                          (guild_id, proclamation_id))
    conn.commit()
    return cursor.rowcount > 0


def unhide(guild_id: int, proclamation_id: str) -> bool:
    """Show a hidden proclamation again. False if it wasn't hidden."""
    cursor = conn.execute("DELETE FROM hidden_proclamations WHERE guild_id = ? AND proclamation_id = ?",
                          (guild_id, proclamation_id))
    conn.commit()
    return cursor.rowcount > 0


def forget(guild_id: int) -> None:
    """A server's filters, its channels' included: /setup reset, or the bot leaving it. (Its daily post stays, for a
    reset: stop_daily stops that.)"""
    with conn:
        conn.execute("DELETE FROM filter_levels WHERE guild_id = ?", (guild_id,))
        conn.execute("DELETE FROM channel_levels WHERE guild_id = ?", (guild_id,))
        conn.execute("DELETE FROM hidden_proclamations WHERE guild_id = ?", (guild_id,))


# --- The Proclamation of the Day (daily.py) ---

@dataclass(frozen=True)
class DailySetup:
    guild_id: int
    channel_id: int
    clock: str  # "09:00", in config.BOT_TIMEZONE
    next_run: str  # UTC, ISO

    @property
    def next_run_at(self) -> datetime:
        return datetime.fromisoformat(self.next_run)


DAILY_COLUMNS = "guild_id, channel_id, clock, next_run"


def daily(guild_id: int) -> DailySetup | None:
    row = conn.execute(f"SELECT {DAILY_COLUMNS} FROM daily_posts WHERE guild_id = ?", (guild_id,)).fetchone()
    return DailySetup(*row) if row else None


def set_daily(guild_id: int, channel_id: int, clock: str, next_run: datetime) -> None:
    """Set up (or move) a server's daily post."""
    with conn:
        conn.execute(f"INSERT OR REPLACE INTO daily_posts ({DAILY_COLUMNS}) VALUES (?, ?, ?, ?)",
                     (guild_id, channel_id, clock, next_run.isoformat()))


def stop_daily(guild_id: int) -> bool:
    """False if there was none."""
    cursor = conn.execute("DELETE FROM daily_posts WHERE guild_id = ?", (guild_id,))
    conn.commit()
    return cursor.rowcount > 0


def stop_daily_in(channel_id: int) -> bool:
    """A deleted channel's daily post stops. False if it had none."""
    cursor = conn.execute("DELETE FROM daily_posts WHERE channel_id = ?", (channel_id,))
    conn.commit()
    return cursor.rowcount > 0


def dailies_due(now: datetime) -> list[DailySetup]:
    rows = conn.execute(f"SELECT {DAILY_COLUMNS} FROM daily_posts").fetchall()
    return [setup for setup in (DailySetup(*row) for row in rows) if setup.next_run_at <= now]


def daily_posted(guild_id: int, next_run: datetime) -> None:
    with conn:
        conn.execute("UPDATE daily_posts SET next_run = ? WHERE guild_id = ?", (next_run.isoformat(), guild_id))
