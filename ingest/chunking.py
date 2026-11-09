"""Chunk record + size-aware splitting helpers shared by all splitters."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

MAX_CHARS = 2400      # ≈ 500–600 tokens: one coherent idea per chunk
MIN_CHARS = 300       # merge fragments smaller than this into the neighbour


@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {"id": self.id, "text": self.text, "metadata": self.metadata}


def make_id(*parts) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


# Metadata every chunk carries (Part 2 indexes these). Splitters fill what they know;
# link/classify stages fill the rest.
BASE_METADATA = {
    "sub_topic": None,           # "R1.2"
    "understanding": None,       # "R1.2.3"
    "theme": None,               # "R1"
    "sub_topics_all": [],        # every sub-topic the chunk touches (primary first)
    "source_type": None,         # syllabus | textbook | textbook_answers | past_paper | markscheme | data_booklet
    "origin": None,
    "doc_id": None,
    "page_start": None,
    "page_end": None,
    "printed_page": None,
    "level": None,               # SL | HL | AHL (syllabus/textbook) — question level for papers
    "question_ref": None,        # canonical QRef key
    "question_part": None,       # "a.i" when a long question/markscheme was split by part
    "session": None,
    "paper": None,
    "variant": None,
    "syllabus_era": None,        # "2025" | "legacy"
    "question_type": None,       # mcq | structured
    "difficulty": None,
    "has_markscheme": None,
    "linked_ids": [],            # question <-> markscheme, textbook <-> answers
    "cross_links": [],           # sub-topics named in linking questions / "see Structure 2.2"
    "data_booklet_sections": [],
    "tag_method": None,          # regex_header | running_header | ref_link | data_booklet_map | syllabus | classifier_llm | classifier_lexical
    "tag_confidence": None,
}


def new_meta(**kw) -> dict:
    m = {k: (list(v) if isinstance(v, list) else v) for k, v in BASE_METADATA.items()}
    m.update(kw)
    if m.get("sub_topic") and not m.get("theme"):
        m["theme"] = m["sub_topic"].split(".")[0]
    if m.get("sub_topic") and not m.get("sub_topics_all"):
        m["sub_topics_all"] = [m["sub_topic"]]
    return m


def split_long(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """Split on markdown headings, then blank lines, then lines; never mid-line.
    Tables (lines starting with '|') and [FIGURE: …] blocks are kept whole where possible."""
    if len(text) <= max_chars:
        return [text]
    blocks = re.split(r"\n(?=#{2,4} )", text)
    if len(blocks) == 1:
        blocks = re.split(r"\n\s*\n", text)
    if len(blocks) == 1:
        blocks = text.split("\n")
    out, cur = [], ""
    for b in blocks:
        if len(b) > max_chars and b is not text:
            if cur:
                out.append(cur); cur = ""
            out.extend(split_long(b, max_chars) if len(b) < len(text) else _hard_split(b, max_chars))
            continue
        if len(cur) + len(b) + 1 > max_chars and cur:
            out.append(cur); cur = b
        else:
            cur = f"{cur}\n{b}" if cur else b
    if cur:
        out.append(cur)
    # merge tiny tail fragments
    merged: list[str] = []
    for piece in out:
        if merged and len(piece) < MIN_CHARS and len(merged[-1]) + len(piece) < max_chars * 1.25:
            merged[-1] += "\n" + piece
        else:
            merged.append(piece)
    return [m.strip() for m in merged if m.strip()]


def _hard_split(text: str, max_chars: int) -> list[str]:
    lines, out, cur = text.split("\n"), [], ""
    for ln in lines:
        if len(cur) + len(ln) + 1 > max_chars and cur:
            out.append(cur); cur = ln
        else:
            cur = f"{cur}\n{ln}" if cur else ln
    if cur:
        out.append(cur)
    return out
