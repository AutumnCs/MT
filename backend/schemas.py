from typing import Any, List, Optional

from pydantic import BaseModel, Field


class POI(BaseModel):
    id: str
    name: str
    category: str
    city: str
    address: str
    latitude: float
    longitude: float
    price: int = 0
    rating: float = 4.5
    description: str = ""
    tags: List[str] = Field(default_factory=list)

    sub_category: Optional[str] = None
    district: Optional[str] = None
    visit_duration: int = 90
    business_hours: Optional[str] = None
    suitable_for: List[str] = Field(default_factory=list)
    queue_level: int = Field(default=2, ge=1, le=5)
    photo_score: int = Field(default=3, ge=1, le=5)
    date_score: int = Field(default=3, ge=1, le=5)
    food_score: int = Field(default=3, ge=1, le=5)
    culture_score: int = Field(default=3, ge=1, le=5)
    local_feature_score: int = Field(default=3, ge=1, le=5)
    rainy_day_score: int = Field(default=3, ge=1, le=5)
    indoor_outdoor: str = "indoor"


class ParsedIntent(BaseModel):
    city: str = "广州"
    start_location: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    budget: Optional[int] = None
    preferences: List[str] = Field(default_factory=list)
    avoid: List[str] = Field(default_factory=list)
    required_categories: List[str] = Field(default_factory=list)
    preferred_categories: List[str] = Field(default_factory=list)
    max_distance: Optional[float] = None
    current_route: Optional[Any] = None

    prefer_couple: bool = False
    prefer_photo: bool = False
    prefer_food: bool = False
    prefer_culture: bool = False
    prefer_local_feature: bool = False
    prefer_night_view: bool = False
    prefer_quiet: bool = False
    prefer_rainy_day: bool = False
    avoid_queue: bool = False
    avoid_crowded: bool = False

    pace: str = "normal"
    transport_mode: str = "walking"
    must_include: List[str] = Field(default_factory=list)
    intent_tags: List[str] = Field(default_factory=list)


class RouteStop(BaseModel):
    poi: POI
    arrival_time: str
    departure_time: str
    stay_minutes: int
    reason: str
    risk_alert: Optional[str] = None
    travel_from_previous: Optional[dict[str, Any]] = None


class RouteResponse(BaseModel):
    title: str
    summary: str
    total_cost: int
    total_duration: int
    total_distance: float
    poi_count: int
    covered_types: List[str]
    stops: List[RouteStop]
    route_explanation: str
    strategy_type: Optional[str] = None
    original_query: Optional[str] = None
    generated_at: Optional[str] = None
