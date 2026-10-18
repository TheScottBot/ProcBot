# procbot

A Discord bot that reads out real proclamations of the kings, queens, lords lieutenant and privy councils of
England, Ireland and Scotland, 1485-1700, as they were printed and posted up: against tobacco, starch and coffee
houses, for the apprehension of traitors, on plague, Jesuits and the price of ale.

About 1,800 of them, from the [Text Creation Partnership](https://textcreationpartnership.org/)'s transcriptions of
Early English Books Online, which are public domain (CC0). Each links to its full text. Built the way
[Hammered of Witches](https://github.com/TheScottBot/Hammered-of-Witches) is.

## Commands

| Command | What it does |
|---|---|
| `/proclaim [about] [realm] [monarch] [modern]` | A random proclamation, or one that mentions something: `about: tobacco`, `realm: Ireland`, `monarch: Elizabeth I`. `modern: True` tidies the printers' spelling (vnto, haue, Maiestie) |
| `/proclaim id:#a39500` | A particular one, by the id in its footer |
| `/wanted @someone` | Proclaim them a traitor (named, not pinged), with a real proclamation "for the apprehension of" one, and the reward when it says |
| `/decree thing [kind] [voice]` | A made-up proclamation `against` (or `for`, or `concerning`) anything, by the King or the Queen, in the real ones' words and spelling, dated today. Marked as not real |
| `/setup show` | This server's filters, and how many proclamations they allow |
| `/setup preset` | Every filter at once: 🕊️ Tame, ⚖️ Tasteful (the default), 🪓 Grim, 📜 Unabridged |
| `/setup <category> level:` | One filter: **off** (none of it), **mild** (passing mentions), **full** (anything) |
| `/setup hide` / `unhide` | Hide one proclamation that slipped through, by the `#id` in its footer |
| `/setup reset` | Back to the default in every channel, with nothing hidden |
| `/setup here …` | The same for just the channel you're in: `here show`, `here preset`, `here <category>`, `here reset` |
| `/help` | The above, in Discord |

Searches find old spellings too: `jesuit` finds "Iesuites". Dates are as printed (Old Style: until 1752 the English
and Irish year began on 25 March).

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

The default (Tasteful) allows 1,650 of the 1,812; Tame 1,224.

## Running it

```
py -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
copy .env.example .env.dev        (and add a test bot's token)
.venv\Scripts\python.exe bot.py --dev
```

On Linux, `deploy/procbot.service` runs it from `/opt/procbot`. Tests: `python -m pytest`.

## The data

`procbot/data/proclamations.json` is built by `python -m procbot.tools.proclamations_build` (no extra
dependencies). It reads the Text Creation Partnership's catalogue, picks out the proclamations, downloads their
TEI XML into `build/tcp/` (once), and keeps the text as printed, with long s as s and broken words joined.
`--offline` rebuilds from what's downloaded. See the tool's docstring for how proclamations, realms, monarchs and
dates are worked out.

Further reading: Robert Steele, *Tudor and Stuart Proclamations 1485-1714* (1910), and James Kelly and Mary Ann
Lyons (eds.), *The Proclamations of Ireland 1660-1820* (Irish Manuscripts Commission, 2014; in copyright, so not
used here).
