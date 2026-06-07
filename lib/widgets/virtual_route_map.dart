import 'dart:math' as math;

import 'package:flutter/material.dart';

class VirtualRouteMap extends StatelessWidget {
  final Map<String, dynamic> preview;
  final String city;

  const VirtualRouteMap({
    super.key,
    required this.preview,
    this.city = '',
  });

  @override
  Widget build(BuildContext context) {
    final markers = _readPoints(preview['markers']);
    final polyline = _readPoints(preview['polyline']);
    final routeLine = polyline.length > 1 ? polyline : markers;

    if (markers.isEmpty) {
      return const ColoredBox(
        color: Color(0xFFF5F7FB),
        child: Center(
          child: Text(
            '暂无地图点位',
            style: TextStyle(
              color: Color(0xFF4B5563),
              fontSize: 13,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      );
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        final width = math.max(constraints.maxWidth, 360.0);
        final height = math.max(constraints.maxHeight, 220.0);
        return InteractiveViewer(
          minScale: 0.85,
          maxScale: 4.0,
          boundaryMargin: const EdgeInsets.all(96),
          child: CustomPaint(
            size: Size(width, height),
            painter: _VirtualRouteMapPainter(
              markers: markers,
              routeLine: routeLine,
              city: city,
              sourceLabel: _sourceLabel(preview),
            ),
          ),
        );
      },
    );
  }

  static String _sourceLabel(Map<String, dynamic> preview) {
    final coordinateSource = preview['coordinate_source']?.toString() ?? '';
    final polylineSource = preview['polyline_source']?.toString() ?? '';
    if (coordinateSource.startsWith('tdt') || polylineSource.startsWith('tdt')) {
      return '天地图校准 + 虚拟渲染';
    }
    return '本地 POI + 虚拟路网';
  }

  static List<_VirtualMapPoint> _readPoints(Object? raw) {
    if (raw is! List) return const [];
    final points = <_VirtualMapPoint>[];
    for (var index = 0; index < raw.length; index++) {
      final item = raw[index];
      if (item is! Map) continue;
      final lat = (item['latitude'] as num?)?.toDouble();
      final lng = (item['longitude'] as num?)?.toDouble();
      if (lat == null || lng == null) continue;
      points.add(
        _VirtualMapPoint(
          latitude: lat,
          longitude: lng,
          label: item['label']?.toString() ?? '${index + 1}',
          name: item['name']?.toString() ?? '',
          category: item['category']?.toString() ?? '',
          address: item['address']?.toString() ?? '',
        ),
      );
    }
    return points;
  }
}

class _VirtualMapPoint {
  final double latitude;
  final double longitude;
  final String label;
  final String name;
  final String category;
  final String address;

  const _VirtualMapPoint({
    required this.latitude,
    required this.longitude,
    required this.label,
    required this.name,
    required this.category,
    required this.address,
  });
}

class _VirtualRouteMapPainter extends CustomPainter {
  final List<_VirtualMapPoint> markers;
  final List<_VirtualMapPoint> routeLine;
  final String city;
  final String sourceLabel;

  const _VirtualRouteMapPainter({
    required this.markers,
    required this.routeLine,
    required this.city,
    required this.sourceLabel,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    canvas.drawRect(rect, Paint()..color = const Color(0xFFF5F7FB));
    _drawDistricts(canvas, size);
    _drawRoadNetwork(canvas, size);

    final allPoints = <_VirtualMapPoint>[...markers, ...routeLine];
    final projection = _Projection.fromPoints(allPoints, size);
    final routeOffsets = routeLine.map(projection.offsetOf).toList();
    _drawRoute(canvas, routeOffsets);

    for (var index = 0; index < markers.length; index++) {
      final point = markers[index];
      _drawMarker(canvas, projection.offsetOf(point), point, index == 0);
    }

    _drawMapBadges(canvas, size);
  }

  void _drawDistricts(Canvas canvas, Size size) {
    final districts = [
      (const Color(0xFFD9F3E5), Rect.fromLTWH(size.width * 0.06, size.height * 0.10, size.width * 0.32, size.height * 0.28), '核心商圈'),
      (const Color(0xFFE8EEFF), Rect.fromLTWH(size.width * 0.43, size.height * 0.08, size.width * 0.42, size.height * 0.24), '文化展馆'),
      (const Color(0xFFFFF0C7), Rect.fromLTWH(size.width * 0.12, size.height * 0.48, size.width * 0.34, size.height * 0.30), '餐饮街区'),
      (const Color(0xFFEBDDF7), Rect.fromLTWH(size.width * 0.56, size.height * 0.44, size.width * 0.34, size.height * 0.34), '夜景休闲'),
    ];

    for (final district in districts) {
      final paint = Paint()..color = district.$1.withValues(alpha: 0.72);
      canvas.drawRRect(
        RRect.fromRectAndRadius(district.$2, const Radius.circular(22)),
        paint,
      );
      _drawText(
        canvas,
        district.$3,
        district.$2.topLeft + const Offset(14, 12),
        const TextStyle(
          color: Color(0xFF64748B),
          fontSize: 12,
          fontWeight: FontWeight.w700,
        ),
        maxWidth: district.$2.width - 24,
      );
    }

    final waterPaint = Paint()
      ..color = const Color(0xFFB8D7F4).withValues(alpha: 0.55)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 18
      ..strokeCap = StrokeCap.round;
    final river = Path()
      ..moveTo(size.width * 0.02, size.height * 0.82)
      ..cubicTo(size.width * 0.28, size.height * 0.70, size.width * 0.46, size.height * 0.92, size.width * 0.68, size.height * 0.72)
      ..cubicTo(size.width * 0.80, size.height * 0.62, size.width * 0.90, size.height * 0.68, size.width * 0.98, size.height * 0.58);
    canvas.drawPath(river, waterPaint);
  }

  void _drawRoadNetwork(Canvas canvas, Size size) {
    final minorPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.95)
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round;
    final minorShadow = Paint()
      ..color = const Color(0xFFD1D5DB)
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round;

    for (var i = 1; i < 6; i++) {
      final x = size.width * i / 6;
      canvas.drawLine(Offset(x, size.height * 0.08), Offset(x, size.height * 0.92), minorShadow);
      canvas.drawLine(Offset(x, size.height * 0.08), Offset(x, size.height * 0.92), minorPaint);
    }
    for (var i = 1; i < 5; i++) {
      final y = size.height * i / 5;
      canvas.drawLine(Offset(size.width * 0.06, y), Offset(size.width * 0.94, y), minorShadow);
      canvas.drawLine(Offset(size.width * 0.06, y), Offset(size.width * 0.94, y), minorPaint);
    }

    final majorBase = Paint()
      ..color = const Color(0xFFEAB308).withValues(alpha: 0.28)
      ..strokeWidth = 16
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    final majorLine = Paint()
      ..color = const Color(0xFFFFD34D)
      ..strokeWidth = 8
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    final arterial = Path()
      ..moveTo(size.width * 0.05, size.height * 0.34)
      ..lineTo(size.width * 0.30, size.height * 0.34)
      ..quadraticBezierTo(size.width * 0.48, size.height * 0.30, size.width * 0.56, size.height * 0.42)
      ..lineTo(size.width * 0.86, size.height * 0.42);
    canvas.drawPath(arterial, majorBase);
    canvas.drawPath(arterial, majorLine);

    final ring = Path()
      ..moveTo(size.width * 0.18, size.height * 0.20)
      ..lineTo(size.width * 0.78, size.height * 0.20)
      ..lineTo(size.width * 0.84, size.height * 0.76)
      ..lineTo(size.width * 0.24, size.height * 0.82)
      ..close();
    canvas.drawPath(ring, majorBase);
    canvas.drawPath(ring, majorLine);
  }

  void _drawRoute(Canvas canvas, List<Offset> offsets) {
    if (offsets.length < 2) return;
    final path = Path()..moveTo(offsets.first.dx, offsets.first.dy);
    for (var i = 1; i < offsets.length; i++) {
      final previous = offsets[i - 1];
      final current = offsets[i];
      final mid = Offset((previous.dx + current.dx) / 2, (previous.dy + current.dy) / 2);
      final control = Offset(mid.dx, i.isEven ? previous.dy : current.dy);
      path.quadraticBezierTo(control.dx, control.dy, current.dx, current.dy);
    }

    canvas.drawPath(
      path,
      Paint()
        ..color = Colors.white.withValues(alpha: 0.96)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 12
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );
    canvas.drawPath(
      path,
      Paint()
        ..color = const Color(0xFFF2C230)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 6
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );
  }

  void _drawMarker(Canvas canvas, Offset offset, _VirtualMapPoint point, bool isStart) {
    canvas.drawCircle(
      offset + const Offset(2, 5),
      15,
      Paint()
        ..color = Colors.black.withValues(alpha: 0.20)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8),
    );
    canvas.drawCircle(offset, 15, Paint()..color = Colors.white);
    canvas.drawCircle(offset, 11, Paint()..color = isStart ? const Color(0xFF34D399) : const Color(0xFFF2C230));

    _drawText(
      canvas,
      point.label,
      offset - const Offset(5, 8),
      const TextStyle(
        color: Color(0xFF111827),
        fontSize: 12,
        fontWeight: FontWeight.w900,
      ),
      maxWidth: 26,
    );

    final labelRect = Rect.fromLTWH(offset.dx + 18, offset.dy - 18, 150, 36);
    canvas.drawRRect(
      RRect.fromRectAndRadius(labelRect, const Radius.circular(9)),
      Paint()..color = Colors.white.withValues(alpha: 0.94),
    );
    _drawText(
      canvas,
      point.name.isEmpty ? '站点 ${point.label}' : point.name,
      labelRect.topLeft + const Offset(8, 5),
      const TextStyle(
        color: Color(0xFF111827),
        fontSize: 12,
        fontWeight: FontWeight.w800,
      ),
      maxWidth: labelRect.width - 16,
    );
    if (point.category.isNotEmpty) {
      _drawText(
        canvas,
        point.category,
        labelRect.topLeft + const Offset(8, 20),
        const TextStyle(
          color: Color(0xFF6B7280),
          fontSize: 10,
          fontWeight: FontWeight.w600,
        ),
        maxWidth: labelRect.width - 16,
      );
    }
  }

  void _drawMapBadges(Canvas canvas, Size size) {
    final title = city.trim().isEmpty ? '虚拟城市路线' : '$city虚拟路线';
    _drawBadge(canvas, Offset(14, 14), title, const Color(0xFF102332));
    _drawBadge(canvas, Offset(14, size.height - 40), sourceLabel, const Color(0xFF334155));
  }

  void _drawBadge(Canvas canvas, Offset offset, String text, Color color) {
    final painter = TextPainter(
      text: TextSpan(
        text: text,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 12,
          fontWeight: FontWeight.w800,
        ),
      ),
      textDirection: TextDirection.ltr,
      maxLines: 1,
    )..layout(maxWidth: 220);
    final rect = Rect.fromLTWH(offset.dx, offset.dy, painter.width + 22, 28);
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(999)),
      Paint()..color = color.withValues(alpha: 0.92),
    );
    painter.paint(canvas, offset + const Offset(11, 6));
  }

  void _drawText(Canvas canvas, String text, Offset offset, TextStyle style, {required double maxWidth}) {
    final painter = TextPainter(
      text: TextSpan(text: text, style: style),
      textDirection: TextDirection.ltr,
      maxLines: 1,
      ellipsis: '…',
    )..layout(maxWidth: maxWidth);
    painter.paint(canvas, offset);
  }

  @override
  bool shouldRepaint(covariant _VirtualRouteMapPainter oldDelegate) {
    return oldDelegate.markers != markers ||
        oldDelegate.routeLine != routeLine ||
        oldDelegate.city != city ||
        oldDelegate.sourceLabel != sourceLabel;
  }
}

class _Projection {
  final double minLat;
  final double maxLat;
  final double minLng;
  final double maxLng;
  final Size size;

  const _Projection({
    required this.minLat,
    required this.maxLat,
    required this.minLng,
    required this.maxLng,
    required this.size,
  });

  factory _Projection.fromPoints(List<_VirtualMapPoint> points, Size size) {
    final lats = points.map((point) => point.latitude).toList();
    final lngs = points.map((point) => point.longitude).toList();
    final minLat = lats.reduce(math.min);
    final maxLat = lats.reduce(math.max);
    final minLng = lngs.reduce(math.min);
    final maxLng = lngs.reduce(math.max);
    final latPad = math.max((maxLat - minLat).abs() * 0.22, 0.006);
    final lngPad = math.max((maxLng - minLng).abs() * 0.22, 0.006);
    return _Projection(
      minLat: minLat - latPad,
      maxLat: maxLat + latPad,
      minLng: minLng - lngPad,
      maxLng: maxLng + lngPad,
      size: size,
    );
  }

  Offset offsetOf(_VirtualMapPoint point) {
    final lngSpan = math.max(maxLng - minLng, 0.0001);
    final latSpan = math.max(maxLat - minLat, 0.0001);
    final x = ((point.longitude - minLng) / lngSpan).clamp(0.08, 0.92);
    final y = (1 - ((point.latitude - minLat) / latSpan)).clamp(0.12, 0.88);
    return Offset(size.width * x, size.height * y);
  }
}
