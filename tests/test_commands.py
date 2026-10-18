"""The slash commands (procbot/commands.py), run against fake interactions, and their registration."""

import re
import types

import discord
import pytest

from procbot import commands, content, db, proclamations
from procbot.bot import ProcBot
from tests.fakes import Guild, Interaction, Thread, User, run


def choice(value, name="x"):
    return discord.app_commands.Choice(name=name, value=value)


def subcommand(name):
    return commands.setup.get_command(name)


def here_command(name):
    return commands.here.get_command(name)


def shown(interaction) -> proclamations.Proclamation:
    return proclamations.BY_ID[interaction.last.embed.footer.text.split("#", 1)[1].split(" ", 1)[0]]


def shown_ids(interaction, times=30, **options) -> set[str]:
    """The proclamations /proclaim reads out here, over a few goes."""
    ids = set()
    for _ in range(times):
        run(commands.proclaim.callback(interaction, **options))
        ids.add(shown(interaction).id)
    return ids


# --- /proclaim ---

def test_proclaim_posts_one_the_default_allows():
    interaction = Interaction()
    for proclamation_id in shown_ids(interaction):
        assert content.allowed(proclamations.BY_ID[proclamation_id].tags, content.DEFAULT.limits)
    assert not interaction.last.ephemeral


def test_proclaim_about_realm_monarch():
    interaction = Interaction()
    run(commands.proclaim.callback(interaction, about="tobacco", realm=choice("england"), monarch="James I"))
    p = shown(interaction)
    assert p.realm == "england" and p.monarch == "James I" and "obacco" in p.text


def test_proclaim_modern():
    interaction = Interaction()
    run(commands.proclaim.callback(interaction, modern=True))
    assert interaction.last.embed.footer.text.endswith("spelling tidied")


def test_proclaim_by_id():
    interaction = Interaction()
    run(commands.proclaim.callback(interaction, id="#A39500"))
    assert shown(interaction).id == "a39500"
    run(commands.proclaim.callback(interaction, id="nope"))
    assert interaction.last.ephemeral and "no proclamation `#nope`" in interaction.last.content


def test_proclaim_by_id_keeps_to_the_filters():
    popish = next(p for p in proclamations.PROCLAMATIONS if p.tags.get("religion") == content.FULL)
    interaction = Interaction()
    run(commands.proclaim.callback(interaction, id=popish.id))
    assert interaction.last.ephemeral and "isn't one the filters here allow" in interaction.last.content
    db.hide(111, "a39500")
    run(commands.proclaim.callback(interaction, id="a39500"))
    assert "isn't one the filters here allow" in interaction.last.content


def test_proclaim_says_why_theres_nothing():
    interaction = Interaction()
    run(commands.proclaim.callback(interaction, about="popish"))
    assert interaction.last.ephemeral and "not one the filters here allow" in interaction.last.content
    run(commands.proclaim.callback(interaction, about="xylophone", realm=choice("ireland")))
    assert "No proclamation of Ireland about **xylophone** survives" in interaction.last.content
    db.set_limits(111, content.every(content.OFF))
    run(commands.proclaim.callback(interaction, about="plague"))
    assert "There is a proclamation about **plague**, but" in interaction.last.content


def test_proclaim_in_a_dm_uses_the_default():
    interaction = Interaction(guild=None)
    for proclamation_id in shown_ids(interaction, times=10):
        assert content.allowed(proclamations.BY_ID[proclamation_id].tags, content.DEFAULT.limits)


@pytest.mark.parametrize("suspect, title", [
    (User(2, "agnes"), "🔔 WANTED: agnes"),
    (User(1, "scott"), "🙇 scott has surrendered to the Crown"),
    (User(999, "ProcBot"), "📜 The Crown does not apprehend itself"),
])
def test_wanted(suspect, title):
    interaction = Interaction()
    run(commands.wanted.callback(interaction, suspect=suspect))
    assert interaction.last.embed.title == title
    assert interaction.last.allowed_mentions == commands.NO_PINGS and suspect.mention in interaction.last.content
    p = shown(interaction)
    assert proclamations.WANTED.search(p.names)
    assert content.allowed(p.tags, content.DEFAULT.limits)


def test_wanted_shows_the_reward():
    run(subcommand("preset").callback(Interaction(), preset=choice("unabridged")))
    interaction = Interaction()
    for _ in range(40):
        run(commands.wanted.callback(interaction, suspect=User(2, "agnes")))
        if proclamations.reward(shown(interaction)):
            break
    assert any(field.name == "💰 Reward" for field in interaction.last.embed.fields)


def test_wanted_when_the_filters_allow_none():
    for p in proclamations.matching(kind=proclamations.WANTED):
        db.hide(111, p.id)
    interaction = Interaction()
    run(commands.wanted.callback(interaction, suspect=User(2, "agnes")))
    assert interaction.last.ephemeral and "gets past the filters here" in interaction.last.content


def test_decree():
    interaction = Interaction()
    run(commands.decree_command.callback(interaction, thing="pineapple on pizza"))
    embed = interaction.last.embed
    assert embed.title == "By the King. A Proclamation against pineapple on pizza."
    assert embed.author.name == "Not a real proclamation" and "Proclaimed by scott" in embed.footer.text
    assert interaction.last.allowed_mentions == commands.NO_PINGS and not interaction.last.ephemeral
    run(commands.decree_command.callback(interaction, thing="crocs", kind=choice("for"), voice=choice("queen"),
                                         modern=True))
    embed = interaction.last.embed
    assert embed.title == "By the Queene. A Proclamation for crocs." and "Majestie" in embed.description


def test_decree_escapes_markdown():
    interaction = Interaction()
    run(commands.decree_command.callback(interaction, thing="**bold** claims"))
    assert "\\*\\*bold\\*\\*" in interaction.last.embed.description


def test_monarch_autocomplete():
    names = run(commands.monarch_names(Interaction(), "charles"))
    assert [c.value for c in names] == ["Charles I", "Charles II"]


# --- /setup ---

def test_setup_a_category_changes_what_the_server_sees():
    interaction = Interaction()
    run(subcommand("violence").callback(interaction, level=choice(content.OFF)))
    assert db.limits(111)["violence"] == content.OFF and db.limits(222)["violence"] == content.MILD  # Only here
    assert interaction.last.ephemeral and "is now 🚫 off" in interaction.last.content
    assert all("violence" not in proclamations.BY_ID[i].tags for i in shown_ids(interaction))


def test_setup_lgbt_friendly():
    run(subcommand("lgbt").callback(Interaction(), level=choice(content.OFF)))
    assert not any("lgbt" in p.tags for p in proclamations.matching(db.limits(111)))


def test_setup_preset_and_show():
    interaction = Interaction()
    run(subcommand("preset").callback(interaction, preset=choice("unabridged")))
    assert db.limits(111) == content.every(content.FULL)
    assert "**Preset:** 📜 Unabridged" in interaction.last.embed.description
    run(commands.proclaim.callback(interaction, about="popish"))
    assert shown(interaction).tags.get("religion") == content.FULL
    run(subcommand("religion").callback(interaction, level=choice(content.MILD)))
    assert "**Preset:** custom" in interaction.last.embed.description
    run(subcommand("reset").callback(interaction))
    assert db.limits(111) == content.DEFAULT.limits
    run(subcommand("show").callback(interaction))
    assert "**Preset:** ⚖️ Tasteful" in interaction.last.embed.description


def test_setup_hide_and_unhide():
    proclamation = proclamations.matching(content.DEFAULT.limits)[0]
    interaction = Interaction()
    run(subcommand("hide").callback(interaction, proclamation=f"#{proclamation.id.upper()}"))
    assert "is now hidden" in interaction.last.content and proclamation.id in db.hidden(111)
    run(subcommand("hide").callback(interaction, proclamation=proclamation.id))
    assert "was already hidden" in interaction.last.content
    run(subcommand("hide").callback(interaction, proclamation="nope"))
    assert "There's no proclamation `#nope`" in interaction.last.content
    run(subcommand("unhide").callback(interaction, proclamation=proclamation.id))
    assert proclamation.id not in db.hidden(111)
    run(subcommand("unhide").callback(interaction, proclamation=proclamation.id))
    assert "wasn't hidden" in interaction.last.content


def test_setup_here_gives_one_channel_its_own_filters():
    grim = Interaction(channel_id=666)
    run(here_command("preset").callback(grim, preset=choice("unabridged")))
    assert db.limits(111, 666) == content.every(content.FULL)
    assert db.limits(111, 500) == content.DEFAULT.limits and db.limits(111) == content.DEFAULT.limits
    assert "allows more than the rest of the server" in grim.last.content
    run(commands.proclaim.callback(grim, about="popish"))
    assert grim.last.embed is not None
    elsewhere = Interaction()
    run(commands.proclaim.callback(elsewhere, about="popish"))
    assert elsewhere.last.embed is None


def test_a_channel_follows_the_server_for_what_it_doesnt_set():
    run(here_command("violence").callback(Interaction(channel_id=666), level=choice(content.FULL)))
    assert db.channel_levels(666) == {"violence": content.FULL}
    run(subcommand("lgbt").callback(Interaction(), level=choice(content.FULL)))
    assert db.limits(111, 666)["lgbt"] == content.FULL  # The server's change reaches the channel
    run(subcommand("violence").callback(Interaction(), level=choice(content.OFF)))
    assert db.limits(111, 666)["violence"] == content.FULL  # But not over what the channel set itself
    interaction = Interaction(channel_id=666)
    run(here_command("show").callback(interaction))
    fields = {f.name: f.value for f in interaction.last.embed.fields}
    assert fields["🩸 Executions & violence"].startswith("🔥 full · set here")
    assert fields["🌍 Other peoples"] == "🚫 off · the server's"


def test_a_stricter_channel_gets_no_tip():
    interaction = Interaction(channel_id=777)
    run(here_command("preset").callback(interaction, preset=choice("tame")))
    assert "allows more" not in interaction.last.content


def test_threads_follow_their_channel():
    run(here_command("preset").callback(Interaction(channel_id=666), preset=choice("tame")))
    in_thread = Interaction(thread=Thread(9001, parent_id=666))
    assert commands.channel_of(in_thread) == 666
    assert all(not proclamations.BY_ID[i].tags for i in shown_ids(in_thread))


def test_setup_here_reset_and_the_server_overview():
    run(here_command("preset").callback(Interaction(channel_id=666), preset=choice("unabridged")))
    run(here_command("sex").callback(Interaction(channel_id=667), level=choice(content.FULL)))
    interaction = Interaction()
    run(subcommand("show").callback(interaction))
    overview = interaction.last.embed.fields[-1]
    assert overview.name == "Channels with filters of their own"
    assert overview.value == "<#666>: 📜 Unabridged\n<#667>: custom"

    reset = Interaction(channel_id=666)
    run(here_command("reset").callback(reset))
    assert "follows the server's filters again" in reset.last.content and db.channel_levels(666) == {}
    run(here_command("reset").callback(reset))
    assert "had no filters of its own" in reset.last.content

    run(subcommand("reset").callback(Interaction()))  # The server's reset clears every channel too
    assert db.channels(111) == {}


def test_settings_embed_fits():
    embed = commands.settings_embed(Guild())
    assert len(embed.fields) == len(content.CATEGORIES) and len(embed) <= 6000


# --- /help and registration ---

def test_help():
    interaction = Interaction()
    run(commands.help_command.callback(interaction))
    embed = interaction.last.embed
    assert interaction.last.ephemeral and all(f"`{c.key}`" in embed.fields[1].value for c in content.CATEGORIES)
    assert len(embed) <= 6000 and all(len(field.value) <= 1024 for field in embed.fields)


def test_the_commands_register_within_discords_limits():
    bot = ProcBot()
    names = {command.name for command in bot.tree.get_commands()}
    assert names == {"proclaim", "wanted", "decree", "onthisday", "setup", "help"}
    for command in bot.tree.get_commands():
        payload = command.to_dict(bot.tree)
        stack = [payload]
        while stack:
            item = stack.pop()
            assert re.fullmatch(r"[-_a-z0-9]{1,32}", item["name"]), item["name"]
            assert 1 <= len(item["description"]) <= 100, item["description"]
            assert len(item.get("options", [])) <= 25 and len(item.get("choices", [])) <= 25
            assert all(len(c["name"]) <= 100 for c in item.get("choices", []))
            stack.extend(item.get("options", []))
    setup = commands.setup.to_dict(bot.tree)
    assert int(setup["default_member_permissions"]) == discord.Permissions(manage_guild=True).value
    assert {o["name"] for o in setup["options"]} >= set(content.BY_KEY) | {"show", "preset", "hide", "reset"}


def test_leaving_a_server_forgets_it():
    db.set_level(111, "violence", content.FULL)
    db.hide(111, "a39500")
    run(ProcBot().on_guild_remove(Guild(111)))
    assert db.limits(111) == content.DEFAULT.limits and db.hidden(111) == set()


def test_deleting_a_channel_forgets_its_filters():
    db.set_channel_limits(111, 666, {"violence": content.FULL})
    run(ProcBot().on_guild_channel_delete(types.SimpleNamespace(id=666)))
    assert db.channel_levels(666) == {}
