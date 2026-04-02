import re

# Engine code displacement patterns
# Format: regex pattern -> displacement in cc
ENGINE_CODE_PATTERNS = [
    # Nissan VQ series: VQ37 = 3.7L, VQ35 = 3.5L
    (r'VQ(\d{2})', lambda m: int(m.group(1)) * 100),
    # Nissan VR series: VR38 = 3.8L
    (r'VR(\d{2})', lambda m: int(m.group(1)) * 100),
    # Nissan RB series: RB26 = 2.6L
    (r'RB(\d{2})', lambda m: int(m.group(1)) * 100),
    # Nissan SR series: SR20 = 2.0L
    (r'SR(\d{2})', lambda m: int(m.group(1)) * 100),
    # Honda K series: K20 = 2.0L, K24 = 2.4L
    (r'\bK(\d{2})\b', lambda m: int(m.group(1)) * 100),
    # Honda B series: B18 = 1.8L, B16 = 1.6L
    (r'\bB(\d{2})[A-Z]', lambda m: int(m.group(1)) * 100),
    # Honda F series: F20 = 2.0L
    (r'\bF(\d{2})[A-Z]', lambda m: int(m.group(1)) * 100),
    # Toyota JZ: 2JZ = 3.0L, 1JZ = 2.5L (JZ series are all ~3.0 or 2.5)
    (r'2JZ', lambda m: 2998),
    (r'1JZ', lambda m: 2492),
    # Toyota UR: 1UR = 4.6L, 2UR = 5.0L, 3UR = 5.7L
    (r'1UR', lambda m: 4608),
    (r'2UR', lambda m: 4969),
    (r'3UR', lambda m: 5663),
    # Subaru EJ: EJ20 = 2.0L, EJ25 = 2.5L
    (r'EJ(\d{2})', lambda m: int(m.group(1)) * 100),
    # Subaru FA: FA20 = 2.0L
    (r'FA(\d{2})', lambda m: int(m.group(1)) * 100),
    # Mitsubishi 4G: 4G63 = 2.0L (63 = 1997cc), 4B11 = 2.0L
    (r'4G6[0-9]', lambda m: 1997),
    (r'4B11', lambda m: 1998),
    # GM LS series: LS3 = 6.2L, LS7 = 7.0L, LS9 = 6.2L
    (r'\bLS3\b', lambda m: 6162),
    (r'\bLS7\b', lambda m: 7011),
    (r'\bLS9\b', lambda m: 6162),
    (r'\bLS6\b', lambda m: 5665),
    (r'\bLS2\b', lambda m: 5967),
    (r'\bLS1\b', lambda m: 5733),
    # GM LT series: LT1 = 6.2L, LT4 = 6.2L, LT6 = 5.5L
    (r'\bLT4\b', lambda m: 6162),
    (r'\bLT6\b', lambda m: 5499),
    (r'\bLT1\b', lambda m: 6162),
    # Ford Modular: 5.0 Coyote, 5.2 Voodoo, 5.8 Trinity
    (r'5\.0.*[Cc]oyote', lambda m: 4951),
    (r'5\.2.*[Vv]oodoo', lambda m: 5163),
    (r'5\.8.*[Tt]rinity', lambda m: 5856),
    # BMW S series: S54 = 3.2L, S65 = 4.0L, S55 = 3.0L, S58 = 3.0L
    (r'\bS54\b', lambda m: 3246),
    (r'\bS65\b', lambda m: 3999),
    (r'\bS55\b', lambda m: 2979),
    (r'\bS58\b', lambda m: 2993),
    (r'\bS63\b', lambda m: 4395),
    # BMW N series: N54 = 3.0L, N55 = 3.0L, N63 = 4.4L
    (r'\bN54\b', lambda m: 2979),
    (r'\bN55\b', lambda m: 2979),
    (r'\bN63\b', lambda m: 4395),
    (r'\bN52\b', lambda m: 2996),
    # BMW B series: B48 = 2.0L, B58 = 3.0L
    (r'\bB48\b', lambda m: 1998),
    (r'\bB58\b', lambda m: 2998),
    # Mercedes AMG: M156 = 6.2L, M159 = 6.2L, M177 = 4.0L
    (r'\bM156\b', lambda m: 6208),
    (r'\bM159\b', lambda m: 6208),
    (r'\bM177\b', lambda m: 3982),
    (r'\bM178\b', lambda m: 3982),
    # Mercedes OM diesel: OM642 = 3.0L, OM651 = 2.1L
    (r'\bOM642\b', lambda m: 2987),
    (r'\bOM651\b', lambda m: 2143),
    # Bugatti W16
    (r'\bW16\b', lambda m: 7993),
    (r'\bWR16\b', lambda m: 7993),
    # McLaren M840T = 4.0L
    (r'\bM840T\b', lambda m: 3994),
    # Audi: 2.5 TFSI = 2480cc
    (r'2\.5.*TFSI', lambda m: 2480),
    # Ferrari F154 = 3.9L twin turbo V8
    (r'F154', lambda m: 3902),
    # Generic displacement pattern: "3.7L" or "3700cc" in engine name
    (r'(\d+\.\d+)\s*[Ll]', lambda m: round(float(m.group(1)) * 1000)),
]

def parse_displacement_from_code(engine_name):
    """
    Try to extract displacement in cc from engine code/name.
    Returns displacement in cc or None if not found.
    """
    for pattern, extractor in ENGINE_CODE_PATTERNS:
        match = re.search(pattern, engine_name)
        if match:
            try:
                cc = extractor(match)
                if 50 < cc < 20000:
                    return cc
            except:
                continue
    return None

if __name__ == "__main__":
    # Test it
    test_engines = [
        "VQ37VHR", "VR38DETT", "RB26DETT", "SR20DET",
        "Honda K20A", "Honda B18C", "Toyota 2JZ-GTE",
        "Subaru EJ257", "GM LS3", "Ford 5.0 Coyote",
        "BMW S54B32", "BMW B58B30", "Mercedes M156",
        "Bugatti WR16", "McLaren M840T", "Ferrari F154"
    ]
    print("Engine code displacement parsing test:")
    for engine in test_engines:
        cc = parse_displacement_from_code(engine)
        print(f"  {engine}: {cc}cc ({round(cc/1000, 1)}L)" if cc else f"  {engine}: not parsed")
