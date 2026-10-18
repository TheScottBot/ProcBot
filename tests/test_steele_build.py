"""Reading Steele's calendar from its OCR (procbot/tools/steele_build.py), without downloading."""

import pytest

from procbot.tools import steele_build as build

# Two entries as archive.org's OCR has them: one paragraph a line, with its slips.
LINES = """\
1666-7: 18-19 Charles II
Nos 776-82
7 JANUARY —BY THE LORD LIEUTEN- ANT AND COUNCIL : [Begins] Wee the Lord Lieutenant . . .
[Authorizing purchase of Trumpets, Colours, Drums, &c., for Militia.]
Dublin : 7 January 1666[-7].
Dublin: J. Crook: 1666[-7].
1 f. Gothic letter.
Arms 180 the sums it
Ormonde.
Authorizing expenditure of £10 for a horse-troop or £6 for a foot-company on trumpets, colours, drums, and other trophies.
Ja. Armachanus, Santry, Hen. Midensis, Jo. Bysse, J. Temple, Robert Byron, Robert Forth, Rob. Meredith.
P.R.O. Dub. 1. A. (259) ; 1. B. (149). N° 77 6.
24 JULY.— BY THE LORDS JUSTICES AND COUNCIL OF IRELAND. A Proclamation For a General Fast.
Dublin : 24 July 1714.
2 ff. Roman letter.
A fast is to be observed on Friday. P.R.O. Dub. C. 1 (32).
Dub. Gaz. 1022. jfo 777^
16 MAY.
London : Bill & Barker : 1660.
Another edition of No. 733, q.v.
""".splitlines()


def entries():
    lines = [(leaf, build.tidy(line)) for leaf, line in enumerate(LINES)]
    section = build.Section("ireland", "ire", "book", build.re.compile("x"), build.re.compile("y"))
    return build.entries_of(section, lines, {1: "96", 3: "96"})


def test_reads_entries():
    first, second = entries()  # The other edition isn't a third
    assert first["id"] == "ire776" and first["number"] == "776"
    assert first["issuer"] == "Lord Lieutenant and Council" and first["date"] == "1666-01-07"
    assert first["opening"] == "Wee the Lord Lieutenant"
    assert first["summary"] == "Authorizing purchase of Trumpets, Colours, Drums, &c., for Militia"
    assert first["abstract"].startswith("Authorizing expenditure of £10") and "P.R.O" not in first["abstract"]
    assert first["signed"].startswith("Ormonde, Ja. Armachanus")
    assert first["dateline"] == "Dublin : 7 January 1666[-7]"
    assert first["page"] == "96" and first["status"] == "printed"
    assert second["id"] == "ire777" and second["title"] == "A Proclamation For a General Fast"
    assert second["abstract"] == "A fast is to be observed on Friday." and second["date"] == "1714-07-24"


@pytest.mark.parametrize("raw, name", [("LORD LIEUTENANT AND COUNCIL", "Lord Lieutenant and Council"),
                                       ("PRIVY COUN CIL", "Privy Council"), ("LORDS JUS TICES", "Lords Justices"),
                                       ("KING", "King")])
def test_issuer_names(raw, name):
    assert build.issuer_name(raw) == name


@pytest.mark.parametrize("line, number", [("P.R.O. Original signed, P.S.B. N° 1.", "1"), ("Rot. Pat. NO 5^", "5"),
                                          ("R. xii. 277. Ro 3.", "3"), ("Hall 431. N° 6a. B", "6a"),
                                          ("S.P.I. Cal. p. 59 ; Carew i. 158. N’° 4.", "4")])
def test_numbers_as_the_ocr_reads_them(line, number):
    found = build.NUMBER_AT_END.search(line)
    assert found.group(1).replace(" ", "") + (found.group(2) or "") == number


def test_place_is_a_name_not_the_title():
    found = list(build.PLACE_DATE.finditer("A Proclamation For a General Fast. Dublin : 22 December 1701"))[-1]
    assert found.group("place") == "Dublin" and found.group("year") == "1701"


def test_a_bad_number_is_dropped():
    lines = [(0, build.tidy(line)) for line in [
        "1 MAY.— BY THE KING. A Proclamation for Hops.", "London : 1 May 1600.", "Of hops. N° 10.",
        "2 MAY.— BY THE KING. A Proclamation for Ale.", "London : 2 May 1600.", "Of ale. N° 1690.",  # A year
    ]]
    section = build.Section("england", "eng", "book", build.re.compile("x"), build.re.compile("y"))
    first, second = build.entries_of(section, lines, {})
    assert first["id"] == "eng10" and second["id"] == "eng10-1" and "number" not in second or not second["number"]
