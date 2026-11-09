"""Engine path with a stand-in Anthropic client: gate, synthesis plumbing, validation, status merge."""
import copy
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from engine import technique_engine as te  # noqa: E402

PILOT = json.loads((Path(__file__).resolve().parents[1] / "data" / "techniques" / "R3.1.json").read_text(encoding="utf-8"))

def steps(key_ref="24M.1.HL.TZ1.5"):
    common = {"short": "Act on the question", "why": "It works here", "avoid": "The tempting wrong move", "seconds": 10}
    return {
        "4_command_terms": {**common, "command_term": "none", "demands": "Pick one option", "score_mechanics": "One mark, no working credit"},
        "1_context": {**common, "ao_level": "AO2", "syllabus_hook": "R3.1.4 links pH and pOH", "textbook_gap": "Books teach them apart"},
        "3_novel_application": {**common, "disguise": "The base hides in an option", "heuristic": "Name the ion first"},
        "7_elimination": {**common, "definitely_wrong": [{"target": "A", "rule": "Wrong side of 7"}]},
        "6_data_booklet": {**common, "sections": [1], "pattern": "Section 1 prints pOH", "memorise": "pH + pOH = 14"},
        "5_time_efficiency": {**common, "workflow": ["pOH first", "Subtract from 14"], "fat_to_trim": "Rebuilding it from Kw"},
        "2_markscheme_logic": {**common, "trigger_phrases": ["conversion step"], "trap_boundary": "Stopping at pOH",
                               "delta": "The conversion is the mark", "evidence_ref": key_ref},
    }


def walkthrough(ref="24M.1.HL.TZ1.5", answer="B"):
    return {"question_ref": ref, "question": "In my own words: a base solution is given and its pH is wanted.", "marks": 1,
            "key_idea": "Convert to pOH first.", "question_type": "pH of a base", "careful": "Find pOH before pH.", "procedure": ["Find the hydroxide concentration", "Take the negative log for pOH", "Subtract from 14"],
            "tricks": ["A base must give pH above 7."], "if_lost": ["Is it an acid or a base?", "Which ion does the concentration describe?"], "steps": steps(ref), "answer": answer, "try_next": []}


def with_walkthroughs(cards):
    """Give the pilot cards (written before walkthroughs existed) a valid one, using a real keyed question from the pack."""
    pack = te.evidence_mod.build("R3.1")
    q = next(x for x in pack["questions"] if x["mcq_answer"] and x["question"])
    wrong = next(x for x in "ABCD" if x != q["mcq_answer"])
    for c in cards:
        c["walkthrough"] = walkthrough(q["ref"], f"{q['mcq_answer']} because of the sign check")
        c["walkthrough"]["steps"]["7_elimination"]["definitely_wrong"] = [{"target": wrong, "rule": "Wrong side of 7"}]
        c["walkthrough"]["steps"]["1_context"]["syllabus_hook"] = f"{pack['understandings'][0]['code']} links pH and pOH"
    return cards


class FakeClient:
    def __init__(self, deck):
        self.deck, self.calls = deck, []
        self.messages = NS(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        return NS(content=[NS(type="tool_use", input=copy.deepcopy(self.deck))])


def test_gate_pauses_without_markschemes():
    with pytest.raises(te.MarkschemeMissing) as e:
        te.run("R3.1", client=FakeClient({"cards": []}))
    assert "07M.1.HL.TZ0.3" in e.value.refs


def test_full_path_validates_and_keeps_mastered(tmp_path, monkeypatch):
    monkeypatch.setattr(te, "TECH_DIR", tmp_path)
    old = copy.deepcopy(PILOT)
    old["cards"][0]["status"]["mastered"] = True                 # student ticked T01 earlier
    (tmp_path / "R3.1.json").write_text(json.dumps(old))
    fake = FakeClient({"cards": with_walkthroughs(copy.deepcopy(PILOT["cards"])), "cross_links": PILOT["cross_links"]})
    deck = te.run("R3.1", allow_partial=True, client=fake)
    call = fake.calls[0]
    assert call["model"] == te.MODEL and call["tool_choice"]["name"] == "emit_technique_deck"
    assert deck["validation_issues"] == []
    assert deck["cards"][0]["status"]["mastered"] is True and deck["cards"][1]["status"]["mastered"] is False
    assert set(deck["excluded_no_markscheme"]) >= {"07M.1.HL.TZ0.3"}


def test_validation_catches_bad_claims(tmp_path, monkeypatch):
    monkeypatch.setattr(te, "TECH_DIR", tmp_path)
    cards = copy.deepcopy(PILOT["cards"][:2])
    cards[0]["evidence"].append({"ref": "99M.1.HL.TZ9.99", "kind": "mcq", "note": "invented"})
    cards[1]["pillars"]["6_data_booklet"]["hack"] = "pKa + pKb = 14 is printed in the data booklet, section 1."
    cards[1]["evidence"][0]["note"] = "correct answer is A"           # key for 25M.1A.HL.6213.33 is B
    deck = te.run("R3.1", allow_partial=True, client=FakeClient({"cards": cards}))
    text = json.dumps(deck["validation_issues"])
    assert "unknown ref 99M.1.HL.TZ9.99" in text
    assert "claimed to be in the booklet" in text
    assert "key is B" in text
    assert all(c["status"]["needs_review"] for c in deck["cards"])


KNOWN = {"24M.1.HL.TZ1.5": {"has_markscheme": True, "mcq_answer": "B", "question": "Which solution has a pH of 9?\nA. one\nB. two",
                            "markscheme": "B"},
         "24M.2.HL.TZ1.3": {"has_markscheme": True, "mcq_answer": None, "question": "Explain why the pH changes.",
                            "markscheme": "the conversion step from pOH earns the mark"},
         "24M.1.HL.TZ1.6": {"has_markscheme": False, "mcq_answer": None, "question": "No markscheme here.", "markscheme": None}}
TERMS = {"explain", "calculate"}
CODES = {"R3.1.4"}


def check(wt):
    return " ".join(te.walkthrough_issues(wt, KNOWN, TERMS, CODES))


def changed(pillar, **fields):
    wt = walkthrough()
    wt["steps"][pillar].update(fields)
    return check(wt)


def test_good_walkthrough_passes():
    assert check(walkthrough()) == ""


def test_card_stays_short_enough_to_read_at_a_glance():
    long = "word " * 40
    assert "4_command_terms short is over 12 words" in changed("4_command_terms", short="word " * 13)
    assert "1_context why is over 35 words" in changed("1_context", why=long)
    assert "3_novel_application disguise is over 35 words" in changed("3_novel_application", disguise=long)
    assert "key idea is over 15 words" in check({**walkthrough(), "key_idea": "word " * 16})
    assert "no key idea" in check({**walkthrough(), "key_idea": ""})
    assert "no question type" in check({**walkthrough(), "question_type": ""})
    assert "no careful step" in check({**walkthrough(), "careful": ""})
    assert "question_type is over 8 words" in check({**walkthrough(), "question_type": "word " * 9})
    assert "careful is over 12 words" in check({**walkthrough(), "careful": "word " * 13})
    assert "over 8 words" in changed("5_time_efficiency", workflow=["word " * 9, "Second"])
    assert "more than 5 steps" in changed("5_time_efficiency", workflow=["a", "b", "c", "d", "e", "f"])


def cycle(target=30):
    return {"unit": "kJ", "route": ["a", "b", "c"], "levels": [{"id": x, "label": x, "x0": 0, "x1": 1} for x in "abc"],
            "arrows": [{"id": "1", "name": "n", "from": "b", "to": "a", "value": -10, "x": .1, "short": "s", "why": "w"},
                       {"id": "2", "name": "n", "from": "b", "to": "c", "value": 20, "x": .2, "short": "s", "why": "w"},
                       {"id": "3", "name": "t", "from": "a", "to": "c", "value": target, "x": .3, "short": "s", "why": "w", "target": True}]}


def test_clickable_cycle_numbers_must_add_up():
    assert te.diagram_issues(None) == []
    assert te.diagram_issues(cycle()) == []
    assert "totals 30, but the target says 99" in " ".join(te.diagram_issues(cycle(99)))
    broken = cycle()
    broken["route"] = ["a", "c"]
    assert "no arrow from a to c" in " ".join(te.diagram_issues(broken))
    none = cycle()
    none["arrows"][2].pop("target")
    assert "exactly one target" in " ".join(te.diagram_issues(none))


def test_added_cards_take_the_next_ids_and_existing_cards_are_untouched():
    deck = {"cards": [{"card_id": "R1.1-01", "x": 1}, {"card_id": "R1.1-12", "x": 2}]}
    assert te.merge_added(deck, {"cards": [{"card_id": "R1.1-01", "x": 3}, {"card_id": "zzz", "x": 4}]}, "R1.1") == ["R1.1-13", "R1.1-14"]
    assert [c["x"] for c in deck["cards"]] == [1, 2, 3, 4] and deck["cards"][0]["card_id"] == "R1.1-01"


def test_top_up_prompt_names_the_skills_and_what_exists():
    deck = {"cards": [{"walkthrough": {"question_type": "Hess's law"}}]}
    text = te.add_prompt("uncertainty in ΔH", deck)
    assert "ONLY" in text and "uncertainty in ΔH" in text and "Hess's law" in text


def test_stray_fields_in_steps_are_dropped_and_real_pillars_kept():
    deck = {"cards": [{"card_id": "c", "walkthrough": {"steps": {"7_elimination": {"short": "x"}, "note": "stray", "1_context": "not a dict"}}}]}
    assert te.clean_steps(deck) == ["c: note", "c: 1_context"]
    assert list(deck["cards"][0]["walkthrough"]["steps"]) == ["7_elimination"]


def test_question_that_cannot_be_solved_from_the_card_is_flagged():
    text = "needs a diagram or data the card doesn't have"
    assert text in check({**walkthrough(), "question": "The exact peaks are not in the available text, so read them from the figure in the paper."})
    assert text in check({**walkthrough(), "answer": "B. The graph shapes are not in the available text."})
    assert text not in check(walkthrough())


def test_procedure_tricks_and_hints_are_required_and_short():
    assert "procedure needs 2-6" in check({**walkthrough(), "procedure": ["Only one step"]})
    assert "tricks needs 1-3" in check({**walkthrough(), "tricks": []})
    assert "if_lost needs 2-4" in check({**walkthrough(), "if_lost": ["Just one"]})
    assert "over 12 words" in check({**walkthrough(), "procedure": ["word " * 13, "Second"]})
    assert "over 15 words" in check({**walkthrough(), "if_lost": ["word " * 16, "Second?"]})


def test_planted_hints_that_give_the_answer_away_are_caught():
    assert "gives the answer away" in check({**walkthrough(), "if_lost": ["The answer is B.", "Which ion?"]})
    leaky = {**walkthrough(), "answer": "B: the pH is 11.5", "if_lost": ["Is it near 11.5?", "Which ion?"]}
    assert "gives the answer away" in check(leaky)
    fine = {**walkthrough(), "question": "A base at pH 11.5 is diluted.", "answer": "B: the pH is 11.5", "if_lost": ["What does 11.5 tell you?", "Which ion?"]}
    assert "gives the answer away" not in check(fine)


def test_every_criterion_is_required():
    assert "no step-by-step" in check(None)
    for pillar in te.STEP_ORDER:
        wt = walkthrough()
        del wt["steps"][pillar]
        assert f"missing {pillar}" in check(wt)
    assert "1_context has no textbook_gap" in changed("1_context", textbook_gap="")
    assert "2_markscheme_logic has no delta" in changed("2_markscheme_logic", delta="")
    assert "3_novel_application has no heuristic" in changed("3_novel_application", heuristic="")
    assert "5_time_efficiency has no fat_to_trim" in changed("5_time_efficiency", fat_to_trim="")
    assert "4_command_terms has no score_mechanics" in changed("4_command_terms", score_mechanics="")


def test_planted_errors_in_each_criterion_are_caught():
    assert "not an AO level" in changed("1_context", ao_level="AO9")
    assert "no understanding code" in changed("1_context", syllabus_hook="Links pH and pOH")
    assert "doesn't have" in changed("1_context", syllabus_hook="R9.9.9 is invented")
    assert "rules out the correct answer B" in changed("7_elimination", definitely_wrong=[{"target": "B", "rule": "Wrong"}])
    assert "not an option letter" in changed("7_elimination", definitely_wrong=[{"target": "big numbers", "rule": "Wrong"}])
    assert "rules nothing out" in changed("7_elimination", definitely_wrong=[])
    assert "section 99 does not exist" in changed("6_data_booklet", sections=[99])
    assert "no pattern" in changed("6_data_booklet", pattern="")
    assert "nothing to memorise" in changed("6_data_booklet", sections=[], memorise="")
    assert "fewer than 2 moves" in changed("5_time_efficiency", workflow=["Just do it"])
    assert "more than 4 moves" in changed("5_time_efficiency", workflow=["a", "b", "c", "d", "e"])
    assert "over 6 words" in changed("5_time_efficiency", workflow=["one two three four five six seven", "b"])
    assert "no markscheme in the pack" in changed("2_markscheme_logic", evidence_ref="24M.1.HL.TZ1.6")
    assert "no trigger phrases" in changed("2_markscheme_logic", trigger_phrases=[])


def test_planted_errors_in_the_worked_question_are_caught():
    def issues(**change):
        return check({**walkthrough(), **change})
    assert "unknown ref" in issues(question_ref="99M.1.HL.TZ9.9")
    assert "no markscheme" in issues(question_ref="24M.1.HL.TZ1.6")
    assert "key is B" in issues(answer="C")
    assert "start with a letter" in issues(answer="the second one")
    assert "copies the original" in issues(question="Which solution has a pH of 9?\nA. one\nB. two")
    assert "isn't in the pack" in issues(try_next=["24M.1.HL.TZ1.6"])
    assert "doesn't balance" in issues(question="Consider H2(g) + Cl2(g) → HCl(g) in my own words.")


def test_question_rebuilt_from_a_markscheme_is_flagged():
    known = {**KNOWN, "24M.1.HL.TZ1.9": {"has_markscheme": True, "mcq_answer": "B", "question": None, "markscheme": "B"}}
    assert "no question text" in " ".join(te.walkthrough_issues(walkthrough("24M.1.HL.TZ1.9"), known, TERMS, CODES))


def test_structured_question_checks_term_and_trigger_phrases():
    wt = walkthrough("24M.2.HL.TZ1.3", "Because it changes.")
    wt["steps"]["4_command_terms"]["command_term"] = "Explain"
    wt["steps"]["7_elimination"]["definitely_wrong"] = [{"target": "An answer with no reason", "rule": "Explain needs a cause"}]
    assert check(wt) == ""
    wt["steps"]["4_command_terms"]["command_term"] = "Think about"
    assert "not a syllabus command term" in check(wt)
    wt["steps"]["4_command_terms"]["command_term"] = "Explain"
    wt["steps"]["2_markscheme_logic"]["trigger_phrases"] = ["totally unrelated wording"]
    assert "share no words" in check(wt)


def test_cli_schema_stays_shell_safe_with_walkthrough():
    def strip(node):                                              # synthesize_cli drops descriptions the same way
        if isinstance(node, dict):
            return {k: strip(v) for k, v in node.items() if k != "description"}
        return [strip(v) for v in node] if isinstance(node, list) else node
    text = json.dumps(strip(te.TOOL["input_schema"]), separators=(",", ":"))
    assert "definitely_wrong" in text and "trap_boundary" in text
    assert not re.search(r"[&|<>^%\s]", text)


def _fake_claude(tmp_path, body: str):
    exe = tmp_path / "claude"
    exe.write_text("#!/usr/bin/env python3\nimport sys, json\nsys.stdin.read()\n" + body)
    exe.chmod(0o755)
    return exe


@pytest.mark.skipif(sys.platform == "win32", reason="the stand-in claude script cannot run on Windows; a real claude on PATH would be called instead")
def test_claude_cli_backend(tmp_path, monkeypatch):
    deck = {"cards": copy.deepcopy(PILOT["cards"][:3])}
    (tmp_path / "deck.json").write_text(json.dumps(deck))
    _fake_claude(tmp_path, f"print(json.dumps({{'type':'result','is_error':False,"
                           f"'structured_output':json.load(open(r'{tmp_path / 'deck.json'}')),"
                           f"'total_cost_usd':0.42}}))\n")
    monkeypatch.setenv("PATH", f"{tmp_path}:" + __import__("os").environ["PATH"])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-be-removed")
    monkeypatch.setattr(te, "TECH_DIR", tmp_path / "tech")
    monkeypatch.setattr(te, "LOG", tmp_path / "log.jsonl")
    out = te.run("R3.1", allow_partial=True, backend="claude-cli", model="opus")
    assert len(out["cards"]) == 3 and out["generated_by"] == "claude-code:opus"
    assert out["validation_issues"] == []
    assert json.loads((tmp_path / "log.jsonl").read_text().splitlines()[-1])["ok"] is True


@pytest.mark.skipif(sys.platform == "win32", reason="the stand-in claude script cannot run on Windows; a real claude on PATH would be called instead")
def test_claude_cli_usage_limit(tmp_path, monkeypatch):
    _fake_claude(tmp_path, "print(json.dumps({'type':'result','is_error':True,"
                           "'result':'Claude usage limit reached. Your limit resets at 5pm'}))\nsys.exit(1)\n")
    monkeypatch.setenv("PATH", f"{tmp_path}:" + __import__("os").environ["PATH"])
    monkeypatch.setattr(te, "LOG", tmp_path / "log.jsonl")
    with pytest.raises(te.UsageLimitReached):
        te.run("R3.1", allow_partial=True, backend="claude-cli")
