from schemas import POI, ParsedIntent


def filter_by_constraints(pois: list[POI], intent: ParsedIntent) -> list[POI]:
    filtered: list[POI] = []
    category_count = max(len(intent.required_categories), 1)

    for poi in pois:
        if intent.budget and poi.price > max(120, intent.budget / category_count * 1.6):
            continue

        if "spicy" in intent.avoid and any(tag in ["辣", "重辣"] for tag in poi.tags):
            continue

        if intent.avoid_queue and poi.queue_level >= 4:
            continue

        if intent.avoid_crowded and poi.queue_level >= 4:
            continue

        filtered.append(poi)

    return filtered
