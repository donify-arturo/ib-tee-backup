"""
Sub-topic classification for chunks that carry no syllabus header —
mainly past-paper questions (RevisionHub prints truncate the topic chip to
"Reac") and orphan markschemes.

Two classifiers share one interface:

* ClaudeClassifier  — production. Claude reads the question (+ its markscheme,
  which is the strongest signal) against all 165 understandings and returns
  a structured tool call. Results are cached on disk, keyed by text hash.
* LexicalClassifier — offline fallback / sanity baseline. TF-IDF cosine against
  each sub-topic's statements, skills and guidance plus curated keyword hints.

Both respect `scope` (e.g. ["R"] for a Reactivity-only question bank) and the
question level (SL questions can't be in AHL-only Reactivity 1.4).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import taxonomy
from .chunking import Chunk

CACHE = Path(__file__).resolve().parents[1] / "data" / "cache" / "classify.jsonl"

# Curated exam-vocabulary hints per sub-topic (what questions say, not what the guide says).
KEYWORDS: dict[str, str] = {
    "S1.1": "element compound mixture homogeneous heterogeneous filtration distillation chromatography state symbol kinetic molecular theory sublimation deposition kelvin",
    "S1.2": "proton neutron electron nucleon isotope nuclear symbol mass number atomic number relative atomic mass mass spectrum abundance",
    "S1.3": "emission spectrum line spectrum energy level sublevel orbital electron configuration aufbau hund pauli ionization energy convergence limit successive ionization",
    "S1.4": "mole avogadro molar mass empirical formula molecular formula concentration mol dm-3 solution volume dilution",
    "S1.5": "ideal gas pressure volume temperature molar volume pv=nrt real gas deviation boyle charles",
    "S2.1": "ionic bond lattice cation anion ionic compound formula electron transfer lattice enthalpy brittle conductivity molten",
    "S2.2": "covalent bond lewis formula vsepr molecular geometry bond angle polarity dipole electronegativity intermolecular forces hydrogen bonding london dispersion resonance sigma pi hybridization formal charge giant covalent",
    "S2.3": "metallic bond delocalized electrons sea of electrons malleable ductile alloy transition element metallic conductivity",
    "S2.4": "bonding triangle van arkel ketelaar alloy polymer addition polymer condensation polymer monomer biodegradable",
    "S3.1": "periodic table group period trend atomic radius ionic radius electronegativity electron affinity oxides acidic basic amphoteric transition element complex ion ligand colour oxidation state",
    "S3.2": "functional group homologous series iupac name isomer structural isomer stereoisomer cis trans optical chiral infrared ir spectrum nmr chemical shift mass spectrometry fragment index of hydrogen deficiency",
    "R1.1": "enthalpy change exothermic endothermic calorimetry q=mcδt specific heat capacity temperature rise surroundings system energy profile heat loss",
    "R1.2": "bond enthalpy bonds broken bonds formed hess's law hess cycle enthalpy of formation enthalpy of combustion born-haber lattice enthalpy electron affinity atomization",
    "R1.3": "combustion complete incomplete carbon monoxide soot fossil fuel coal crude oil natural gas biofuel ethanol specific energy energy density fuel cell carbon dioxide",
    "R1.4": "entropy disorder gibbs energy spontaneous spontaneity δg δs δh-tδs equilibrium constant gibbs temperature feasible",
    "R2.1": "stoichiometry mole ratio limiting reactant excess theoretical yield percentage yield atom economy balanced equation coefficients",
    "R2.2": "rate of reaction collision theory activation energy maxwell-boltzmann catalyst rate equation rate constant order half-life mechanism rate-determining step arrhenius",
    "R2.3": "equilibrium dynamic equilibrium le chatelier equilibrium constant kc reaction quotient position of equilibrium haber process yield",
    "R3.1": "acid base bronsted-lowry conjugate ph poh kw pka pkb kb strong acid weak acid neutralization titration buffer indicator salt hydrolysis lewis acid",
    "R3.2": "oxidation reduction redox oxidation state half-equation electrochemical cell voltaic galvanic electrolysis cell potential standard electrode potential reducing agent oxidizing agent",
    "R3.3": "radical homolytic fission free radical substitution halogenation chain initiation propagation termination uv light alkane",
    "R3.4": "nucleophile electrophile nucleophilic substitution sn1 sn2 electrophilic addition markovnikov curly arrow carbocation heterolytic fission electrophilic substitution benzene lewis acid coordination bond",
}

SKILL_RE = re.compile(
    r"\b(uncertaint|significant figure|hypothes|graph(?:s|ing)?\b|data (?:analysis|processing)|evaluat\w* (?:of )?(?:the )?"
    r"(?:method|procedure|investigation)|experimental design|command terms?|terminology|following instructions|"
    r"reading the question|units\b|precision|accuracy)", re.I)

_STOP = set("""a an the of in on to and or for by with is are be as at from that this which what when how
into its it their than then there these those such not only all any each more most other some can may
will would should could does do have has had been being was were also both between""".split())


def _tokens(text: str) -> list[str]:
    toks = re.findall(r"[a-zδ][a-z0-9δ'\-]+", text.lower())
    out = []
    for t in toks:
        if t in _STOP or len(t) < 3:
            continue
        for suf in ("ization", "isation", "ations", "ation", "ities", "ness", "ing", "ies", "es", "s"):
            if t.endswith(suf) and len(t) - len(suf) >= 4:
                t = t[: -len(suf)]
                break
        out.append(t)
    return out


def _allowed(scope: list[str] | None, level: str | None) -> list[str]:
    subs = sorted(taxonomy.valid_sub_topics())
    if scope:
        subs = [s for s in subs if any(s.startswith(p) for p in scope)]
    if level == "SL":
        hl_only = {s["code"] for s in taxonomy.load_syllabus()["sub_topics"] if s.get("hl_only")}
        subs = [s for s in subs if s not in hl_only]
    return subs


def _text_for(chunk: Chunk, by_id: dict[str, Chunk]) -> str:
    """Question text + linked markscheme text (markschemes name the chemistry explicitly)."""
    parts = [chunk.text]
    for lid in chunk.metadata.get("linked_ids", [])[:3]:
        other = by_id.get(lid)
        # a bare answer letter from a scanned book adds nothing, and must not shift a library question's tag
        if other is not None and (chunk.metadata.get("scan_book") or not other.metadata.get("scan_book")):
            parts.append(other.text)
    return "\n\n".join(parts)[:6000]


class LexicalClassifier:
    name = "classifier_lexical"

    def __init__(self):
        syl = taxonomy.load_syllabus()
        docs: dict[str, list[str]] = {}
        for s in syl["sub_topics"]:
            docs[s["code"]] = _tokens(f"{s['title']} {s.get('guiding_question') or ''}")
        for u in syl["understandings"].values():
            docs[u["sub_topic"]] += _tokens(" ".join([u["statement"], *u["skills"], *u["guidance"]]))
        for code, kw in KEYWORDS.items():
            docs[code] += _tokens(kw) * 3            # weight curated exam vocabulary
        df = Counter()
        for toks in docs.values():
            df.update(set(toks))
        n = len(docs)
        self.idf = {t: math.log((n + 1) / (c + 0.5)) for t, c in df.items()}
        self.vecs = {code: self._vec(toks) for code, toks in docs.items()}

    def _vec(self, toks):
        tf = Counter(toks)
        v = {t: (1 + math.log(c)) * self.idf.get(t, 0.0) for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    def classify(self, text: str, scope=None, level=None, min_tokens: int = 5, min_sim: float = 0.08) -> dict:
        toks = _tokens(text)
        if len(toks) < min_tokens:
            return {"sub_topic": None, "understanding": None, "secondary": [], "confidence": 0.0, "legacy_only": False}
        qv = self._vec(toks)
        scores = sorted(((sum(w * self.vecs[c].get(t, 0.0) for t, w in qv.items()), c)
                         for c in _allowed(scope, level)), reverse=True)
        best, second = scores[0], scores[1] if len(scores) > 1 else (0.0, None)
        if best[0] < min_sim:                      # nothing in the syllabus genuinely matches
            return {"sub_topic": None, "understanding": None, "secondary": [], "confidence": 0.0, "legacy_only": False}
        margin = best[0] - second[0]
        conf = round(min(0.95, 0.30 + 1.5 * best[0] + 2.0 * margin), 2)
        secondary = [c for s, c in scores[1:3] if s >= best[0] * 0.8]
        return {"sub_topic": best[1] if best[0] > 0 else None, "understanding": None,
                "secondary": secondary, "confidence": conf, "legacy_only": False}


class ClaudeClassifier:
    """Structured classification with Claude via tool use + prompt caching."""
    name = "classifier_llm"

    def __init__(self, model: str | None = None, max_workers: int = 4):
        import anthropic
        self.client = anthropic.Anthropic()          # ANTHROPIC_API_KEY
        self.model = model or os.environ.get("IBTEE_CLASSIFIER_MODEL", "claude-haiku-5-5")
        self.max_workers = max_workers
        syl = taxonomy.load_syllabus()
        lines = []
        for s in syl["sub_topics"]:
            lines.append(f"\n## {s['code']} {s['title']}{' (HL only)' if s.get('hl_only') else ''}")
            for code in s["understandings"]:
                u = syl["understandings"][code]
                lines.append(f"- {code} [{u['level']}] {u['statement']}")
        self.system = [
            {"type": "text", "text": (
                "You classify IB Diploma Chemistry exam questions and markschemes onto the 2025 syllabus "
                "(first assessment 2025). Older questions (2000–2024) were written for the previous syllabus: "
                "map them to the 2025 understanding that now covers the same chemistry. If the chemistry is no "
                "longer in the 2025 syllabus at all (e.g. a removed option topic), set legacy_only=true and give "
                "the closest sub-topic. Pick the PRIMARY sub-topic the marks depend on; list others under secondary.")},
            {"type": "text", "text": "2025 syllabus understandings:\n" + "\n".join(lines),
             "cache_control": {"type": "ephemeral"}},
        ]

    def _tool(self, allowed: list[str]) -> dict:
        und = sorted(c for c in taxonomy.valid_understandings() if c.rsplit(".", 1)[0] in allowed)
        return {
            "name": "assign_syllabus_codes",
            "description": "Record the syllabus classification of this question.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "sub_topic": {"type": "string", "enum": allowed},
                    "understanding": {"type": "string", "enum": und},
                    "secondary": {"type": "array", "items": {"type": "string", "enum": allowed}, "maxItems": 3},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "legacy_only": {"type": "boolean"},
                },
                "required": ["sub_topic", "understanding", "confidence", "legacy_only"],
            },
        }

    def classify(self, text: str, scope=None, level=None, min_tokens: int = 0, min_sim: float = 0.0) -> dict:
        allowed = _allowed(scope, level)
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=400,
            system=self.system,
            tools=[self._tool(allowed)],
            tool_choice={"type": "tool", "name": "assign_syllabus_codes"},
            messages=[{"role": "user", "content": f"Classify this item.\n\n<item>\n{text}\n</item>"}],
        )
        block = next(b for b in resp.content if b.type == "tool_use")
        out = dict(block.input)
        out.setdefault("secondary", [])
        return out


def _load_cache() -> dict:
    if not CACHE.exists():
        return {}
    d = {}
    for line in CACHE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            d[r["key"]] = r["result"]
    return d


def classify_chunks(chunks: list[Chunk], classifier, only_untagged: bool = True) -> int:
    """Classify question/markscheme units in place. One call per question_ref, shared by its parts."""
    by_id = {c.id: c for c in chunks}
    groups: dict[str, list[Chunk]] = {}
    for c in chunks:
        m = c.metadata
        if only_untagged and m.get("sub_topic"):
            continue
        if m["source_type"] == "markscheme" and m.get("has_question"):
            continue                                    # inherits from its question (link.propagate_tags)
        body = c.text.split("\n", 1)[1] if "\n" in c.text else c.text
        if m["source_type"] == "markscheme" and len(re.findall(r"[A-Za-z]{3,}", body)) < 4:
            # e.g. an MCQ key ("B") whose question isn't in the library: nothing to classify
            m.update(tag_method="unclassifiable", orphan_answer_key=True)
            continue
        if m["source_type"] not in {"past_paper", "markscheme", "textbook", "textbook_answers",
                                    "examiner_report", "examiner_finding"}:
            continue
        if m["source_type"] == "examiner_report" and (m.get("has_question") or m.get("has_markscheme")):
            continue                                    # inherits from what it discusses (propagate_report_tags)
        if m.get("option_question") or (m["source_type"] == "examiner_finding"
                                         and re.search(r"\bOption\s+[A-H]\b", c.text)):
            m.update(tag_method="legacy_option")        # old option papers (A–H): no 2025 home
            continue
        if m["source_type"] == "examiner_finding" and SKILL_RE.search(c.text.split(": ", 1)[-1]):
            m.update(tag_method="cross_cutting_skill")  # Tools / Inquiry skills, not a sub-topic
            continue
        key = m.get("classify_group") or m.get("question_ref") or c.id
        groups.setdefault(f"{m['doc_id']}::{key}", []).append(c)

    cache = _load_cache()
    CACHE.parent.mkdir(parents=True, exist_ok=True)

    def work(item):
        _key, members = item
        head = members[0]
        text = "\n".join(_text_for(c, by_id) if i == 0 else c.text for i, c in enumerate(members))[:8000]
        scope = head.metadata.get("scope") or None
        level = head.metadata.get("level") if head.metadata.get("level") in {"SL", "HL"} else None
        if head.metadata["source_type"] in {"examiner_report", "examiner_finding"}:
            level = None                                # old-syllabus HL/SL split ≠ 2025 AHL split
        finding = head.metadata["source_type"] == "examiner_finding"
        kw = dict(min_tokens=2 if finding else 5, min_sim=0.10 if finding else 0.08)
        if classifier.name == "classifier_lexical":           # cheap and deterministic: never cached
            return members, classifier.classify(text, scope=scope, level=level, **kw), None
        ck = hashlib.sha1(f"{classifier.name}|{getattr(classifier, 'model', '')}|{scope}|{level}|{kw}|{text}".encode()).hexdigest()
        if ck in cache:
            return members, cache[ck], None
        res = classifier.classify(text, scope=scope, level=level, **kw)
        return members, res, ck

    items = list(groups.items())
    workers = getattr(classifier, "max_workers", 1)
    results = list(ThreadPoolExecutor(workers).map(work, items)) if workers > 1 else [work(i) for i in items]

    n = 0
    with CACHE.open("a", encoding="utf-8") as f:
        for members, res, ck in results:
            if ck:
                f.write(json.dumps({"key": ck, "result": res}) + "\n")
            sub = res.get("sub_topic")
            if not sub:
                continue
            und = res.get("understanding")
            if und and not und.startswith(sub + "."):
                und = None
            for c in members:
                c.metadata.update(
                    sub_topic=sub, understanding=und, theme=sub.split(".")[0],
                    sub_topics_all=[sub, *[s for s in res.get("secondary", []) if s != sub]],
                    tag_method=classifier.name, tag_confidence=res.get("confidence"),
                    legacy_only=res.get("legacy_only", False),
                )
                n += 1
    return n


def get_classifier(name: str):
    if name == "claude":
        return ClaudeClassifier()
    if name == "lexical":
        return LexicalClassifier()
    raise ValueError(name)
