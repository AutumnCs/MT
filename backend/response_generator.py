from datetime import datetime

from schemas import ParsedIntent, RouteResponse


def generate_response(route: RouteResponse, intent: ParsedIntent) -> RouteResponse:
    """Final response normalization layer.

    This layer should not re-decide the route. It only fills in missing
    presentation details and keeps the response contract stable.
    """

    if not route.strategy_type:
        if intent.prefer_couple:
            route.strategy_type = "约会方案"
        elif intent.prefer_photo:
            route.strategy_type = "拍照方案"
        elif intent.budget and intent.budget <= 150:
            route.strategy_type = "高性价比方案"
        else:
            route.strategy_type = "稳妥方案"

    if not route.generated_at:
        route.generated_at = datetime.now().isoformat()

    return route
