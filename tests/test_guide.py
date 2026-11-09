"""Study guide: book page lookup and the checks on generated explanations. No Claude call is made."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import book_view  # noqa: E402
from engine import foundations_builder as fb, guide_builder as gb  # noqa: E402


def test_printed_pages_map_to_the_right_pdf_pages():
    assert book_view.pdf_index("prepared", 93) == 100          # printed 93 is PDF page 101 in IB Prepared
    chapter = json.loads((Path(__file__).resolve().parents[1] / "data/books/companion/R1.1.json").read_text(encoding="utf-8"))
    assert book_view.pdf_index("companion", chapter["printed_pages"][0]) == chapter["pdf_pages"][0] - 1


def test_prepared_chapter_starts_on_its_own_first_page():
    chapter = fb.chapter("R1.1", fb.PREPARED)
    assert chapter["pages"][0]["printed"] == 93
    assert "1.1 Mea" in chapter["pages"][0]["text"]


def test_merge_pages_skips_junk():
    assert book_view.merge_pages(["395", "x", None], [393, "395"]) == [393, 395]


def test_guide_check_flags_gaps():
    ch = {"pages": [{"printed": "389", "text": ""}]}
    result = {"sections": [{"understanding": "R1.1.1", "explanation": "short", "companion_pages": ["389", "999"], "prepared_pages": []}]}
    issues = gb.check(result, {"R1.1.1", "R1.1.2"}, ch, None)
    assert "no section for R1.1.2" in issues
    assert any("999" in i for i in issues) and any("under 80 words" in i for i in issues)


def test_study_guide_page_navigates_without_errors():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=180)
    at.session_state["auth_user"] = {"id": "owner", "username": "owner", "name": "Owner", "owner": True, "onboarded": True}
    at.session_state["page"] = "Study guide"
    at.session_state["sg_topic"] = "R1.1"
    at.run()
    assert not at.exception
    at.button(key="sg_next").click().run()
    assert not at.exception and at.selectbox(key="sg_section").value == "R1.1.2"
    assert not at.button(key="sg_prev").disabled
    at.button(key="sg_prev").click().run()
    assert at.selectbox(key="sg_section").value == "R1.1.1"
