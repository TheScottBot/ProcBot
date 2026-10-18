"""/decree: a made-up proclamation about anything, in the words the real ones used. Plain Python, no Discord.

The formulae are the real ones', from the proclamations in data/: "WHereas Wee are giuen to vnderstand…", "doe
straitly charge and command…", "vpon paine of Our high displeasure", "Giuen at Our Court at Whitehall, the…", and
the spelling is the printers' of about 1620 (spelling.modern tidies it, as for the real ones). It's always marked as
not a real proclamation.
"""

import random
from dataclasses import dataclass
from datetime import date

AGAINST, FOR, CONCERNING = "against", "for", "concerning"

# Whose voice: (heading, "His/Her Maiestie", the sovereign's sign-off)
VOICES = {
    "king": ("By the King.", "His Maiestie", "God saue the King."),
    "queen": ("By the Queene.", "Her Maiestie", "God saue the Queene."),
}
# Where it was given, as the datelines say it.
COURTS = ["Our Court at Whitehall", "Our Palace of Westminster", "Our Mannour of Greenwich", "Our Court at Theobalds",
          "Our Honour of Hampton Court", "Our Castle of Windsor", "Our Court at New-market", "Our Court at Royston",
          "Our Mannour of Oatlands", "Our Palace of Richmond"]

OPENINGS = {
    AGAINST: [
        "WHereas {majesty} is giuen to vnderstand, that of late {thing} hath growne very common within this Realme, "
        "to the great offence of Almighty God, and the hurt and impouerishing of {pronoun} louing Subiects:",
        "WHereas diuers lewd and ill-disposed persons haue of late taken vpon them to vse and practise {thing}, in "
        "contempt of {pronoun} Lawes, and to the euill example of others:",
        "WHereas it hath beene represented vnto {majesty}, by the humble Petition of many {pronoun} louing Subiects, "
        "that {thing} is become a great annoyance and burthen vnto them, and a meanes of much disorder:",
    ],
    FOR: [
        "WHereas {majesty}, taking into {pronoun} Princely consideration the great benefit that may arise vnto "
        "{pronoun} louing Subiects by {thing}, hath thought fit to giue all due encouragement thereunto:",
        "WHereas {majesty} hath beene informed by diuers of {pronoun} Priuy Councell, how greatly it would conduce "
        "to the welfare and quiet of this Realme, that {thing} should be duly obserued in all places:",
    ],
    CONCERNING: [
        "WHereas sundry doubts and questions haue of late arisen concerning {thing}, to the trouble of {pronoun} "
        "louing Subiects, and the hindrance of Iustice:",
        "WHereas {majesty} is informed, that great abuses haue of late beene committed in the matter of {thing}, "
        "which, if they be not speedily reformed, may tend to the great preiudice of the Common-wealth:",
    ],
}
COMMANDS = {
    AGAINST: [
        "{majesty} therefore, minding the reformation thereof, doth by this {pronoun} Royall Proclamation straitly "
        "charge and command all and euery {pronoun} Subiects, of what estate, degree or condition soeuer, That from "
        "henceforth they doe not presume to make, sell, vse, or in any wise meddle with {thing}, vpon paine of "
        "{pronoun} high displeasure, and of such further punishment as by the Lawes of this Realme may be inflicted.",
        "{majesty} doth therefore straitly charge and command all Maiors, Sheriffes, Iustices of Peace, Constables, "
        "and all other {pronoun} Officers, to make diligent search for all such as shall offend in {thing}, and them "
        "to commit to the next Gaole, there to remaine vntill they shall be thence deliuered by due course of Law.",
    ],
    FOR: [
        "{majesty} doth therefore by this {pronoun} Royall Proclamation will and require all {pronoun} louing "
        "Subiects, to further and encourage {thing} by all good meanes they may, as they tender {pronoun} fauour, "
        "and will answere the contrary at their perils.",
        "{majesty} doth hereby publish and declare {pronoun} expresse will and pleasure, That {thing} be from "
        "henceforth duely and orderly obserued throughout this Realme, and doth straitly charge all {pronoun} "
        "Officers to see the same put in due execution.",
    ],
    CONCERNING: [
        "{majesty} doth therefore hereby declare {pronoun} Royall pleasure touching {thing}, and doth straitly "
        "charge and command all {pronoun} Subiects to conforme themselues thereunto, vpon paine of {pronoun} high "
        "displeasure.",
        "{majesty} doth therefore will and command, that no person whatsoeuer doe from henceforth intermeddle in "
        "{thing}, but as {pronoun} Lawes shall direct, as they will answere the contrary at their vttermost perils.",
    ],
}

ONES = ["", "first", "second", "third", "fourth", "fift", "sixt", "seuenth", "eighth", "ninth", "tenth", "eleuenth",
        "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seuenteenth", "eighteenth", "nineteenth"]
CARDINALS = ["", "one", "two", "three", "foure", "fiue", "sixe", "seuen", "eight", "nine"]
MONTHS = ["Ianuary", "February", "March", "Aprill", "May", "Iune", "Iuly", "August", "September", "October",
          "Nouember", "December"]


def ordinal(n: int) -> str:
    """1 -> 'first', 22 -> 'two and twentieth', 30 -> 'thirtieth', as the datelines have them."""
    if n < 20:
        return ONES[n]
    tens = {20: "twentieth", 30: "thirtieth"}[n // 10 * 10]
    return f"{CARDINALS[n % 10]} and {tens}" if n % 10 else tens


THING = "{thing}"  # Where the thing goes: filled in by Decree.render, after any tidying, so it's as it was typed


@dataclass(frozen=True)
class Decree:
    thing: str
    heading: str  # "By the King."
    title: str  # "A Proclamation against {thing}."
    paragraphs: tuple[str, ...]
    dateline: str
    closing: str  # "God saue the King."

    def render(self, text: str, tidy=lambda text: text) -> str:
        """One of its texts, tidied if asked, with the thing put in."""
        return tidy(text).replace(THING, self.thing)


def make(thing: str, kind: str = AGAINST, voice: str = "king", on: date | None = None,
         rng: random.Random | None = None) -> Decree:
    """A proclamation `kind` (against, for or concerning) `thing`, given today in a random court and year of the
    reign."""
    rng = rng or random.Random()
    on = on or date.today()
    heading, majesty, closing = VOICES[voice]
    pronoun = "Her" if voice == "queen" else "His"
    words = {"thing": THING, "majesty": majesty, "pronoun": pronoun}
    paragraphs = (rng.choice(OPENINGS[kind]).format(**words), rng.choice(COMMANDS[kind]).format(**words))
    dateline = (f"Giuen at {rng.choice(COURTS)}, the "
                f"{ordinal(on.day)} day of {MONTHS[on.month - 1]}, in the {ordinal(rng.randint(1, 22))} yeere of "
                "Our Reigne.")
    return Decree(thing, heading, f"A Proclamation {kind} {THING}.", paragraphs, dateline, closing)
