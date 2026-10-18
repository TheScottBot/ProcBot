"""The build tool's reading of the Text Creation Partnership catalogue and TEI (procbot/tools/proclamations_build.py),
without downloading."""

import pytest

from procbot.tools import proclamations_build as build

TEI = """<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc><publicationStmt><availability><p>Available
under <ref target="https://creativecommons.org/publicdomain/zero/1.0/">CC0</ref></p></availability></publicationStmt>
<sourceDesc><biblFull><publicationStmt><publisher>Printed by Benjamin Tooke,</publisher><pubPlace>Dublin :</pubPlace>
</publicationStmt></biblFull></sourceDesc></fileDesc><profileDesc><langUsage><language ident="eng">eng</language>
</langUsage></profileDesc></teiHeader>
<text xml:lang="unk"><body><div type="royal_proclamation">
<head><figure><p>DIEV ET MON DROIT</p></figure></head>
<byline><g ref="char:leaf">❧</g> By the Lord Lieutenant and Council.</byline>
<head>A PROCLAMATION For the Apprehending of <hi>Redmond O Hanlon</hi>.</head>
<opener><signed><list><item>ESSEX.</item></list></signed></opener>
<p>WHereas the ſaid Pro<g ref="char:EOLhyphen"/>clamation <gap reason="illegible"/> was 〈◊〉 iſſued<note>a note</note>,
we do hereby command all His Majeſties Subjects.</p>
<closer><signed><list><item>Arran.</item><item>Ja: Cuffe.</item></list></signed>
<dateline>Given at the Council-Chamber in <hi>Dublin</hi> the 14th day of <hi>December</hi> 1674.</dateline></closer>
</div></body></text></TEI>"""


def row(author="Ireland. Lord Lieutenant (1672-1677 : Essex); Essex, Arthur Capel, Earl of, 1631-1683.",
        title="By the Lord Lieutenant and Council, a proclamation", terms="", pages="1", date="1674", status="Free"):
    return {"TCP": "A46162", "Author": author, "Title": title, "Terms": terms, "Pages": pages, "Date": date,
            "Status": status}


def test_reads_a_proclamation():
    read = build.read("A46162", TEI.encode())
    assert read["heading"] == ["By the Lord Lieutenant and Council.",
                               "A PROCLAMATION For the Apprehending of Redmond O Hanlon."]
    assert read["paragraphs"] == ["WHereas the said Proclamation … was … issued, we do hereby command all His "
                                  "Majesties Subjects."]
    assert read["signed"] == ["ESSEX.", "Arran.", "Ja: Cuffe."]
    assert read["place"] == "Dublin" and read["printer"] == "Printed by Benjamin Tooke"
    assert "14th day of December 1674" in read["dateline"]


def test_skips_what_isnt_cc0_or_english():
    assert build.read("x", TEI.replace("publicdomain/zero", "licenses/by-nc").encode()) is None
    assert build.read("x", TEI.replace('ident="eng"', 'ident="lat"').encode()) is None


def test_entry_from_catalogue_and_text():
    entry = build.entry(row(), build.read("A46162", TEI.encode()))
    assert entry["id"] == "a46162" and entry["phase"] == 1
    assert (entry["realm"], entry["issuer"], entry["holder"]) == ("ireland", "Lord Lieutenant", "Essex")
    assert entry["date"] == "1674-12-14" and entry["monarch"] == "Charles II"


def test_which_rows_are_proclamations():
    assert build.is_proclamation(row())
    # The government needn't be the first name in the author
    assert build.is_proclamation(row(author="Charles II, King of England, 1630-1685.; England and Wales. Sovereign "
                                            "(1660-1685 : Charles II)"))
    assert build.is_proclamation(row(title="A declaration", terms="England and Wales. -- Proclamations. 1661-01-01"))
    assert not build.is_proclamation(row(title="A declaration of the Army"))
    assert not build.is_proclamation(row(author="France. Sovereign (1610-1643 : Louis XIII)"))
    assert not build.is_proclamation(row(author="England and Wales. Army. Council."))
    assert not build.is_proclamation(row(pages="120"))  # A book of them


def test_issuer_with_a_full_stop_in_the_name():
    assert build.issuer_of("England and Wales. Lord Protector (1653-1658 : O. Cromwell)") == \
        ("England and Wales", "Lord Protector", "O. Cromwell")
    assert build.issuer_of("Scotland. Privy Council.") == ("Scotland", "Privy Council", "")


@pytest.mark.parametrize("dateline, expected", [
    ("Given at the Council Chamber at Whitehall, the Three and Twentieth Day of May, 1696.", "1696-05-23"),
    ("Giuen at our Mannour of Saint Iames the sixt day of Nouember in the fiue & twentieth yeere", "1620-11-06"),
    ("Gyuen at her Palaice of Westminster the.xxii. day of December. 1565. the eyght yere", "1565-12-22"),
    ("Giuen at his Maiesties Palace of Westminster the xxviij. day of December", "1620-12-28"),
    ("Given at Our Court at OXFORD, the 22th day of December, in the Nineteenth yeare of Our Reigne. 1643.",
     "1643-12-22"),
    ("Given under Our Signet at Edinburgh the third of December, and of Our Reign the eight year 1696.",
     "1696-12-03"),
    ("Giuen at her Maiesties Palace at Westminster the xiiii. day of Aprill, 1580.", "1580-04-14"),
    ("Wednesday March 28. 1660.", "1660-03-28"),
    ("Given at Our Court at Whitehall the 2d day of November, 1688.", "1688-11-02"),
    ("Given under Our Signet at Edinburgh, the last day of January, 1693", "1693-01"),
    ("Witnesse our selfe. &c.", "1620"),
])
def test_dates_from_datelines(dateline, expected):
    assert build.date_of(row(date="1620"), dateline) == expected


def test_subject_terms_date_comes_first():
    assert build.date_of(row(terms="Proclamations. 1638-06-28"), "the first day of May 1600") == "1638-06-28"


def test_monarchs():
    assert build.monarch_of("england", "1610", "James I", "Sovereign") == "James I"
    assert build.monarch_of("scotland", "1610", "James I", "Sovereign") == "James VI"
    assert build.monarch_of("scotland", "1692", "William and Mary", "Sovereign") == "William II and Mary II"
    assert build.monarch_of("ireland", "1662", "Ormonde", "Lord Lieutenant") == "Charles II"
    assert build.monarch_of("england", "1655", "O. Cromwell", "Lord Protector") == "the Commonwealth"


def test_realm_from_where_it_was_printed():
    assert build.realm_of("England and Wales", "Dublin") == "ireland"
    assert build.realm_of("England and Wales", "Edinburgh") == "scotland"
    assert build.realm_of("England and Wales", "London") == "england"
    assert build.realm_of("Scotland", "London") == "scotland"
