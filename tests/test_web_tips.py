"""Web tips: the local checks must stop bad tips, nothing shows until accepted, and source scores follow the student's decisions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import web_tips as wt  # noqa: E402
from card_ui import TILES, card_data  # noqa: E402

CARD = {"card_id": "R1.2-11", "title": "Born-Haber: walking against an arrow flips its sign", "priority": 3,
        "walkthrough": {"key_idea": "Flip the formation arrow.", "careful": "Keep electron affinity as drawn.", "question": "Pick one.\nA. a\nB. b\nC. c\nD. d",
                        "marks": 1, "question_ref": "x", "answer": "B", "try_next": [],
                        "steps": {k: {"short": "Basic line", "why": "Reason", "avoid": "Trap", "seconds": 5} for k, _l in TILES}}}
GOOD = {"tip": "Multiply the atomisation term by two for compounds such as MgCl2.", "why": "Students often forget there are two chlorine atoms.",
        "kind": "mistake", "pillar": "7_elimination", "url": "https://chem.libretexts.org/page"}


def reasons(**change):
    return " ".join(wt.check({**GOOD, **change}, CARD, [])[0])


def test_a_slow_search_cannot_overwrite_a_decision_made_while_it_ran(tmp_path):
    f = tmp_path / "web_tips.json"
    wt.update(lambda d: wt.add_proposals(d, [GOOD], CARD, "R1.2"), f)
    stale = wt.load(f)                                                 # a search starts and reads the file
    (tip_id, _t), = wt.pending(stale)
    wt.update(lambda d: wt.set_status(d, tip_id, "accepted"), f)       # the student accepts a tip meanwhile
    other = {**CARD, "card_id": "R1.1-01"}
    found = [{**GOOD, "tip": "A different idea about significant figures in calorimetry."}]
    wt.update(lambda d: wt.add_proposals(d, found, other, "R1.1"), f)  # the search finishes
    data = wt.load(f)
    assert data["tips"][tip_id]["status"] == "accepted" and len(data["tips"]) == 2
    assert set(data["researched"]) == {"R1.2-11", "R1.1-01"}


def test_many_writers_at_once_lose_nothing(tmp_path):
    import threading
    f = tmp_path / "web_tips.json"

    def write(n):
        card = {**CARD, "card_id": f"card-{n}"}
        wt.update(lambda d: wt.add_proposals(d, [{**GOOD, "tip": f"Idea number {n} about energy cycles."}], card, "R1.2"), f)
    threads = [threading.Thread(target=write, args=(n,)) for n in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(wt.load(f)["tips"]) == 12 and not list(tmp_path.glob("*.lock")) and not list(tmp_path.glob("*.tmp"))


def test_good_tip_passes():
    assert wt.check(GOOD, CARD, []) == ([], [])


def test_planted_bad_tips_are_stopped():
    assert "hosts copied papers" in reasons(url="https://www.scribd.com/document/1")
    assert "hosts copied papers" in reasons(url="https://uk.scribd.com/document/1")
    assert "no usable source link" in reasons(url="javascript:alert(1)")
    assert "no usable source link" in reasons(url="")
    assert "unknown criterion" in reasons(pillar="8_magic")
    assert "unknown kind" in reasons(kind="gossip")
    assert "over 30 words" in reasons(tip="word " * 31)
    assert "doesn't balance" in reasons(tip="Remember H2(g) + Cl2(g) → HCl(g) for this.")
    assert "isn't an element" in reasons(tip="Compare H-Bf with H-Cl first.")
    assert "lattice enthalpy is negative" in reasons(tip="Lattice enthalpy is always negative.")
    assert "bond breaking releases" in reasons(tip="Bond breaking releases energy.")
    assert "bond forming takes in" in reasons(tip="Forming bonds requires energy.")
    assert "data booklet" in reasons(tip="pH + pOH = 14 is in the data booklet.")
    assert "old syllabus" in reasons(tip="This appears on Paper 3 every year.")
    assert "the card already says" in reasons(tip="Born-Haber: walking against an arrow flips its sign")


def test_correct_statements_are_not_stopped():
    assert reasons(tip="Lattice enthalpy is positive in the IB, not negative.") == ""
    assert reasons(tip="The lattice enthalpy of formation is negative, the reverse process.") == ""
    assert reasons(tip="pH + pOH = 14 is not in the data booklet, so memorise it.") == ""
    assert reasons(tip="Bond forming releases energy, and breaking bonds takes it in.") == ""
    assert reasons(tip="½Cl2(g) → Cl(g) is the atomisation step for chlorine.") == ""


def test_other_board_and_old_syllabus_only_warn():
    fail, warn = wt.check({**GOOD, "url": "https://example.com/a-level/energetics"}, CARD, [])
    assert not fail and "another exam board" in warn[0]
    fail, warn = wt.check({**GOOD, "tip": "Topic 5 often tests this kind of cycle."}, CARD, [])
    assert not fail and "old syllabus" in warn[0]


def test_only_accepted_tips_reach_the_card():
    data = {"tips": {}, "researched": {}}
    tally = wt.add_proposals(data, [GOOD, {**GOOD, "tip": "Lattice enthalpy is negative.", "url": "https://bad.example/x"}], CARD, "R1.2")
    assert tally == {"pending": 1, "failed": 1} and data["researched"]["R1.2-11"]
    assert wt.accepted_for(data, "R1.2-11") == []
    (tip_id, _t), = wt.pending(data)
    wt.set_status(data, tip_id, "accepted")
    assert [t["tip"] for t in wt.accepted_for(data, "R1.2-11")] == [GOOD["tip"]] and wt.pending(data) == []


def test_same_tip_is_not_suggested_twice_even_if_rejected():
    data = {"tips": {}, "researched": {}}
    wt.add_proposals(data, [GOOD], CARD, "R1.2")
    (tip_id, _t), = wt.pending(data)
    wt.set_status(data, tip_id, "rejected")
    tally = wt.add_proposals(data, [GOOD, {**GOOD, "tip": GOOD["tip"] + " Always."}], CARD, "R1.2")
    assert tally["duplicate"] == 1 and tally["failed"] == 1 and wt.pending(data) == []


def test_source_scores_learn_from_decisions():
    def tip(domain, status, reasons=()):
        return {"domain": domain, "status": status, "reasons": list(reasons), "card_id": "x"}
    data = {"researched": {}, "tips": {
        "1": tip("good.org", "accepted"), "2": tip("good.org", "accepted"), "3": tip("bad.net", "rejected"), "4": tip("bad.net", "rejected"),
        "5": tip("bad.net", "failed", ["says bond breaking releases energy"]), "6": tip("neutral.io", "failed", ["the card already says this"]),
        "7": tip("waiting.com", "pending")}}
    scores = wt.source_scores(data)
    assert scores["good.org"]["accepted"] == 2 and scores["bad.net"]["rejected"] == 3
    assert "neutral.io" not in scores and "waiting.com" not in scores
    assert wt.preferred_and_avoided(data) == (["good.org"], ["bad.net"])


def test_next_card_puts_hard_notes_first_and_skips_researched():
    cards = [("R1.1", {"card_id": "a", "priority": 1, "walkthrough": {"question": "q"}}), ("R1.1", {"card_id": "b", "priority": 5, "walkthrough": {"question": "q"}}),
             ("R1.1", {"card_id": "c", "priority": 2, "walkthrough": {"question": "q"}}), ("R3.1", {"card_id": "old", "priority": 1})]
    data = {"tips": {}, "researched": {"a": "2026-11-04"}}
    assert [c["card_id"] for _s, c in wt.next_cards(data, cards, limit=2)] == ["c", "b"]
    assert [c["card_id"] for _s, c in wt.next_cards(data, cards, {"b"}, limit=1)] == ["b"]


def test_card_shows_accepted_tips_under_their_criterion_with_a_safe_link():
    web = [{"pillar": "7_elimination", "tip": "Web idea", "why": "Because", "url": "https://chem.libretexts.org/p", "domain": "chem.libretexts.org"},
           {"pillar": "7_elimination", "tip": "Unsafe link", "why": "", "url": "javascript:alert(1)", "domain": ""}]
    d = card_data(CARD, Path("."), [], web)
    tile = next(t for t in d["tiles"] if t["key"] == "7_elimination")
    assert [w["tip"] for w in tile["web"]] == ["Web idea"]
    assert next(t for t in d["tiles"] if t["key"] == "1_context")["web"] == []
