"""The slash commands (procbot/commands.py), run against fake interactions, and their registration."""

import discord

from procbot import commands, proclamations
from procbot.bot import ProcBot
from tests.fakes import Interaction, run


def choice(value, name="x"):
    return discord.app_commands.Choice(name=name, value=value)


def shown(interaction) -> proclamations.Proclamation:
    return proclamations.BY_ID[interaction.last.embed.footer.text.split("#", 1)[1].split(" ", 1)[0]]


def test_proclaim_posts_one():
    interaction = Interaction()
    run(commands.proclaim.callback(interaction))
    assert interaction.last.embed is not None and not interaction.last.ephemeral


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


def test_proclaim_nothing_found():
    interaction = Interaction()
    run(commands.proclaim.callback(interaction, about="xylophone", realm=choice("ireland")))
    assert interaction.last.ephemeral and "of Ireland" in interaction.last.content
    assert "xylophone" in interaction.last.content


def test_proclaim_in_a_dm():
    interaction = Interaction(guild=None)
    run(commands.proclaim.callback(interaction))
    assert interaction.last.embed is not None


def test_monarch_autocomplete():
    names = run(commands.monarch_names(Interaction(), "charles"))
    assert [c.value for c in names] == ["Charles I", "Charles II"]


def test_help():
    interaction = Interaction()
    run(commands.help_command.callback(interaction))
    embed = interaction.last.embed
    assert interaction.last.ephemeral and len(embed) <= 6000
    assert all(len(field.value) <= 1024 for field in embed.fields)


def test_commands_register():
    bot = ProcBot()
    names = {command.name for command in bot.tree.get_commands()}
    assert names == {"proclaim", "help"}
    for command in bot.tree.get_commands():
        assert len(command.description) <= 100
