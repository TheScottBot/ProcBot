"""modern:True's spelling tidy (procbot/spelling.py)."""

import pytest

from procbot.spelling import modern


@pytest.mark.parametrize("printed, tidied", [
    ("vnto all his Maiesties louing Subiects, vpon paine", "unto all his Majesties loving Subjects, upon paine"),
    ("Giuen at Saint Iames the sixt day of Nouember", "Given at Saint James the sixt day of November"),
    ("Euery Iustice of Peace shall haue", "Every Justice of Peace shall have"),
    ("VVhereas the Iesuites", "Whereas the Jesuites"),
    ("cōmaunded without directiō", "commaunded without direction"),
    ("cōtained", "contained"),  # As TCP has it: o and a combining stroke
    ("the ȝeir of God", "the yeir of God"),
    ("VNTO OVR REALME", "UNTO OUR REALME"),
    ("a Iuell", "a Juell"),
    ("the iiii. day", "the iiii. day"),  # Roman numerals stay
    ("all Maiors, Sheriffes", "all Maiors, Sheriffes"),  # Mayors, not majors
])
def test_tidies_printers_spelling(printed, tidied):
    assert modern(printed) == tidied


@pytest.mark.parametrize("word", ["receiue", "Ireland", "in", "is", "LOVE", "obedience", "value", "quiet"])
def test_leaves_real_letters_alone(word):
    assert modern(word).replace("receive", "receiue") == word
