import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../models/route_models.dart';

class RouteApiService {
  static String get baseUrl {
    if (Platform.isAndroid) {
      return 'http://10.0.2.2:8000/api';
    }
    return 'http://127.0.0.1:8000/api';
  }

  static const Duration timeout = Duration(seconds: 30);

  final http.Client _client;

  RouteApiService({http.Client? client}) : _client = client ?? http.Client();

  Future<RouteResponse> generateRoute(RouteRequest request) async {
    try {
      final response = await _client
          .post(
            Uri.parse('$baseUrl/route/generate'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(request.toJson()),
          )
          .timeout(timeout);

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
        return RouteResponse.fromJson(data);
      }

      throw ApiException('生成路线失败: ${response.statusCode}', statusCode: response.statusCode);
    } catch (e) {
      if (e is ApiException) rethrow;
      return _getMockRouteResponse(request.query);
    }
  }

  Future<RouteResponse> modifyRoute(ModifyRequest request) async {
    try {
      final response = await _client
          .post(
            Uri.parse('$baseUrl/route/modify'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(request.toJson()),
          )
          .timeout(timeout);

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
        return RouteResponse.fromJson(data);
      }

      throw ApiException('修改路线失败: ${response.statusCode}', statusCode: response.statusCode);
    } catch (e) {
      if (e is ApiException) rethrow;
      return _getMockRouteResponse(
        '${request.originalQuery ?? ''} ${request.query}'.trim(),
        isModified: true,
      );
    }
  }

  Future<IntentPromptBundle> fetchIntentPrompt({
    required String query,
    String? city,
  }) async {
    try {
      final response = await _client
          .post(
            Uri.parse('$baseUrl/intent/prompt'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'query': query, 'city': city}),
          )
          .timeout(timeout);

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
        return IntentPromptBundle.fromJson(data);
      }

      throw ApiException('获取意图提示失败: ${response.statusCode}', statusCode: response.statusCode);
    } catch (e) {
      if (e is ApiException) rethrow;
      return IntentPromptBundle(
        systemPrompt: 'LLM prompt unavailable',
        userPrompt: query,
      );
    }
  }

  Future<ParsedIntent> parseIntent({
    required String query,
    String? city,
    IntentDraft? llmDraft,
  }) async {
    try {
      final response = await _client
          .post(
            Uri.parse('$baseUrl/intent/parse'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'query': query,
              'city': city,
              'llm_draft': llmDraft?.toJson(),
            }),
          )
          .timeout(timeout);

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
        return ParsedIntent.fromJson(data);
      }

      throw ApiException('解析意图失败: ${response.statusCode}', statusCode: response.statusCode);
    } catch (e) {
      if (e is ApiException) rethrow;
      return ParsedIntent(
        city: city ?? '广州',
        startLocation: null,
        startTime: null,
        endTime: null,
        budget: null,
        parseSource: 'fallback',
      );
    }
  }

  RouteResponse _getMockRouteResponse(String query, {bool isModified = false}) {
    final isShanghai = query.contains('上海') || query.contains('外滩') || query.contains('武康路');

    final stops = isShanghai
        ? [
            RouteStop(
              poi: Poi(
                id: 'sh-coffee-mock',
                name: '% Arabica 上海烘焙坊',
                category: 'coffee',
                subCategory: 'specialty_coffee',
                district: '黄浦区',
                city: '上海',
                address: '上海市黄浦区进贤路120号',
                latitude: 31.2244,
                longitude: 121.4629,
                price: 45,
                visitDuration: 45,
                rating: 4.7,
                businessHours: '08:00-20:00',
                tags: const ['咖啡', '拍照'],
                suitableFor: const ['情侣', '朋友'],
                queueLevel: 2,
                photoScore: 5,
                dateScore: 4,
                foodScore: 3,
                cultureScore: 2,
                localFeatureScore: 2,
                rainyDayScore: 4,
                indoorOutdoor: 'indoor',
                description: '适合路线起点的咖啡站。',
              ),
              arrivalTime: '14:00',
              departureTime: '14:45',
              stayMinutes: 45,
              reason: '先用一站轻松咖啡开启今天的行程。',
            ),
            RouteStop(
              poi: Poi(
                id: 'sh-exhibition-mock',
                name: '上海当代艺术博物馆',
                category: 'exhibition',
                subCategory: 'art_museum',
                district: '黄浦区',
                city: '上海',
                address: '上海市黄浦区花园港路200号',
                latitude: 31.2058,
                longitude: 121.4812,
                price: 0,
                visitDuration: 90,
                rating: 4.8,
                businessHours: '11:00-19:00',
                tags: const ['艺术', '看展'],
                suitableFor: const ['情侣', '朋友'],
                queueLevel: 1,
                photoScore: 4,
                dateScore: 4,
                foodScore: 1,
                cultureScore: 5,
                localFeatureScore: 3,
                rainyDayScore: 5,
                indoorOutdoor: 'indoor',
                description: '适合下午逛展的场馆。',
              ),
              arrivalTime: '15:10',
              departureTime: '16:40',
              stayMinutes: 90,
              reason: '中段安排室内展览，节奏更稳，雨天也适合。',
            ),
            RouteStop(
              poi: Poi(
                id: 'sh-food-mock',
                name: '德兴馆 广东路店',
                category: 'food',
                subCategory: 'shanghai_cuisine',
                district: '黄浦区',
                city: '上海',
                address: '上海市黄浦区广东路471号',
                latitude: 31.2321,
                longitude: 121.4736,
                price: 68,
                visitDuration: 70,
                rating: 4.4,
                businessHours: '10:30-21:00',
                tags: const ['本帮菜', '老字号'],
                suitableFor: const ['情侣', '朋友'],
                queueLevel: 3,
                photoScore: 2,
                dateScore: 3,
                foodScore: 4,
                cultureScore: 3,
                localFeatureScore: 5,
                rainyDayScore: 4,
                indoorOutdoor: 'indoor',
                description: '适合作为路线收尾的一顿正餐。',
              ),
              arrivalTime: '17:10',
              departureTime: '18:20',
              stayMinutes: 70,
              reason: '最后用一顿稳定的本帮菜收尾，体验更完整。',
            ),
          ]
        : [
            RouteStop(
              poi: Poi(
                id: 'gz-coffee-mock',
                name: 'M Stand 广州塔店',
                category: 'coffee',
                subCategory: 'specialty_coffee',
                district: '海珠区',
                city: '广州',
                address: '广州市海珠区广州塔周边',
                latitude: 23.1086,
                longitude: 113.3247,
                price: 38,
                visitDuration: 45,
                rating: 4.6,
                businessHours: '10:00-22:00',
                tags: const ['咖啡', '拍照'],
                suitableFor: const ['情侣', '朋友'],
                queueLevel: 2,
                photoScore: 5,
                dateScore: 4,
                foodScore: 3,
                cultureScore: 2,
                localFeatureScore: 2,
                rainyDayScore: 4,
                indoorOutdoor: 'indoor',
                description: '适合广州塔周边路线起点。',
              ),
              arrivalTime: '14:00',
              departureTime: '14:45',
              stayMinutes: 45,
              reason: '先用一站咖啡调整节奏，适合作为开场。',
            ),
            RouteStop(
              poi: Poi(
                id: 'gz-exhibition-mock',
                name: '广东美术馆',
                category: 'exhibition',
                subCategory: 'art_gallery',
                district: '海珠区',
                city: '广州',
                address: '广州市海珠区艺苑路198号',
                latitude: 23.1124,
                longitude: 113.3172,
                price: 0,
                visitDuration: 90,
                rating: 4.8,
                businessHours: '10:00-18:00',
                tags: const ['艺术', '看展'],
                suitableFor: const ['情侣', '朋友'],
                queueLevel: 1,
                photoScore: 4,
                dateScore: 4,
                foodScore: 1,
                cultureScore: 5,
                localFeatureScore: 3,
                rainyDayScore: 5,
                indoorOutdoor: 'indoor',
                description: '适合轻松逛展。',
              ),
              arrivalTime: '15:00',
              departureTime: '16:30',
              stayMinutes: 90,
              reason: '中间安排室内展览，既能休息也有内容。',
            ),
            RouteStop(
              poi: Poi(
                id: 'gz-food-mock',
                name: '炳胜私厨 珠江新城店',
                category: 'food',
                subCategory: 'cantonese',
                district: '天河区',
                city: '广州',
                address: '广州市天河区珠江新城',
                latitude: 23.1181,
                longitude: 113.3249,
                price: 150,
                visitDuration: 90,
                rating: 4.7,
                businessHours: '11:00-21:30',
                tags: const ['粤菜', '约会'],
                suitableFor: const ['情侣', '家庭'],
                queueLevel: 3,
                photoScore: 3,
                dateScore: 5,
                foodScore: 5,
                cultureScore: 2,
                localFeatureScore: 4,
                rainyDayScore: 4,
                indoorOutdoor: 'indoor',
                description: '适合作为路线收尾的粤菜正餐。',
              ),
              arrivalTime: '17:10',
              departureTime: '18:40',
              stayMinutes: 90,
              reason: '最后用一顿稳定的粤菜正餐收尾，体验更完整。',
            ),
          ];

    final totalCost = stops.fold<int>(0, (sum, stop) => sum + stop.poi.price);
    final totalDuration = stops.fold<int>(0, (sum, stop) => sum + stop.stayMinutes);

    return RouteResponse(
      title: isModified ? '调整后的路线方案' : '${isShanghai ? '上海' : '广州'}城市路线',
      summary: '这是后端不可用时的演示方案，仍然可以完整展示页面流程。',
      totalCost: totalCost,
      totalDuration: totalDuration,
      totalDistance: isShanghai ? 4.6 : 4.1,
      poiCount: stops.length,
      coveredTypes: stops.map((stop) => stop.poi.categoryLabel).toSet().toList(),
      stops: stops,
      routeExplanation: '当前显示的是本地 mock 数据，用于后端异常时保障演示流程不中断。',
      strategyType: isModified ? '重新规划' : '稳妥方案',
      generatedAt: DateTime.now().toIso8601String(),
      mapPreview: _buildMockMapPreview(stops),
      trace: {
        'version': 'local-mock',
        'parse_source': 'mock',
        'matched_capabilities': ['route_generation'],
        'recognized_signals': [],
        'unclassified_clues': [],
        'hard_constraints': [],
        'preferences': [],
        'avoid': [],
        'required_categories': stops.map((stop) => stop.poi.category).toSet().toList(),
        'poi_count': stops.length,
        'route_score': null,
        'map_enabled': false,
        'map_provider': 'local',
      },
    );
  }

  Map<String, dynamic> _buildMockMapPreview(List<RouteStop> stops) {
    final markers = <Map<String, dynamic>>[];
    final polyline = <Map<String, dynamic>>[];
    for (var i = 0; i < stops.length; i++) {
      final stop = stops[i];
      markers.add({
        'id': stop.poi.id,
        'name': stop.poi.name,
        'category': stop.poi.category,
        'city': stop.poi.city,
        'latitude': stop.poi.latitude,
        'longitude': stop.poi.longitude,
        'label': i + 1,
        'address': stop.poi.address,
      });
      polyline.add({
        'latitude': stop.poi.latitude,
        'longitude': stop.poi.longitude,
      });
    }

    double? minLat;
    double? maxLat;
    double? minLng;
    double? maxLng;
    for (final marker in markers) {
      final lat = (marker['latitude'] as num?)?.toDouble();
      final lng = (marker['longitude'] as num?)?.toDouble();
      if (lat == null || lng == null) continue;
      minLat = minLat == null ? lat : (lat < minLat ? lat : minLat);
      maxLat = maxLat == null ? lat : (lat > maxLat ? lat : maxLat);
      minLng = minLng == null ? lng : (lng < minLng ? lng : minLng);
      maxLng = maxLng == null ? lng : (lng > maxLng ? lng : maxLng);
    }

    Map<String, dynamic>? center;
    if (markers.isNotEmpty) {
      final avgLat = markers
              .map((m) => (m['latitude'] as num).toDouble())
              .reduce((a, b) => a + b) /
          markers.length;
      final avgLng = markers
              .map((m) => (m['longitude'] as num).toDouble())
              .reduce((a, b) => a + b) /
          markers.length;
      center = {
        'latitude': avgLat,
        'longitude': avgLng,
      };
    }

    final segments = stops
        .where((stop) => stop.travelFromPrevious != null)
        .map(
          (stop) => {
            'mode': stop.travelFromPrevious?['mode'],
            'distance_km': stop.travelFromPrevious?['distance_km'],
            'duration_min': stop.travelFromPrevious?['duration_min'],
            'cost': stop.travelFromPrevious?['cost'],
            'source': stop.travelFromPrevious?['source'] ?? 'local',
          },
        )
        .toList();

    return {
      'provider': 'local',
      'enabled': false,
      'mode': 'walking',
      'route_title': 'mock-map-preview',
      'route_summary': '本地 mock 路线预览',
      'center': center,
      'bounds': {
        'min_latitude': minLat,
        'max_latitude': maxLat,
        'min_longitude': minLng,
        'max_longitude': maxLng,
      },
      'markers': markers,
      'polyline': polyline,
      'segments': segments,
      'point_count': markers.length,
    };
  }

  void dispose() {
    _client.close();
  }
}

class ApiException implements Exception {
  final String message;
  final int? statusCode;

  ApiException(this.message, {this.statusCode});

  @override
  String toString() => 'ApiException: $message (status: $statusCode)';
}
