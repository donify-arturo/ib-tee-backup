"""
Syllabus sub-topic tags for Maths AI HL questions, from keyword rules. Offline, free and repeatable: no model calls.

Each part gets a primary sub-topic inside its revision paper's topic (the paper says which topic it is). Strong matches from other
topics become secondary tags, which is what makes a question "mixed" (it is used in the mixed-topic bank, where the tags stay hidden
until after the attempt). Rules are judgement; `data/maths/tag_overrides.json` ({"<question id>": ["1.12", ...]}) wins over them.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES = ROOT / "data" / "maths" / "tag_overrides.json"

R = lambda *pats: [(re.compile(p, re.I), w) for p, w in pats]

RULES: dict[str, list] = {
    # Topic 1
    "1.1": R((r"\d\s*×\s*10\s*\^?\s*[−-]?\s*k|a\s*×\s*10|standard form|scientific notation|1\s*≤\s*a\s*<\s*10", 3)),
    "1.2": R((r"arithmetic (sequence|series|progression)", 4), (r"common difference", 3), (r"\(n\s*[–−-]\s*1\)\s*d", 2)),
    "1.3": R((r"geometric (sequence|series|progression)", 4), (r"common ratio", 3)),
    "1.4": R((r"compound(ed)?|interest", 3), (r"depreciat|invest|inflation|per annum|savings account|nominal", 2)),
    "1.5": R((r"\blog|\bln\b|logarithm", 1), (r"exponent", 1)),
    "1.6": R((r"significant figure|decimal place", 2), (r"percentage error", 4), (r"upper bound|lower bound|estimate", 1)),
    "1.7": R((r"loan|mortgage|repay|monthly payment|annuit|amorti[sz]|instal", 4), (r"\bPMT\b", 2)),
    "1.8": R((r"system of (linear )?equations|simultaneous", 3), (r"polynomial|cubic equation|quadratic equation", 1)),
    "1.9": R((r"laws? of logarithms|log\s*\w*\s*\(|single logarithm|in terms of log", 3)),
    "1.10": R((r"rational exponent|fractional (index|exponent)", 3)),
    "1.11": R((r"infinite|sum to infinity|S\s*∞", 4)),
    "1.12": R((r"complex number", 3), (r"real part|imaginary|Re\(|Im\(|Argand|conjugate", 2)),
    "1.13": R((r"modulus|argument|polar form|exponential form|cis\b|\barg\b|re\s*iθ|e\s*iθ", 3)),
    "1.14": R((r"matri(x|ces)", 2), (r"determinant|inverse", 1)),
    "1.15": R((r"eigen(value|vector)|characteristic (polynomial|equation)|diagonali[sz]", 5)),
    # Topic 2
    "2.1": R((r"gradient|straight line|y\s*=\s*mx|perpendicular|parallel|y-intercept", 2)),
    "2.2": R((r"domain|range|inverse function|function notation", 2)),
    "2.3": R((r"sketch|graph of", 1)),
    "2.4": R((r"asymptote|intercept|vertex|zeros?\b|axis of symmetry|maximum point|minimum point", 2)),
    "2.5": R((r"model", 0.5), (r"varies (directly|inversely)|proportional|inverse variation|direct variation|quadratic|cubic", 2)),
    "2.6": R((r"reasonable|appropriate|validity|limitation|suitab", 1)),
    "2.7": R((r"composite|∘|f\s*\(\s*g\s*\(|g\s*\(\s*f\s*\(|inverse", 3)),
    "2.8": R((r"translat|stretch|reflect|transformation", 3)),
    "2.9": R((r"logistic|sinusoidal|piecewise|half-life|carrying capacity|exponential (model|decay|growth)|natural logarithmic model", 3)),
    "2.10": R((r"log-log|semi-log|lineari[sz]|ln\s*y\s*(against|=)|log\s*y\s*against|logarithmic scale", 4)),
    # Topic 3
    "3.1": R((r"volume|surface area|cuboid|cone|sphere|pyramid|cylinder|hemisphere|prism|midpoint", 2)),
    "3.2": R((r"sine rule|cosine rule|area of (the )?triangle", 3), (r"triangle|\bsin|\bcos|\btan", 1)),
    "3.3": R((r"bearing|elevation|depression|clinometer|north", 3)),
    "3.4": R((r"\barc\b|sector", 3)),
    "3.5": R((r"perpendicular bisector", 5)),
    "3.6": R((r"voronoi|toxic waste|nearest neighbour interpolation|\bcells?\b|\bsites?\b", 3)),
    "3.7": R((r"radian", 3)),
    "3.8": R((r"unit circle|trigonometric (equation|identit)|sin\s*2|cos\s*2|identity", 2)),
    "3.9": R((r"enlargement|rotation|reflection in|shear|(anti)?clockwise|transformation matri|image of", 3)),
    "3.10": R((r"vector|magnitude|position vector|unit vector", 1)),
    "3.11": R((r"vector equation|equation of (the )?line|parametric|\br\s*=", 3)),
    "3.12": R((r"velocity vector|position vector|constant velocity|direction of the vector|ship|boat|aircraft|drone|speedboat", 3)),
    "3.13": R((r"scalar product|dot product|vector product|cross product|angle between|perpendicular to both|component", 3)),
    "3.14": R((r"\bgraph\b|vertex|vertices|\bedges?\b|degree|complete graph|simple graph|\btree\b|directed|weighted", 1)),
    "3.15": R((r"adjacency matrix|walks? of length|number of walks", 5)),
    "3.16": R((r"kruskal|prim|spanning tree|chinese postman|travel+ing salesman|nearest neighbour algorithm|deleted vertex|eulerian|hamiltonian|route inspection", 5)),
    # Topic 4
    "4.1": R((r"sampl|bias|random sample|discrete|continuous|outlier|population", 1)),
    "4.2": R((r"histogram|cumulative frequency|box(-| and | & )whisker|box plot|frequency table", 3)),
    "4.3": R((r"\bmean\b|median|mode\b|standard deviation|variance|interquartile|quartile|\brange\b", 1)),
    "4.4": R((r"correlation|pearson|regression line|line of best fit|scatter|y on x", 3)),
    "4.5": R((r"probability|expected number|relative frequency|sample space", 1)),
    "4.6": R((r"venn|tree diagram|conditional|given that|independent|mutually exclusive", 2)),
    "4.7": R((r"random variable|probability distribution|E\s*\(\s*X\s*\)|expected value|fair game", 2)),
    "4.8": R((r"binomial|\bB\s*\(\s*\d", 4)),
    "4.9": R((r"normal(ly)? distribut|\bN\s*\(|inverse normal", 4)),
    "4.10": R((r"spearman|\brank", 4)),
    "4.11": R((r"hypothes|χ|chi|goodness of fit|t-test|p-value|significance level|expected frequenc|degrees of freedom|contingency", 2)),
    "4.12": R((r"questionnaire|survey|reliab|validity|test-retest|parallel forms|categori", 2)),
    "4.13": R((r"coefficient of determination|R\s*2\b|R²|sum of (the )?square(d)? residuals|least squares|regression (model|curve)|exponential regression|power regression", 3)),
    "4.14": R((r"unbiased|linear combination|Var\s*\(|E\s*\(\s*\d?\s*[A-Z]\s*[+−-]", 3)),
    "4.15": R((r"central limit|sample mean|X̄|sum of .{0,30}independent", 3)),
    "4.16": R((r"confidence interval", 5)),
    "4.17": R((r"poisson|Po\s*\(", 4)),
    "4.18": R((r"critical (region|value)|type (I|II|1|2) error|one-tailed|two-tailed|proportion", 3)),
    "4.19": R((r"markov|steady state|long[- ]term|transition matrix|initial state", 4)),
    # Topic 5 (no calculus revision papers in the folder; these catch calculus inside other topics)
    "5.1": R((r"derivative|rate of change|dy\s*/\s*dx|gradient function|\blimit\b", 2)),
    "5.2": R((r"increasing|decreasing", 2)),
    "5.3": R((r"differentiat|f\s*′|f\s*'\s*\(", 2)),
    "5.4": R((r"tangent|normal to the curve|equation of the normal", 3)),
    "5.5": R((r"integra|∫|area under", 2)),
    "5.6": R((r"stationary|turning point|local (maximum|minimum)", 3)),
    "5.7": R((r"optimi[sz]|maximi[sz]|minimi[sz]", 3)),
    "5.8": R((r"trapezoid|trapezium rule", 5)),
    "5.9": R((r"chain rule|product rule|quotient rule|related rate", 4)),
    "5.10": R((r"second derivative|concav|inflexion|inflection", 4)),
    "5.11": R((r"by substitution|indefinite integral|anti-?derivative", 3)),
    "5.12": R((r"volume of revolution|revolution|rotated (through|about)|enclosed by|bounded by", 3)),
    "5.13": R((r"displacement|acceleration|distance travelled|straight line with velocity|velocity,? v", 3)),
    "5.14": R((r"differential equation|separation of variables", 4)),
    "5.15": R((r"slope field", 5)),
    "5.16": R((r"euler'?s method|step (length|size)", 5)),
    "5.17": R((r"phase portrait|coupled|equilibrium point|saddle", 4)),
    "5.18": R((r"second[- ]order|d\s*2\s*x\s*/\s*dt\s*2", 4)),
}
OUTSIDE_RATIO = 1.5    # how much stronger an outside-topic match must be to become a part's primary tag
CROSS_MIN = 4          # score a sub-topic outside the paper's topic needs to become a secondary tag
TAG_METHOD = "keyword rules (ingest/maths_tagging.py)"


def topic_of(code: str) -> int:
    return int(code.split(".")[0])


def scores(q_text: str, ms_text: str) -> dict[str, float]:
    out = {}
    for code, rules in RULES.items():
        s = 0.0
        for pattern, weight in rules:
            s += 2 * weight * min(3, len(pattern.findall(q_text))) + weight * min(3, len(pattern.findall(ms_text)))
        if s:
            out[code] = s
    return out


def overrides() -> dict:
    try:
        return json.loads(OVERRIDES.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def tag_question(q: dict) -> dict:
    """{"subtopics": [primary first], "part_subtopics": {label: code}, "cross_topics": [...], "tag_method", "tag_confidence"}"""
    topic = q["topic"]
    totals: dict[str, float] = {}
    part_tags, confs = {}, []
    for p in q["parts"]:
        s = scores(p["q_text"], p["ms_text"])
        inside = sorted(((v, c) for c, v in s.items() if topic_of(c) == topic), reverse=True)
        anywhere = sorted(((v, c) for c, v in s.items()), reverse=True)
        for c, v in s.items():
            totals[c] = totals.get(c, 0) + v
        # The revision papers group by IB's topic filter, so a "Functions" paper also holds calculus. A part whose best match in
        # another topic is clearly stronger than anything in its own topic takes that sub-topic instead.
        if anywhere and topic_of(anywhere[0][1]) != topic and anywhere[0][0] >= CROSS_MIN and anywhere[0][0] >= OUTSIDE_RATIO * (inside[0][0] if inside else 0):
            inside = anywhere
        if inside:
            part_tags[p["label"]] = inside[0][1]
            second = inside[1][0] if len(inside) > 1 else 0
            confs.append(inside[0][0] / (inside[0][0] + second))
    stem = scores(q["parts"][0]["q_text"] if q["parts"] else "", "")
    for p in q["parts"]:          # a part with no keyword of its own inherits the question's best match
        if p["label"] not in part_tags:
            inside = sorted(((v, c) for c, v in {**totals, **stem}.items() if topic_of(c) == topic), reverse=True)
            if inside:
                part_tags[p["label"]] = inside[0][1]
    primary = list(dict.fromkeys(part_tags.values()))
    primary.sort(key=lambda c: -totals.get(c, 0))
    cross = sorted((c for c, v in totals.items() if topic_of(c) != topic and v >= CROSS_MIN and c not in primary), key=lambda c: -totals[c])[:3]
    forced = overrides().get(q["id"])
    if forced:
        return {"subtopics": forced, "part_subtopics": {p["label"]: forced[0] for p in q["parts"]},
                "cross_topics": sorted({topic_of(c) for c in forced} - {topic}), "tag_method": "hand override", "tag_confidence": 1.0}
    subs = primary + [c for c in cross if c not in primary]
    return {"subtopics": subs, "part_subtopics": part_tags, "cross_topics": sorted({topic_of(c) for c in subs} - {topic}),
            "tag_method": TAG_METHOD, "tag_confidence": round(sum(confs) / len(confs), 2) if confs else 0.0}
