import re

ENGINE_CODE_PATTERNS = [
    # Toyota JZ
    (r'2JZ', lambda m: 2998),
    (r'1JZ', lambda m: 2492),
    # Toyota UR
    (r'1UR', lambda m: 4608),
    (r'2UR', lambda m: 4969),
    (r'3UR', lambda m: 5663),
    # Toyota GR
    (r'2GR', lambda m: 3456),
    (r'1GR', lambda m: 3956),
    # Toyota LR
    (r'1LR', lambda m: 4805),
    # Nissan VQ
    (r'VQ(\d{2})', lambda m: int(m.group(1)) * 100),
    # Nissan VR — specific VR6 before generic VR pattern
    (r'\bVR6\b', lambda m: 2792),
    (r'VR(\d{2})', lambda m: int(m.group(1)) * 100),
    # Nissan RB
    (r'RB(\d{2})', lambda m: int(m.group(1)) * 100),
    # Nissan SR
    (r'SR(\d{2})', lambda m: int(m.group(1)) * 100),
    # Nissan KA
    (r'KA(\d{2})', lambda m: int(m.group(1)) * 100),
    # Lamborghini — before generic patterns
    (r'V12.*6\.5', lambda m: 6498),
    (r'6\.5.*V12', lambda m: 6498),
    (r'V10.*5\.2', lambda m: 5204),
    (r'5\.2.*V10', lambda m: 5204),
    (r'L539', lambda m: 5204),
    (r'L411', lambda m: 6498),
    # BMW B series — MUST come before Honda B series
    (r'B38[A-Z0-9]', lambda m: 1499),
    (r'B46[A-Z0-9]', lambda m: 1998),
    (r'B47[A-Z0-9]', lambda m: 1995),
    (r'B48[A-Z0-9]', lambda m: 1998),
    (r'B57[A-Z0-9]', lambda m: 2993),
    (r'B58[A-Z0-9]', lambda m: 2998),
    (r'B68[A-Z0-9]', lambda m: 2998),
    # BMW S series — before Honda/Subaru patterns
    (r'S14[A-Z0-9]', lambda m: 1990),
    (r'S38[A-Z0-9]', lambda m: 3795),
    (r'S50[A-Z0-9]', lambda m: 3201),
    (r'S52[A-Z0-9]', lambda m: 3152),
    (r'S54[A-Z0-9]', lambda m: 3246),
    (r'S55[A-Z0-9]', lambda m: 2979),
    (r'S58[A-Z0-9]', lambda m: 2993),
    (r'S62[A-Z0-9]', lambda m: 4941),
    (r'S63[A-Z0-9]', lambda m: 4395),
    (r'S65[A-Z0-9]', lambda m: 3999),
    (r'S85[A-Z0-9]', lambda m: 5003),
    # BMW N series
    (r'N20[A-Z0-9]', lambda m: 1997),
    (r'N26[A-Z0-9]', lambda m: 1997),
    (r'N52[A-Z0-9]', lambda m: 2996),
    (r'N54[A-Z0-9]', lambda m: 2979),
    (r'N55[A-Z0-9]', lambda m: 2979),
    (r'N63[A-Z0-9]', lambda m: 4395),
    (r'N74[A-Z0-9]', lambda m: 6592),
    # BMW M series engine codes
    (r'M10[A-Z0-9]', lambda m: 1990),
    (r'M20[A-Z0-9]', lambda m: 2494),
    (r'M30[A-Z0-9]', lambda m: 3430),
    (r'M50[A-Z0-9]', lambda m: 2494),
    (r'M52[A-Z0-9]', lambda m: 2494),
    (r'M54[A-Z0-9]', lambda m: 2979),
    (r'M57[A-Z0-9]', lambda m: 2993),
    (r'M62[A-Z0-9]', lambda m: 4398),
    # Honda K series — after BMW
    (r'\bK(\d{2})[A-Za-z]?', lambda m: int(m.group(1)) * 100),
    # Honda B series — after BMW B series
    (r'\bB(\d{2})[A-Z]', lambda m: int(m.group(1)) * 100),
    # Honda F series
    (r'\bF(\d{2})[A-Z]', lambda m: int(m.group(1)) * 100),
    # Honda J series
    (r'\bJ(\d{2})[A-Z]', lambda m: int(m.group(1)) * 100),
    # Honda C series
    (r'\bC(\d{2})[A-Z]', lambda m: int(m.group(1)) * 100),
    # Subaru EJ
    (r'EJ(\d{2})', lambda m: int(m.group(1)) * 100),
    # Subaru FA
    (r'FA(\d{2})', lambda m: int(m.group(1)) * 100),
    # Mitsubishi
    (r'4G6[0-9]', lambda m: 1997),
    (r'4B11', lambda m: 1998),
    # GM LS — specific before generic
    (r'\bLS9\b', lambda m: 6162),
    (r'\bLS7\b', lambda m: 7011),
    (r'\bLS6\b', lambda m: 5665),
    (r'\bLS3\b', lambda m: 6162),
    (r'\bLS2\b', lambda m: 5967),
    (r'\bLS1\b', lambda m: 5733),
    # GM LT
    (r'\bLT6\b', lambda m: 5499),
    (r'\bLT5\b', lambda m: 6162),
    (r'\bLT4\b', lambda m: 6162),
    (r'\bLT2\b', lambda m: 6162),
    (r'\bLT1\b', lambda m: 6162),
    # Ford
    (r'5\.0.*[Cc]oyote', lambda m: 4951),
    (r'5\.2.*[Vv]oodoo', lambda m: 5163),
    (r'5\.8.*[Tt]rinity', lambda m: 5856),
    (r'7\.3.*[Gg]odzilla', lambda m: 7322),
    (r'Predator', lambda m: 5166),
    # Mercedes AMG
    (r'\bM156\b', lambda m: 6208),
    (r'\bM159\b', lambda m: 6208),
    (r'\bM177\b', lambda m: 3982),
    (r'\bM178\b', lambda m: 3982),
    (r'\bM158\b', lambda m: 5980),
    (r'\bM279\b', lambda m: 5513),
    # Mercedes OM diesel
    (r'\bOM642\b', lambda m: 2987),
    (r'\bOM651\b', lambda m: 2143),
    (r'\bOM646\b', lambda m: 2148),
    # Bugatti W16
    (r'\bWR16\b', lambda m: 7993),
    (r'\bW16\b', lambda m: 7993),
    # McLaren
    (r'\bM840T\b', lambda m: 3994),
    (r'\bM838T\b', lambda m: 3799),
    # Ferrari
    (r'\bF154\b', lambda m: 3902),
    (r'\bF136\b', lambda m: 4499),
    (r'\bF140\b', lambda m: 6262),
    # Audi
    (r'2\.5.*TFSI', lambda m: 2480),
    (r'4\.2.*FSI', lambda m: 4163),
    # Kia/Hyundai
    (r'Lambda II', lambda m: 3342),
    (r'Theta II', lambda m: 1998),
    (r'Smartstream.*2\.5', lambda m: 2497),
    # Dodge/Chrysler
    (r'Hellcat', lambda m: 6166),
    (r'Demon', lambda m: 6166),
    (r'Redeye', lambda m: 6166),
    # Generic displacement — LAST resort
    (r'^(\d+\.\d+)[Ll]', lambda m: round(float(m.group(1)) * 1000)),
]

def parse_displacement_from_code(engine_name):
    """
    Try to extract displacement in cc from engine code/name.
    Returns displacement in cc or None if not found.
    Patterns ordered most specific to least specific.
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
    test_engines = [
        "VQ37VHR", "VR38DETT", "RB26DETT", "SR20DET",
        "Honda K20A", "Honda B18C", "Honda F20C", "Honda J35Y",
        "Toyota 2JZ-GTE", "Toyota 1UR-FE", "Toyota 2GR-FE",
        "Subaru EJ257", "Subaru FA20",
        "Mitsubishi 4G63T", "Mitsubishi 4B11T",
        "GM LS3", "GM LS7", "GM LS9", "Cadillac LT4",
        "Ford 5.0 Coyote", "Ford 5.2 Voodoo", "Ford 7.3 Godzilla",
        "BMW S54B32", "BMW S65B40", "BMW B58B30", "BMW B48B20",
        "BMW N54B30", "BMW N55B30", "BMW S55B30", "BMW M62B44",
        "Mercedes M156", "Mercedes M159", "Mercedes M177", "Mercedes OM642",
        "Bugatti WR16", "McLaren M840T", "Ferrari F154 CB",
        "Lamborghini V12 6.5", "Kia Lambda II", "Kia Theta II",
        "Volkswagen VR6", "Nissan VQ35DE",
    ]
    print("Engine code displacement parsing test:")
    passed = 0
    failed = 0
    for engine in test_engines:
        cc = parse_displacement_from_code(engine)
        if cc:
            print(f"  ✅ {engine}: {cc}cc ({round(cc/1000, 1)}L)")
            passed += 1
        else:
            print(f"  ❌ {engine}: not parsed")
            failed += 1
    print(f"\nPassed: {passed}/{len(test_engines)}")
