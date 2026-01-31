#!/usr/bin/env python3
"""Update scenarios with pre-defined persona mappings.

Each scenario gets a 'personas' field with historical figures for both sides.
This ensures consistency between scenario themes and available AI opponents.

Run once to update all scenarios:
    uv run python scripts/update_scenario_personas.py
"""

import json
from pathlib import Path

# Mapping of scenario ID patterns to personas
# Each entry defines the historical figures appropriate for sides A and B
PERSONA_MAPPINGS = {
    "cuban_missile_crisis": {
        "side_a": {
            "persona": "nixon",
            "role_name": "American President",
            "role_description": "Leader of the United States, balancing domestic pressure with the risk of nuclear war.",
        },
        "side_b": {
            "persona": "khrushchev",
            "role_name": "Soviet Premier",
            "role_description": "Leader of the Soviet Union, defending Communist interests while avoiding catastrophe.",
        },
    },
    "berlin_blockade": {
        "side_a": {
            "persona": "nixon",
            "role_name": "Western Allied Commander",
            "role_description": "Representative of Western powers, defending Berlin's freedom.",
        },
        "side_b": {
            "persona": "khrushchev",
            "role_name": "Soviet Leadership",
            "role_description": "Soviet leadership seeking to consolidate control over Eastern Europe.",
        },
    },
    "taiwan_strait": {
        "side_a": {
            "persona": "kissinger",
            "role_name": "American Diplomat",
            "role_description": "US diplomatic representative managing the delicate Taiwan situation.",
        },
        "side_b": {
            "persona": "khrushchev",
            "role_name": "Communist Leadership",
            "role_description": "Representative of Communist bloc interests in the region.",
        },
    },
    "cold_war_espionage": {
        "side_a": {
            "persona": "kissinger",
            "role_name": "Western Intelligence Chief",
            "role_description": "Director of Western intelligence operations during the Cold War.",
        },
        "side_b": {
            "persona": "khrushchev",
            "role_name": "Soviet Spymaster",
            "role_description": "Head of Soviet intelligence apparatus.",
        },
    },
    "cold_war_mole_hunt": {
        "side_a": {
            "persona": "kissinger",
            "role_name": "CIA Counterintelligence Chief",
            "role_description": "Director of CIA counterintelligence, hunting for Soviet moles.",
        },
        "side_b": {
            "persona": "khrushchev",
            "role_name": "KGB Handler",
            "role_description": "KGB officer running agents inside Western intelligence.",
        },
    },
    "nato_burden": {
        "side_a": {
            "persona": "nixon",
            "role_name": "American President",
            "role_description": "US leader pushing for fairer burden sharing among NATO allies.",
        },
        "side_b": {
            "persona": "bismarck",
            "role_name": "European Alliance Leader",
            "role_description": "European statesman balancing alliance obligations with national interests.",
        },
    },
    "silicon_valley": {
        "side_a": {
            "persona": "gates",
            "role_name": "Tech Company CEO",
            "role_description": "Leader of a major technology company competing for market dominance.",
        },
        "side_b": {
            "persona": "jobs",
            "role_name": "Rival Tech CEO",
            "role_description": "Visionary leader of a competing technology empire.",
        },
    },
    "opec": {
        "side_a": {
            "persona": "kissinger",
            "role_name": "Western Energy Minister",
            "role_description": "Representative of Western oil-consuming nations.",
        },
        "side_b": {
            "persona": "bismarck",
            "role_name": "OPEC Representative",
            "role_description": "Spokesman for oil-producing nations seeking fair prices.",
        },
    },
    "brexit": {
        "side_a": {
            "persona": "bismarck",
            "role_name": "British Negotiator",
            "role_description": "UK representative seeking the best possible exit terms.",
        },
        "side_b": {
            "persona": "metternich",
            "role_name": "EU Chief Negotiator",
            "role_description": "European Union representative defending EU unity and interests.",
        },
    },
    "byzantine": {
        "side_a": {
            "persona": "theodora",
            "role_name": "Imperial Faction Leader",
            "role_description": "Head of the established imperial faction in Constantinople.",
        },
        "side_b": {
            "persona": "livia",
            "role_name": "Challenger Faction",
            "role_description": "Leader of the rival faction seeking the throne.",
        },
    },
    "medici": {
        "side_a": {
            "persona": "richelieu",
            "role_name": "Banking House Patriarch",
            "role_description": "Head of a powerful Renaissance banking dynasty.",
        },
        "side_b": {
            "persona": "metternich",
            "role_name": "Rival Banking House",
            "role_description": "Leader of a competing financial power.",
        },
    },
}


def update_scenario_file(scenario_path: Path) -> bool:
    """Update a scenario file with persona mapping if applicable."""
    with open(scenario_path) as f:
        scenario = json.load(f)

    scenario_id = scenario.get("scenario_id", "").lower()

    # Find matching persona mapping
    matching_key = None
    for key in PERSONA_MAPPINGS:
        if key in scenario_id:
            matching_key = key
            break

    if not matching_key:
        print(f"  No persona mapping for: {scenario_id}")
        return False

    # Add personas field
    scenario["personas"] = PERSONA_MAPPINGS[matching_key]

    # Write back
    with open(scenario_path, "w") as f:
        json.dump(scenario, f, indent=2)

    print(f"  Updated: {scenario_path.name} with {matching_key} personas")
    return True


def main():
    scenarios_dir = Path("scenarios")
    if not scenarios_dir.exists():
        print("Error: scenarios directory not found")
        return

    updated = 0
    for scenario_file in scenarios_dir.glob("*.json"):
        if update_scenario_file(scenario_file):
            updated += 1

    print(f"\nUpdated {updated} scenario files with persona definitions")


if __name__ == "__main__":
    main()
