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
| `/help` | The above, in Discord |

Searches find old spellings too: `jesuit` finds "Iesuites". Dates are as printed (Old Style: until 1752 the English
and Irish year began on 25 March).

## Running it

```
py -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
copy .env.example .env.dev        (and add a test bot's token)
.venv\Scripts\python.exe bot.py --dev
```

On Linux, `deploy/procbot.service` runs it from `/opt/procbot`. Tests: `python -m pytest`.

## The data

`procbot/data/proclamations.json` is built by `python -m procbot.tools.tcp_build` (no extra dependencies). It reads
the TCP catalogue, picks out the proclamations, downloads their TEI XML into `build/tcp/` (once), and keeps the
text as printed, with long s as s and broken words joined. `--offline` rebuilds from what's downloaded. See the
tool's docstring for how proclamations, realms, monarchs and dates are worked out.

Further reading: Robert Steele, *Tudor and Stuart Proclamations 1485-1714* (1910), and James Kelly and Mary Ann
Lyons (eds.), *The Proclamations of Ireland 1660-1820* (Irish Manuscripts Commission, 2014; in copyright, so not
used here).
