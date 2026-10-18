"""What's in each proclamation, so each server can choose what it's shown (as Hammered of Witches does).

Every proclamation is tagged, per category, as 0 (nothing), 1 (mild: in passing) or 2 (strong), and each server
chooses, per category, how much it allows (/setup): OFF allows 0, MILD up to 1, FULL anything.

The proclamations are milder than the Malleus, but they are the state's voice, and they speak of "papists" and
"popish recusants", of "savages", of Quakers and conventicles to be broken up, of traitors to be brought in "dead or
alive", and of the plague. Tagging is by patterns, not AI, so it can be read, tested and fixed. It errs on the side
of tagging: a false tag only hides a proclamation from a strict server, a missed one shows it.
tests/test_content.py pins down the known cases; when one gets through that shouldn't, add a pattern and a test.

Old spelling is matched too: u for v ("saluage"), i for j ("Iewes"), "murther" for "murder", "bloud" for "blood".

This module is plain Python, no Discord.
"""

import re
from dataclasses import dataclass

OFF, MILD, FULL = 0, 1, 2
LEVEL_NAMES = {OFF: "off", MILD: "mild", FULL: "full"}


def words(*patterns: str) -> re.Pattern:
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.I)


@dataclass(frozen=True)
class Category:
    key: str  # As in /setup <key>
    name: str
    emoji: str
    about: str  # What it covers, for /setup and /help
    strong: re.Pattern  # Any match: level 2
    mild: re.Pattern  # Any match: level 1

    def level(self, text: str) -> int:
        if self.strong.search(text):
            return FULL
        if self.mild.search(text):
            return MILD
        return OFF


CATEGORIES = [
    Category(
        "religion", "Religious hostility", "✝️",
        "\"Papists\", \"popery\" and \"idolatry\" (strong); Jesuits and priests banished, recusants fined, Quakers "
        "and conventicles broken up (mild).",
        strong=words(r"\bpapists?\b", r"\bpap[ia]stri", r"\bpopish", r"\bpopery", r"\bpopelings?", r"\bromish",
                     r"\bantichrist", r"\bidolatr", r"\bwhore of babylon", r"\bsuperstiti\w+ (of )?(the )?(church of )?"
                     r"rome", r"\bmasse? ?(-| )?(priests?|mongers?)", r"\bfanatick", r"\bfanatic"),
        mild=words(r"\b[ij]esuit", r"\bseminar(y|ie|ies) (priest|men)", r"\bmass(e)?\b(?! of)", r"\brecusan",
                   r"\bpriests?\b", r"\bfriars?\b", r"\bpope\b", r"\bpopes\b", r"\bquakers?", r"\banabaptist",
                   r"\bconventicle", r"\bsectar(y|ie|ies)", r"\bschismati", r"\bheretic", r"\bheres(y|ie)",
                   r"\bseditious (preach|minist)", r"\bsepara(tist|tists)\b", r"\bnonconformi", r"\bdissenters?\b",
                   r"\bcatholi(c|ck|que)s\b", r"\broman catholi")),
    Category(
        "peoples", "Other peoples", "🌍",
        "\"Savages\", \"blackamoors\", \"negroes\", Jews, \"Egyptians\" (Romani people), \"wild Irish\" and the like "
        "(strong); Turks, Moors, \"barbarous\" nations and Highland \"broken men\" (mild).",
        strong=words(r"\bsa[uv]ages?\b", r"\bsal[uv]age", r"\bblack-?a-?moores?", r"\bnegro", r"\b[ij]ewe?s\b",
                     r"\b[ij]ewish", r"\b[ij]ewr(y|ie)", r"\begyptians?\b", r"\bgips(y|ie|ies)", r"\bgyps(y|ie|ies)",
                     r"\bwild(e)? irish", r"\bmere irish", r"\bbeastl(y|ie) indian", r"\binfidels?\b",
                     r"\bheathens?\b", r"\bheathenish"),
        mild=words(r"\bturks?\b", r"\bturkish", r"\bmoores\b", r"\bmoors\b", r"\bsaracens?", r"\bindians?\b",
                   r"\bbarbar\w* (people|nations?|irish|enem\w*|highland\w*|rebels?)", r"\bbroken men\b",
                   r"\bhighland (thie|robb|limm)", r"\bcaterans?", r"\btor(y|ie|ies)\b", r"\birish rebels?",
                   r"\brebels? in ireland", r"\bslaves?\b", r"\bsla[uv]er(y|ie)")),
    Category(
        "violence", "Executions & violence", "🩸",
        "Hanging, drawing and quartering, bounties for men \"dead or alive\", massacres and murders (strong); \"upon "
        "pain of death\", hangings and killing in passing (mild).",
        # Not "quartered" alone: that's soldiers billeted on people ("free-quartering"), not the traitor's death.
        strong=words(r"\bdrawn,? (hanged )?and quarter", r"\bhanged,? drawn", r"\bbehead",
                     r"\bdead or a[luv]i[uv]e", r"\ba[luv]i[uv]e or dead", r"\bmassacre", r"\btortur", r"\bthe rack\b",
                     r"\bput to the sword", r"\bburn(ed|t) (a[luv]i[uv]e|to death)", r"\bhis head\b[^.]{0,60}"
                     r"\b(reward|bring|brought)", r"\bcut (them|him|her)\b", r"\bbarbarous(ly)? (murth|murd)",
                     r"\bhanged (them|him|until|till)", r"\bin cold bl(oo|ou)d"),
        # "Man-slaughter" is mild: it's the crime's legal name, in lists of what a pardon covers.
        mild=words(r"\bpain(e)? of death", r"\bhang(ed|ing)?\b", r"\bgallows", r"\bgibbet", r"\bslaughter",
                   r"\bmurth(er|ar)",
                   r"\bmurd(er|ar)", r"\bkill(ed|ing|s)?\b", r"\bslain\b", r"\bslay", r"\bslew\b", r"\bbl(oo|ou)d",
                   r"\bplace of execution", r"\bexecuted\b", r"\bsuffer(ed)? death", r"\bput to death",
                   r"\bwounded\b", r"\bstabb")),
    Category(
        "sex", "Sex & sexual crimes", "🍆",
        "Rape and \"ravishing\" (strong); whores, bawdy-houses, adultery and fornication (mild). Mostly in the lists "
        "of crimes a general pardon leaves out.",
        # Not a Sussex "rape" (a division of a county, like a hundred or wapentake), nor rape-seed.
        strong=words(r"(?<!hundred )(?<!hundred, )(?<!lath, )\brapes?\b(?!,? (lath|wapentake|or wapentake|or hundred))"
                     r"(?![- ]?seed)",
                     r"\bra[uv]ish", r"\bcarnal(l)? knowledge", r"\bdeflower", r"\bagainst (her|their) wills?\b"),
        mild=words(r"\bwhore", r"\bbawd", r"\bstrumpet", r"\bharlot", r"\badulter", r"\bfornicat", r"\blewd women",
                   r"\bincest", r"\bbastard")),
    Category(
        "lgbt", "Gender & sexuality (LGBTQ+)", "🏳️‍🌈",
        "\"The detestable and abominable vice of buggery\", sodomy, and other gender or sexuality treated as crime or "
        "sin. Set it off for an LGBTQ+-friendly server.",
        strong=words(r"\bbugg?er", r"\bsodom(?!a\b)", r"\bsodomit", r"\bagainst nature", r"\bunnatural (vice|sin|lust)",
                     r"\beffeminat", r"\bhermaphrodit"),
        mild=words(r"\b(women|woman) in (mens|man's|mans) (apparel|clothes|habit)",
                   r"\b(men|man) in (womens|woman's|womans) (apparel|clothes|habit)")),
    Category(
        "plague", "Plague & disease", "🦠",
        "The plague and pestilence (strong); infection, contagion and sickness (mild). Fairs cancelled, ships kept "
        "out, the infected shut up in their houses.",
        strong=words(r"\bplague", r"\bpestilen", r"\bthe sickness\b", r"\bshut up\b[^.]{0,40}\binfect"),
        mild=words(r"\binfect(ed|ion|ious)", r"\bcontagi", r"\bsickness", r"\bdiseases?\b", r"\bsmall ?-?pox",
                   r"\bleprosie|\bleprosy|\blepers?\b", r"\bpox\b")),
]
BY_KEY = {category.key: category for category in CATEGORIES}


def tag(text: str) -> dict[str, int]:
    """Each category's level in a proclamation's text: only the ones above OFF."""
    return {c.key: level for c in CATEGORIES if (level := c.level(text))}


def allowed(tags: dict[str, int], limits: dict[str, int]) -> bool:
    """Whether a proclamation with these tags may be shown where these limits (category -> highest level) apply."""
    return all(level <= limits.get(key, OFF) for key, level in tags.items())


@dataclass(frozen=True)
class Preset:
    key: str
    name: str
    about: str
    limits: dict[str, int]


def every(level: int, **overrides: int) -> dict[str, int]:
    return {c.key: overrides.get(c.key, level) for c in CATEGORIES}


PRESETS = [
    Preset("tame", "🕊️ Tame", "Nothing from any category: tobacco, starch, fairs, coinage and the price of ale.",
           every(OFF)),
    Preset("default", "⚖️ Tasteful", "Where every server starts. The plague in full, and violence and religious "
           "quarrels in passing (Jesuits banished, \"upon pain of death\"); no \"papists\" or \"savages\", no "
           "bounties dead or alive, and nothing on sex or sexuality.",
           every(MILD, plague=FULL, peoples=OFF, sex=OFF, lgbt=OFF)),
    Preset("grim", "🪓 Grim", "The state at its harshest: religious persecution, executions and the plague in full, "
           "sex crimes in passing, but nothing against other peoples or LGBTQ+ people.",
           every(FULL, peoples=OFF, sex=MILD, lgbt=OFF)),
    Preset("unabridged", "📜 Unabridged", "Every proclamation, as the Crown had it printed. All of it.", every(FULL)),
]
PRESETS_BY_KEY = {preset.key: preset for preset in PRESETS}
DEFAULT = PRESETS_BY_KEY["default"]


def preset_for(limits: dict[str, int]) -> Preset | None:
    """The preset these limits match exactly, if any."""
    return next((preset for preset in PRESETS if preset.limits == limits), None)
