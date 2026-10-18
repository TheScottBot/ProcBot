"""On this day and the Proclamation of the Day (procbot/daily.py), and their commands."""

import types
from datetime import datetime, timedelta, timezone

import discord
import pytest

from procbot import commands, content, daily, db, proclamations
from procbot.bot import ProcBot
from tests.fakes import Guild, Interaction, run

UTC = timezone.utc


@pytest.mark.parametrize("text, clock", [("9am", "09:00"), ("9:30pm", "21:30"), ("12am", "00:00"), ("12pm", "12:00"),
                                         ("21:00", "21:00"), ("0715", "07:15"), (" 6.45 PM ", "18:45")])
def test_parse_clock(text, clock):
    assert daily.parse_clock(text) == clock


@pytest.mark.parametrize("text", ["noon", "25:00", "13pm", "9:75", ""])
def test_parse_clock_says_how(text):
    with pytest.raises(daily.Unreadable, match="isn't|can't"):
        daily.parse_clock(text)


@pytest.mark.parametrize("text, on", [("18 October", "10-18"), ("October 18", "10-18"), ("oct 18th", "10-18"),
                                      ("5th of November", "11-05"), ("25/3", "03-25"), ("29 Feb", "02-29")])
def test_parse_day(text, on):
    assert daily.parse_day(text) == on


@pytest.mark.parametrize("text", ["31 June", "ma 5", "someday", "13/13"])
def test_parse_day_says_how(text):
    with pytest.raises(daily.Unreadable, match="can't read"):
        daily.parse_day(text)


def test_next_post_in_london_time():
    # Summer: 9am in London is 8am UTC; already past today, so tomorrow.
    assert daily.next_post("09:00", datetime(2026, 7, 1, 7, 0, tzinfo=UTC)) == datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    assert daily.next_post("09:00", datetime(2026, 7, 1, 8, 0, tzinfo=UTC)) == datetime(2026, 7, 2, 8, 0, tzinfo=UTC)
    # Winter: 9am is 9am UTC. And across the clocks going back (25 October 2026).
    assert daily.next_post("09:00", datetime(2026, 12, 1, 12, 0, tzinfo=UTC)) == datetime(2026, 12, 2, 9, 0, tzinfo=UTC)
    assert daily.next_post("09:00", datetime(2026, 10, 24, 12, 0, tzinfo=UTC)) == \
        datetime(2026, 10, 25, 9, 0, tzinfo=UTC)


def test_today_is_the_bots_day():
    assert daily.today(datetime(2026, 7, 1, 23, 30, tzinfo=UTC)) == "07-02"  # Already the 2nd in London


def test_pick_for_a_day():
    proclamation, title = daily.pick_for(1, content.DEFAULT.limits, set(), "10-18")
    assert proclamation.date.endswith("-10-18") and title == f"📅 On this day, {proclamation.when}"


def given_on(on: str) -> set[str]:
    """Every proclamation given on this day: hidden, they leave it with none."""
    return {p.id for p in proclamations.matching(on=on)}


def test_pick_for_a_day_with_none_falls_back_to_the_month():
    proclamation, title = daily.pick_for(1, proclamations.UNLIMITED, given_on("01-09"), "01-09")
    assert proclamation.date[5:7] == "01" and title.startswith("📅 This month")


# --- Posting ---

class Channel:
    def __init__(self, channel_id=600, fail=False):
        self.id, self.fail, self.sent = channel_id, fail, []

    async def send(self, embed=None, **kwargs):
        if self.fail:
            raise discord.HTTPException(types.SimpleNamespace(status=403, reason="Forbidden"), "Missing Access")
        self.sent.append(embed)


def client_with(*channels):
    by_id = {channel.id: channel for channel in channels}
    return types.SimpleNamespace(get_channel=by_id.get)


def test_post_due_posts_and_moves_on():
    now = datetime(2026, 10, 18, 8, 0, tzinfo=UTC)  # 9am in London
    db.set_daily(111, 600, "09:00", now - timedelta(minutes=1))
    channel = Channel()
    run(daily.post_due(client_with(channel), now))
    assert len(channel.sent) == 1 and channel.sent[0].title.startswith("📅 On this day, ")
    assert db.daily(111).next_run_at == datetime(2026, 10, 19, 8, 0, tzinfo=UTC)
    run(daily.post_due(client_with(channel), now))  # Not again today
    assert len(channel.sent) == 1


def test_post_due_follows_the_channels_filters():
    now = datetime(2026, 10, 18, 8, 0, tzinfo=UTC)
    db.set_channel_limits(111, 600, content.every(content.OFF))
    for _ in range(10):
        db.set_daily(111, 600, "09:00", now)
        channel = Channel()
        run(daily.post_due(client_with(channel), now))
        assert not proclamations.BY_ID[channel.sent[0].footer.text.split("#")[1].split(" ")[0]].tags


def test_post_due_skips_a_day_missed_by_hours():
    now = datetime(2026, 10, 18, 20, 0, tzinfo=UTC)
    db.set_daily(111, 600, "09:00", now - timedelta(hours=12))
    channel = Channel()
    run(daily.post_due(client_with(channel), now))
    assert channel.sent == [] and db.daily(111).next_run_at > now


def test_post_due_moves_on_even_when_posting_fails():
    now = datetime(2026, 10, 18, 8, 0, tzinfo=UTC)
    db.set_daily(111, 600, "09:00", now)
    db.set_daily(222, 999, "09:00", now)  # A channel it can't find
    run(daily.post_due(client_with(Channel(fail=True)), now))
    assert db.daily(111).next_run_at > now and db.daily(222).next_run_at > now


# --- Commands ---

def test_onthisday():
    interaction = Interaction()
    run(commands.onthisday.callback(interaction, day="5 November"))
    p = proclamations.BY_ID[interaction.last.embed.footer.text.split("#")[1].split(" ")[0]]
    assert p.date.endswith("-11-05") and interaction.last.embed.title.startswith("📅 On this day")
    assert content.allowed(p.tags, content.DEFAULT.limits)


def test_onthisday_today_and_unreadable():
    interaction = Interaction()
    run(commands.onthisday.callback(interaction))
    assert interaction.last.embed is not None
    run(commands.onthisday.callback(interaction, day="Thermidor"))
    assert interaction.last.ephemeral and "can't read" in interaction.last.content


def test_onthisday_none_that_day():
    for proclamation_id in given_on("01-09"):
        db.hide(111, proclamation_id)
    interaction = Interaction()
    run(commands.onthisday.callback(interaction, day="9 January"))
    assert interaction.last.embed.title.startswith("📅 None survive from 9 January")


def daily_command(name):
    return commands.daily_group.get_command(name)


def test_setup_daily_here_show_stop():
    interaction = Interaction(channel_id=600)
    run(daily_command("here").callback(interaction, time="6:30pm"))
    assert db.daily(111).channel_id == 600 and db.daily(111).clock == "18:30"
    assert "goes to <#600> every day at 18:30" in interaction.last.content and interaction.last.ephemeral
    moved = Interaction(channel_id=601)
    run(daily_command("here").callback(moved))
    assert db.daily(111).channel_id == 601 and "moved here from <#600>" in moved.last.content
    run(daily_command("show").callback(moved))
    assert "<#601>" in moved.last.content
    run(daily_command("stop").callback(moved))
    assert db.daily(111) is None and "No more" in moved.last.content
    run(daily_command("stop").callback(moved))
    assert "nothing to stop" in moved.last.content
    run(daily_command("show").callback(moved))
    assert "There's no Proclamation of the Day here" in moved.last.content


def test_setup_daily_bad_time():
    interaction = Interaction()
    run(daily_command("here").callback(interaction, time="teatime"))
    assert db.daily(111) is None and "can't read `teatime`" in interaction.last.content


def test_setup_reset_keeps_the_daily_post():
    run(daily_command("here").callback(Interaction()))
    run(commands.setup.get_command("reset").callback(Interaction()))
    assert db.daily(111) is not None


def test_leaving_a_server_or_deleting_the_channel_stops_it():
    db.set_daily(111, 600, "09:00", datetime.now(UTC))
    run(ProcBot().on_guild_channel_delete(types.SimpleNamespace(id=600)))
    assert db.daily(111) is None
    db.set_daily(111, 600, "09:00", datetime.now(UTC))
    run(ProcBot().on_guild_remove(Guild(111)))
    assert db.daily(111) is None
