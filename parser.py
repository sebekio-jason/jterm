import re
# build name, install name, fwp name
AMPLIFIER_REGISTRY = {
    "AM-S20H-2":    ("ams20h2", "f8-am-s20h-2", ""),
    "AM-S20L":      ("ams20l", "f8-am-s20l", ""),
    "AM-S20L-2":    ("ams20l2", "f8-am-s20l-2", ""),
    "AM-S22H-L":    ("ams22hl", "f8-am-s22h-l", "edfa-lpc"),
    "AM-S22L-L":    ("ams22ll", "f8-am-s22l-l", "edfa-lpc"),
    "AM-S23H":      ("ams23h", "f8-am-s23h", ""),
    "AM-S23L":      ("ams23l", "f8-am-s23l", ""),
    "AM-S23LR15":   ("ams23lr15", "f8-am-s23lr15", ""),
    "AM-S23L-TD":   ("ams23ltd", "f8-am-s23l-td", ""),
    "AM-S24L-TD":   ("ams24ltd", "f8-am-s24l-td", ""),
    "AM-2S23-M":    ("am2s23m", "f8-am-2s23-m", "edfa-sm_dual"),
    "AM-2S20L":     ("am2s20l", "f8-am-2s20l", ""),
    "FD-40D24L-TD": ("fd40d24ltd", "f8-fd-40d24l-td", ""),
    "OT-8ES18-MO":  ("ot8es18mo", "f8-ot-8es18-mo", ""),
    "AM-R15-CL": ("amr15cl", "f8-am-r15-cl", "raman-lpc"),
}


CARD_ROW_REGEX = re.compile(r'^card\s+(\S+)\s+(\S+)\s+(\S+|\-\-)\s+(\S+|\-\-)\s+(\S+|\-\-)\s+(.+)$',re.MULTILINE)
def parse_ecm_cards(output, ip) -> list:
    cards = []
    for match in CARD_ROW_REGEX.finditer(output):
        name_raw = match[2].strip()
        if not name_raw.lower().startswith("am") and not name_raw.lower().startswith('fd'):
            continue
        name_clean = name_raw.upper()
        if not any(name_clean.startswith(valid) for valid in AMPLIFIER_REGISTRY.keys()):
            continue

        cards.append({
            'name': name_clean,
            'slot': match[1].strip().split("/")[-1],
            'part_number': match[3].strip(),
            'admin': match[4].strip(),
            'status': match[5].strip(),
            'description': match[6].strip(),
        })
    return cards