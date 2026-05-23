import json
from pathlib import Path

from schemas import POI, ParsedIntent


POI_FILE = Path(__file__).with_name("pois.json")


def load_pois() -> list:
    with POI_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def retrieve_pois(intent: ParsedIntent) -> list[POI]:
    all_pois = load_pois()
    filtered = []

    for poi in all_pois:
        if poi.get("city") != intent.city:
            continue

        if intent.required_categories and poi.get("category") not in intent.required_categories:
            continue

        filtered.append(POI(**poi))

    return filtered
