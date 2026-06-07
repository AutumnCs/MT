import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

class MapApiService {
  static String get baseUrl {
    if (Platform.isAndroid) {
      return 'http://10.0.2.2:8000/api';
    }
    return 'http://127.0.0.1:8000/api';
  }

  static const Duration timeout = Duration(seconds: 20);

  final http.Client _client;

  MapApiService({http.Client? client}) : _client = client ?? http.Client();

  Future<Map<String, dynamic>> fetchStatus() => _get('/map/status');

  Future<Map<String, dynamic>> geocode(String address, {String? city}) {
    return _post('/map/geocode', {
      'address': address,
      'city': city,
    });
  }

  Future<Map<String, dynamic>> reverseGeocode(double longitude, double latitude) {
    return _post('/map/reverse-geocode', {
      'longitude': longitude,
      'latitude': latitude,
    });
  }

  Future<Map<String, dynamic>> searchPoi({
    required String keyword,
    String? city,
    String? location,
    int radius = 1000,
    String? types,
    int limit = 10,
  }) {
    return _post('/map/poi-search', {
      'keyword': keyword,
      'city': city,
      'location': location,
      'radius': radius,
      'types': types,
      'limit': limit,
    });
  }

  Future<Map<String, dynamic>> planRoute({
    required double originLongitude,
    required double originLatitude,
    required double destinationLongitude,
    required double destinationLatitude,
    String mode = 'walking',
    String? strategy,
    List<String> waypoints = const [],
  }) {
    return _post('/map/route', {
      'origin_longitude': originLongitude,
      'origin_latitude': originLatitude,
      'destination_longitude': destinationLongitude,
      'destination_latitude': destinationLatitude,
      'mode': mode,
      'strategy': strategy,
      'waypoints': waypoints,
    });
  }

  Future<Map<String, dynamic>> buildPreview({
    required List<Map<String, dynamic>> points,
    String mode = 'walking',
    String? title,
  }) {
    return _post('/map/preview', {
      'points': points,
      'mode': mode,
      'title': title,
    });
  }

  Future<Map<String, dynamic>> _get(String path) async {
    final response = await _client.get(Uri.parse('$baseUrl$path')).timeout(timeout);
    return _decodeResponse(response);
  }

  Future<Map<String, dynamic>> _post(String path, Map<String, dynamic> body) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl$path'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(body),
        )
        .timeout(timeout);
    return _decodeResponse(response);
  }

  Map<String, dynamic> _decodeResponse(http.Response response) {
    if (response.statusCode != 200) {
      return {
        'provider': 'tdt',
        'enabled': false,
        'success': false,
        'message': 'HTTP ${response.statusCode}',
        'data': const <String, dynamic>{},
      };
    }

    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (decoded is Map<String, dynamic>) {
      return decoded;
    }
    return {
      'provider': 'tdt',
      'enabled': false,
      'success': false,
      'message': 'Unexpected response format',
      'data': const <String, dynamic>{},
    };
  }

  void dispose() {
    _client.close();
  }
}
