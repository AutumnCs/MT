class Poi {
  final String id;
  final String name;
  final String category;
  final String? subCategory;
  final String? district;
  final String city;
  final String address;
  final double latitude;
  final double longitude;
  final int price;
  final int visitDuration;
  final double rating;
  final String? businessHours;
  final List<String> tags;
  final List<String> suitableFor;
  final int queueLevel;
  final int photoScore;
  final int dateScore;
  final int foodScore;
  final int cultureScore;
  final int localFeatureScore;
  final int rainyDayScore;
  final String indoorOutdoor;
  final String description;

  Poi({
    required this.id,
    required this.name,
    required this.category,
    this.subCategory,
    this.district,
    required this.city,
    required this.address,
    required this.latitude,
    required this.longitude,
    required this.price,
    required this.visitDuration,
    required this.rating,
    this.businessHours,
    required this.tags,
    required this.suitableFor,
    required this.queueLevel,
    required this.photoScore,
    required this.dateScore,
    required this.foodScore,
    required this.cultureScore,
    required this.localFeatureScore,
    required this.rainyDayScore,
    required this.indoorOutdoor,
    required this.description,
  });

  factory Poi.fromJson(Map<String, dynamic> json) {
    return Poi(
      id: json['id'] ?? '',
      name: json['name'] ?? '',
      category: json['category'] ?? '',
      subCategory: json['sub_category'],
      district: json['district'],
      city: json['city'] ?? '',
      address: json['address'] ?? '',
      latitude: (json['latitude'] ?? 0).toDouble(),
      longitude: (json['longitude'] ?? 0).toDouble(),
      price: json['price'] ?? 0,
      visitDuration: json['visit_duration'] ?? 90,
      rating: (json['rating'] ?? 0).toDouble(),
      businessHours: json['business_hours'],
      tags: List<String>.from(json['tags'] ?? const []),
      suitableFor: List<String>.from(json['suitable_for'] ?? const []),
      queueLevel: json['queue_level'] ?? 2,
      photoScore: json['photo_score'] ?? 3,
      dateScore: json['date_score'] ?? 3,
      foodScore: json['food_score'] ?? 3,
      cultureScore: json['culture_score'] ?? 3,
      localFeatureScore: json['local_feature_score'] ?? 3,
      rainyDayScore: json['rainy_day_score'] ?? 3,
      indoorOutdoor: json['indoor_outdoor'] ?? 'indoor',
      description: json['description'] ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'category': category,
      'sub_category': subCategory,
      'district': district,
      'city': city,
      'address': address,
      'latitude': latitude,
      'longitude': longitude,
      'price': price,
      'visit_duration': visitDuration,
      'rating': rating,
      'business_hours': businessHours,
      'tags': tags,
      'suitable_for': suitableFor,
      'queue_level': queueLevel,
      'photo_score': photoScore,
      'date_score': dateScore,
      'food_score': foodScore,
      'culture_score': cultureScore,
      'local_feature_score': localFeatureScore,
      'rainy_day_score': rainyDayScore,
      'indoor_outdoor': indoorOutdoor,
      'description': description,
    };
  }

  String get categoryLabel {
    const labels = {
      'coffee': '咖啡',
      'food': '餐饮',
      'museum': '博物馆',
      'exhibition': '展览',
      'scene': '景点',
      'street': '街区',
      'shopping': '购物',
      'park': '公园',
      'night': '夜景',
    };
    return labels[category] ?? category;
  }
}

class RouteStop {
  final Poi poi;
  final String arrivalTime;
  final String departureTime;
  final int stayMinutes;
  final String reason;
  final String? riskAlert;
  final Map<String, dynamic>? travelFromPrevious;

  RouteStop({
    required this.poi,
    required this.arrivalTime,
    required this.departureTime,
    required this.stayMinutes,
    required this.reason,
    this.riskAlert,
    this.travelFromPrevious,
  });

  factory RouteStop.fromJson(Map<String, dynamic> json) {
    return RouteStop(
      poi: Poi.fromJson(json['poi'] ?? {}),
      arrivalTime: json['arrival_time'] ?? '',
      departureTime: json['departure_time'] ?? '',
      stayMinutes: json['stay_minutes'] ?? 0,
      reason: json['reason'] ?? '',
      riskAlert: json['risk_alert'],
      travelFromPrevious: json['travel_from_previous'] == null
          ? null
          : Map<String, dynamic>.from(json['travel_from_previous']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'poi': poi.toJson(),
      'arrival_time': arrivalTime,
      'departure_time': departureTime,
      'stay_minutes': stayMinutes,
      'reason': reason,
      'risk_alert': riskAlert,
      'travel_from_previous': travelFromPrevious,
    };
  }
}

class RouteResponse {
  final String title;
  final String summary;
  final int totalCost;
  final int totalDuration;
  final double totalDistance;
  final int poiCount;
  final List<String> coveredTypes;
  final List<RouteStop> stops;
  final String routeExplanation;
  final String? strategyType;
  final String? originalQuery;
  final String? generatedAt;

  RouteResponse({
    required this.title,
    required this.summary,
    required this.totalCost,
    required this.totalDuration,
    required this.totalDistance,
    required this.poiCount,
    required this.coveredTypes,
    required this.stops,
    required this.routeExplanation,
    this.strategyType,
    this.originalQuery,
    this.generatedAt,
  });

  factory RouteResponse.fromJson(Map<String, dynamic> json) {
    final stops = (json['stops'] as List<dynamic>? ?? const [])
        .map((item) => RouteStop.fromJson(Map<String, dynamic>.from(item)))
        .toList();

    final coveredTypes = List<String>.from(json['covered_types'] ?? const []);

    return RouteResponse(
      title: json['title'] ?? '',
      summary: json['summary'] ?? '',
      totalCost: json['total_cost'] ?? json['total_budget'] ?? 0,
      totalDuration: json['total_duration'] ?? 0,
      totalDistance: (json['total_distance'] ?? 0).toDouble(),
      poiCount: json['poi_count'] ?? stops.length,
      coveredTypes: coveredTypes.isNotEmpty
          ? coveredTypes
          : stops.map((stop) => stop.poi.categoryLabel).toSet().toList(),
      stops: stops,
      routeExplanation: json['route_explanation'] ?? json['summary'] ?? '',
      strategyType: json['strategy_type'],
      originalQuery: json['original_query'],
      generatedAt: json['generated_at'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'summary': summary,
      'total_cost': totalCost,
      'total_duration': totalDuration,
      'total_distance': totalDistance,
      'poi_count': poiCount,
      'covered_types': coveredTypes,
      'stops': stops.map((item) => item.toJson()).toList(),
      'route_explanation': routeExplanation,
      'strategy_type': strategyType,
      'original_query': originalQuery,
      'generated_at': generatedAt,
    };
  }
}

class RouteRequest {
  final String query;
  final List<String>? preferences;

  RouteRequest({
    required this.query,
    this.preferences,
  });

  Map<String, dynamic> toJson() {
    return {
      'query': query,
      'preferences': preferences ?? [],
    };
  }
}

class ModifyRequest {
  final String query;
  final String? originalQuery;
  final Map<String, dynamic>? currentRoute;

  ModifyRequest({
    required this.query,
    this.originalQuery,
    this.currentRoute,
  });

  Map<String, dynamic> toJson() {
    return {
      'query': query,
      'original_query': originalQuery,
      'current_route': currentRoute,
    };
  }
}
