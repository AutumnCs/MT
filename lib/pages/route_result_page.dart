import 'package:flutter/material.dart';

import '../models/route_models.dart';
import '../services/route_api_service.dart';

class RouteResultPage extends StatefulWidget {
  final RouteResponse routeResponse;
  final String originalQuery;

  const RouteResultPage({
    super.key,
    required this.routeResponse,
    required this.originalQuery,
  });

  @override
  State<RouteResultPage> createState() => _RouteResultPageState();
}

class _RouteResultPageState extends State<RouteResultPage> {
  final TextEditingController _modifyController = TextEditingController();
  bool _isLoading = false;
  String? _loadingMessage;

  @override
  void dispose() {
    _modifyController.dispose();
    super.dispose();
  }

  Future<void> _modifyRoute() async {
    final query = _modifyController.text.trim();
    if (query.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('请输入你想调整的内容'),
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }

    setState(() {
      _isLoading = true;
      _loadingMessage = '正在分析修改需求...';
    });

    await Future.delayed(const Duration(milliseconds: 600));
    if (!mounted) {
      return;
    }

    setState(() => _loadingMessage = '正在重新生成路线...');

    try {
      final request = ModifyRequest(
        query: query,
        originalQuery: widget.originalQuery,
        currentRoute: widget.routeResponse.toJson(),
      );

      final apiService = RouteApiService();
      final newRouteResponse = await apiService.modifyRoute(request);

      if (!mounted) {
        return;
      }

      setState(() => _isLoading = false);
      _modifyController.clear();

      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (context) => RouteResultPage(
            routeResponse: newRouteResponse,
            originalQuery: widget.originalQuery,
          ),
        ),
      );
    } catch (e) {
      if (!mounted) {
        return;
      }

      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('修改路线失败：$e'),
          behavior: SnackBarBehavior.floating,
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final route = widget.routeResponse;

    return Scaffold(
      body: Stack(
        children: [
          Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0xFFFFF3C4), Color(0xFFF6F7FB), Color(0xFFEEF2F9)],
              ),
            ),
            child: SafeArea(
              child: Column(
                children: [
                  _buildHeader(context),
                  Expanded(
                    child: ListView(
                      padding: const EdgeInsets.all(20),
                      children: [
                        _buildSummaryCard(route),
                        const SizedBox(height: 18),
                        _buildStrategyCard(route),
                        const SizedBox(height: 18),
                        _buildRouteTimeline(route),
                        const SizedBox(height: 18),
                        _buildExplanationCard(route),
                        const SizedBox(height: 18),
                        _buildModifyCard(),
                        const SizedBox(height: 18),
                        _buildActions(context),
                        const SizedBox(height: 20),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          if (_isLoading) _buildLoadingOverlay(),
        ],
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.arrow_back_ios_new, color: Color(0xFF111827)),
            onPressed: () => Navigator.pop(context),
          ),
          const Expanded(
            child: Text(
              '路线规划结果',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: Color(0xFF111827),
              ),
            ),
          ),
          const SizedBox(width: 48),
        ],
      ),
    );
  }

  Widget _buildSummaryCard(RouteResponse route) {
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFFE27A), Color(0xFFFFF3C4)],
        ),
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(
            color: Color.fromRGBO(157, 122, 22, 0.12),
            blurRadius: 24,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            route.title,
            style: const TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w800,
              color: Color(0xFF111827),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            route.summary,
            style: const TextStyle(
              fontSize: 15,
              color: Color(0xFF4B5563),
              height: 1.55,
            ),
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              _buildStatItem(Icons.payments_outlined, '¥${route.totalCost}', '预算'),
              _buildStatItem(Icons.access_time, '${route.totalDuration} 分钟', '时长'),
              _buildStatItem(Icons.straighten, '${route.totalDistance.toStringAsFixed(1)} km', '距离'),
              _buildStatItem(Icons.place_outlined, '${route.poiCount} 个', '站点'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatItem(IconData icon, String value, String label) {
    return Expanded(
      child: Column(
        children: [
          Icon(icon, size: 18, color: const Color(0xFF6B7280)),
          const SizedBox(height: 4),
          Text(
            value,
            style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: Color(0xFF111827),
            ),
            textAlign: TextAlign.center,
          ),
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              color: Color(0xFF6B7280),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStrategyCard(RouteResponse route) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(
            color: Color.fromRGBO(15, 23, 42, 0.06),
            blurRadius: 24,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: BoxDecoration(
              color: const Color(0xFFFEF3C7),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              route.strategyType ?? '稳妥方案',
              style: const TextStyle(
                color: Color(0xFFD97706),
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              route.coveredTypes.isEmpty ? '已完成路线组合' : '覆盖：${route.coveredTypes.join(' / ')}',
              style: const TextStyle(
                fontSize: 14,
                color: Color(0xFF4B5563),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRouteTimeline(RouteResponse route) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(
            color: Color.fromRGBO(15, 23, 42, 0.06),
            blurRadius: 24,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '路线站点',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: Color(0xFF111827),
            ),
          ),
          const SizedBox(height: 16),
          if (route.stops.isEmpty)
            const Text(
              '当前没有可展示的站点，建议修改需求后再试一次。',
              style: TextStyle(color: Color(0xFF6B7280)),
            )
          else
            ...List.generate(
              route.stops.length,
              (index) => _buildStopCard(route.stops[index], index, route.stops.length),
            ),
        ],
      ),
    );
  }

  Widget _buildStopCard(RouteStop stop, int index, int total) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: const Color(0xFFF2C230),
                  borderRadius: BorderRadius.circular(12),
                ),
                alignment: Alignment.center,
                child: Text(
                  '${index + 1}',
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF111827),
                  ),
                ),
              ),
              if (index < total - 1)
                Container(
                  width: 2,
                  height: 120,
                  color: const Color(0xFFE5E7EB),
                ),
            ],
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFFF8FAFC),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFE5E7EB)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          stop.poi.name,
                          style: const TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.w700,
                            color: Color(0xFF111827),
                          ),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFEF3C7),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          stop.poi.categoryLabel,
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                            color: Color(0xFFD97706),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 12,
                    runSpacing: 6,
                    children: [
                      _meta(Icons.access_time, '${stop.arrivalTime} - ${stop.departureTime}'),
                      _meta(Icons.timer_outlined, '停留 ${stop.stayMinutes} 分钟'),
                      _meta(Icons.star, '${stop.poi.rating}'),
                      _meta(Icons.payments_outlined, stop.poi.price > 0 ? '¥${stop.poi.price}' : '免费'),
                    ],
                  ),
                  if (stop.travelFromPrevious != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      '上一站到这里：${stop.travelFromPrevious!['mode']} · ${stop.travelFromPrevious!['distance_km']} km · ${stop.travelFromPrevious!['duration_min']} 分钟',
                      style: const TextStyle(
                        fontSize: 12,
                        color: Color(0xFF6B7280),
                      ),
                    ),
                  ],
                  const SizedBox(height: 10),
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF0F9FF),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.lightbulb_outline, size: 16, color: Color(0xFF0369A1)),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            stop.reason,
                            style: const TextStyle(
                              fontSize: 13,
                              color: Color(0xFF0369A1),
                              height: 1.4,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (stop.riskAlert != null) ...[
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFEF3C7),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(Icons.warning_amber_outlined, size: 16, color: Color(0xFFD97706)),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              stop.riskAlert!,
                              style: const TextStyle(
                                fontSize: 13,
                                color: Color(0xFFD97706),
                                height: 1.4,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _meta(IconData icon, String text) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: const Color(0xFF6B7280)),
        const SizedBox(width: 4),
        Text(
          text,
          style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
        ),
      ],
    );
  }

  Widget _buildExplanationCard(RouteResponse route) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(
            color: Color.fromRGBO(15, 23, 42, 0.06),
            blurRadius: 24,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '路线说明',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: Color(0xFF111827),
            ),
          ),
          const SizedBox(height: 12),
          Text(
            route.routeExplanation,
            style: const TextStyle(
              fontSize: 14,
              color: Color(0xFF374151),
              height: 1.6,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildModifyCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(
            color: Color.fromRGBO(15, 23, 42, 0.06),
            blurRadius: 24,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '再调整一下',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: Color(0xFF111827),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _modifyController,
            minLines: 2,
            maxLines: 4,
            decoration: InputDecoration(
              hintText: '比如：太远了，换近一点；预算降到 150；不想吃辣',
              filled: true,
              fillColor: const Color(0xFFF8FAFC),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: BorderSide.none,
              ),
              contentPadding: const EdgeInsets.all(16),
            ),
          ),
          const SizedBox(height: 14),
          FilledButton(
            onPressed: _isLoading ? null : _modifyRoute,
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(48),
              backgroundColor: const Color(0xFF111827),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            ),
            child: const Text('重新调整路线'),
          ),
        ],
      ),
    );
  }

  Widget _buildActions(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton(
            onPressed: () => Navigator.pop(context),
            style: OutlinedButton.styleFrom(
              minimumSize: const Size.fromHeight(48),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            ),
            child: const Text('返回修改需求'),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: FilledButton(
            onPressed: () => Navigator.pop(context),
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(48),
              backgroundColor: const Color(0xFFF2C230),
              foregroundColor: const Color(0xFF111827),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            ),
            child: const Text('重新规划'),
          ),
        ),
      ],
    );
  }

  Widget _buildLoadingOverlay() {
    return Container(
      color: Colors.black.withValues(alpha: 0.28),
      child: Center(
        child: Container(
          width: 220,
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(24),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircularProgressIndicator(),
              const SizedBox(height: 16),
              Text(
                _loadingMessage ?? '处理中...',
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
