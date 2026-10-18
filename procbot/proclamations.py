"""The proclamations (data/proclamations.json, built by tools/proclamations_build.py): loading, searching, picking
one, and how one looks in Discord."""

import json
import random
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import discord

from procbot import spelling

DATA = Path(__file__).resolve().parent / "data"
COLOR = discord.Color.from_str("#9E1B32")  # Sealing-wax red
SOURCE = "EEBO-TCP, public domain"
REALMS = {"england": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 England", "ireland": "☘️ Ireland", "scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scotland"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
EXCERPT = 1000  # Characters of the opening shown
COMMAND_EXCERPT = 600  # And of what it commands, if that comes later


@dataclass(frozen=True)
class Proclamation:
    id: str  # The TCP id, lower case: "a39500"
    phase: int  # EEBO-TCP phase 1 or 2: which of Michigan's collections it's in
    realm: str  # england, ireland, scotland
    title: str  # The catalogue's
    paragraphs: tuple[str, ...]
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
    text: str = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        object.__setattr__(self, "text", " ".join(self.heading + (self.title,) + self.paragraphs))

    @property
    def url(self) -> str:
        """Its page in the University of Michigan's EEBO-TCP reader."""
        collection = "eebo" if self.phase == 1 else "eebo2"
        return f"https://quod.lib.umich.edu/e/{collection}/{self.id.upper()}.0001.001"

    @property
    def source_url(self) -> str:
        """The transcription itself, TEI XML on GitHub."""
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
        if self.issuer in ("", "Sovereign"):
            return self.monarch
        office = f"{self.issuer} ({self.holder})" if self.holder else self.issuer
        return f"{office}, under {self.monarch}" if self.monarch and self.monarch != "the Commonwealth" else office


def load() -> list[Proclamation]:
    raw = json.loads((DATA / "proclamations.json").read_text(encoding="utf-8"))
    return [Proclamation(**{key: tuple(value) if isinstance(value, list) else value for key, value in entry.items()})
            for entry in raw]


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
    return 1 if ROUTINE.search(proclamation.title) else 3


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


def matching(realm: str = "", monarch: str = "", about: str = "", hidden: set[str] = frozenset()) -> list[Proclamation]:
    patterns = words_in(about)
    return [p for p in PROCLAMATIONS if p.id not in hidden and (not realm or p.realm == realm)
            and (not monarch or p.monarch == monarch) and all(pattern.search(p.text) for pattern in patterns)]


def pick(where: int, realm: str = "", monarch: str = "", about: str = "",
         hidden: set[str] = frozenset()) -> Proclamation | None:
    """A random proclamation (of this realm, monarch and about these words, if given), avoiding ones shown here
    lately."""
    candidates = matching(realm, monarch, about, hidden)
    if not candidates:
        return None
    shown = recent.setdefault(where, deque(maxlen=RECENT_SIZE))
    fresh = [p for p in candidates if p.id not in shown] or candidates
    proclamation = random.choices(fresh, weights=[WEIGHTS.get(p.id, 1) for p in fresh])[0]
    shown.append(proclamation.id)
    return proclamation


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


def embed(proclamation: Proclamation, modern: bool = False, title: str = "") -> discord.Embed:
    tidy = spelling.modern if modern else (lambda text: text)
    heading = tidy(" ".join(proclamation.heading)) or tidy(proclamation.title)
    result = discord.Embed(title=clip(title or heading, 256), url=proclamation.url, color=COLOR,
                           description=quote(tidy(excerpt(proclamation)))[:4096])
    if title:  # A title of the command's own: the proclamation's own heading goes above the text instead
        result.description = (f"**{discord.utils.escape_markdown(clip(heading, 300))}**\n"
                              f"{result.description}")[:4096]
    author = " · ".join(part for part in (REALMS[proclamation.realm], proclamation.by, proclamation.when) if part)
    result.set_author(name=clip(author, 256))
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
