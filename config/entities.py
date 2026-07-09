"""Canonical Exponent entity name variants — single source of truth."""

# Current corporate names (1998-present)
EXPONENT_NAMES = [
    "Exponent, Inc.",
    "Exponent Inc.",
    "Exponent Inc",
    "Exponent, Incorporated",
]

# Pre-1998 name (founded 1967 as Failure Analysis Associates; holding co "The Failure Group")
LEGACY_NAMES = [
    "Failure Analysis Associates",
    "The Failure Group",
]

ALL_NAMES = EXPONENT_NAMES + LEGACY_NAMES

# Context words that indicate an expert-witness usage of "Exponent" in legal text
EXPERT_CONTEXT_TERMS = [
    "expert", "witness", "testimony", "testified", "retained",
    "deposition", "report", "Daubert", "Rule 702",
]

OPENALEX_INSTITUTION_ID = "I13383945"
ROR_ID = "https://ror.org/04wzb3z02"

EXPO_TICKER = "EXPO"
