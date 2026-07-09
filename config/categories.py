"""P3 Reactive Demand Index: category keyword maps + severity-weight rubric.

This file is the SINGLE source of truth for how incidents/recalls are
categorized and weighted. It is rendered verbatim into the website
explainer so viewers see exactly the same rules the code uses.
"""

# Exponent-relevant categories. A record is tagged with every category whose
# keywords match its text fields (case-insensitive substring match).
CATEGORY_KEYWORDS = {
    "battery_energy": [
        "lithium", "li-ion", "battery", "batteries", "thermal runaway",
        "energy storage", "power bank", "charger", "charging",
    ],
    "vehicle_ev_adas": [
        "electric vehicle", "hybrid", "autonomous", "self-driving",
        "adas", "autopilot", "fuel cell", "propulsion", "airbag",
        "unintended acceleration", "brake", "steering",
    ],
    "medical_device": [
        "implant", "pacemaker", "defibrillator", "insulin pump",
        "catheter", "surgical", "infusion", "ventilator", "prosthe",
        "stent", "hip replacement", "knee replacement",
    ],
    "consumer_electronics": [
        "smartphone", "laptop", "tablet", "wearable", "headphone",
        "e-cigarette", "vape", "hoverboard", "e-bike", "e-scooter",
        "scooter", "drone", "appliance", "heater", "dehumidifier",
    ],
    "fire_structural": [
        "fire hazard", "burn hazard", "overheat", "smoke", "explosion",
        "combust", "flammab", "carbon monoxide", "collapse",
    ],
}

# Severity weights. Rationale: events that involve deaths/serious injuries or
# the most serious recall class generate forensic investigation + litigation
# work; routine complaints are a weak individual signal, so they are
# down-weighted but still counted in aggregate.
SEVERITY_WEIGHTS = {
    "nhtsa_recall": 2.0,             # federally mandated vehicle recall
    "nhtsa_complaint": 0.25,         # single consumer complaint
    "nhtsa_complaint_injury": 1.0,   # complaint reporting injuries/deaths
    "cpsc_recall": 2.0,              # consumer product recall
    "cpsc_recall_injury": 3.0,       # recall citing injuries/deaths
    "fda_recall_class_1": 3.0,       # reasonable probability of death/serious harm
    "fda_recall_class_2": 2.0,
    "fda_recall_class_3": 1.0,
    "maude_death": 3.0,              # device adverse event: death
    "maude_injury": 1.0,             # device adverse event: injury
    "maude_malfunction": 0.25,       # device adverse event: malfunction only
}
