import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

class TiandituRouteMap extends StatelessWidget {
  static const String _webKey = String.fromEnvironment('TDT_WEB_KEY');
  static const String _token = String.fromEnvironment('TDT_TOKEN');

  final Map<String, dynamic> preview;
  final Widget fallback;

  const TiandituRouteMap({
    super.key,
    required this.preview,
    required this.fallback,
  });

  static String get _effectiveKey => _webKey.trim().isNotEmpty ? _webKey.trim() : _token.trim();

  static bool get isConfigured => _effectiveKey.isNotEmpty;

  @override
  Widget build(BuildContext context) {
    if (!isConfigured || !_hasUsablePreview(preview)) {
      return fallback;
    }

    if (Theme.of(context).platform == TargetPlatform.android ||
        Theme.of(context).platform == TargetPlatform.iOS ||
        Theme.of(context).platform == TargetPlatform.macOS) {
      return _MobileTiandituRouteMap(preview: preview, fallback: fallback);
    }

    return fallback;
  }

  static bool _hasUsablePreview(Map<String, dynamic> preview) {
    final markers = preview['markers'];
    if (markers is! List || markers.isEmpty) return false;
    return markers.any((item) {
      if (item is! Map) return false;
      return item['latitude'] is num && item['longitude'] is num;
    });
  }

  static String buildHtml(Map<String, dynamic> preview) {
    final routeData = _buildRouteData(preview);
    final routeJson = jsonEncode(routeData);
    final key = Uri.encodeComponent(_effectiveKey);

    return '''
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="initial-scale=1.0, user-scalable=no, width=device-width">
  <style>
    html, body {
      width: 100%;
      height: 100%;
      min-width: 100vw;
      min-height: 100vh;
      margin: 0;
      padding: 0;
      overflow: hidden;
      background: #f6f7fb;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    body {
      position: relative;
    }
    #container {
      position: absolute;
      inset: 0;
      width: 100vw;
      height: 100vh;
    }
    #route-overlay {
      position: absolute;
      inset: 0;
      z-index: 9999;
      pointer-events: none;
    }
    .route-dot {
      position: absolute;
      width: 24px;
      height: 24px;
      margin-left: -12px;
      margin-top: -12px;
      border-radius: 9px;
      background: #f2c230;
      color: #111827;
      border: 3px solid #ffffff;
      box-shadow: 0 6px 16px rgba(15, 23, 42, 0.28);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      font-weight: 800;
      box-sizing: border-box;
    }
    .route-dot.start {
      background: #34d399;
    }
    .route-label {
      position: absolute;
      max-width: 160px;
      padding: 4px 8px;
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.94);
      color: #111827;
      box-shadow: 0 6px 16px rgba(15, 23, 42, 0.16);
      font-size: 12px;
      font-weight: 750;
      line-height: 1.25;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      transform: translate(14px, -50%);
    }
    .info {
      min-width: 190px;
      max-width: 260px;
      padding: 2px 0;
      color: #111827;
      line-height: 1.45;
    }
    .info-title {
      font-size: 14px;
      font-weight: 800;
      margin-bottom: 4px;
    }
    .info-meta {
      color: #6b7280;
      font-size: 12px;
    }
    .map-error {
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #4b5563;
      font-size: 13px;
      text-align: center;
      padding: 24px;
      box-sizing: border-box;
    }
  </style>
  <script src="https://api.tianditu.gov.cn/api?v=4.0&tk=$key"></script>
</head>
<body>
  <div id="container"></div>
  <div id="route-overlay"></div>
  <script>
    const route = $routeJson;

    function h(value) {
      return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function lngLat(point) {
      return new T.LngLat(Number(point.longitude), Number(point.latitude));
    }

    function validNumber(value) {
      return value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
    }

    function showError(message) {
      document.getElementById('container').innerHTML =
        '<div class="map-error">' + h(message) + '</div>';
    }

    function usablePoints() {
      const raw = Array.isArray(route.markers) ? route.markers : [];
      return raw
        .filter(function(point) {
          return validNumber(point.latitude) && validNumber(point.longitude);
        })
        .map(function(point) {
          return Object.assign({}, point, {
            latitude: Number(point.latitude),
            longitude: Number(point.longitude)
          });
        });
    }

    function usableLinePoints() {
      const raw = Array.isArray(route.polyline) && route.polyline.length > 1
        ? route.polyline
        : (Array.isArray(route.markers) ? route.markers : []);
      return raw
        .filter(function(point) {
          return validNumber(point.latitude) && validNumber(point.longitude);
        })
        .map(function(point) {
          return Object.assign({}, point, {
            latitude: Number(point.latitude),
            longitude: Number(point.longitude)
          });
        });
    }

    function routeZoom(points) {
      if (!points || points.length < 2) return 15;
      const lats = points.map(function(point) { return point.latitude; });
      const lngs = points.map(function(point) { return point.longitude; });
      const latSpan = Math.max.apply(null, lats) - Math.min.apply(null, lats);
      const lngSpan = Math.max.apply(null, lngs) - Math.min.apply(null, lngs);
      const span = Math.max(latSpan, lngSpan);
      if (span < 0.012) return 15;
      if (span < 0.035) return 14;
      if (span < 0.08) return 13;
      return 12;
    }

    function addRouteMarker(map, point, index) {
      const position = lngLat(point);
      const marker = new T.Marker(position);
      marker.addEventListener('click', function() {
        const html =
          '<div class="info"><div class="info-title">' + h(point.label || index + 1) + '. ' + h(point.name) +
          '</div><div class="info-meta">' + h(point.address || point.category || '') + '</div></div>';
        marker.openInfoWindow(new T.InfoWindow(html));
      });
      map.addOverLay(marker);
      return marker;
    }

    function containerReady() {
      const el = document.getElementById('container');
      return el && el.clientWidth > 120 && el.clientHeight > 120;
    }

    function containerSize() {
      const el = document.getElementById('container');
      return {
        width: el ? el.clientWidth : 0,
        height: el ? el.clientHeight : 0
      };
    }

    function projectPoint(map, point) {
      if (!map || typeof map.lngLatToContainerPoint !== 'function') return null;
      const pixel = map.lngLatToContainerPoint(lngLat(point));
      if (pixel && validNumber(pixel.x) && validNumber(pixel.y)) {
        return { x: Number(pixel.x), y: Number(pixel.y) };
      }
      return null;
    }

    function drawSyncedOverlay(map) {
      const overlay = document.getElementById('route-overlay');
      if (!overlay) return;
      const markerPoints = usablePoints();
      const linePoints = usableLinePoints();
      const projectedLine = linePoints.map(function(point) { return projectPoint(map, point); }).filter(Boolean);
      overlay.innerHTML = '';

      if (projectedLine.length > 1) {
        const width = overlay.clientWidth || document.body.clientWidth;
        const height = overlay.clientHeight || document.body.clientHeight;
        const polyPoints = projectedLine.map(function(point) {
          return point.x.toFixed(1) + ',' + point.y.toFixed(1);
        }).join(' ');
        overlay.innerHTML =
          '<svg width="100%" height="100%" viewBox="0 0 ' + width + ' ' + height + '" preserveAspectRatio="none">' +
          '<polyline points="' + polyPoints + '" fill="none" stroke="rgba(255,255,255,0.92)" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"></polyline>' +
          '<polyline points="' + polyPoints + '" fill="none" stroke="#f2c230" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"></polyline>' +
          '</svg>';
      }

      markerPoints.forEach(function(point, index) {
        const pixel = projectPoint(map, point);
        if (!pixel) return;
        const dot = document.createElement('div');
        dot.className = 'route-dot' + (index === 0 ? ' start' : '');
        dot.style.left = pixel.x + 'px';
        dot.style.top = pixel.y + 'px';
        dot.textContent = String(point.label || index + 1);
        overlay.appendChild(dot);

        if (point.name) {
          const label = document.createElement('div');
          label.className = 'route-label';
          label.style.left = pixel.x + 'px';
          label.style.top = pixel.y + 'px';
          label.textContent = String(point.name);
          overlay.appendChild(label);
        }
      });
    }

    try {
      if (!window.T) {
        showError('天地图脚本加载失败，请检查 Token 和网络。');
      } else {
        function initializeMap(attempt, lastWidth, lastHeight, stableCount) {
          if (!containerReady()) {
            if (attempt > 30) {
              showError('地图容器尺寸未就绪，请重新打开地图。');
              return;
            }
            setTimeout(function() { initializeMap(attempt + 1, 0, 0, 0); }, 100);
            return;
          }

          const size = containerSize();
          const stable = Math.abs(size.width - lastWidth) < 2 && Math.abs(size.height - lastHeight) < 2
            ? stableCount + 1
            : 0;
          if (stable < 3 && attempt <= 40) {
            setTimeout(function() { initializeMap(attempt + 1, size.width, size.height, stable); }, 100);
            return;
          }

          const points = usablePoints();
          if (points.length === 0) {
            showError('路线点位为空，无法绘制地图路线。');
            return;
          }

          const center = route.center ? lngLat(route.center) : lngLat(points[0]);
          const map = new T.Map('container');
          map.centerAndZoom(center, routeZoom(points));
          map.enableScrollWheelZoom();

          points.forEach(function(point, index) {
            addRouteMarker(map, point, index);
          });

          const linePath = usableLinePoints().map(lngLat);

          if (linePath.length > 1) {
            try {
              const polyline = new T.Polyline(linePath, {
                color: '#f2c230',
                weight: 6,
                opacity: 0.95,
                lineStyle: 'solid'
              });
              map.addOverLay(polyline);
            } catch (_) {
              // The synced SVG overlay below still renders the route if native polyline fails.
            }
          }

          function fitRouteView() {
            if (map.checkResize) map.checkResize();
            const viewPoints = usableLinePoints().concat(points).map(lngLat);
            if (typeof map.setViewport === 'function' && viewPoints.length > 1) {
              map.setViewport(viewPoints);
            } else {
              map.centerAndZoom(center, routeZoom(points));
            }
            setTimeout(function() { drawSyncedOverlay(map); }, 80);
          }

          setTimeout(fitRouteView, 150);
          setTimeout(fitRouteView, 500);
          setTimeout(fitRouteView, 1200);
          setTimeout(fitRouteView, 2200);
          if (map.addEventListener) {
            map.addEventListener('moveend', function() { drawSyncedOverlay(map); });
            map.addEventListener('zoomend', function() { drawSyncedOverlay(map); });
          }
          window.addEventListener('resize', fitRouteView);
        }

        initializeMap(0, 0, 0, 0);
      }
    } catch (error) {
      showError('地图渲染失败：' + (error && error.message ? error.message : error));
    }
  </script>
</body>
</html>
''';
  }

  static Map<String, dynamic> _buildRouteData(Map<String, dynamic> preview) {
    final markers = _normalizePoints(preview['markers']);
    final polyline = _normalizePoints(preview['polyline']);
    final center = _normalizePoint(preview['center']) ?? _averageCenter(markers);

    return {
      'center': center,
      'markers': markers,
      'polyline': polyline.isEmpty ? markers : polyline,
      'title': preview['route_title']?.toString() ?? '',
      'summary': preview['route_summary']?.toString() ?? '',
    };
  }

  static List<Map<String, dynamic>> _normalizePoints(Object? raw) {
    if (raw is! List) return const [];
    final points = <Map<String, dynamic>>[];
    for (var i = 0; i < raw.length; i++) {
      final point = _normalizePoint(raw[i]);
      if (point == null) continue;
      point['label'] ??= '${i + 1}';
      points.add(point);
    }
    return points;
  }

  static Map<String, dynamic>? _normalizePoint(Object? raw) {
    if (raw is! Map) return null;
    final latitude = (raw['latitude'] as num?)?.toDouble();
    final longitude = (raw['longitude'] as num?)?.toDouble();
    if (latitude == null || longitude == null) return null;

    return {
      'id': raw['id']?.toString() ?? '',
      'name': raw['name']?.toString() ?? '',
      'category': raw['category']?.toString() ?? '',
      'address': raw['address']?.toString() ?? '',
      'latitude': latitude,
      'longitude': longitude,
      'label': raw['label']?.toString(),
    };
  }

  static Map<String, dynamic>? _averageCenter(List<Map<String, dynamic>> points) {
    if (points.isEmpty) return null;
    final latitude = points
            .map((point) => point['latitude'] as double)
            .reduce((value, item) => value + item) /
        points.length;
    final longitude = points
            .map((point) => point['longitude'] as double)
            .reduce((value, item) => value + item) /
        points.length;

    return {
      'latitude': latitude,
      'longitude': longitude,
    };
  }
}

class _MobileTiandituRouteMap extends StatefulWidget {
  final Map<String, dynamic> preview;
  final Widget fallback;

  const _MobileTiandituRouteMap({
    required this.preview,
    required this.fallback,
  });

  @override
  State<_MobileTiandituRouteMap> createState() => _MobileTiandituRouteMapState();
}

class _MobileTiandituRouteMapState extends State<_MobileTiandituRouteMap> {
  late final WebViewController _controller;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(Colors.transparent)
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageFinished: (_) {
            if (mounted) setState(() => _isLoading = false);
          },
          onWebResourceError: (_) {
            if (mounted) setState(() => _isLoading = false);
          },
        ),
      );
    _loadHtml();
  }

  @override
  void didUpdateWidget(covariant _MobileTiandituRouteMap oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.preview != widget.preview) {
      setState(() => _isLoading = true);
      _loadHtml();
    }
  }

  void _loadHtml() {
    unawaited(_controller.loadHtmlString(TiandituRouteMap.buildHtml(widget.preview)));
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        WebViewWidget(controller: _controller),
        if (_isLoading) const _TiandituLoadingOverlay(),
      ],
    );
  }
}

class _TiandituLoadingOverlay extends StatelessWidget {
  const _TiandituLoadingOverlay();

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: const Color(0xFFF6F7FB),
      child: Center(
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.92),
            borderRadius: BorderRadius.circular(999),
            border: Border.all(color: const Color(0xFFE5E7EB)),
          ),
          child: const Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFFF2C230)),
              ),
              SizedBox(width: 8),
              Text(
                '正在加载天地图',
                style: TextStyle(
                  color: Color(0xFF111827),
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
