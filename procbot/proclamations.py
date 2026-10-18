"""The proclamations: loading, searching, picking one, and how one looks in Discord.

Two sources, as one list:
- data/proclamations.json (tools/proclamations_build.py): the full text of 1,812, from EEBO-TCP;
- data/calendar.json (tools/steele_build.py): Steele's 1910 calendar of the rest, 1485-1714, with his summaries.
  An entry for one that EEBO-TCP has the text of ("tcp") is left out: the text is better.
"""

import hashlib
import json
import random
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import discord

from procbot import content, spelling

DATA = Path(__file__).resolve().parent / "data"
COLOR = discord.Color.from_str("#FF1A70")  # The icon's pink (assets/icon.png)
SOURCE = "EEBO-TCP, public domain"
CALENDAR_SOURCE = "Steele, Tudor and Stuart Proclamations (1910)"
STATUS = {"printed": "Printed: Steele lists where copies are.", "manuscript": "Survives only in manuscript.",
          "lost": "No copy known: Steele knew of it from other records."}
REALMS = {"england": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 England", "ireland": "☘️ Ireland", "scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scotland"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
EXCERPT = 1000  # Characters of the opening shown
COMMAND_EXCERPT = 600  # And of what it commands, if that comes later


@dataclass(frozen=True)
class Proclamation:
    id: str  # The TCP id, lower case: "a39500"; or Steele's, by realm and number: "ire776"
    phase: int  # EEBO-TCP phase 1 or 2: which of Michigan's collections it's in (0 for Steele's)
    realm: str  # england, ireland, scotland
    title: str  # The catalogue's; Steele's as printed, or ""
    paragraphs: tuple[str, ...]  # The text; for Steele's, his abstract
    issuer: str = ""  # "Sovereign", "Privy Council", "Lord Lieutenant"
    holder: str = ""  # Who held the office, if not the sovereign: "Ormonde", "O. Cromwell"
    monarch: str = ""
    date: str = ""  # "1696-05-23", "1696-05" or "1696", Old Style
    heading: tuple[str, ...] = ()  # As printed: "By the King.", "A PROCLAMATION for…"
    cut: bool = False  # The text was cut short in the build: the link has the rest
    signed: tuple[str, ...] = ()
    dateline: str = ""  # "Given at our Court at Whitehall, the…"
    place: str = ""  # Where it was printed
    printer: str = ""
    # Steele's calendar only:
    source: str = "tcp"  # "tcp" or "steele"
    summary: str = ""  # Steele's own, in brackets in the calendar: "Customs on Foreign and Colonial Produce"
    opening: str = ""  # Its first words, as printed: "Wee the Lord Lieutenant"
    status: str = ""  # printed, manuscript or lost
    number: str = ""  # Steele's number, in its volume's part: "776"
    book: str = ""  # The archive.org scan
    leaf: int = 0  # Its page in the scan, from 0
    page: str = ""  # Its page as printed
    tags: dict | None = field(default=None, repr=False, compare=False)  # category -> level (content.py); from the cache
    text: str = field(init=False, repr=False, compare=False)  # All of it, for searching and tagging

    def __post_init__(self):
        object.__setattr__(self, "text", " ".join(self.heading + (self.title, self.summary, self.opening)
                                                  + self.paragraphs))
        if self.tags is None:
            object.__setattr__(self, "tags", content.tag(self.text))

    @property
    def calendar(self) -> bool:
        """From Steele's calendar: his summary, not the proclamation's text."""
        return self.source == "steele"

    @property
    def headline(self) -> str:
        """What to call it: as printed if we have it, or Steele's summary of it."""
        if self.calendar:
            return self.title or self.summary or (f"{self.opening} …" if self.opening else "A Proclamation")
        return " ".join(self.heading) or self.title

    @property
    def names(self) -> str:
        """Everything it's called, for telling what kind it is (WANTED): headings, title and Steele's summary."""
        return " ".join(self.heading + (self.title, self.summary))

    @property
    def url(self) -> str:
        """Its page in the University of Michigan's EEBO-TCP reader, or in the scan of Steele's calendar."""
        if self.calendar:
            return f"https://archive.org/details/{self.book}/page/n{self.leaf}/mode/1up"
        collection = "eebo" if self.phase == 1 else "eebo2"
        return f"https://quod.lib.umich.edu/e/{collection}/{self.id.upper()}.0001.001"

    @property
    def source_url(self) -> str:
        """The transcription itself, TEI XML on GitHub (or for Steele's, the same page)."""
        if self.calendar:
            return self.url
        return f"https://github.com/textcreationpartnership/{self.id.upper()}"

    @property
    def when(self) -> str:
        """'23 May 1696', 'May 1696' or '1696'."""
        parts = self.date.split("-")
        if len(parts) == 3:
            return f"{int(parts[2])} {MONTHS[int(parts[1]) - 1]} {parts[0]}"
        if len(parts) == 2:
            return f"{MONTHS[int(parts[1]) - 1]} {parts[0]}"
        return self.date

    @property
    def year(self) -> int | None:
        return int(self.date[:4]) if self.date[:4].isdigit() else None

    @property
    def by(self) -> str:
        """Who issued it, for the embed: "Charles II", "Lord Lieutenant (Ormonde), under Charles II"."""
        if self.issuer in SOVEREIGNS:
            return self.monarch
        office = f"{self.issuer} ({self.holder})" if self.holder else self.issuer
        return f"{office}, under {self.monarch}" if self.monarch and self.monarch != "the Commonwealth" else office


# Steele says "BY THE KING", "BY THE QUEENE", …: the monarch, not an office.
SOVEREIGNS = {"", "Sovereign", "King", "Queen", "Queene", "Quene", "King and Queen", "King and Queene"}


def from_calendar(entry: dict, tags: dict | None = None) -> Proclamation:
    return Proclamation(
        entry["id"], 0, entry["realm"], entry.get("title", ""), (entry["abstract"],) if entry.get("abstract") else (),
        issuer=entry.get("issuer", ""), monarch=entry.get("monarch", ""), date=entry["date"],
        signed=(entry["signed"],) if entry.get("signed") else (), dateline=entry.get("dateline", ""),
        source="steele", summary=entry.get("summary", ""), opening=entry.get("opening", ""),
        status=entry.get("status", ""), number=entry.get("number", ""), book=entry["book"], leaf=entry["leaf"],
        page=entry.get("page", ""), tags=tags)


TAGS_CACHE = Path(__file__).resolve().parent.parent / "build" / "tags.json"


def load() -> list[Proclamation]:
    """Both sources. Tagging nearly 9,000 takes seconds, so the tags are kept in build/tags.json between runs, for
    as long as content.py and the data are the same."""
    files = [DATA / "proclamations.json", DATA / "calendar.json", Path(content.__file__)]
    data = [path.read_bytes() for path in files]
    key = hashlib.sha256(b"".join(data)).hexdigest()
    try:
        cache = json.loads(TAGS_CACHE.read_text(encoding="utf-8"))
        tags = cache["tags"] if cache.get("key") == key else {}
    except (OSError, ValueError, KeyError):
        tags = {}
    raw, calendar = json.loads(data[0]), json.loads(data[1])
    texts = [Proclamation(**{key: tuple(value) if isinstance(value, list) else value for key, value in entry.items()},
                          tags=tags.get(entry["id"])) for entry in raw]
    out = texts + [from_calendar(entry, tags.get(entry["id"])) for entry in calendar if "tcp" not in entry]
    if len(tags) != len(out):
        try:
            TAGS_CACHE.parent.mkdir(parents=True, exist_ok=True)
            TAGS_CACHE.write_text(json.dumps({"key": key, "tags": {p.id: p.tags for p in out}}), encoding="utf-8")
        except OSError:
            pass  # Read-only: it'll tag them again next time
    return out


PROCLAMATIONS = load()
BY_ID = {p.id: p for p in PROCLAMATIONS}
REIGN_ORDER = ["Henry VII", "Henry VIII", "Edward VI", "Mary I", "Elizabeth I", "James IV", "James V",
               "Mary, Queen of Scots", "James VI", "James I", "Charles I", "the Commonwealth", "Charles II", "James II",
               "James VII", "William III and Mary II", "William II and Mary II", "William III", "William II", "Anne"]
MONARCHS = sorted({p.monarch for p in PROCLAMATIONS if p.monarch},
                  key=lambda name: REIGN_ORDER.index(name) if name in REIGN_ORDER else len(REIGN_ORDER))

# The last few shown in each server (or DM), so the same one doesn't come up twice in a row.
RECENT_SIZE = 100
recent: dict[int, deque] = {}

# Plenty are routine: parliament put off again, a fast day, a fair moved. They stay, but come up less often than
# the ones about tobacco, starch, wolves and Jesuits.
ROUTINE = re.compile(r"\b(prorog|adiourn|adjourn|continu\w* (of )?(the )?parliament|dissol\w*|general fast|"
                     r"thanksgiving|fast day|day of humiliation|fair|term|assiz|sheriff|writs?)\b", re.I)


def weight(proclamation: Proclamation) -> int:
    """How often it comes up, against the others. The full texts more than Steele's summaries (there are four
    times as many of them), and his summaries with an abstract more than the bare titles."""
    routine = ROUTINE.search(proclamation.headline)
    if proclamation.calendar:
        return (1 if routine else 2) + bool(proclamation.paragraphs)
    return 2 if routine else 6


WEIGHTS = {p.id: weight(p) for p in PROCLAMATIONS}


def words_in(query: str) -> list[re.Pattern]:
    """Each word of a search, matched at the start of a word, in either spelling: 'iesuit' and 'jesuit' both find
    'Iesuites'."""
    patterns = []
    for word in re.findall(r"[A-Za-z']+", query):
        letters = "".join(f"[{c}{spelling_twin(c)}]" if spelling_twin(c) else re.escape(c) for c in word.lower())
        patterns.append(re.compile(rf"\b{letters}", re.I))
    return patterns


def spelling_twin(letter: str) -> str:
    """The letter printers used in its place: u/v, i/j/y."""
    return {"u": "v", "v": "u", "i": "jy", "j": "i", "y": "i"}.get(letter, "")


UNLIMITED = content.every(content.FULL)


def on_date(proclamation: Proclamation, on: str) -> bool:
    """Whether it was given on this day of the year ("10-18") or in this month ("10"), any year, as printed."""
    if len(on) == 5:
        return len(proclamation.date) == 10 and proclamation.date[5:] == on
    return len(proclamation.date) >= 7 and proclamation.date[5:7] == on


def matching(limits: dict[str, int] = UNLIMITED, hidden: set[str] = frozenset(), realm: str = "", monarch: str = "",
             about: str = "", kind: re.Pattern | None = None, on: str = "") -> list[Proclamation]:
    """The proclamations these limits allow (content.py) and aren't hidden, of this realm and monarch and about these
    words, if given. `kind` must match what it's called (names): WANTED for the ones for apprehending someone. `on` is a
    day ("10-18") or month ("10") of any year."""
    patterns = words_in(about)
    return [p for p in PROCLAMATIONS if p.id not in hidden and content.allowed(p.tags, limits)
            and (not realm or p.realm == realm) and (not monarch or p.monarch == monarch)
            and all(pattern.search(p.text) for pattern in patterns)
            and (kind is None or kind.search(p.names)) and (not on or on_date(p, on))]


def pick(where: int, limits: dict[str, int] = UNLIMITED, hidden: set[str] = frozenset(), realm: str = "",
         monarch: str = "", about: str = "", kind: re.Pattern | None = None, on: str = "") -> Proclamation | None:
    """A random proclamation that matching() allows, avoiding ones shown here lately."""
    candidates = matching(limits, hidden, realm, monarch, about, kind, on)
    if not candidates:
        return None
    shown = recent.setdefault(where, deque(maxlen=RECENT_SIZE))
    fresh = [p for p in candidates if p.id not in shown] or candidates
    proclamation = random.choices(fresh, weights=[WEIGHTS.get(p.id, 1) for p in fresh])[0]
    shown.append(proclamation.id)
    return proclamation


# Proclamations for catching someone: "for the apprehension of", "for discovering and apprehending", "offering a
# reward for", and Steele's "For the arrest of the murderers of …". /wanted reads these out.
WANTED = re.compile(r"\bapprehen|\bdisco[uv]er\w* and apprehen|\bfor the taking of|\boffering a reward|"
                    r"\bfor the arrest of|\breward for (the )?(arrest|discovery|apprehen|taking)", re.I)
NUMBER_WORDS = (r"(?:an?|one|two|three|four|fiue|five|six|seuen|seven|eight|nine|ten|tenne|eleuen|eleven|twelue|"
                r"twelve|\w+teen|twenty|thirty|forty|fourty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|and)")
# "Five hundred pounds", "two thousand merks", and Steele's "£40"
MONEY = re.compile(rf"\b((?:{NUMBER_WORDS}[\s-]+){{0,6}}{NUMBER_WORDS}|\d[\d,]*)\s+(pounds?|merks|markes|marks|"
                   rf"guineas|crownes|crowns)\b|£\s?\d[\d,]*", re.I)


def reward(proclamation: Proclamation) -> str:
    """The reward offered, if it says: "Five hundred pounds", "Two thousand merks". The first sum of money in the
    250 characters after "reward", or in a proclamation for apprehending someone, after "the sum of" ("Wee doe
    promise to bestow vpon such person as shall apprehend the said Feild … the summe of tenne Pounds")."""
    money = None
    for found in re.finditer(r"\breward", proclamation.text, re.I):
        # Steele puts the sum first ("£40 reward for…"), the proclamations after
        if money := MONEY.search(proclamation.text, found.end(), found.end() + 250) or \
                re.search(rf"(?:{MONEY.pattern})\s*$", proclamation.text[max(0, found.start() - 30):found.start()],
                          re.I):
            break
    if not money and WANTED.search(proclamation.names):
        money = next((found for found in MONEY.finditer(proclamation.text)
                      if re.search(r"\bsumm?e? of\s*$", proclamation.text[max(0, found.start() - 12):found.start()],
                                   re.I)), None)
    if not money:
        return ""
    amount = re.sub(r"\s+", " ", money.group(0)).strip()
    return amount[0].upper() + amount[1:].lower()


def clip(text: str, limit: int) -> str:
    """Text cut to a limit at a word, with "…" if cut."""
    if len(text) <= limit:
        return text
    return text[:limit - 2].rsplit(" ", 1)[0].rstrip(",;:") + " …"


# "We do hereby straitly charge and command", "His Majestie doth will and require", "Wee doe therefore …"
COMMANDS = re.compile(r"\b(?:do(?:e|th|eth)?|doo)\s+(?:\w+\s+){0,4}?(?:charge|command|require|will|forbid|prohibit|"
                      r"publish|declare|ordain|enioyne|enjoyne)", re.I)


def excerpt(proclamation: Proclamation) -> str:
    """The opening ("Whereas…"), and if it comes later, what it commands. Paragraphs kept."""
    body = "\n".join(proclamation.paragraphs)
    opening = clip(body, EXCERPT)
    command = COMMANDS.search(body, len(opening))
    if command and len(body) > EXCERPT:
        # From the start of the sentence it's in
        start = max(body.rfind(stop, 0, command.start()) for stop in (". ", "; ", ": ", "\n")) + 1
        if start > len(opening) - 4:
            return f"{opening}\n\n… {clip(body[start:].strip(), COMMAND_EXCERPT)}"
    return opening


def quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in discord.utils.escape_markdown(text).split("\n"))


def calendar_description(proclamation: Proclamation, tidy) -> str:
    """Steele's entry: his summary (when the title doesn't already say it), the opening words as printed, and his
    abstract."""
    escape = discord.utils.escape_markdown
    parts = []
    if proclamation.summary and proclamation.title:
        parts.append(f"*{escape(proclamation.summary)}*")
    if proclamation.opening:
        parts.append(quote(tidy(f"{proclamation.opening} …")))
    if proclamation.paragraphs:
        parts.append(escape(clip(proclamation.paragraphs[0], 3000)))
    if not parts:
        parts.append("*Steele gives only its title.*")
    return "\n\n".join(parts)[:4096]


def embed(proclamation: Proclamation, modern: bool = False, title: str = "") -> discord.Embed:
    if proclamation.calendar:
        return calendar_embed(proclamation, modern, title)
    tidy = spelling.modern if modern else (lambda text: text)
    heading = tidy(" ".join(proclamation.heading)) or tidy(proclamation.title)
    result = discord.Embed(title=clip(title or heading, 256), url=proclamation.url, color=COLOR,
                           description=quote(tidy(excerpt(proclamation)))[:4096])
    if title:  # A title of the command's own: the proclamation's own heading goes above the text instead
        result.description = (f"**{discord.utils.escape_markdown(clip(heading, 300))}**\n"
                              f"{result.description}")[:4096]
    author = " · ".join(part for part in (REALMS[proclamation.realm], proclamation.by, proclamation.when) if part)
    result.set_author(name=clip(author, 256))
    if amount := reward(proclamation):
        result.add_field(name="💰 Reward", value=tidy(amount), inline=False)
    if proclamation.dateline:
        result.add_field(name="Given", value=clip(tidy(proclamation.dateline), 1024), inline=False)
    if proclamation.signed:
        names = list(proclamation.signed[:8]) + ([f"and {len(proclamation.signed) - 8} more"]
                                                  if len(proclamation.signed) > 8 else [])
        result.add_field(name="Signed", value=clip(tidy(", ".join(names)), 1024), inline=False)
    result.add_field(name="Read it all", value=f"[The full text]({proclamation.url}) · "
                                               f"[transcription]({proclamation.source_url})", inline=False)
    footer = f"{SOURCE} · #{proclamation.id}"
    if modern:
        footer += " · spelling tidied"
    result.set_footer(text=footer)
    return result


def calendar_embed(proclamation: Proclamation, modern: bool = False, title: str = "") -> discord.Embed:
    """One known from Steele's calendar: his summary of it, linked to his page."""
    tidy = spelling.modern if modern else (lambda text: text)
    headline = tidy(proclamation.headline)
    description = calendar_description(proclamation, tidy)
    if title:
        description = f"**{discord.utils.escape_markdown(clip(headline, 300))}**\n{description}"[:4096]
    result = discord.Embed(title=clip(title or headline, 256), url=proclamation.url, color=COLOR,
                           description=description)
    author = " · ".join(part for part in (REALMS[proclamation.realm], proclamation.by, proclamation.when) if part)
    result.set_author(name=clip(author, 256))
    if amount := reward(proclamation):
        result.add_field(name="💰 Reward", value=amount, inline=False)
    if proclamation.dateline:
        result.add_field(name="Given", value=clip(proclamation.dateline, 1024), inline=False)
    if proclamation.signed:
        result.add_field(name="Signed", value=clip(", ".join(proclamation.signed), 1024), inline=False)
    page = f", page {proclamation.page}" if proclamation.page else ""
    result.add_field(name="Where it's from", inline=False, value=clip(
        f"{STATUS.get(proclamation.status, '')} Known from [Steele's calendar{page}]({proclamation.url}): "
        "his summary, not its own words.".strip(), 1024))
    number = f"No. {proclamation.number} · " if proclamation.number else ""
    footer = f"{CALENDAR_SOURCE} · {number}#{proclamation.id}"
    if modern:
        footer += " · spelling tidied"
    result.set_footer(text=footer)
    return result
