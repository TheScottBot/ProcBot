"""Builds procbot/data/proclamations.json: royal (and other official) proclamations of England, Ireland and Scotland,
1485-1700, from the Early English Books Online Text Creation Partnership (EEBO-TCP).

    python -m procbot.tools.proclamations_build          (no extra dependencies)
    python -m procbot.tools.proclamations_build --offline   (only what's already downloaded)

EEBO-TCP keyboarded the texts of early printed books, proclamations among them, and released them as CC0 (public
domain): Phase I in 2015, Phase II in 2020. Each text is a TEI XML file in its own GitHub repository
(github.com/textcreationpartnership/A39500), and TCP.csv in the Texts repository catalogues them all.

Which texts are proclamations comes from the catalogue: the author is a government of one of the three kingdoms
("England and Wales. Sovereign (1603-1625 : James I)", "Ireland. Lord Lieutenant (1661-1669 : Ormonde)",
"Scotland. Privy Council") and the title or subject terms say "proclamation". Collections of proclamations (books
of them) are skipped by length, as are texts not in English or Scots, and any whose header isn't CC0.

The realm is the government's, or for the King's own proclamations, where it was printed: one printed in Dublin
was for Ireland, in Edinburgh for Scotland.

Text is as printed (spelling, capitals and all), except: long s is s, words broken over a line are joined, and
what TCP couldn't read (<gap>, "〈◊〉") is "…". Very long texts are cut at MAX_TEXT, at a paragraph, and marked so;
the bot links to the full text.

Downloads are kept in build/tcp/ (gitignored), so a rebuild only fetches what's new.
"""

import csv
import io
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BUILD = ROOT / "build" / "tcp"
OUT = ROOT / "procbot" / "data" / "proclamations.json"
CATALOGUE_URL = "https://raw.githubusercontent.com/textcreationpartnership/Texts/master/TCP.csv"
XML_URL = "https://raw.githubusercontent.com/textcreationpartnership/{id}/master/{id}.xml"
TEI = "{http://www.tei-c.org/ns/1.0}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

MAX_PAGES = 8  # A proclamation is a broadside or a short pamphlet; longer is a book of them, or a treatise
MAX_TEXT = 6000  # Characters of text kept: an embed shows far less, and the link has the rest
LANGUAGES = {"eng", "sco"}

# "England and Wales. Sovereign (1603-1625 : James I)": the government, then who in it. It's one of the author's
# ";"-separated names, not always the first ("Charles II, King of England, 1630-1685.; England and Wales. ...").
GOVERNMENT = re.compile(r"^(England and Wales|Great Britain|Ireland|Scotland)\.\s*(.*?)[\s.]*$")
REALMS = {"England and Wales": "england", "Great Britain": "england", "Ireland": "ireland", "Scotland": "scotland"}
# Not proclamations, though catalogued under a government: the New Model Army's declarations and the like.
NOT_ISSUERS = {"Army", "Commissioners of Subsidy", "General Assembly at Kilkenny"}
HOLDER = re.compile(r"^(?P<office>[^(]+?)\s*\((?P<years>[\d?]{4}-[\d?]{4})\s*:\s*(?P<who>[^)]+)\)")
PROCLAMATION = re.compile(r"proclam", re.I)


# --- Downloading ---

def fetch(url: str, timeout: int = 60) -> bytes | None:
    """The file at a URL, or None if it isn't there."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def catalogue(offline: bool) -> list[dict]:
    path = BUILD / "TCP.csv"
    if not path.exists():
        if offline:
            raise SystemExit(f"{path} isn't downloaded yet: run without --offline once.")
        print(f"Downloading {CATALOGUE_URL} ...")
        BUILD.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fetch(CATALOGUE_URL) or b"")
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


def xml_for(tcp_id: str, offline: bool) -> bytes | None:
    """A text's TEI XML, from build/tcp/xml/ or GitHub. None if it has none (yet)."""
    path = BUILD / "xml" / f"{tcp_id}.xml"
    missing = BUILD / "xml" / f"{tcp_id}.missing"  # So a rebuild doesn't ask GitHub again for texts it hasn't got
    if path.exists():
        return path.read_bytes()
    if offline or missing.exists():
        return None
    data = fetch(XML_URL.format(id=tcp_id))
    path.parent.mkdir(parents=True, exist_ok=True)
    if data is None:
        missing.touch()
    else:
        path.write_bytes(data)
    return data


# --- Choosing the proclamations ---

def government_of(author: str) -> re.Match | None:
    return next((found for name in author.split(";") if (found := GOVERNMENT.match(name.strip()))), None)


def is_proclamation(row: dict) -> bool:
    government = government_of(row["Author"])
    if not government or re.split(r"[.(]", government.group(2))[0].strip() in NOT_ISSUERS:
        return False
    if not (PROCLAMATION.search(row["Title"]) or "Proclamations" in row["Terms"]):
        return False
    pages = row["Pages"].strip()
    return not pages.isdigit() or int(pages) <= MAX_PAGES


def issuer_of(author: str) -> tuple[str, str, str]:
    """(government, office, who holds it) from the catalogue's author: ("Ireland", "Lord Lieutenant", "Ormonde").
    The sovereign's "who" is the monarch ("James I"); for a council it's "". The office is "" if not given."""
    government = government_of(author)
    office = government.group(2).strip()
    holder = HOLDER.match(office)
    if holder:
        return government.group(1), holder.group("office").strip(), holder.group("who").strip()
    return government.group(1), office, ""


# --- Reading the TEI ---

def clean(text: str) -> str:
    text = text.replace("ſ", "s").replace("〈◊〉", "…").replace("•", "…").replace("¶", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"…(\s*…)+", "…", text)
    return re.sub(r"\s+([,.;:])", r"\1", text).strip()


# TCP's special characters (<g ref="char:...">) that aren't simply their text. The abbreviation stroke ("cōtained")
# stays, as a combining macron; spelling.modern() spells it out.
GLYPHS = {
    "char:EOLhyphen": "",  # A word broken over a line
    "char:EOLunhyphen": "",
    "char:leaf": "",  # ❧, an ornament
    "char:cross": "",
    "char:punc": ",",  # A stop TCP couldn't tell apart; usually a comma
    "char:V": "V",  # Ʋ, a V in a fancy type
}


def text_of(element: ET.Element) -> str:
    """An element's text as printed: hyphens at line ends joined, notes and pictures left out, gaps as "…"."""
    parts: list[str] = []

    def walk(node: ET.Element):
        tag = node.tag.removeprefix(TEI)
        if tag in ("note", "figure", "figDesc"):
            pass
        elif tag == "gap":
            parts.append("…")
        elif tag == "g" and node.get("ref") in GLYPHS:
            parts.append(GLYPHS[node.get("ref")])
        elif tag in ("lb", "pb", "milestone"):
            parts.append(" " if tag == "lb" else "")
        else:
            parts.append(node.text or "")
            for child in node:
                walk(child)
        parts.append(node.tail or "")

    parts.append(element.text or "")
    for child in element:
        walk(child)
    return clean("".join(parts))


def find_all(element: ET.Element, *tags: str) -> list[ET.Element]:
    return [node for tag in tags for node in element.iter(f"{TEI}{tag}")]


NS = {"t": TEI[1:-1]}


def read(tcp_id: str, data: bytes) -> dict | None:
    """What a proclamation says, from its TEI. None if it isn't CC0, or isn't in English or Scots."""
    root = ET.fromstring(data)
    availability = root.find(".//t:publicationStmt/t:availability", NS)
    if availability is None or "publicdomain/zero" not in ET.tostring(availability, encoding="unicode"):
        return None
    # The header's language: the <text>'s own xml:lang is often "unk" for texts that are plainly English.
    languages = {node.get("ident") for node in root.iterfind(".//t:langUsage/t:language", NS)}
    text = root.find("t:text", NS)
    if text is None or not (languages & LANGUAGES or (text.get(XML_LANG) or "").split()[:1] in (["eng"], ["sco"])):
        return None
    body = text.find("t:body", NS)
    if body is None:
        return None

    printed = root.find(".//t:sourceDesc//t:publicationStmt", NS)
    place = clean("".join(printed.find("t:pubPlace", NS).itertext())) if printed is not None and \
        printed.find("t:pubPlace", NS) is not None else ""
    printer = clean("".join(printed.find("t:publisher", NS).itertext())) if printed is not None and \
        printed.find("t:publisher", NS) is not None else ""

    # Headings: "By the King." and "A PROCLAMATION for…", but not a coat of arms' motto.
    heading = []
    for node in find_all(body, "byline", "head"):
        # Printers' ornaments (❧, ¶) at the start aren't part of it.
        if node.find("t:figure", NS) is None and (line := re.sub(r"^[^\w\[(]+", "", text_of(node))):
            heading.append(line)
    signed = [text_of(item) for node in find_all(body, "signed") for item in (node.findall(".//t:item", NS) or [node])]
    signed = [name for name in signed if name and len(name) < 80]
    dateline = next((text_of(node) for node in find_all(body, "dateline")), "")

    paragraphs, length, cut = [], 0, False
    skip = {id(node) for holder in find_all(body, "opener", "closer", "figure", "head", "byline")
            for node in holder.iter()}
    for node in body.iter(f"{TEI}p"):
        if id(node) in skip or node.find(".//t:p", NS) is not None:
            continue
        paragraph = text_of(node)
        if not paragraph:
            continue
        if length + len(paragraph) > MAX_TEXT and paragraphs:
            cut = True
            break
        paragraphs.append(paragraph[:MAX_TEXT])
        length += len(paragraph)
    if not paragraphs:
        return None
    return {"heading": heading, "paragraphs": paragraphs, "cut": cut, "signed": signed, "dateline": dateline,
            "place": place.rstrip(" :,;"), "printer": printer.rstrip(" ,;")}


# --- Dates ---

def spelt(word: str) -> str:
    """A word with the period's spellings evened out, to compare with: 'Nouember' and 'November', 'eyght' and
    'eight', 'thirde' and 'third', 'Aprill' and 'April' all look the same."""
    word = word.lower().replace("v", "u").replace("j", "i").replace("y", "i").rstrip("e")
    return re.sub(r"(.)\1", r"\1", word)


MONTHS = {spelt(name): number for number, name in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
     "december"], start=1)}
ORDINALS = {spelt(word): n for n, words in enumerate(
    ["first one", "second two", "third three", "fourth four fowerth fourt", "fifth five fift fist", "sixth six sixt",
     "seventh seven", "eighth eight eigth", "ninth nine nineth", "tenth ten", "eleventh eleven", "twelfth twelve twelft",
     "thirteenth thirteen", "fourteenth fourteen", "fifteenth fifteen", "sixteenth sixteen", "seventeenth seventeen",
     "eighteenth eighteen", "nineteenth nineteen", "twentieth twenty"], start=1) for word in words.split()}
ORDINALS.update({spelt("thirtieth"): 30, spelt("thirty"): 30, spelt("thirtith"): 30})
ROMAN_DAY = re.compile(r"^[xvi]{1,6}$")
TERMS_DATE = re.compile(r"\b(1[4-7]\d\d)-(\d\d)-(\d\d)\b")
YEAR = re.compile(r"\b(1[4-7]\d\d)\b")
# "the 23. day of April", "the.xxii. day of December", "the third of December", "the Three and Twentieth Day of May"
DAY_OF_MONTH = re.compile(r"((?:[\w-]+[\s.]+){1,4}?)(?:day[\s.]+)?of[\s.]+([A-Za-z]+)", re.I)
# "March 28. 1660", "May 9th"
MONTH_DAY = re.compile(r"\b([A-Z][a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th|d)?\b")


def roman(numeral: str) -> int:
    values = {"i": 1, "v": 5, "x": 10}
    total = 0
    for here, after in zip(numeral, numeral[1:] + " "):
        total += -values[here] if values.get(after, 0) > values[here] else values[here]
    return total


def day_from(words: str) -> int | None:
    """'three and twentieth' / 'twenty third' / 'the 23.' / '22th' / 'xxii' -> the day of the month."""
    tokens = [token for token in re.findall(r"[a-z0-9]+", words.lower().replace("j", "i"))
              if token not in ("the", "and", "day")]
    if not tokens:
        return None
    if digits := re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th|d)?", tokens[-1]):
        day = int(digits.group(1))
    elif ROMAN_DAY.match(tokens[-1]):
        day = roman(tokens[-1])
    else:
        day = 0
        for token in reversed(tokens):  # "three and twentieth": add up the ordinal words, back from "day"
            if spelt(token) not in ORDINALS:
                break
            day += ORDINALS[spelt(token)]
    return day if 1 <= day <= 31 else None


def date_of(row: dict, dateline: str) -> str:
    """'1696-05-23', or as much of it as is known ('1696-05', '1696'). The subject terms often give it exactly;
    otherwise the dateline does ('the Three and Twentieth Day of May, 1696'). Dates are as printed, Old Style:
    in England and Ireland the year began on 25 March."""
    if exact := TERMS_DATE.search(row["Terms"]):
        return exact.group(0)
    year = found.group(1) if (found := YEAR.search(dateline)) else row["Date"][:4] if row["Date"][:4].isdigit() else ""
    month = day = None
    for found in DAY_OF_MONTH.finditer(dateline):
        if month := MONTHS.get(spelt(found.group(2))):
            day = day_from(found.group(1))
            break
    else:
        for found in MONTH_DAY.finditer(dateline):
            if month := MONTHS.get(spelt(found.group(1))):
                day = int(found.group(2)) if 1 <= int(found.group(2)) <= 31 else None
                break
    if not year:
        return ""
    if month and day:
        return f"{year}-{month:02}-{day:02}"
    return f"{year}-{month:02}" if month else year


# --- Who reigned ---

# (first year, last year, monarch). By calendar year; the bot only shows it, so a year of overlap does no harm.
REIGNS = {
    "england": [(1485, 1509, "Henry VII"), (1509, 1547, "Henry VIII"), (1547, 1553, "Edward VI"), (1553, 1558, "Mary I"),
                (1558, 1603, "Elizabeth I"), (1603, 1625, "James I"), (1625, 1649, "Charles I"),
                (1649, 1660, "the Commonwealth"), (1660, 1685, "Charles II"), (1685, 1688, "James II"),
                (1689, 1702, "William III"), (1702, 1714, "Anne")],
    "scotland": [(1488, 1513, "James IV"), (1513, 1542, "James V"), (1542, 1567, "Mary, Queen of Scots"),
                 (1567, 1625, "James VI"), (1625, 1649, "Charles I"), (1649, 1660, "the Commonwealth"),
                 (1660, 1685, "Charles II"), (1685, 1688, "James VII"), (1689, 1702, "William II"),
                 (1702, 1714, "Anne")],
}
REIGNS["ireland"] = REIGNS["england"]
SOVEREIGN_NAME = re.compile(r"^(?P<name>William and Mary|(?:Henry|Edward|Mary|Elizabeth|James|Charles|William|Anne)"
                            r"(?: [IVX]+)?)")
# The catalogue numbers monarchs as England did; Scotland counted its own.
ENGLISH_NAMES = {"William and Mary": "William III and Mary II"}
SCOTTISH_NAMES = {"James I": "James VI", "James II": "James VII", "William III": "William II",
                  "William and Mary": "William II and Mary II"}


def monarch_of(realm: str, date: str, holder: str, office: str) -> str:
    if office == "Sovereign" and (name := SOVEREIGN_NAME.match(holder)):
        names = SCOTTISH_NAMES if realm == "scotland" else ENGLISH_NAMES
        return names.get(name.group("name"), name.group("name"))
    year = int(date[:4]) if date[:4].isdigit() else 0
    for first, last, monarch in REIGNS[realm]:
        if first <= year <= last:
            return monarch
    return ""


def realm_of(government: str, place: str) -> str:
    realm = REALMS[government]
    if realm == "england" and re.search(r"Dublin", place, re.I):
        return "ireland"
    if realm == "england" and re.search(r"Edinburgh", place, re.I):
        return "scotland"
    return realm


def entry(row: dict, read_out: dict) -> dict:
    government, office, holder = issuer_of(row["Author"])
    realm = realm_of(government, read_out["place"])
    date = date_of(row, read_out["dateline"])
    out = {
        "id": row["TCP"].lower(),
        "phase": 1 if row["Status"] == "Free" else 2,
        "realm": realm,
        "issuer": office,
        "holder": holder if office != "Sovereign" else "",  # The sovereign is the monarch
        "monarch": monarch_of(realm, date, holder, office),
        "date": date,
        "title": clean(row["Title"]),
        **read_out,
    }
    return {key: value for key, value in out.items() if value not in ("", [], False)}


def main():
    offline = "--offline" in sys.argv
    rows = [row for row in catalogue(offline) if is_proclamation(row)]
    print(f"{len(rows)} proclamations in the catalogue; fetching their texts ...")
    with ThreadPoolExecutor(max_workers=8) as pool:
        texts = list(pool.map(lambda row: xml_for(row["TCP"], offline), rows))
    proclamations, skipped = [], {"no text": 0, "not CC0, English or Scots": 0, "unreadable": 0}
    for row, data in zip(rows, texts):
        if data is None:
            skipped["no text"] += 1
            continue
        try:
            read_out = read(row["TCP"], data)
        except ET.ParseError as error:
            print(f"  {row['TCP']}: {error}")
            skipped["unreadable"] += 1
            continue
        if read_out is None:
            skipped["not CC0, English or Scots"] += 1
            continue
        proclamations.append(entry(row, read_out))
    proclamations.sort(key=lambda p: (p["date"] or "9999", p["id"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(proclamations, ensure_ascii=False, indent=0, separators=(",", ":")) + "\n",
                   encoding="utf-8")
    realms = {realm: sum(p["realm"] == realm for p in proclamations) for realm in ("england", "ireland", "scotland")}
    print(f"Wrote {len(proclamations)} proclamations to {OUT.relative_to(ROOT)}: {realms}")
    print("Skipped: " + ", ".join(f"{count} {why}" for why, count in skipped.items()))


if __name__ == "__main__":
    main()
