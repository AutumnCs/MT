from schemas import ParsedIntent, RouteResponse


CATEGORY_NAMES = {
    "coffee": "咖啡",
    "exhibition": "看展",
    "food": "美食",
    "shopping": "购物",
    "park": "公园",
    "movie": "电影",
    "tea": "茶馆",
    "scene": "景点",
}


def generate_response(route: RouteResponse, intent: ParsedIntent) -> RouteResponse:
    category_list = [CATEGORY_NAMES.get(category, category) for category in intent.required_categories]
    category_summary = " + ".join(category_list) if category_list else "游玩"

    start_str = f"从 {intent.start_location} 出发，" if intent.start_location else ""
    budget_str = f"预算约 {intent.budget} 元，" if intent.budget else ""

    route.title = f"{intent.city}{category_summary}路线"
    route.summary = (
        f"{start_str}为你安排了 {len(route.stops)} 个站点，{budget_str}"
        f"总花费约 {route.total_cost} 元，总时长约 {route.total_duration // 60} 小时 "
        f"{route.total_duration % 60} 分钟，总距离约 {route.total_distance} 公里。"
    )
    route.original_query = route.original_query or None
    return route
