"""The slash commands: /proclaim, /wanted, /decree, /setup and /help.

/setup is only shown to people with Manage Server (Discord's default_permissions; a server can change who sees it
under Server Settings → Integrations). Its replies are only visible to whoever ran it.

A server's filters apply in all its channels, unless a channel has its own (/setup here): a channel only overrides
the categories it sets, and follows the server for the rest. Threads follow their parent channel. Hidden
proclamations are hidden in every channel. (All as in Hammered of Witches.)
"""

import logging

import discord
from discord import app_commands

from procbot import content, db, decree, proclamations, spelling

log = logging.getLogger("procbot")
NO_PINGS = discord.AllowedMentions.none()
DECREE_COLOR = discord.Color.from_str("#6B5B3E")  # Iron-gall ink: not the real ones' red

REALM_CHOICES = [app_commands.Choice(name=name.split(" ", 1)[1], value=key)
                 for key, name in proclamations.REALMS.items()]


def where(interaction: discord.Interaction) -> int:
    """Whose recent proclamations to avoid repeating: the server's, or (in DMs) the person's."""
    return interaction.guild_id if interaction.guild_id is not None else -interaction.user.id


def channel_of(interaction: discord.Interaction) -> int | None:
    """The channel whose filters apply: a thread follows its parent channel's."""
    if isinstance(interaction.channel, discord.Thread):
        return interaction.channel.parent_id
    return interaction.channel_id


def limits_here(interaction: discord.Interaction) -> dict[str, int]:
    return db.limits(interaction.guild_id, channel_of(interaction))


def nothing_found(realm: str, monarch: str, about: str) -> str:
    wanted = "".join(f" {part}" for part in (
        f"of {proclamations.REALMS[realm].split(' ', 1)[1]}" if realm else "",
        f"under {monarch}" if monarch else "",
        f"about **{discord.utils.escape_markdown(about)}**" if about else "") if part)
    if proclamations.matching(realm=realm, monarch=monarch, about=about):
        return (f"There is a proclamation{wanted}, but not one the filters here allow. "
                "(`/setup here show` has them.)")
    return f"No proclamation{wanted} survives. Try fewer words, or another monarch."


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
    to narrow it down. `modern:True` tidies the spelling. Only what the filters here allow (`/setup`). Dates are as
    printed: until 1752 the English year began on 25 March."""
    limits, hidden = limits_here(interaction), db.hidden(interaction.guild_id)
    if id:
        proclamation_id = id.strip().lstrip("#").lower()
        proclamation = proclamations.BY_ID.get(proclamation_id)
        if proclamation is None:
            await interaction.response.send_message(f"There's no proclamation `#{proclamation_id}`. The id is at "
                                                    "the end of a proclamation's footer.", ephemeral=True)
            return
        if proclamation.id in hidden or not content.allowed(proclamation.tags, limits):
            await interaction.response.send_message(f"Proclamation `#{proclamation_id}` isn't one the filters here "
                                                    "allow. (`/setup here show` has them.)", ephemeral=True)
            return
    else:
        realm_key = realm.value if realm else ""
        proclamation = proclamations.pick(where(interaction), limits, hidden, realm_key, monarch.strip(),
                                          about.strip())
        if proclamation is None:
            await interaction.response.send_message(nothing_found(realm_key, monarch.strip(), about.strip()),
                                                    ephemeral=True)
            return
    await interaction.response.send_message(embed=proclamations.embed(proclamation, modern=modern))


@app_commands.command(name="wanted", description="Proclaim someone a traitor, with a real proclamation for "
                                                 "apprehending one.")
@app_commands.describe(suspect="Who the Crown wants apprehended", modern="Tidy the old printers' spelling")
async def wanted(interaction: discord.Interaction, suspect: discord.User, modern: bool = False):
    """Names someone (without pinging them) as wanted by the Crown, with a real proclamation "for the apprehension
    of" a traitor, rebel or highwayman, and the reward on their head when it says. Only what the filters here
    allow."""
    proclamation = proclamations.pick(where(interaction), limits_here(interaction), db.hidden(interaction.guild_id),
                                      kind=proclamations.WANTED)
    if proclamation is None:
        await interaction.response.send_message("No proclamation for apprehending anyone gets past the filters here. "
                                                "(`/setup here show` has them.)", ephemeral=True)
        return
    if suspect.id == interaction.client.user.id:
        title = "📜 The Crown does not apprehend itself"
    elif suspect.id == interaction.user.id:
        title = f"🙇 {suspect.display_name} has surrendered to the Crown"
    else:
        title = f"🔔 WANTED: {suspect.display_name}"
    embed = proclamations.embed(proclamation, modern=modern, title=title)
    await interaction.response.send_message(f"{interaction.user.mention} has {suspect.mention} proclaimed a traitor.",
                                            embed=embed, allowed_mentions=NO_PINGS)


KIND_CHOICES = [app_commands.Choice(name=kind, value=kind) for kind in (decree.AGAINST, decree.FOR, decree.CONCERNING)]
VOICE_CHOICES = [app_commands.Choice(name="the King", value="king"), app_commands.Choice(name="the Queen",
                                                                                         value="queen")]


def decree_embed(made: decree.Decree, by: str, modern: bool = False) -> discord.Embed:
    tidy = spelling.modern if modern else (lambda text: text)
    embed = discord.Embed(title=proclamations.clip(made.render(f"{made.heading} {made.title}", tidy), 256),
                          color=DECREE_COLOR,
                          description=proclamations.quote(made.render("\n".join(made.paragraphs), tidy))[:4096])
    embed.set_author(name="Not a real proclamation")
    embed.add_field(name="Given", value=f"{tidy(made.dateline)}\n*{tidy(made.closing)}*", inline=False)
    embed.set_footer(text=proclamations.clip(f"Proclaimed by {by} with /decree, in the words the real ones used. "
                                             "/proclaim reads out a real one.", 2048))
    return embed


@app_commands.command(name="decree", description="Have a proclamation made about anything, in the Crown's own "
                                                 "words. (Not a real one.)")
@app_commands.describe(thing="What it's about, e.g. pineapple on pizza, the wearing of crocs",
                       kind="Against it (the default), for it, or concerning it",
                       voice="The King's (the default) or the Queen's",
                       modern="Tidy the old printers' spelling")
@app_commands.choices(kind=KIND_CHOICES, voice=VOICE_CHOICES)
async def decree_command(interaction: discord.Interaction, thing: app_commands.Range[str, 1, 100],
                         kind: app_commands.Choice[str] | None = None, voice: app_commands.Choice[str] | None = None,
                         modern: bool = False):
    """Makes up a proclamation against (or for, or concerning) whatever you like, from the formulae the real ones
    used: "WHereas His Maiestie is giuen to vnderstand…", "doth straitly charge and command…", "Giuen at Our Court
    at Whitehall…", dated today. It's marked as not real, and the footer says who proclaimed it."""
    made = decree.make(thing.strip(), kind.value if kind else decree.AGAINST, voice.value if voice else "king")
    await interaction.response.send_message(embed=decree_embed(made, interaction.user.display_name, modern),
                                            allowed_mentions=NO_PINGS)


# --- /setup ---

LEVEL_CHOICES = [
    app_commands.Choice(name="off: strip it all out", value=content.OFF),
    app_commands.Choice(name="mild: passing mentions only", value=content.MILD),
    app_commands.Choice(name="full: as the Crown had it printed", value=content.FULL),
]
LEVEL_LABELS = {content.OFF: "🚫 off", content.MILD: "🟡 mild", content.FULL: "🔥 full"}
PRESET_CHOICES = [app_commands.Choice(name=p.name, value=p.key) for p in content.PRESETS]
LOOSER_TIP = ("\n-# This channel now allows more than the rest of the server. Worth saying so in its topic, so "
              "people know what they're in for, or can mute it.")

setup = app_commands.Group(name="setup", description="Choose which proclamations may be read out in this server.",
                           guild_only=True, default_permissions=discord.Permissions(manage_guild=True))
here = app_commands.Group(name="here", description="Give this channel filters of its own, over the server's.",
                          parent=setup)


def preset_name(limits: dict[str, int]) -> str:
    preset = content.preset_for(limits)
    return preset.name if preset else "custom"


def allowed_line(limits: dict[str, int], guild_id: int) -> str:
    allowed = len(proclamations.matching(limits, db.hidden(guild_id)))
    return (f"**Preset:** {preset_name(limits)}\n"
            f"**Proclamations allowed:** {allowed:,} of {len(proclamations.PROCLAMATIONS):,}")


def settings_embed(guild: discord.Guild) -> discord.Embed:
    limits = db.limits(guild.id)
    embed = discord.Embed(title=f"⚙️ Proclamations in {guild.name}", color=proclamations.COLOR,
                          description=allowed_line(limits, guild.id))
    for category in content.CATEGORIES:
        embed.add_field(name=f"{category.emoji} {category.name}",
                        value=f"{LEVEL_LABELS[limits[category.key]]} · `/setup {category.key}`", inline=True)
    own = db.channels(guild.id)
    if own:
        lines = [f"<#{channel_id}>: {preset_name(db.limits(guild.id, channel_id))}" for channel_id in own]
        if len(lines) > 15:
            lines = lines[:15] + [f"…and {len(lines) - 15} more"]
        embed.add_field(name="Channels with filters of their own", value="\n".join(lines), inline=False)
    hidden = len(db.hidden(guild.id))
    embed.set_footer(text=f"{hidden} proclamation{'s' if hidden != 1 else ''} hidden by hand. /setup preset changes "
                          "everything at once, /setup here one channel.")
    return embed


def looser(interaction: discord.Interaction) -> bool:
    """Whether this channel allows more than its server anywhere."""
    server = db.limits(interaction.guild_id)
    return any(level > server[key] for key, level in limits_here(interaction).items())


def channel_embed(interaction: discord.Interaction) -> discord.Embed:
    channel_id = channel_of(interaction)
    own, limits = db.channel_levels(channel_id), limits_here(interaction)
    embed = discord.Embed(title="⚙️ Proclamations in this channel", color=proclamations.COLOR,
                          description=f"<#{channel_id}>\n{allowed_line(limits, interaction.guild_id)}")
    for category in content.CATEGORIES:
        source = f"set here · `/setup here {category.key}`" if category.key in own else "the server's"
        embed.add_field(name=f"{category.emoji} {category.name}",
                        value=f"{LEVEL_LABELS[limits[category.key]]} · {source}", inline=True)
    embed.set_footer(text="What isn't set here follows the server's filters. "
                          "/setup here reset to follow them for everything again.")
    return embed


@setup.command(name="show", description="Show this server's filters.")
async def setup_show(interaction: discord.Interaction):
    await interaction.response.send_message(embed=settings_embed(interaction.guild), ephemeral=True)


@here.command(name="show", description="Show this channel's filters.")
async def here_show(interaction: discord.Interaction):
    await interaction.response.send_message(embed=channel_embed(interaction), ephemeral=True)


@setup.command(name="preset", description="Set every filter at once: tame, tasteful, grim or unabridged.")
@app_commands.describe(preset="How much of the record this server sees")
@app_commands.choices(preset=PRESET_CHOICES)
async def setup_preset(interaction: discord.Interaction, preset: app_commands.Choice[str]):
    chosen = content.PRESETS_BY_KEY[preset.value]
    db.set_limits(interaction.guild_id, chosen.limits)
    log.info("[%s] preset set to %s", interaction.guild_id, chosen.key)
    await interaction.response.send_message(f"**{chosen.name}**: {chosen.about}", embed=settings_embed(interaction.guild),
                                            ephemeral=True)


@here.command(name="preset", description="Set every filter for this channel at once.")
@app_commands.describe(preset="How much of the record this channel sees")
@app_commands.choices(preset=PRESET_CHOICES)
async def here_preset(interaction: discord.Interaction, preset: app_commands.Choice[str]):
    chosen = content.PRESETS_BY_KEY[preset.value]
    db.set_channel_limits(interaction.guild_id, channel_of(interaction), chosen.limits)
    log.info("[%s] channel %s preset set to %s", interaction.guild_id, channel_of(interaction), chosen.key)
    tip = LOOSER_TIP if looser(interaction) else ""
    await interaction.response.send_message(f"This channel is now **{chosen.name}**: {chosen.about}{tip}",
                                            embed=channel_embed(interaction), ephemeral=True)


def category_command(category: content.Category, channel: bool = False) -> app_commands.Command:
    where_text = " in this channel" if channel else ""

    @app_commands.command(name=category.key,
                          description=f"How much {category.name.lower()} to allow{where_text}"[:100])
    @app_commands.describe(level="off strips it all out; mild allows passing mentions; full allows anything")
    @app_commands.choices(level=LEVEL_CHOICES)
    async def command(interaction: discord.Interaction, level: app_commands.Choice[int]):
        if channel:
            db.set_channel_limits(interaction.guild_id, channel_of(interaction), {category.key: level.value})
            log.info("[%s] channel %s %s set to %s", interaction.guild_id, channel_of(interaction), category.key,
                     level.value)
            embed, tip = channel_embed(interaction), LOOSER_TIP if looser(interaction) else ""
        else:
            db.set_level(interaction.guild_id, category.key, level.value)
            log.info("[%s] %s set to %s", interaction.guild_id, category.key, level.value)
            embed, tip = settings_embed(interaction.guild), ""
        await interaction.response.send_message(
            f"{category.emoji} **{category.name}** is now {LEVEL_LABELS[level.value]}{where_text}. "
            f"{category.about}{tip}", embed=embed, ephemeral=True)
    command.__doc__ = category.about
    return command


for _category in content.CATEGORIES:
    setup.add_command(category_command(_category))
    here.add_command(category_command(_category, channel=True))


@setup.command(name="hide", description="Never read out one proclamation in this server again (# in its footer).")
@app_commands.describe(proclamation="The proclamation's id, from the footer: #a39500")
async def setup_hide(interaction: discord.Interaction, proclamation: str):
    proclamation_id = proclamation.strip().lstrip("#").lower()
    if proclamation_id not in proclamations.BY_ID:
        await interaction.response.send_message(f"There's no proclamation `#{proclamation_id}`. The id is at the end "
                                                "of a proclamation's footer.", ephemeral=True)
        return
    newly = db.hide(interaction.guild_id, proclamation_id)
    log.info("[%s] proclamation %s hidden", interaction.guild_id, proclamation_id)
    await interaction.response.send_message(f"Proclamation `#{proclamation_id}` {'is now' if newly else 'was already'} "
                                            "hidden in this server. `/setup unhide` brings it back.", ephemeral=True)


@setup.command(name="unhide", description="Read out a proclamation you hid again.")
@app_commands.describe(proclamation="The proclamation's id: #a39500")
async def setup_unhide(interaction: discord.Interaction, proclamation: str):
    proclamation_id = proclamation.strip().lstrip("#").lower()
    if db.unhide(interaction.guild_id, proclamation_id):
        await interaction.response.send_message(f"Proclamation `#{proclamation_id}` can be read out here again.",
                                                ephemeral=True)
    else:
        await interaction.response.send_message(f"Proclamation `#{proclamation_id}` wasn't hidden.", ephemeral=True)


@setup.command(name="reset", description="Back to the default (tasteful) filters in every channel, nothing hidden.")
async def setup_reset(interaction: discord.Interaction):
    db.forget(interaction.guild_id)
    log.info("[%s] filters reset", interaction.guild_id)
    await interaction.response.send_message("Back to the defaults, in every channel.",
                                            embed=settings_embed(interaction.guild), ephemeral=True)


@here.command(name="reset", description="Make this channel follow the server's filters again.")
async def here_reset(interaction: discord.Interaction):
    had = db.forget_channel(channel_of(interaction))
    log.info("[%s] channel %s reset", interaction.guild_id, channel_of(interaction))
    message = ("This channel follows the server's filters again." if had
               else "This channel had no filters of its own: it already follows the server's.")
    await interaction.response.send_message(message, embed=channel_embed(interaction), ephemeral=True)


# --- /help ---

@app_commands.command(name="help", description="What procbot does, where its proclamations come from, and filters.")
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
        "`/proclaim id:#a39500`: a particular one, by the id in its footer\n"
        "`/wanted @someone`: proclaim them a traitor, with a real proclamation for apprehending one\n"
        "`/decree thing`: have a (made-up) proclamation against anything, in the Crown's words\n"
        "`/setup ...`: choose what this server sees (Manage Server)"))
    embed.add_field(name="Filters", inline=False, value=(
        "They're the state's voice, and some of it is ugly. Each server chooses, per category, **off** (none of "
        "it), **mild** (passing mentions) or **full**:\n"
        + "\n".join(f"{c.emoji} `{c.key}`: {c.name}" for c in content.CATEGORIES)
        + "\n\nOr `/setup preset`: "
        + ", ".join(f"**{p.name.split(' ', 1)[1]}**" for p in content.PRESETS)
        + ". New servers start on Tasteful. One that slips through can be hidden with `/setup hide`, and "
          "`/setup here ...` gives just the channel you're in rules of its own."))
    embed.add_field(name="Where they come from", inline=False, value=(
        "The [Text Creation Partnership](https://textcreationpartnership.org/)'s transcriptions of Early English "
        "Books Online, which it gave to the public domain (CC0). Each links to its full text. The spelling is as "
        "printed, and so are the dates: until 1752 the English and Irish year began on 25 March."))
    embed.add_field(name="Further reading", inline=False, value=(
        "Robert Steele, *Tudor and Stuart Proclamations 1485-1714* (1910), which lists every one known; and "
        "James Kelly and Mary Ann Lyons (eds.), *The Proclamations of Ireland 1660-1820* (Irish Manuscripts "
        "Commission, 2014)."))
    embed.set_footer(text="Tagging is done by keyword, so it errs on the strict side, but isn't perfect.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


COMMANDS = [proclaim, wanted, decree_command, setup, help_command]
