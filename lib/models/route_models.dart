import 'dart:math';

int _jsonInt(dynamic value, [int fallback = 0]) {
  if (value == null) return fallback;
  if (value is int) return value;
  if (value is num) return value.round();
  return int.tryParse(value.toString()) ?? fallback;
}

int? _jsonNullableInt(dynamic value) {
  if (value == null) return null;
  if (value is int) return value;
  if (value is num) return value.round();
  return int.tryParse(value.toString());
}

class RouteSessionManager {
  static String? _sessionId;

  static String get sessionId {
    _sessionId ??= 'session-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(1 << 32)}';
    return _sessionId!;
  }
}

class IntentPromptBundle {
  final String systemPrompt;
  final String userPrompt;

  IntentPromptBundle({
    required this.systemPrompt,
    required this.userPrompt,
  });

  factory IntentPromptBundle.fromJson(Map<String, dynamic> json) {
    return IntentPromptBundle(
      systemPrompt: json['system_prompt'] ?? '',
      userPrompt: json['user_prompt'] ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'system_prompt': systemPrompt,
      'user_prompt': userPrompt,
    };
  }
}

class IntentDraft {
  final String? city;
  final String? startLocation;
  final String? startTime;
  final String? endTime;
  final int? budget;
  final List<String> requiredCategories;
  final List<String> preferences;
  final List<String> avoid;
  final String? pace;
  final String? transportMode;
  final List<String> mustInclude;
  final String? notes;

  IntentDraft({
    this.city,
    this.startLocation,
    this.startTime,
    this.endTime,
    this.budget,
    this.requiredCategories = const [],
    this.preferences = const [],
    this.avoid = const [],
    this.pace,
    this.transportMode,
    this.mustInclude = const [],
    this.notes,
  });

  factory IntentDraft.fromJson(Map<String, dynamic> json) {
    return IntentDraft(
      city: json['city'],
      startLocation: json['start_location'],
      startTime: json['start_time'],
      endTime: json['end_time'],
      budget: _jsonNullableInt(json['budget']),
      requiredCategories: List<String>.from(json['required_categories'] ?? const []),
      preferences: List<String>.from(json['preferences'] ?? const []),
      avoid: List<String>.from(json['avoid'] ?? const []),
      pace: json['pace'],
      transportMode: json['transport_mode'],
      mustInclude: List<String>.from(json['must_include'] ?? const []),
      notes: json['notes'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'city': city,
      'start_location': startLocation,
      'start_time': startTime,
      'end_time': endTime,
      'budget': budget,
      'required_categories': requiredCategories,
      'preferences': preferences,
      'avoid': avoid,
      'pace': pace,
      'transport_mode': transportMode,
      'must_include': mustInclude,
      'notes': notes,
    };
  }
}

class ParsedIntent {
  final String city;
  final String? startLocation;
  final String? startTime;
  final String? endTime;
  final int? budget;
  final List<String> preferences;
  final List<String> softPreferences;
  final List<String> hardConstraints;
  final List<String> avoid;
  final List<String> requiredCategories;
  final List<String> preferredCategories;
  final double? maxDistance;
  final String pace;
  final String transportMode;
  final List<String> mustInclude;
  final List<String> intentTags;
  final String parseSource;
  final Map<String, dynamic>? llmPayload;

  ParsedIntent({
    required this.city,
    this.startLocation,
    this.startTime,
    this.endTime,
    this.budget,
    this.preferences = const [],
    this.softPreferences = const [],
    this.hardConstraints = const [],
    this.avoid = const [],
    this.requiredCategories = const [],
    this.preferredCategories = const [],
    this.maxDistance,
    this.pace = 'normal',
    this.transportMode = 'walking',
    this.mustInclude = const [],
    this.intentTags = const [],
    this.parseSource = 'fallback',
    this.llmPayload,
  });

  factory ParsedIntent.fromJson(Map<String, dynamic> json) {
    return ParsedIntent(
      city: json['city'] ?? '广州',
      startLocation: json['start_location'],
      startTime: json['start_time'],
      endTime: json['end_time'],
      budget: _jsonNullableInt(json['budget']),
      preferences: List<String>.from(json['preferences'] ?? const []),
      softPreferences: List<String>.from(json['soft_preferences'] ?? const []),
      hardConstraints: List<String>.from(json['hard_constraints'] ?? const []),
      avoid: List<String>.from(json['avoid'] ?? const []),
      requiredCategories: List<String>.from(json['required_categories'] ?? const []),
      preferredCategories: List<String>.from(json['preferred_categories'] ?? const []),
      maxDistance: (json['max_distance'] as num?)?.toDouble(),
      pace: json['pace'] ?? 'normal',
      transportMode: json['transport_mode'] ?? 'walking',
      mustInclude: List<String>.from(json['must_include'] ?? const []),
      intentTags: List<String>.from(json['intent_tags'] ?? const []),
      parseSource: json['parse_source'] ?? 'fallback',
      llmPayload: json['llm_payload'] == null ? null : Map<String, dynamic>.from(json['llm_payload']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'city': city,
      'start_location': startLocation,
      'start_time': startTime,
      'end_time': endTime,
      'budget': budget,
      'preferences': preferences,
      'soft_preferences': softPreferences,
      'hard_constraints': hardConstraints,
      'avoid': avoid,
      'required_categories': requiredCategories,
      'preferred_categories': preferredCategories,
      'max_distance': maxDistance,
      'pace': pace,
      'transport_mode': transportMode,
      'must_include': mustInclude,
      'intent_tags': intentTags,
      'parse_source': parseSource,
      'llm_payload': llmPayload,
    };
  }
}

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
      price: _jsonInt(json['price']),
      visitDuration: _jsonInt(json['visit_duration'], 90),
      rating: (json['rating'] ?? 0).toDouble(),
      businessHours: json['business_hours'],
      tags: List<String>.from(json['tags'] ?? const []),
      suitableFor: List<String>.from(json['suitable_for'] ?? const []),
      queueLevel: _jsonInt(json['queue_level'], 2),
      photoScore: _jsonInt(json['photo_score'], 3),
      dateScore: _jsonInt(json['date_score'], 3),
      foodScore: _jsonInt(json['food_score'], 3),
      cultureScore: _jsonInt(json['culture_score'], 3),
      localFeatureScore: _jsonInt(json['local_feature_score'], 3),
      rainyDayScore: _jsonInt(json['rainy_day_score'], 3),
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
      'library': '图书馆',
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
      stayMinutes: _jsonInt(json['stay_minutes']),
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
  final double? routeScore;
  final double? travelTimeRatio;
  final List<String> warnings;
  final List<RouteOption> routeOptions;
  final String? originalQuery;
  final String? intentSummary;
  final String? parseSource;
  final List<String> appliedPreferences;
  final String? generatedAt;
  final Map<String, dynamic>? mapPreview;
  final Map<String, dynamic>? trace;
  final bool clarificationNeeded;
  final String? clarificationQuestion;
  final List<String> clarificationOptions;
  final String? clarificationReason;

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
    this.routeScore,
    this.travelTimeRatio,
    this.warnings = const [],
    this.routeOptions = const [],
    this.originalQuery,
    this.intentSummary,
    this.parseSource,
    this.appliedPreferences = const [],
    this.generatedAt,
    this.mapPreview,
    this.trace,
    this.clarificationNeeded = false,
    this.clarificationQuestion,
    this.clarificationOptions = const [],
    this.clarificationReason,
  });

  factory RouteResponse.fromJson(Map<String, dynamic> json) {
    final stops = (json['stops'] as List<dynamic>? ?? const [])
        .map((item) => RouteStop.fromJson(Map<String, dynamic>.from(item)))
        .toList();

    final coveredTypes = List<String>.from(json['covered_types'] ?? const []);

    return RouteResponse(
      title: json['title'] ?? '',
      summary: json['summary'] ?? '',
      totalCost: _jsonInt(json['total_cost'] ?? json['total_budget']),
      totalDuration: _jsonInt(json['total_duration']),
      totalDistance: (json['total_distance'] ?? 0).toDouble(),
      poiCount: _jsonInt(json['poi_count'], stops.length),
      coveredTypes: coveredTypes.isNotEmpty
          ? coveredTypes
          : stops.map((stop) => stop.poi.categoryLabel).toSet().toList(),
      stops: stops,
      routeExplanation: json['route_explanation'] ?? json['summary'] ?? '',
      strategyType: json['strategy_type'],
      routeScore: (json['route_score'] as num?)?.toDouble(),
      travelTimeRatio: (json['travel_time_ratio'] as num?)?.toDouble(),
      warnings: List<String>.from(json['warnings'] ?? const []),
      routeOptions: (json['route_options'] as List<dynamic>? ?? const [])
          .map((item) => RouteOption.fromJson(Map<String, dynamic>.from(item)))
          .toList(),
      originalQuery: json['original_query'],
      intentSummary: json['intent_summary'],
      parseSource: json['parse_source'],
      appliedPreferences: List<String>.from(json['applied_preferences'] ?? const []),
      generatedAt: json['generated_at'],
      mapPreview: json['map_preview'] == null ? null : Map<String, dynamic>.from(json['map_preview']),
      trace: json['trace'] == null ? null : Map<String, dynamic>.from(json['trace']),
      clarificationNeeded: json['clarification_needed'] ?? false,
      clarificationQuestion: json['clarification_question'],
      clarificationOptions: List<String>.from(json['clarification_options'] ?? const []),
      clarificationReason: json['clarification_reason'],
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
      'route_score': routeScore,
      'travel_time_ratio': travelTimeRatio,
      'warnings': warnings,
      'route_options': routeOptions.map((item) => item.toJson()).toList(),
      'original_query': originalQuery,
      'intent_summary': intentSummary,
      'parse_source': parseSource,
      'applied_preferences': appliedPreferences,
      'generated_at': generatedAt,
      'map_preview': mapPreview,
      'trace': trace,
      'clarification_needed': clarificationNeeded,
      'clarification_question': clarificationQuestion,
      'clarification_options': clarificationOptions,
      'clarification_reason': clarificationReason,
    };
  }
}

class RouteOption {
  final String strategyType;
  final double routeScore;
  final int totalCost;
  final int totalDuration;
  final double totalDistance;
  final int poiCount;
  final List<String> stops;
  final List<RouteStop> routeStops;
  final List<String> coveredTypes;
  final Map<String, dynamic>? mapPreview;

  RouteOption({
    required this.strategyType,
    required this.routeScore,
    required this.totalCost,
    required this.totalDuration,
    required this.totalDistance,
    required this.poiCount,
    required this.stops,
    this.routeStops = const [],
    this.coveredTypes = const [],
    this.mapPreview,
  });

  factory RouteOption.fromJson(Map<String, dynamic> json) {
    return RouteOption(
      strategyType: json['strategy_type'] ?? '',
      routeScore: (json['route_score'] ?? 0).toDouble(),
      totalCost: _jsonInt(json['total_cost']),
      totalDuration: _jsonInt(json['total_duration']),
      totalDistance: (json['total_distance'] ?? 0).toDouble(),
      poiCount: _jsonInt(json['poi_count']),
      stops: List<String>.from(json['stops'] ?? const []),
      routeStops: (json['route_stops'] as List<dynamic>? ?? const [])
          .map((item) => RouteStop.fromJson(Map<String, dynamic>.from(item)))
          .toList(),
      coveredTypes: List<String>.from(json['covered_types'] ?? const []),
      mapPreview: json['map_preview'] == null ? null : Map<String, dynamic>.from(json['map_preview']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'strategy_type': strategyType,
      'route_score': routeScore,
      'total_cost': totalCost,
      'total_duration': totalDuration,
      'total_distance': totalDistance,
      'poi_count': poiCount,
      'stops': stops,
      'route_stops': routeStops.map((item) => item.toJson()).toList(),
      'covered_types': coveredTypes,
      'map_preview': mapPreview,
    };
  }
}

class RouteRequest {
  final String query;
  final List<String>? preferences;
  final String? city;
  final String? sessionId;

  RouteRequest({
    required this.query,
    this.preferences,
    this.city,
    this.sessionId,
  });

  Map<String, dynamic> toJson() {
    return {
      'query': query,
      'preferences': preferences ?? [],
      'city': city,
      'session_id': sessionId ?? RouteSessionManager.sessionId,
    };
  }
}

class ModifyRequest {
  final String query;
  final String? originalQuery;
  final Map<String, dynamic>? currentRoute;
  final String? sessionId;

  ModifyRequest({
    required this.query,
    this.originalQuery,
    this.currentRoute,
    this.sessionId,
  });

  Map<String, dynamic> toJson() {
    return {
      'query': query,
      'original_query': originalQuery,
      'current_route': currentRoute,
      'session_id': sessionId ?? RouteSessionManager.sessionId,
    };
  }
}
