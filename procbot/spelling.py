"""Tidying old spelling for modern:True. Plain Python, no Discord.

Only the printers' conventions are changed, not the words: u and v (printed by position, not sound: "vnto",
"haue"), i and j ("Iames", "iustice", "Maiestie"), vv for w, the yogh (ȝ) of Scots ("ȝeir"), and the stroke over a
vowel that stood for a following m or n ("cōmaunded"). So "Maiestie" becomes "Majestie", not "Majesty".
"""

import re
import unicodedata

VOWELS = "aeiouAEIOU"
# Where an i inside a word is a j. Inside a word it's too often a real i ("receiue") for a general rule.
INNER_J = re.compile(r"(?<=ma)i(?=est)|(?<=sub)i(?=ect)|(?<=ob)i(?=ect)|(?<=re)i(?=ect)|(?<=pro)i(?=ect)|"
                     r"(?<=ad)i(?=o?urn)|(?<=in)i(?=ur)|(?<=ad)i(?=udg)|(?<=con)i(?=ur)|(?<=pre)i(?=udic)|"
                     r"(?<=ma)i(?=or)|(?<=en)i(?=oy)|(?<=ad)i(?=oyn)|(?<=con)i(?=unct)", re.I)

RULES = [
    (re.compile(r"VV"), "W"),
    (re.compile(r"Vv|vv"), lambda m: "W" if m.group()[0] == "V" else "w"),
    # The stroke: + "m" before b, p or m ("cōmaunded" -> "commaunded"), else + "n" ("directiō" -> "direction")
    (re.compile(r"([A-Za-z])̄(?=[bpmBPM])"), r"\1m"),
    (re.compile(r"([A-Za-z])̄"), r"\1n"),
    (re.compile(r"ȝ"), "y"),
    (re.compile(r"Ȝ"), "Y"),
    # v at the start of a word, before a consonant, is u: "vnto", "vpon", "vs"
    (re.compile(rf"\bv(?=[^{VOWELS}\W])"), "u"),
    (re.compile(rf"\bV(?=[^{VOWELS}\W\d])(?=[a-z])"), "U"),
    # In capitals, V before a consonant is U anywhere: "VNTO", "OVR", "EVROPE"
    (re.compile(r"V(?=[B-DF-HJ-NP-TV-Z])"), "U"),
    # u between vowels is v: "haue", "giuen", "Souereign", "Euery"
    (re.compile(rf"(?<=[{VOWELS}])u(?=[{VOWELS}])"), "v"),
    # I or i starting a word, before a vowel, is j: "Iames", "Iohn", "iustice", "Iuly". ("Ireland", "in", "is" stay.)
    (re.compile(r"\bI(?=[aeiou])"), "J"),
    (re.compile(r"\bi(?=[aeiou])"), "j"),
    (INNER_J, lambda m: "J" if m.group() == "I" else "j"),
]


def modern(text: str) -> str:
    text = unicodedata.normalize("NFD", text)  # "ō" -> "o" + the combining stroke, so the rule above sees it
    for pattern, replacement in RULES:
        text = pattern.sub(replacement, text)
    return unicodedata.normalize("NFC", text)
