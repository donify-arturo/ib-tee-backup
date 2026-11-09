"""
Data booklet section → syllabus sub-topics (2025 Chemistry data booklet, 24 sections).

Hand-curated mapping: the booklet itself carries no syllabus codes, and Pillar 6
("Data Booklet Pattern Hacks") needs to know which tables are fair game for
each sub-topic. Keep this list in sync if the booklet is updated.
"""
DATA_BOOKLET_SECTIONS: dict[int, dict] = {
    1:  {"title": "Some relevant equations",
         "sub_topics": ["S1.3", "S1.4", "S1.5", "R1.1", "R1.4", "R2.2", "R2.3", "R3.1", "R3.2"]},
    2:  {"title": "Physical constants", "sub_topics": ["S1.3", "S1.4", "S1.5", "R1.4", "R2.2", "R3.2"]},
    3:  {"title": "Metric (SI) multipliers", "sub_topics": ["S1.4"]},
    4:  {"title": "Unit conversions and standard conditions", "sub_topics": ["S1.4", "S1.5", "R1.1"]},
    5:  {"title": "The electromagnetic spectrum", "sub_topics": ["S1.3", "S3.2"]},
    6:  {"title": "Names of the elements", "sub_topics": ["S3.1"]},
    7:  {"title": "The periodic table", "sub_topics": ["S1.2", "S1.3", "S1.4", "S3.1"]},
    8:  {"title": "Melting points and boiling points of the elements", "sub_topics": ["S2.3", "S3.1"]},
    9:  {"title": "First ionization energy, electron affinity and electronegativity",
         "sub_topics": ["S1.3", "S2.1", "S2.2", "S2.4", "S3.1", "R1.2"]},
    10: {"title": "Atomic and ionic radii of the elements", "sub_topics": ["S2.1", "S3.1"]},
    11: {"title": "Covalent or average covalent bond lengths", "sub_topics": ["S2.2"]},
    12: {"title": "Bond enthalpies or average bond enthalpies at 298.15 K", "sub_topics": ["R1.2", "S2.2"]},
    13: {"title": "Thermodynamic data (selected compounds)", "sub_topics": ["R1.2", "R1.4"]},
    14: {"title": "Enthalpies of combustion", "sub_topics": ["R1.2", "R1.3"]},
    15: {"title": "Colour wheel with wavelengths of the visible spectrum", "sub_topics": ["S3.1"]},
    16: {"title": "Lattice enthalpies at 298.15 K (experimental values)", "sub_topics": ["S2.1", "R1.2"]},
    17: {"title": "Triangular bonding diagram (van Arkel–Ketelaar triangle)", "sub_topics": ["S2.4"]},
    18: {"title": "Acid–base indicators", "sub_topics": ["R3.1"]},
    19: {"title": "Standard reduction potentials at 298.15 K", "sub_topics": ["R3.2"]},
    20: {"title": "Infrared data", "sub_topics": ["S3.2"]},
    21: {"title": "1H NMR data", "sub_topics": ["S3.2"]},
    22: {"title": "Mass spectral fragments lost", "sub_topics": ["S3.2"]},
    23: {"title": "Uncertainties", "sub_topics": []},       # Tools (skills) — cross-cutting
    24: {"title": "References", "sub_topics": []},
}
