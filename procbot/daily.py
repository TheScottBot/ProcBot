"""On this day: /onthisday, and the Proclamation of the Day posted in a channel each server chooses (/setup daily).

As in ktdi's daily.py: each server has at most one channel and time (setting it up elsewhere moves it), stored in
the daily_posts table, so nothing needs a restart. The bot's loop calls post_due every minute, and a due post always
moves on to the next day, even when posting fails, so nothing is posted over and over; a day missed by hours (the
bot was down) is skipped, not posted late.

"On this day" is by the date as printed. Before 1752 that's Old Style (the Julian calendar), ten or eleven days
behind ours: a proclamation of 18 October 1625 was given on what we'd call 28 October.
"""

import logging
import re
from datetime import date, datetime, time, timedelta, timezone

import discord

from procbot import config, db, proclamations

log = logging.getLogger("procbot")
DEFAULT_TIME = "09:00"
GRACE = timedelta(hours=6)  # Later than this, a day's is skipped rather than posted late
MONTHS = [name.lower() for name in proclamations.MONTHS]


class Unreadable(ValueError):
    """A time or date that can't be read. Its message says how to write one."""


def parse_clock(text: str) -> str:
    """'9am', '9:30pm', '21:30', '0900' -> 'HH:MM'."""
    found = re.fullmatch(r"\s*(\d{1,2})(?:[:.]?(\d{2}))?\s*(am|pm)?\s*", text.lower())
    if not found:
        raise Unreadable(f"I can't read `{text}` as a time. Try `9am`, `6:30pm` or `21:00`.")
    hour, minute = int(found.group(1)), int(found.group(2) or 0)
    if found.group(3):
        if not 1 <= hour <= 12:
            raise Unreadable(f"`{text}` isn't a time: with am or pm, the hour is 1 to 12.")
        hour = hour % 12 + (12 if found.group(3) == "pm" else 0)
    if hour > 23 or minute > 59:
        raise Unreadable(f"`{text}` isn't a time of day.")
    return f"{hour:02d}:{minute:02d}"


def parse_day(text: str) -> str:
    """'18 October', 'October 18', 'oct 18th', '18/10' -> '10-18'."""
    cleaned = text.strip().lower()
    day = month = 0
    if found := re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]{3,})", cleaned):
        day, month = int(found.group(1)), month_number(found.group(2))
    elif found := re.fullmatch(r"([a-z]{3,})\s+(\d{1,2})(?:st|nd|rd|th)?", cleaned):
        day, month = int(found.group(2)), month_number(found.group(1))
    elif found := re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})", cleaned):  # Day first, as in Britain and Ireland
        day, month = int(found.group(1)), int(found.group(2))
    try:
        return date(2024, month, day).strftime("%m-%d")  # 2024: a leap year, so 29 February is a day
    except ValueError:
        raise Unreadable(f"I can't read `{text}` as a day. Try `18 October` or `October 18`.") from None


def month_number(name: str) -> int:
    """'oct' or 'october' -> 10; 0 if it isn't a month."""
    return next((number for number, month in enumerate(MONTHS, 1) if month.startswith(name)), 0)


def day_name(on: str) -> str:
    """'10-18' -> '18 October'."""
    return f"{int(on[3:])} {proclamations.MONTHS[int(on[:2]) - 1]}"


def today(now: datetime | None = None) -> str:
    """Today's day of the year where the bot is: '10-18'."""
    return (now or datetime.now(timezone.utc)).astimezone(config.BOT_TIMEZONE).strftime("%m-%d")


def next_post(clock: str, after: datetime) -> datetime:
    """The next time (UTC) after `after` that it's this time of day where the bot is."""
    hour, minute = map(int, clock.split(":"))
    local = after.astimezone(config.BOT_TIMEZONE)
    when = datetime.combine(local.date(), time(hour, minute), tzinfo=config.BOT_TIMEZONE)
    if when <= local:
        when = datetime.combine(local.date() + timedelta(days=1), time(hour, minute), tzinfo=config.BOT_TIMEZONE)
    return when.astimezone(timezone.utc)


def pick_for(where: int, limits: dict[str, int], hidden: set[str], on: str):
    """A proclamation given on this day (any year), or failing that in this month, or failing that any. With the
    title to give it: (proclamation, title), or (None, "") if the filters allow nothing at all."""
    if proclamation := proclamations.pick(where, limits, hidden, on=on):
        return proclamation, f"📅 On this day, {proclamation.when}"
    if proclamation := proclamations.pick(where, limits, hidden, on=on[:2]):
        return proclamation, f"📅 This month, {proclamation.when}"
    if proclamation := proclamations.pick(where, limits, hidden):
        return proclamation, "📜 Proclamation of the Day"
    return None, ""


# --- Posting ---

async def post_due(client: discord.Client, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    for setup in db.dailies_due(now):
        try:
            channel = client.get_channel(setup.channel_id)
            if channel is None:
                log.warning("Proclamation of the Day: can't find channel %s", setup.channel_id)
            elif now - setup.next_run_at > GRACE:
                log.warning("Skipped the Proclamation of the Day for server %s: it was due at %s", setup.guild_id,
                            setup.next_run)
            else:
                proclamation, title = pick_for(setup.guild_id, db.limits(setup.guild_id, setup.channel_id),
                                               db.hidden(setup.guild_id), today(now))
                if proclamation:
                    await channel.send(embed=proclamations.embed(proclamation, title=title))
                    log.info("Posted the Proclamation of the Day in server %s", setup.guild_id)
        except discord.HTTPException as error:
            log.warning("Couldn't post the Proclamation of the Day in server %s: %s", setup.guild_id, error)
        finally:  # Always on to tomorrow, so a failure can't post it over and over
            db.daily_posted(setup.guild_id, next_post(setup.clock, now))
