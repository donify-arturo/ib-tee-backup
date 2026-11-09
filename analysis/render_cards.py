"""Render a technique deck (data/techniques/<sub>.json) as Markdown for review.

    python -m analysis.render_cards R3.1      # → data/techniques/R3.1.md
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = {
    "1_context": "1 · Syllabus-to-exam bridge", "2_markscheme_logic": "2 · Markscheme logic & trigger phrases",
    "3_novel_application": "3 · Novel application", "4_command_terms": "4 · Command terms & score mechanics",
    "5_time_efficiency": "5 · Time efficiency", "6_data_booklet": "6 · Data booklet", "7_elimination": "7 · Instant elimination",
}


STEP_ORDER = ["4_command_terms", "1_context", "3_novel_application", "7_elimination", "6_data_booklet", "5_time_efficiency",
              "2_markscheme_logic"]


def _val(v):
    if isinstance(v, list):
        return "\n".join(f"  - {x}" for x in v) if v else "  - —"
    return f" {v}"


def render(deck: dict) -> str:
    out = [f"# {deck['sub_topic']} {deck['title']} — technique deck", ""]
    eb = deck.get("evidence_base", {})
    if eb:
        out += ["Evidence: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in eb.items()), ""]
    for x in deck.get("cross_links", []):
        out.append(f"- Cross-link → **{x['sub_topic']}**: {x['note']}")
    for card in sorted(deck["cards"], key=lambda c: (c["priority"], c["card_id"])):
        tick = "x" if card.get("status", {}).get("mastered") else " "
        out += ["", f"## [{tick}] {card['card_id']} · {card['title']}",
                f"Priority {card['priority']} · {', '.join(card['understandings'])} · {card['difficulty_signal']}", ""]
        wt = card.get("walkthrough")
        if wt:
            out += [f"**Step by step** (`{wt['question_ref']}`, {wt['marks']} marks)", "", wt["question"], ""]
            for i, key in enumerate(STEP_ORDER, start=1):
                s = wt["steps"].get(key)
                if not s:
                    continue
                out.append(f"{i}. **{LABELS[key]}** (about {s['seconds']} s): {s['short']}")
                for field, v in s.items():
                    if field in {"short", "why", "avoid", "seconds"}:
                        continue
                    if field == "definitely_wrong":
                        v = [f"{x['target']}: {x['rule']}" for x in v]
                    out.append(f"   - *{field.replace('_', ' ')}*: " + ("; ".join(map(str, v)) if isinstance(v, list) else str(v)))
                out.append(f"   - *avoid*: {s['avoid']}")
                out.append(f"   - *why*: {s['why']}")
            out += ["", f"**Answer:** {wt['answer']} ({wt.get('key_idea', '')})"]
            if wt.get("try_next"):
                out.append("**Try next:** " + ", ".join(f"`{r}`" for r in wt["try_next"]))
            out.append("")
        for key, label in LABELS.items():
            out.append(f"**{label}**")
            for field, v in card["pillars"][key].items():
                out.append(f"- *{field.replace('_', ' ')}*:{_val(v)}")
            out.append("")
        out.append("**Evidence**")
        out += [f"- `{e['ref']}` ({e['kind']}) — {e['note']}" for e in card["evidence"]]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    sub = sys.argv[1]
    deck = json.loads((ROOT / "data" / "techniques" / f"{sub}.json").read_text(encoding="utf-8"))
    path = ROOT / "data" / "techniques" / f"{sub}.md"
    path.write_text(render(deck), encoding="utf-8")
    print(f"wrote {path}")
