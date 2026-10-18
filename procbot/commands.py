"""The slash commands: /proclaim and /help."""

import logging

import discord
from discord import app_commands

from procbot import proclamations

log = logging.getLogger("procbot")

REALM_CHOICES = [app_commands.Choice(name=name.split(" ", 1)[1], value=key)
                 for key, name in proclamations.REALMS.items()]


def where(interaction: discord.Interaction) -> int:
    """Whose recent proclamations to avoid repeating: the server's, or (in DMs) the person's."""
    return interaction.guild_id if interaction.guild_id is not None else -interaction.user.id


def nothing_found(realm: str, monarch: str, about: str) -> str:
    wanted = " ".join(part for part in (
        f"of {proclamations.REALMS[realm].split(' ', 1)[1]}" if realm else "",
        f"under {monarch}" if monarch else "",
        f"about **{discord.utils.escape_markdown(about)}**" if about else "") if part)
    return f"No proclamation {wanted} survives. Try fewer words, or another monarch."


async def monarch_names(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    current = current.lower()
    return [app_commands.Choice(name=name, value=name) for name in proclamations.MONARCHS
            if current in name.lower()][:25]


@app_commands.command(name="proclaim", description="Read out a real royal proclamation of England, Ireland or "
                                                   "Scotland (1485-1700).")
@app_commands.describe(about="Only proclamations that mention this, e.g. tobacco, starch, coffee, ale, plague",
                       realm="Only England's, Ireland's or Scotland's",
                       monarch="Only those under this monarch",
                       modern="Tidy the old printers' spelling (vnto, haue, Maiestie)",
                       id="A particular one, by the # in its footer")
@app_commands.choices(realm=REALM_CHOICES)
@app_commands.autocomplete(monarch=monarch_names)
async def proclaim(interaction: discord.Interaction, about: str = "", realm: app_commands.Choice[str] | None = None,
                   monarch: str = "", modern: bool = False, id: str = ""):
    """A random proclamation, as printed, from the transcriptions of the Text Creation Partnership: who issued it,
    when, the opening, and what it commands, linked to the full text. Give `about:` for ones that mention something
    (all the words you give; old spellings are found too, so `jesuit` finds "Iesuites"), and `realm:` or `monarch:`
    to narrow it down. `modern:True` tidies the spelling. Dates are as printed: until 1752 the English year began on
    25 March."""
    realm_key = realm.value if realm else ""
    if id:
        proclamation = proclamations.BY_ID.get(id.strip().lstrip("#").lower())
        if proclamation is None:
            await interaction.response.send_message(f"There's no proclamation `#{id.strip().lstrip('#')}`. The id is "
                                                    "at the end of a proclamation's footer.", ephemeral=True)
            return
    else:
        proclamation = proclamations.pick(where(interaction), realm_key, monarch.strip(), about.strip())
        if proclamation is None:
            await interaction.response.send_message(nothing_found(realm_key, monarch.strip(), about.strip()),
                                                    ephemeral=True)
            return
    await interaction.response.send_message(embed=proclamations.embed(proclamation, modern=modern))


@app_commands.command(name="help", description="What procbot does, and where its proclamations come from.")
async def help_command(interaction: discord.Interaction):
    counts = {realm: sum(p.realm == realm for p in proclamations.PROCLAMATIONS) for realm in proclamations.REALMS}
    embed = discord.Embed(
        title="📜 procbot", color=proclamations.COLOR,
        description="Real proclamations of the kings, queens, lords lieutenant and privy councils of England, "
                    "Ireland and Scotland, 1485-1700, as they were printed and posted up: against tobacco, starch "
                    "and coffee houses; for the apprehension of traitors; on plague, Jesuits and the price of ale. "
                    f"{len(proclamations.PROCLAMATIONS):,} of them: "
                    + ", ".join(f"{counts[key]:,} {name}" for key, name in proclamations.REALMS.items()) + ".")
    embed.add_field(name="Commands", inline=False, value=(
        "`/proclaim [about] [realm] [monarch] [modern]`: a random proclamation, or one about something\n"
        "`/proclaim id:#a39500`: a particular one, by the id in its footer"))
    embed.add_field(name="Where they come from", inline=False, value=(
        "The [Text Creation Partnership](https://textcreationpartnership.org/)'s transcriptions of Early English "
        "Books Online, which it gave to the public domain (CC0). Each links to its full text. The spelling is as "
        "printed, and so are the dates: until 1752 the English and Irish year began on 25 March."))
    embed.add_field(name="Further reading", inline=False, value=(
        "Robert Steele, *Tudor and Stuart Proclamations 1485-1714* (1910), which lists every one known; and "
        "James Kelly and Mary Ann Lyons (eds.), *The Proclamations of Ireland 1660-1820* (Irish Manuscripts "
        "Commission, 2014)."))
    await interaction.response.send_message(embed=embed, ephemeral=True)


COMMANDS = [proclaim, help_command]
