import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/route_models.dart';
import '../services/route_api_service.dart';
import '../widgets/route_map_view.dart';
import 'clarification_page.dart';
import 'knowledge_explanation_page.dart';

class RouteResultPage extends StatefulWidget {
  final RouteResponse routeResponse;
  final String originalQuery;
  final String currentCity;

  const RouteResultPage({
    super.key,
    required this.routeResponse,
    required this.originalQuery,
    required this.currentCity,
  });

  @override
  State<RouteResultPage> createState() => _RouteResultPageState();
}

class _RouteResultPageState extends State<RouteResultPage> {
  static const bool _showRouteMapPanel = bool.fromEnvironment('SHOW_ROUTE_MAP_PANEL');

  final TextEditingController _modifyController = TextEditingController();
  bool _isLoading = false;
  String? _loadingMessage;
  bool _isFavorited = false;
  int _selectedStrategyIndex = 0;

  static const List<String> _quickModifySuggestions = [
    '太贵了',
    '更轻松一点',
    '不要排队',
    '再紧凑一点',
    '多一点拍照点',
    '换成室内点',
  ];

  @override
  void dispose() {
    _modifyController.dispose();
    super.dispose();
  }

  void _applyQuickModify(String text) {
    setState(() {
      _modifyController.text = text;
      _modifyController.selection = TextSelection.fromPosition(
        TextPosition(offset: text.length),
      );
    });
  }

  String _buildShareText(RouteResponse route) {
    final buffer = StringBuffer()
      ..writeln(route.title)
      ..writeln(route.summary)
      ..writeln('城市：${widget.currentCity}')
      ..writeln('预算：¥${route.totalCost}  时长：${route.totalDuration} 分钟  距离：${route.totalDistance.toStringAsFixed(1)} km')
      ..writeln('站点数：${route.poiCount}');

    if (route.intentSummary != null && route.intentSummary!.trim().isNotEmpty) {
      buffer.writeln('系统理解：${route.intentSummary}');
    }
    if (route.routeOptions.isNotEmpty) {
      buffer.writeln('候选方案：');
      for (final option in route.routeOptions.take(3)) {
        buffer.writeln('- ${option.strategyType} / ¥${option.totalCost} / ${option.totalDuration} 分钟 / ${option.poiCount} 站');
      }
    }
    if (route.stops.isNotEmpty) {
      buffer.writeln('站点：${route.stops.map((stop) => stop.poi.name).join(' → ')}');
    }
    return buffer.toString().trim();
  }

  Future<void> _copyRouteSummary() async {
    final route = _activeRoute();
    await Clipboard.setData(ClipboardData(text: _buildShareText(route)));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('路线摘要已复制，可以直接发给朋友'),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  void _toggleFavorite() {
    setState(() {
      _isFavorited = !_isFavorited;
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(_isFavorited ? '已收藏当前方案' : '已取消收藏'),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  void _openKnowledgePage() {
    final route = _activeRoute();
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => KnowledgeExplanationPage(
          routeResponse: route,
          originalQuery: widget.originalQuery,
        ),
      ),
    );
  }

  void _selectStrategy(int index, RouteOption option) {
    setState(() {
      _selectedStrategyIndex = index;
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('已选择${option.strategyType}'),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  Future<void> _resolveClarification(String choice) async {
    setState(() {
      _isLoading = true;
      _loadingMessage = '正在补全你的意图...';
    });

    await Future.delayed(const Duration(milliseconds: 240));
    if (!mounted) return;

    try {
      final apiService = RouteApiService();
      final query = '${widget.originalQuery}，$choice';
      final request = RouteRequest(
        query: query,
        preferences: const [],
        city: widget.currentCity,
      );
      final newRouteResponse = await apiService.generateRoute(request);

      if (!mounted) return;
      setState(() => _isLoading = false);
      Navigator.pushReplacement(
        context,
        _buildRouteTransition(
          RouteResultPage(
            routeResponse: newRouteResponse,
            originalQuery: widget.originalQuery,
            currentCity: widget.currentCity,
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('补充意图失败：$e'),
          behavior: SnackBarBehavior.floating,
          backgroundColor: Colors.red,
        ),
      );
    }
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
      _loadingMessage = '正在理解你的修改...';
    });

    await Future.delayed(const Duration(milliseconds: 280));
    if (!mounted) return;

    setState(() => _loadingMessage = '正在重新生成路线...');

    try {
      final request = ModifyRequest(
        query: query,
        originalQuery: widget.originalQuery,
        currentRoute: _activeRoute().toJson(),
      );

      final apiService = RouteApiService();
      final newRouteResponse = await apiService.modifyRoute(request);

      if (!mounted) return;
      setState(() => _isLoading = false);
      _modifyController.clear();

      if (newRouteResponse.clarificationNeeded) {
        Navigator.push(
          context,
          _buildRouteTransition(
            ClarificationPage(
              clarificationResponse: newRouteResponse,
              originalQuery: widget.originalQuery,
              currentCity: widget.currentCity,
              currentRoute: _activeRoute().toJson(),
              isModification: true,
            ),
          ),
        );
        return;
      }

      Navigator.pushReplacement(
        context,
        _buildRouteTransition(
          RouteResultPage(
            routeResponse: newRouteResponse,
            originalQuery: widget.originalQuery,
            currentCity: widget.currentCity,
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
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

  PageRouteBuilder<void> _buildRouteTransition(Widget child) {
    return PageRouteBuilder<void>(
      transitionDuration: const Duration(milliseconds: 260),
      reverseTransitionDuration: const Duration(milliseconds: 220),
      pageBuilder: (context, animation, secondaryAnimation) => child,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        final fade = CurvedAnimation(parent: animation, curve: Curves.easeOutCubic);
        final slide = Tween<Offset>(
          begin: const Offset(0, 0.03),
          end: Offset.zero,
        ).animate(fade);
        return FadeTransition(
          opacity: fade,
          child: SlideTransition(position: slide, child: child),
        );
      },
    );
  }

  RouteOption? _selectedRouteOption(RouteResponse route) {
    if (route.routeOptions.isEmpty) return null;
    final safeIndex = _selectedStrategyIndex.clamp(0, route.routeOptions.length - 1).toInt();
    return route.routeOptions[safeIndex];
  }

  RouteResponse _activeRoute() {
    final base = widget.routeResponse;
    final option = _selectedRouteOption(base);
    if (option == null || option.routeStops.isEmpty) {
      return base;
    }

    return RouteResponse(
      title: base.title,
      summary: base.summary,
      totalCost: option.totalCost,
      totalDuration: option.totalDuration,
      totalDistance: option.totalDistance,
      poiCount: option.poiCount,
      coveredTypes: option.coveredTypes.isNotEmpty ? option.coveredTypes : base.coveredTypes,
      stops: option.routeStops,
      routeExplanation: base.routeExplanation,
      strategyType: option.strategyType,
      routeScore: option.routeScore,
      travelTimeRatio: base.travelTimeRatio,
      warnings: base.warnings,
      routeOptions: base.routeOptions,
      originalQuery: base.originalQuery,
      intentSummary: base.intentSummary,
      parseSource: base.parseSource,
      appliedPreferences: base.appliedPreferences,
      generatedAt: base.generatedAt,
      mapPreview: option.mapPreview ?? base.mapPreview,
      trace: base.trace,
      clarificationNeeded: base.clarificationNeeded,
      clarificationQuestion: base.clarificationQuestion,
      clarificationOptions: base.clarificationOptions,
      clarificationReason: base.clarificationReason,
    );
  }

  @override
  Widget build(BuildContext context) {
    final route = _activeRoute();
    return Scaffold(
      body: Stack(
        children: [
          Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0xFFECF4F8), Color(0xFFF6F7FB), Color(0xFFEEF2F9)],
              ),
            ),
            child: SafeArea(
              child: Column(
                children: [
                  _buildHeader(context, route),
                  Expanded(
                    child: ListView(
                      padding: const EdgeInsets.fromLTRB(18, 14, 18, 18),
                      children: [
                        if (_showRouteMapPanel) ...[
                          _buildMapHero(route),
                          const SizedBox(height: 16),
                        ],
                        _buildSummaryCard(route),
                        const SizedBox(height: 14),
                        _buildSystemUnderstandingCard(route),
                        if (route.clarificationNeeded) ...[
                          const SizedBox(height: 14),
                          _buildClarificationCard(route),
                        ],
                        const SizedBox(height: 14),
                        _buildStrategyScroller(route),
                        if (route.warnings.isNotEmpty) ...[
                          const SizedBox(height: 14),
                          _buildWarningCard(route),
                        ],
                        const SizedBox(height: 14),
                        if (route.stops.isNotEmpty) _buildTimeline(route),
                        const SizedBox(height: 14),
                        _buildDiagnosticsCard(route),
                        const SizedBox(height: 120),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          _buildBottomRefineBar(route),
          if (_isLoading) _buildLoadingOverlay(),
        ],
      ),
    );
  }

  Widget _buildHeader(BuildContext context, RouteResponse route) {
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
              '路线工作台',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w800,
                color: Color(0xFF111827),
              ),
            ),
          ),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              IconButton(
                tooltip: '分享',
                icon: const Icon(Icons.share_outlined, color: Color(0xFF111827)),
                onPressed: _copyRouteSummary,
              ),
              IconButton(
                tooltip: '收藏',
                icon: Icon(
                  _isFavorited ? Icons.bookmark : Icons.bookmark_outline,
                  color: const Color(0xFF111827),
                ),
                onPressed: _toggleFavorite,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMapHero(RouteResponse route) {
    final preview = route.mapPreview ?? const <String, dynamic>{};
    final width = MediaQuery.sizeOf(context).width;
    final mapHeight = width >= 900 ? 320.0 : 220.0;
    final mapLabels = RouteMapView.labels(preview);

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF102332),
        borderRadius: BorderRadius.circular(30),
        boxShadow: const [
          BoxShadow(
            color: Color.fromRGBO(15, 23, 42, 0.20),
            blurRadius: 28,
            offset: Offset(0, 14),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  route.title,
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.w900,
                    color: Colors.white,
                    height: 1.1,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  mapLabels.mapLabel,
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            route.summary,
            style: TextStyle(
              fontSize: 14,
              color: Colors.white.withValues(alpha: 0.86),
              height: 1.55,
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _buildDarkTag('¥${route.totalCost} 预算'),
              _buildDarkTag('${route.totalDuration} 分钟'),
              _buildDarkTag('${route.poiCount} 个站点'),
              _buildDarkTag(mapLabels.sourceLabel),
              _buildDarkTag(mapLabels.coordinateLabel),
              _buildDarkTag(mapLabels.routeLineLabel),
            ],
          ),
          const SizedBox(height: 14),
          _buildRouteMiniPlan(route),
          const SizedBox(height: 14),
          Stack(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(22),
                child: SizedBox(
                  height: mapHeight,
                  width: double.infinity,
                  child: RouteMapView(
                    preview: preview,
                    city: widget.currentCity,
                  ),
                ),
              ),
              Positioned(
                top: 10,
                right: 10,
                child: TextButton.icon(
                  onPressed: () => _openMapPreviewSheet(route),
                  style: TextButton.styleFrom(
                    foregroundColor: const Color(0xFF111827),
                    backgroundColor: Colors.white.withValues(alpha: 0.92),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
                  ),
                  icon: const Icon(Icons.open_in_full, size: 16),
                  label: const Text('展开'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildRouteMiniPlan(RouteResponse route) {
    final stopNames = route.stops.map((stop) => stop.poi.name).take(4).toList();
    final remaining = route.stops.length - stopNames.length;
    final pathText = [
      ...stopNames,
      if (remaining > 0) '等 $remaining 站',
    ].join(' → ');

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white.withValues(alpha: 0.14)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '路线安排',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w800,
              color: Colors.white,
            ),
          ),
          if (pathText.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              pathText,
              style: TextStyle(
                fontSize: 13,
                color: Colors.white.withValues(alpha: 0.88),
                height: 1.45,
              ),
            ),
          ],
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: route.stops.take(3).map((stop) {
              final time = stop.arrivalTime.isNotEmpty ? '${stop.arrivalTime} 到达' : '${stop.stayMinutes} 分钟';
              return _buildDarkTag('$time · ${stop.poi.categoryLabel}');
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildDarkTag(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: Colors.white.withValues(alpha: 0.16)),
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w700,
          color: Colors.white.withValues(alpha: 0.95),
        ),
      ),
    );
  }

  Widget _buildSummaryCard(RouteResponse route) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.97),
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(
            color: Color.fromRGBO(15, 23, 42, 0.06),
            blurRadius: 20,
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
              fontSize: 23,
              fontWeight: FontWeight.w900,
              color: Color(0xFF111827),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            route.summary,
            style: const TextStyle(
              fontSize: 14,
              color: Color(0xFF4B5563),
              height: 1.55,
            ),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _buildSummaryTag('城市：${widget.currentCity}'),
              if (route.strategyType != null) _buildSummaryTag('策略：${route.strategyType}'),
              if (route.routeScore != null) _buildSummaryTag('评分：${(route.routeScore! * 100).round()}'),
              _buildSummaryTag('预算：¥${route.totalCost}'),
              _buildSummaryTag('时长：${route.totalDuration} 分钟'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryTag(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Text(
        text,
        style: const TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w700,
          color: Color(0xFF8A5A00),
        ),
      ),
    );
  }

  Widget _buildSystemUnderstandingCard(RouteResponse route) {
    final parseSource = route.parseSource ?? 'unknown';
    final sourceLabel = switch (parseSource) {
      'llm' => 'LLM 理解',
      'fallback' => '规则回退',
      _ => '系统理解',
    };
    final sourceColor = switch (parseSource) {
      'llm' => const Color(0xFF2563EB),
      'fallback' => const Color(0xFF6B7280),
      _ => const Color(0xFFD97706),
    };

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.97),
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(
            color: Color.fromRGBO(15, 23, 42, 0.06),
            blurRadius: 20,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  '系统理解',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF111827),
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: sourceColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  sourceLabel,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: sourceColor,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            route.intentSummary ??
                '系统已将你的需求整理成可执行路线。你可以在下方继续微调预算、节奏、偏好或转场方式。',
            style: const TextStyle(
              fontSize: 14,
              color: Color(0xFF374151),
              height: 1.55,
            ),
          ),
          if (route.appliedPreferences.isNotEmpty) ...[
            const SizedBox(height: 14),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: route.appliedPreferences.map((item) => _buildSummaryTag('偏好：$item')).toList(),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildClarificationCard(RouteResponse route) {
    final question = route.clarificationQuestion ?? '请补充一点信息';
    final reason = route.clarificationReason ?? '当前需求还不够明确，补一个最关键的问题后再继续生成。';
    final options = route.clarificationOptions;

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFFF7D6), Color(0xFFFFFCF0)],
        ),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: const Color(0xFFF2C230)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: const Color(0xFFF2C230).withValues(alpha: 0.20),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(Icons.help_outline, color: Color(0xFF8A5A00)),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Text(
                  '先补一个关键点',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: Color(0xFF111827)),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            question,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w800,
              color: Color(0xFF111827),
              height: 1.45,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            reason,
            style: const TextStyle(
              fontSize: 13,
              color: Color(0xFF6B7280),
              height: 1.5,
            ),
          ),
          if (options.isNotEmpty) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: options
                  .map(
                    (option) => ActionChip(
                      label: Text(option),
                      onPressed: () => _resolveClarification(option),
                      backgroundColor: Colors.white,
                      side: const BorderSide(color: Color(0xFFF2C230)),
                      labelStyle: const TextStyle(
                        color: Color(0xFF8A5A00),
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                      ),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(999),
                      ),
                    ),
                  )
                  .toList(),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStrategyScroller(RouteResponse route) {
    final options = route.routeOptions.isNotEmpty
        ? route.routeOptions
        : [
            RouteOption(
              strategyType: route.strategyType ?? '稳妥方案',
              routeScore: route.routeScore ?? 0,
              totalCost: route.totalCost,
              totalDuration: route.totalDuration,
              totalDistance: route.totalDistance,
              poiCount: route.poiCount,
              stops: route.stops.map((stop) => stop.poi.name).toList(),
              routeStops: route.stops,
              coveredTypes: route.coveredTypes,
              mapPreview: route.mapPreview,
            ),
          ];

    final safeIndex = options.isEmpty
        ? 0
        : _selectedStrategyIndex.clamp(0, options.length - 1).toInt();
    final selectedOption = options.isEmpty ? null : options[safeIndex];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '候选方案',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: Color(0xFF111827)),
        ),
        const SizedBox(height: 10),
        SizedBox(
          height: 150,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemBuilder: (context, index) {
              final option = options[index];
              final selected = index == safeIndex;
              return InkWell(
                onTap: () => _selectStrategy(index, option),
                borderRadius: BorderRadius.circular(22),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 180),
                  curve: Curves.easeOutCubic,
                  width: 180,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.97),
                    borderRadius: BorderRadius.circular(22),
                    border: Border.all(
                      color: selected ? const Color(0xFFF2C230) : const Color(0xFFE5E7EB),
                      width: selected ? 1.6 : 1,
                    ),
                    boxShadow: const [
                      BoxShadow(
                        color: Color.fromRGBO(15, 23, 42, 0.06),
                        blurRadius: 18,
                        offset: Offset(0, 8),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              option.strategyType,
                              style: const TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w800,
                                color: Color(0xFF111827),
                              ),
                            ),
                          ),
                          if (selected)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: const Color(0xFFF2C230),
                                borderRadius: BorderRadius.circular(999),
                              ),
                              child: const Text(
                                '当前',
                                style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800),
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        selected ? '当前展示的主方案' : '点击查看这个方案',
                        style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                      ),
                      const Spacer(),
                      Text(
                        '¥${option.totalCost} · ${option.totalDuration} 分钟',
                        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${option.poiCount} 站 · ${option.totalDistance.toStringAsFixed(1)} km',
                        style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                      ),
                    ],
                  ),
                ),
              );
            },
            separatorBuilder: (_, _) => const SizedBox(width: 12),
            itemCount: options.length,
          ),
        ),
        if (selectedOption != null) ...[
          const SizedBox(height: 10),
          Text(
            '当前选择：${selectedOption.strategyType}',
            style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280), fontWeight: FontWeight.w600),
          ),
        ],
      ],
    );
  }

  Widget _buildTimeline(RouteResponse route) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '路线站点',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: Color(0xFF111827)),
        ),
        const SizedBox(height: 12),
        ...route.stops.asMap().entries.map((entry) {
          final index = entry.key;
          final stop = entry.value;
          final segment = stop.travelFromPrevious;
          return Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Column(
                  children: [
                    Container(
                      width: 30,
                      height: 30,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: const Color(0xFFF2C230),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        '${index + 1}',
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w800,
                          color: Color(0xFF111827),
                        ),
                      ),
                    ),
                    if (index != route.stops.length - 1)
                      Container(
                        width: 2,
                        height: 92,
                        margin: const EdgeInsets.symmetric(vertical: 4),
                        color: const Color(0xFFE5E7EB),
                      ),
                  ],
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.98),
                      borderRadius: BorderRadius.circular(20),
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
                                  fontSize: 16,
                                  fontWeight: FontWeight.w800,
                                  color: Color(0xFF111827),
                                ),
                              ),
                            ),
                            Text(
                              stop.arrivalTime,
                              style: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.w900,
                                color: Color(0xFF111827),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Text(
                          stop.poi.address,
                          style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                        ),
                        const SizedBox(height: 10),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            _buildTimelineTag(stop.poi.categoryLabel),
                            _buildTimelineTag('${stop.stayMinutes} 分钟停留'),
                            _buildTimelineTag('¥${stop.poi.price}'),
                          ],
                        ),
                        const SizedBox(height: 10),
                        Text(
                          stop.reason,
                          style: const TextStyle(
                            fontSize: 13,
                            color: Color(0xFF374151),
                            height: 1.45,
                          ),
                        ),
                        if (segment != null) ...[
                          const SizedBox(height: 12),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                            decoration: BoxDecoration(
                              color: const Color(0xFFF8FAFC),
                              borderRadius: BorderRadius.circular(14),
                              border: Border.all(color: const Color(0xFFE5E7EB)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.directions_walk_outlined, size: 16, color: Color(0xFF6B7280)),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    _buildTravelLabel(segment),
                                    style: const TextStyle(fontSize: 12, color: Color(0xFF374151)),
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
        }),
      ],
    );
  }

  String _buildTravelLabel(Map<String, dynamic> segment) {
    final duration = segment['duration']?.toString();
    final distance = segment['distance']?.toString();
    final label = segment['label']?.toString();
    final provider = segment['provider']?.toString();
    final parts = <String>[];
    if (label != null && label.isNotEmpty) parts.add(label);
    if (duration != null && duration.isNotEmpty) parts.add('$duration 分钟');
    if (distance != null && distance.isNotEmpty) parts.add('$distance km');
    if (provider != null && provider.isNotEmpty) {
      parts.add(provider == 'tdt' ? '天地图' : provider);
    }
    return parts.isEmpty ? '转场信息补充中' : parts.join(' · ');
  }

  Widget _buildTimelineTag(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          color: Color(0xFF6B7280),
        ),
      ),
    );
  }

  Widget _buildWarningCard(RouteResponse route) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.97),
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(
            color: Color.fromRGBO(15, 23, 42, 0.06),
            blurRadius: 20,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '路线提醒',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: Color(0xFF111827)),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: route.warnings.map((warning) => _buildSummaryTag(warning)).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildDiagnosticsCard(RouteResponse route) {
    final trace = route.trace ?? const <String, dynamic>{};
    final matched = List<String>.from(trace['matched_capabilities'] ?? const []);
    final clues = List<String>.from(trace['unclassified_clues'] ?? const []);
    final signals = List<String>.from(trace['recognized_signals'] ?? const []);

    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      collapsedBackgroundColor: Colors.white.withValues(alpha: 0.96),
      backgroundColor: Colors.white.withValues(alpha: 0.98),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      collapsedShape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      title: const Text(
        '路线诊断',
        style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: Color(0xFF111827)),
      ),
      subtitle: const Text(
        '查看解析来源、命中的能力和未归类片段',
        style: TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
      ),
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(18, 0, 18, 18),
          child: Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _buildSummaryTag('解析来源：${trace['parse_source'] ?? 'unknown'}'),
              _buildSummaryTag('命中能力：${matched.length}'),
              _buildSummaryTag('未归类：${clues.length}'),
              _buildSummaryTag('识别信号：${signals.length}'),
              if (trace['map_enabled'] == true) _buildSummaryTag('地图已联动'),
              if (trace['map_enabled'] != true) _buildSummaryTag('本地预览'),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildBottomRefineBar(RouteResponse route) {
    return Align(
      alignment: Alignment.bottomCenter,
      child: SafeArea(
        top: false,
        child: Container(
          padding: const EdgeInsets.fromLTRB(18, 14, 18, 16),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.98),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
            boxShadow: const [
              BoxShadow(
                color: Color.fromRGBO(15, 23, 42, 0.08),
                blurRadius: 24,
                offset: Offset(0, -6),
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: _quickModifySuggestions
                    .map(
                      (text) => ActionChip(
                        label: Text(text),
                        onPressed: () => _applyQuickModify(text),
                        backgroundColor: const Color(0xFFF8FAFC),
                        side: const BorderSide(color: Color(0xFFE5E7EB)),
                        labelStyle: const TextStyle(
                          color: Color(0xFF374151),
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
                      ),
                    )
                    .toList(),
              ),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.fromLTRB(12, 10, 10, 10),
                decoration: BoxDecoration(
                  color: const Color(0xFFF8FAFC),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: const Color(0xFFE5E7EB)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.edit_outlined, color: Color(0xFF6B7280), size: 18),
                    const SizedBox(width: 10),
                    Expanded(
                      child: TextField(
                        controller: _modifyController,
                        minLines: 1,
                        maxLines: 3,
                        textInputAction: TextInputAction.done,
                        onSubmitted: (_) => _modifyRoute(),
                        decoration: const InputDecoration(
                          hintText: '告诉我需要修改什么…',
                          hintStyle: TextStyle(color: Color(0xFF9CA3AF)),
                          border: InputBorder.none,
                          isDense: true,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    GestureDetector(
                      onTap: _modifyRoute,
                      child: Container(
                        width: 42,
                        height: 42,
                        decoration: BoxDecoration(
                          color: const Color(0xFFF2C230),
                          borderRadius: BorderRadius.circular(14),
                        ),
                        child: const Icon(Icons.send_rounded, color: Color(0xFF111827), size: 18),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: _BottomAction(
                      icon: Icons.bookmark_outline,
                      label: _isFavorited ? '已收藏' : '收藏',
                      onTap: _toggleFavorite,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: _BottomAction(
                      icon: Icons.share_outlined,
                      label: '分享',
                      onTap: _copyRouteSummary,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: _BottomAction(
                      icon: Icons.menu_book_outlined,
                      label: '解释逻辑',
                      onTap: _openKnowledgePage,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLoadingOverlay() {
    return Positioned.fill(
      child: Container(
        color: Colors.black.withValues(alpha: 0.12),
        child: Center(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.97),
              borderRadius: BorderRadius.circular(20),
              boxShadow: const [
                BoxShadow(
                  color: Color.fromRGBO(15, 23, 42, 0.12),
                  blurRadius: 28,
                  offset: Offset(0, 12),
                ),
              ],
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(strokeWidth: 2.4, color: Color(0xFFF2C230)),
                ),
                const SizedBox(width: 14),
                Text(
                  _loadingMessage ?? '正在处理中...',
                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _openMapPreviewSheet(RouteResponse route) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) {
        final preview = route.mapPreview ?? const <String, dynamic>{};
        final points = _extractMapPoints(preview);
        final mapLabels = RouteMapView.labels(preview);

        return DraggableScrollableSheet(
          initialChildSize: 0.82,
          minChildSize: 0.58,
          maxChildSize: 0.96,
          builder: (context, scrollController) {
            return Container(
              decoration: const BoxDecoration(
                color: Color(0xFFF6F7FB),
                borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
              ),
              child: SafeArea(
                top: false,
                child: ListView(
                  controller: scrollController,
                  padding: const EdgeInsets.all(20),
                  children: [
                    Row(
                      children: [
                        const Expanded(
                          child: Text(
                            '路线地图展开视图',
                            style: TextStyle(
                              fontSize: 20,
                              fontWeight: FontWeight.w800,
                              color: Color(0xFF111827),
                            ),
                          ),
                        ),
                        TextButton(
                          onPressed: () => Navigator.pop(context),
                          child: const Text('关闭'),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(26),
                      child: SizedBox(
                        height: 360,
                        child: RouteMapView(
                          preview: preview,
                          city: widget.currentCity,
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        _buildSummaryTag('节点 ${points.length}'),
                        _buildSummaryTag(mapLabels.mapLabel),
                        _buildSummaryTag(mapLabels.sourceLabel),
                      ],
                    ),
                    const SizedBox(height: 16),
                    ...points.map(
                      (point) => Container(
                        margin: const EdgeInsets.only(bottom: 12),
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(18),
                          border: Border.all(color: const Color(0xFFE5E7EB)),
                        ),
                        child: Row(
                          children: [
                            Container(
                              width: 30,
                              height: 30,
                              alignment: Alignment.center,
                              decoration: BoxDecoration(
                                color: const Color(0xFFF2C230),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Text(
                                point.label,
                                style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w800,
                                  color: Color(0xFF111827),
                                ),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    point.name,
                                    style: const TextStyle(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w700,
                                      color: Color(0xFF111827),
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    point.address,
                                    style: const TextStyle(
                                      fontSize: 12,
                                      color: Color(0xFF6B7280),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  List<_MapPreviewPoint> _extractMapPoints(Map<String, dynamic> preview) {
    final markers = List<Map<String, dynamic>>.from(preview['markers'] ?? const []);
    if (markers.isEmpty) return const [];

    return markers.asMap().entries.map((entry) {
      final marker = entry.value;
      return _MapPreviewPoint(
        label: '${marker['label'] ?? entry.key + 1}',
        name: marker['name']?.toString() ?? '',
        address: marker['address']?.toString() ?? '',
      );
    }).toList();
  }
}

class _BottomAction extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _BottomAction({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      child: Container(
        height: 52,
        decoration: BoxDecoration(
          color: const Color(0xFFF8FAFC),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: const Color(0xFFE5E7EB)),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 18, color: const Color(0xFF111827)),
            const SizedBox(width: 6),
            Text(
              label,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
            ),
          ],
        ),
      ),
    );
  }
}

class _MapPreviewPoint {
  final String label;
  final String name;
  final String address;

  const _MapPreviewPoint({
    required this.label,
    required this.name,
    required this.address,
  });
}
