"""Builds procbot/data/calendar.json: Robert Steele's calendar of every proclamation known to him, 1485-1714, from
*A Bibliography of Royal Proclamations of the Tudor and Stuart Sovereigns* (Bibliotheca Lindesiana v-vi, 1910).

    python -m procbot.tools.steele_build            (no extra dependencies)
    python -m procbot.tools.steele_build --offline  (only what's already downloaded)

Volume I is England and Wales, Volume II Ireland (part I) and Scotland (part II). Each entry gives the date, who
issued it, its title or opening words as printed, Steele's own summary in brackets, where it was given, whether a
copy survives, often an abstract of what it says and who signed it, and where copies are (which the bot doesn't
need). Most have no transcription in EEBO-TCP: for Ireland, 1,639 entries against 33 texts.

The scans are the Wellcome Library's, on archive.org (b24872763_0001 and _0002), read from archive.org's OCR: its
per-page text (hocr_searchtext, one paragraph a line) and page index, so each entry links to its page. The OCR is
good but not perfect: an entry is kept only if it has a date and something to say (a title, opening or summary),
and the bot shows them as Steele's summaries, linked to the page, not as the proclamation's own words.

Steele's text is out of copyright: it was published in 1910, and he died in 1944.

Downloads are kept in build/steele/ (gitignored).
"""

import gzip
import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from procbot.tools.proclamations_build import MONTHS, REIGNS, day_from, spelt

ROOT = Path(__file__).resolve().parent.parent.parent
BUILD = ROOT / "build" / "steele"
OUT = ROOT / "procbot" / "data" / "calendar.json"
URL = "https://archive.org/download/{book}/{book}_{file}"
FILES = ["hocr_searchtext.txt.gz", "hocr_pageindex.json.gz", "page_numbers.json"]


@dataclass(frozen=True)
class Section:
    realm: str
    prefix: str  # For the bot's ids: "ire776"
    book: str
    start: re.Pattern  # The line it starts at
    end: re.Pattern  # The line after its last


SECTIONS = [
    Section("england", "eng", "b24872763_0001", re.compile(r"^24 SEPTEMBER\.— \[BY THE KING\]\. \[Begins\] Henry"),
            re.compile(r"(?!)")),  # To the end of the volume
    # The OCR reads the running head's "VOL." as "YOL." as often as not.
    Section("ireland", "ire", "b24872763_0002", re.compile(r"^[VY]OL\. II\. PART I$"),
            re.compile(r"^[VY]OL\. II\. PART II$")),
    Section("scotland", "sco", "b24872763_0002", re.compile(r"^[VY]OL\. II\. PART II$"),
            re.compile(r"^THE ROYAL ARMS AS ON PRINTED PROCLAMATIONS")),
]

FIRST_YEAR, LAST_YEAR = 1485, 1714  # What the calendar covers: a year outside it is the OCR's
MONTH_NAMES = "JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER"
# An entry starts with its date, if known, then who issued it: "31 JULY.— [BY THE KING.]", "After 14 JULY.— [BY THE
# LORD DEPUTY.]", "[BY THE LORD JUSTICE AND COUNCIL.]", and the OCR's "10 JUNE.-^BY THE KING."
WHEN = (rf"(?P<when>(?:(?:After|Before|About|Circa|c\.|Early|Late|End of|Beginning of) )?(?:\[?\d{{1,2}}\]? ?)?"
        rf"(?:{MONTH_NAMES})?)")
BY = r"[\[^(]? ?(?:BY|TO) (?:THE|HIS|HER|THEIR|PARLIAMENT|[A-Z]{4,})\b"
START = re.compile(rf"^{WHEN}[\s.,:;—–^~_-]*(?P<by>{BY}.*)$"
                   # Or any month heading and a dash: "20 NOVEMBER. — An Acte for the attainder …"
                   rf"|^(?P<when2>(?:\[?\d{{1,2}}\]? ?)?(?:{MONTH_NAMES}))\s*\.?\s*[—–-]+\s*(?P<by2>\S.*)$")
ISSUER = re.compile(r"^[\[^(]? ?(?:BY|TO) (?:THE )?([A-Z][A-Z ,&'’-]*?)\s*[.:\]]")
BARE_DATE = re.compile(rf"^(?:(?:After|Before|About|c\.) )?\[?\d{{0,2}}\]? ?(?:{MONTH_NAMES})\s*\.?\s*[—–-]?\s*$")
BEGINS = re.compile(r"[\[^]Beg ?-? ?ins\]\s*(.*?)\s*(?:\.\s*\.\s*\.|…|$)")  # And the OCR's "[Beg ins]"
BRACKETED = re.compile(r"\[([^\[\]]{4,})\]")
# "Dublin : 7 July 1714.", "Westminster : 12 October [1485].", "[Dublin : 19 June 1541.]", "Edinburgh: January 1524[-5]"
# The place is a name, a few capitalised words: "Dublin", "Hampton Court", "St. Andrews", "Kings-Inn".
PLACE_DATE = re.compile(r"(?P<place>(?:St\. )?[A-Z][A-Za-z'’-]+(?: (?:of |upon |on )?[A-Z][A-Za-z'’-]+){0,3})\]?\s*:\s*"
                        r"(?P<date>\[?(?:\d{1,2}\]?\s+)?(?P<month>[A-Z][a-z]+)\.?\s+\[?(?P<year>1[4-7][0-9B]\d)"
                        r"(?:\[-\d{1,2}\])?\]?)")
GENERIC_TITLE = re.compile(r"^(?:A |The )?(?:Proclamation|Declaration|Proclamacion|Act|Acte)s?\.?$", re.I)
YEAR_HEADING = re.compile(r"^(?:[A-Z][A-Z ]+ )?\[?(1[4-7]\d\d)(?:[-–]\d{1,2})?\]?$")  # "1541", "HENRY VIII 1537"
RUNNING_HEAD = re.compile(r"^(1[4-7]\d\d)(?:-\d{1,2})?:\s+\d")  # "1666-7: 18-19 Charles II"
STATUS = re.compile(r"^(Not found|Found only in MS|Only found in MS|Only in MS)", re.I)
PRINTED_BY = re.compile(r"^\[?[A-Z][\w .'’-]{1,30}\]?\s*:.{2,80}:\s*\[?1[4-7]\d\d")  # "Dublin : A. Crooke : 1714."
FORMAT = re.compile(r"^(?:\d+\s*ff?\.|Broadside|s\.\s*sh\.|\d+\s*pp?\.|Arms\s+\d|Gothic|Roman|Black letter)", re.I)
FORMAT_INSIDE = re.compile(r"^\d+\s*ff?\.\s*(?:fo\.\s*)?(?:Gothic|Roman|Black)[\w\s&]*letter[^.]*\.\s*", re.I)
# Where copies are: the libraries and calendars Steele cites.
REFERENCE = re.compile(r"^(?:P\.R\.O|B\.M|Bodl|T\.C\.D|Cal\.|See |Dub\.|Antiq|Lamb|Rot\.|Soc\.|Haliday|Carew|R\.P\.C|"
                       r"Reg\.|Sig\.|Adv\.|U\.L\.C|Queen|Worcester|Wentworth|Huth|Crawford|Guildhall|Lincoln|S\.P\.|"
                       r"Privy|Cotton|Harl|Lansd|Add\.|Ashm|Wood|Douce|Gough|Tanner|Rawl|Ch\.\s?Ch|All Souls|"
                       r"Mag\.|Pepys|St\. John|Trin|Caius|Emman|Rylands|Chetham|Signet|Advocates|Glasgow|Aberdeen|"
                       r"Hodgkin|Kildare|R\.I\.A|Marsh|Armagh|Ormonde|Carte|Hist\.|Steele|Dyson|Grafton|Rymer|R\. ?x|"
                       r"Hall |Bacon |Campbell |Stow|Holinshed|Strype|Hughes|Statutes|Acts)")
# A sentence's end, then a reference: where an abstract runs into its references on one line
REFERENCE_INSIDE = re.compile(r"(?<=[.;)])\s+(?=(?:P\.R\.O|B\.M|Bodl|T\.C\.D|Cal\.|Dub\.|Antiq|Lamb|R\.P\.C|Reg\.|"
                              r"See )\b)")
# "N° 776.", and the OCR's readings of it: "jfo 4^", "Ro 3.", "N® 6.", "NO 5^", "N° 6a. B"
NUMBER_AT_END = re.compile(r"\s*(?:N\S{0,2}|R[o0°]|[Jj][^\s\d]{1,3})\s*(\d[\d ]{0,5}?)\s*([a-z])?[\W_]{0,3}(?: [A-Z])?"
                           r"\s*$")
PLAIN_NUMBER_AT_END = re.compile(r"\s+(\d{1,4})\s*([a-z])?[\W_]{0,2}\s*$")  # "… Carew ii. 61. 7.", "2 a."
# Page furniture: page numbers, "VOL. II", "Nos 776-82", "TUDOR AND STUART PROCLAMATIONS", signature marks.
FURNITURE = re.compile(r"^(?:\d{1,4}|[ivxlc]+|[VY]OL\.? ?I+\.?|(?i:nos?)\.? ?\d+[-–]\d+|TUDOR AND STUART(?: "
                       r"PROCLAMATIONS)?|PROCLAMATIONS|[A-Z] ?[a-z]? ?\d|[^A-Za-z]*|.{1,3})$")


def download(book: str, offline: bool) -> dict:
    """A volume's OCR: its pages' text, and their printed page numbers."""
    folder = BUILD / book
    folder.mkdir(parents=True, exist_ok=True)
    for file in FILES:
        path = folder / file
        if not path.exists():
            if offline:
                raise SystemExit(f"{path} isn't downloaded yet: run without --offline once.")
            url = URL.format(book=book, file=file)
            print(f"Downloading {url} ...")
            with urllib.request.urlopen(url, timeout=120) as response:
                path.write_bytes(response.read())
    text = gzip.decompress((folder / FILES[0]).read_bytes()).decode("utf-8")
    index = json.loads(gzip.decompress((folder / FILES[1]).read_bytes()))
    numbers = json.loads((folder / FILES[2]).read_text(encoding="utf-8"))["pages"]
    return {"text": text, "index": index, "page_numbers": {page["leafNum"]: page["pageNumber"] for page in numbers}}


def tidy(line: str) -> str:
    """Spaces evened out, and words broken over a line joined: "Pro- clamation", "LIEUTEN- ANT"."""
    line = re.sub(r"\s+", " ", line).strip()
    return re.sub(r"(?<=[a-z])- (?=[a-z])|(?<=[A-Z])- (?=[A-Z]{2})", "", line)


def lines_of(volume: dict) -> list[tuple[int, str]]:
    """(leaf, line) for every line in the volume. Leaves count from 0, as archive.org's /page/n links do."""
    out = []
    for leaf, (start, end, *_) in enumerate(volume["index"]):
        for line in volume["text"][start:end].split("\n"):
            if line := tidy(line):
                out.append((leaf, line))
    return out


def section_lines(lines: list[tuple[int, str]], section: Section) -> list[tuple[int, str]]:
    start = next(i for i, (_, line) in enumerate(lines) if section.start.search(line))
    end = next((i for i in range(start + 1, len(lines)) if section.end.search(lines[i][1])), len(lines))
    return lines[start:end]


# --- Reading an entry ---

ISSUER_WORDS = {"COUNCIL", "COUNCELL", "COUNSELL", "JUSTICES", "IUSTICES", "JUSTICE", "IUSTICE", "LIEUTENANT",
                "DEPUTY", "DEPUTIE", "COMMISSIONERS", "COMMISSIONER", "PARLIAMENT", "GOVERNOR", "GOVERNOUR",
                "PROTECTOR", "GENERAL", "SECRET", "CONVENTION", "ESTATES", "REGENT", "QUEEN", "QUENE"}


def issuer_name(raw: str) -> str:
    """'LORD LIEUTENANT AND COUNCIL' -> 'Lord Lieutenant and Council'; 'KING' -> 'King'. Words the OCR split
    ("COUN CIL", "JUS TICES") are put back together."""
    words = raw.split()
    i = 0
    while i < len(words) - 1:
        if words[i] + words[i + 1] in ISSUER_WORDS:
            words[i:i + 2] = [words[i] + words[i + 1]]
        i += 1
    small = {"and", "of", "the", "in", "for"}
    words = [word.lower() if word.lower() in small else word.capitalize() for word in words]
    return " ".join(words).replace(" ,", ",").strip(" ,")


def date_from(found: re.Match | None, when: str, year: int | None) -> str:
    """'1666-01-05', '1666-01' or '1666', from the place and date ("Dublin : 5 January 1666[-7]"), or failing that
    the entry's heading ("5 JANUARY") and the year it's under."""
    day = month = None
    if found and (month := MONTHS.get(spelt(found.group("month")))):
        year = int(found.group("year").replace("B", "8"))  # "14B5": the OCR's 8
        day = day_from(found.group("date").split(found.group("month"))[0])
    elif heading := re.search(rf"(\d{{1,2}})?\]?\s*({MONTH_NAMES})", when):
        month = MONTHS.get(spelt(heading.group(2)))
        day = int(heading.group(1)) if heading.group(1) else None
    if not year:
        return ""
    if month and day and 1 <= day <= 31:
        return f"{year}-{month:02}-{day:02}"
    return f"{year}-{month:02}" if month else str(year)


def is_signatures(line: str) -> bool:
    """A line of who signed it: "Ja. Armachanus, Santry, Hen. Midensis, Jo. Bysse." or just "Ormonde."."""
    words = re.findall(r"[A-Za-z’']+", line)
    if not words or re.search(r"\b(the|to|be|is|are|of|for|by|that|all|from|with|which|shall|any)\b", line):
        return False
    if re.search(r"\d|\b(Gaz|Reg|Price|B\.L|L\.J|C\.J|P\.C|q\.v|MS|Cal|Lond|Bodl|Antiq)\b", line):
        return False  # References, not names
    capitals = sum(word[0].isupper() for word in words)
    return capitals / len(words) >= 0.7 and (line.count(",") >= 1 or len(words) <= 3)


def read_entry(lines: list[tuple[int, str]], year: int | None) -> dict | None:
    """One entry's lines -> what it says. None if there isn't enough of it."""
    first = START.match(lines[0][1])
    when = (first.group("when") or first.group("when2") or "").strip()
    # The heading runs until where it was given, or whether it survives.
    head, rest = [first.group("by") or first.group("by2")], []
    for i, (_, line) in enumerate(lines[1:], 1):
        if STATUS.match(line) or PRINTED_BY.match(line) or FORMAT.match(line) or (
                PLACE_DATE.search(" ".join(head)) and not line.startswith("[")):
            rest = [line for _, line in lines[i:]]
            break
        head.append(line)
    head_text = tidy(" ".join(head))  # tidy again: a word may be broken over two of its lines

    number, marked = "", False
    tail = rest[-1] if rest else head_text
    if found := NUMBER_AT_END.search(tail) or PLAIN_NUMBER_AT_END.search(tail):
        number = found.group(1).replace(" ", "") + (found.group(2) or "")
        marked = found.re is NUMBER_AT_END  # "N° 776", not just a number that could be a page
        tail = tail[:found.start()].strip()
        if rest:
            rest[-1] = tail
        else:
            head_text = tail

    issuer = ISSUER.match(head_text)
    after_issuer = head_text[issuer.end():].strip(" .]") if issuer else head_text
    places = list(PLACE_DATE.finditer(head_text))
    place = places[-1] if places else None
    opening = BEGINS.search(after_issuer)
    summaries = [m.group(1).strip(" .") for m in BRACKETED.finditer(after_issuer)
                 if not re.match(r"Beg ?-? ?ins", m.group(1)) and not PLACE_DATE.search(m.group(1))
                 and not re.fullmatch(r"[\d\s\[\]-]+", m.group(1))]
    # The title is what's printed before the opening, the summary or the place: "A Proclamation For a General Fast."
    title_area = after_issuer
    if place and (at := title_area.find(place.group(0))) >= 0:
        title_area = title_area[:at]
    title = re.split(r"[\[^]Beg ?-? ?ins\]|\[", title_area)[0].strip(" .")

    status, abstract, signed = "printed", [], []
    for line in rest:
        line = FORMAT_INSIDE.sub("", line)
        if not line or STATUS.match(line):
            status = "lost" if line.lower().startswith("not found") else "manuscript" if line else status
        elif re.fullmatch(r"\[?[A-Z][a-z]+\.\]?", line):  # "Ormonde.": the Lord Lieutenant, not the Ormonde MSS
            signed.append(line.strip(" .[]"))
        elif PRINTED_BY.match(line) or FORMAT.match(line) or REFERENCE.match(line) or FURNITURE.match(line):
            continue
        elif is_signatures(line):
            names = re.sub(r"\(\d+\)[,.]?\s*", "", REFERENCE_INSIDE.split(line)[0])  # "Orm. (184), (185)."
            signed.append(names.strip(" .,[]"))
        else:
            prose = REFERENCE_INSIDE.split(line)[0].strip()
            if prose and not REFERENCE.match(prose):
                abstract.append(prose)
    date = date_from(place, when, year)
    summary = summaries[-1] if summaries else ""
    if GENERIC_TITLE.match(title):
        title = ""  # "A Proclamation" says nothing
    if not date or not FIRST_YEAR <= int(date[:4]) <= LAST_YEAR or not (title or opening or summary):
        return None
    return {
        "number": number,
        "marked": marked,
        "issuer": issuer_name(issuer.group(1)) if issuer else "",
        "date": date,
        "title": title if re.search(r"[a-z]{3}", title) else "",
        "opening": opening.group(1).strip(" .") if opening else "",
        "summary": summary,
        # Steele's brackets mark what he supplied ("[1485]"); a lone one is the OCR's
        "dateline": (f"{place.group('place').strip(' [')} : {place.group('date').strip()}"
                     if place else "").replace("[", "" if "]" not in (place.group("date") if place else "") else "["),
        "status": status,
        "abstract": " ".join(abstract),
        "signed": ", ".join(signed),
    }


def entries_of(section: Section, lines: list[tuple[int, str]], page_numbers: dict) -> list[dict]:
    out, year, chunk, previous, unnumbered = [], None, [], 0, 0
    used: set[str] = set()

    def finish():
        nonlocal previous, unnumbered, year
        if not chunk:
            return
        entry = read_entry(chunk, year)
        if entry is None:
            return
        # Where it was given, and when, is the surest year there is: the next ones go on from it.
        if entry["dateline"] and (year is None or year - 1 <= int(entry["date"][:4]) <= year + 3):
            year = int(entry["date"][:4])
        number, marked = entry.pop("number"), entry.pop("marked")
        digits = int(re.match(r"\d+", number).group()) if number else 0
        # Numbers run on, with gaps where entries were missed or are other editions. A marked one ("N° 776") may
        # pick the count up again after a gap; a bare number has to be close, as it could be anything (a year, a page).
        if (previous < digits <= previous + (60 if marked else 12) or (number[-1:].isalpha() and digits == previous)
                or (previous == 0 and marked and digits)):  # The first, wherever the count starts
            previous, unnumbered = digits, 0
        else:
            number = ""  # The OCR misread it: better none than a wrong one
        if number and f"{section.prefix}{number}" not in used:
            key = f"{section.prefix}{number}"
        else:
            number, unnumbered = "", unnumbered + 1
            key = f"{section.prefix}{previous}-{unnumbered}"  # After No. 500: "eng500-1", "eng500-2"
            while key in used:
                unnumbered += 1
                key = f"{section.prefix}{previous}-{unnumbered}"
        used.add(key)
        leaf = chunk[0][0]
        out.append({"id": key, "realm": section.realm, "number": number, **entry, "book": section.book,
                    "leaf": leaf, "page": page_numbers.get(leaf + 1, "")})

    pending = ""  # A date on a line of its own ("16 MAY."): an entry starts if the issuer follows
    for leaf, line in lines:
        if pending:
            date_line, pending = pending, ""
            if re.match(BY, line):
                line = f"{date_line} — {line}"
            else:  # Another edition of one already listed: its lines aren't the last entry's
                finish()
                chunk = []
        if BARE_DATE.match(line):
            pending = line
        elif START.match(line):
            finish()
            chunk = [(leaf, line)]
        elif heading := YEAR_HEADING.match(line) or RUNNING_HEAD.match(line):
            # The calendar goes year by year, so a year heading moves on a little: "1643" alone may well be an entry's
            # number. The running head atop each page ("1666-7: 18-19 Charles II") is sure, and puts it right.
            if heading.re is RUNNING_HEAD or year is None or year - 1 <= int(heading.group(1)) <= year + 3:
                year = int(heading.group(1))
        elif chunk and not FURNITURE.match(line):
            chunk.append((leaf, line))
    finish()
    return out


# --- The ones EEBO-TCP has the text of ---

TCP_DATA = ROOT / "procbot" / "data" / "proclamations.json"
COMMON_WORDS = {spelt(word) for word in ("proclamation", "proclamacion", "majesty", "majesties", "maiesties", "kings",
                                         "queens", "concerning", "against", "whereas", "declaring", "lords", "council",
                                         "councell", "realm", "realme", "subjects", "subiects", "their", "which",
                                         "shall", "these", "other", "persons")}


def words_of(text: str) -> set[str]:
    return {spelt(word) for word in re.findall(r"[A-Za-z]{5,}", text.lower())} - COMMON_WORDS


def link_tcp(calendar: list[dict]) -> int:
    """Marks each entry that's a proclamation EEBO-TCP has the text of ("tcp": its id), so the bot shows the text
    instead. The same realm and day, and either their titles share words, or each is the only one that day."""
    tcp: dict[tuple[str, str], list[dict]] = {}
    for proclamation in json.loads(TCP_DATA.read_text(encoding="utf-8")):
        if len(proclamation.get("date", "")) == 10:
            tcp.setdefault((proclamation["realm"], proclamation["date"]), []).append(proclamation)
    same_day: dict[tuple[str, str], int] = {}
    for entry in calendar:
        same_day[(entry["realm"], entry["date"])] = same_day.get((entry["realm"], entry["date"]), 0) + 1
    linked = 0
    for entry in calendar:
        candidates = tcp.get((entry["realm"], entry["date"]), [])
        ours = words_of(" ".join(entry.get(key, "") for key in ("title", "summary", "opening", "abstract")))
        best, overlap = None, 0.0
        for proclamation in candidates:
            theirs = words_of(" ".join(proclamation.get("heading", []) + [proclamation["title"]]
                                       + proclamation["paragraphs"][:1]))
            score = len(ours & theirs) / max(1, min(len(ours), len(theirs)))
            if score > overlap:
                best, overlap = proclamation, score
        if best and (overlap >= 0.25 or (len(candidates) == 1 and same_day[(entry["realm"], entry["date"])] == 1)):
            entry["tcp"] = best["id"]
            linked += 1
    return linked


# --- Who reigned, as in proclamations_build ---

def monarch(realm: str, date: str) -> str:
    year = int(date[:4])
    return next((name for first, last, name in REIGNS[realm] if first <= year <= last), "")


def main():
    offline = "--offline" in sys.argv
    volumes = {}
    calendar = []
    for section in SECTIONS:
        if section.book not in volumes:
            volume = download(section.book, offline)
            volumes[section.book] = (lines_of(volume), volume["page_numbers"])
        lines, page_numbers = volumes[section.book]
        entries = entries_of(section, section_lines(lines, section), page_numbers)
        for entry in entries:
            entry["monarch"] = monarch(section.realm, entry["date"])
        numbered = sum(bool(entry["number"]) for entry in entries)
        print(f"{section.realm}: {len(entries)} entries ({numbered} with their number read)")
        calendar += entries
    calendar = [{key: value for key, value in entry.items() if value not in ("", None)} for entry in calendar]
    print(f"{link_tcp(calendar)} are proclamations EEBO-TCP has the text of (proclamations_build first, for these)")
    OUT.write_text(json.dumps(calendar, ensure_ascii=False, indent=0, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(calendar)} entries to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
