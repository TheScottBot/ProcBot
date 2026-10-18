<p align="center"><img src="assets/discord-banner.png" alt="ProcBot: a pink scroll with a crowned wax seal. Proclamations of your Server"></p>

# ProcBot

A Discord bot that reads out real proclamations of the kings, queens, lords lieutenant and privy councils of
England, Ireland and Scotland, 1485-1714, as they were printed and posted up: against tobacco, starch and coffee
houses, for the apprehension of traitors, on plague, Jesuits and the price of ale. Built the way
[Hammered of Witches](https://github.com/TheScottBot/Hammered-of-Witches) is.

8,790 of them (4,065 English, 3,271 Scottish, 1,454 Irish), from two public-domain sources:

- **1,812 in full**, from the [Text Creation Partnership](https://textcreationpartnership.org/)'s transcriptions of
  Early English Books Online (CC0), 1509-1700. Each links to its full text.
- **6,978 as summaries**, from Robert Steele's calendar of every proclamation he knew of, *A Bibliography of Royal
  Proclamations of the Tudor and Stuart Sovereigns 1485-1714* (1910): the date, who issued it, its title or first
  words, and Steele's summary of what it says. Read from the Wellcome Library's scans on archive.org, so with the
  odd OCR slip; each links to its page. Most of the Irish ones are only here.

**[Add it to your server](https://discord.com/oauth2/authorize?client_id=CLIENT_ID&permissions=18432&integration_type=0&scope=bot+applications.commands)**
· [Website](https://thescottbot.github.io/ProcBot/)
· [Terms of Service](https://thescottbot.github.io/ProcBot/terms.html)
· [Privacy Policy](https://thescottbot.github.io/ProcBot/privacy.html)

## Commands

| Command | What it does |
|---|---|
| `/proclaim [about] [realm] [monarch] [modern]` | A random proclamation, or one that mentions something: `about: tobacco`, `realm: Ireland`, `monarch: Elizabeth I`. `modern: True` tidies the printers' spelling (vnto, haue, Maiestie) |
| `/proclaim id:#a39500` | A particular one, by the id in its footer |
| `/wanted @someone` | Proclaim them a traitor (named, not pinged), with a real proclamation "for the apprehension of" one, and the reward when it says |
| `/decree thing [kind] [voice]` | A made-up proclamation `against` (or `for`, or `concerning`) anything, by the King or the Queen, in the real ones' words and spelling, dated today. Marked as not real |
| `/onthisday [day]` | One given on today's date (or `day: 5 November`) in some year, or that month if none survives from the day |
| `/setup daily here [time]` | Post a Proclamation of the Day in this channel, at `time:` (9am by default, UK time); `daily show`, `daily stop` |
| `/setup show` | This server's filters, and how many proclamations they allow |
| `/setup preset` | Every filter at once: 🕊️ Tame, ⚖️ Tasteful (the default), 🪓 Grim, 📜 Unabridged |
| `/setup <category> level:` | One filter: **off** (none of it), **mild** (passing mentions), **full** (anything) |
| `/setup hide` / `unhide` | Hide one proclamation that slipped through, by the `#id` in its footer |
| `/setup reset` | Back to the default in every channel, with nothing hidden |
| `/setup here …` | The same for just the channel you're in: `here show`, `here preset`, `here <category>`, `here reset` |
| `/help` | The above, in Discord |

Searches find old spellings too: `jesuit` finds "Iesuites". Dates are as printed: Old Style, the Julian calendar,
ten or eleven days behind ours, and until 1752 the English and Irish year began on 25 March. "On this day" goes by
the printed date. The Proclamation of the Day is one given on that day of the year (every day of the year has
one), and follows its channel's filters.

### Filters

The proclamations are the state's voice, and some of it is ugly. As in Hammered of Witches, every one is tagged
by keyword (`procbot/content.py`), and each server, or channel, chooses how much of each category it allows.
`/setup` needs **Manage Server**, and its replies are only visible to whoever ran it.

| `/setup …` | Covers |
|---|---|
| `religion` | "Papists", "popery" and "idolatry"; Jesuits banished, recusants fined, Quakers and conventicles broken up |
| `peoples` | "Savages", "blackamoors", Jews, "Egyptians" (Romani people), "wild Irish"; Turks, Moors, Highland "broken men" |
| `violence` | Hanging, drawing and quartering, bounties "dead or alive", massacres; "upon pain of death" in passing |
| `sex` | Rape and "ravishing"; whores, bawdy-houses, adultery |
| `lgbt` | "The detestable vice of buggery", sodomy. `/setup lgbt level:off` makes the bot LGBTQ+-friendly |
| `plague` | The plague and pestilence; infection and sickness |

The default (Tasteful) allows 8,204 of the 8,790; Tame 7,196.

## Running it

```
py -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
copy .env.example .env.dev        (and add a test bot's token)
.venv\Scripts\python.exe bot.py --dev
```

On Linux, `deploy/procbot.service` runs it from `/opt/procbot`. Tests: `python -m pytest`.

## The data

Two files, each built by a tool (no extra dependencies; `--offline` rebuilds from what's already downloaded into
`build/`, which isn't kept). Build them in this order:

1. `python -m procbot.tools.proclamations_build` → `procbot/data/proclamations.json`. It reads the Text Creation
   Partnership's catalogue, picks out the proclamations, downloads their TEI XML, and keeps the text as printed,
   with long s as s and broken words joined.
2. `python -m procbot.tools.steele_build` → `procbot/data/calendar.json`. It reads archive.org's OCR of Steele's
   two volumes page by page, splits it into entries (date, issuer, title or opening, Steele's summary and
   abstract, signatories, page), and marks the ones the first file has the text of, which the bot leaves out.

Each tool's docstring says how it works things out. The bot tags every proclamation for the filters when it
starts, and keeps the tags in `build/tags.json` until `content.py` or the data changes.

Further reading: James Kelly and Mary Ann Lyons (eds.), *The Proclamations of Ireland 1660-1820* (Irish
Manuscripts Commission, 2014), which prints the Irish ones in full; it's in copyright, so not used here.

## Website

The site, with the Terms of Service and Privacy Policy that Discord asks for, is plain HTML in `docs/`, served by
GitHub Pages: Settings → Pages → Deploy from a branch → `main`, folder `/docs`. `docs/DISCORD_LISTING.md` has the
copy for the Developer Portal and App Directory. The privacy policy promises the bot stores nothing about users, so
keep it true: no user IDs or names in the database or the logs. The invite links (here, `docs/index.html` and the
listing) need the bot's application ID in place of `CLIENT_ID`.

## Artwork

In `assets/`, as for Hammered of Witches: `icon.png` (1254 × 1254, the app icon; its pink is the embeds' colour),
`discord-banner.png` (2111 × 745, the bot's profile banner and this README's header) and `rich-presence.png`
(1672 × 941, 16:9, the Rich Presence invite image). `docs/` has the site's copies: `icon.png` (512 × 512),
`favicon.png` (64 × 64) and `banner.jpg` (1280 × 452, from the profile banner).
