import 'package:flutter/material.dart';

import 'tianditu_route_map.dart';
import 'virtual_route_map.dart';

class RouteMapLabels {
  final String mapLabel;
  final String sourceLabel;
  final String coordinateLabel;
  final String routeLineLabel;

  const RouteMapLabels({
    required this.mapLabel,
    required this.sourceLabel,
    required this.coordinateLabel,
    required this.routeLineLabel,
  });
}

class RouteMapView extends StatelessWidget {
  static const bool useTianditu = bool.fromEnvironment('USE_TDT_MAP');

  final Map<String, dynamic> preview;
  final String city;

  const RouteMapView({
    super.key,
    required this.preview,
    required this.city,
  });

  static bool get isTiandituActive => useTianditu && TiandituRouteMap.isConfigured;

  static RouteMapLabels labels(Map<String, dynamic> preview) {
    final provider = preview['provider']?.toString() ?? 'local';
    final coordinateSource = preview['coordinate_source']?.toString() ?? '';
    final polylineSource = preview['polyline_source']?.toString() ?? '';

    if (!useTianditu) {
      return const RouteMapLabels(
        mapLabel: '虚拟地图',
        sourceLabel: '本地POI数据',
        coordinateLabel: '本地POI坐标',
        routeLineLabel: '虚拟路网轨迹',
      );
    }

    final sourceLabel = provider == 'tdt'
        ? '天地图数据'
        : (TiandituRouteMap.isConfigured ? '本地POI + 天地图底图' : '本地预览');
    final coordinateLabel = coordinateSource.startsWith('tdt')
        ? '天地图定位POI'
        : (TiandituRouteMap.isConfigured ? '本地POI坐标' : '本地预览坐标');
    final routeLineLabel = polylineSource == 'tdt_drive'
        ? '天地图驾车轨迹'
        : (polylineSource == 'tdt_drive_mixed' ? '部分驾车轨迹' : '本地近似轨迹');

    return RouteMapLabels(
      mapLabel: TiandituRouteMap.isConfigured ? '天地图底图' : '虚拟地图',
      sourceLabel: sourceLabel,
      coordinateLabel: coordinateLabel,
      routeLineLabel: routeLineLabel,
    );
  }

  @override
  Widget build(BuildContext context) {
    final virtual = VirtualRouteMap(
      preview: preview,
      city: city,
    );

    if (!isTiandituActive) {
      return virtual;
    }

    return TiandituRouteMap(
      preview: preview,
      fallback: virtual,
    );
  }
}
