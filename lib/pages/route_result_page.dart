import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/route_models.dart';
import '../services/route_api_service.dart';
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
    final route = widget.routeResponse;
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
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => KnowledgeExplanationPage(
          routeResponse: widget.routeResponse,
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
        content: Text('?????${option.strategyType}'),
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
        currentRoute: widget.routeResponse.toJson(),
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
              currentRoute: widget.routeResponse.toJson(),
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
                        _buildMapHero(route),
                        const SizedBox(height: 16),
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
    final points = _extractMapPoints(preview);
    final enabled = preview['enabled'] == true;
    final provider = preview['provider']?.toString() ?? 'local';

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
          Stack(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(22),
                child: AspectRatio(
                  aspectRatio: 16 / 10,
                  child: _RoutePreviewMapCanvas(
                    preview: preview,
                    points: points,
                    enabled: enabled,
                    provider: provider,
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
          const SizedBox(height: 14),
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
                  enabled ? '地图联动' : '本地预览',
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
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _buildDarkTag('¥${route.totalCost} 预算'),
              _buildDarkTag('${route.totalDuration} 分钟'),
              _buildDarkTag('${route.poiCount} 个站点'),
              _buildDarkTag(provider == 'amap' ? '高德数据' : '本地预览'),
            ],
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
              strategyType: route.strategyType ?? '????',
              routeScore: route.routeScore ?? 0,
              totalCost: route.totalCost,
              totalDuration: route.totalDuration,
              totalDistance: route.totalDistance,
              poiCount: route.poiCount,
              stops: route.stops.map((stop) => stop.poi.name).toList(),
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
          '????',
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
                                'Selected',
                                style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800),
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        selected ? '???????' : '????????',
                        style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                      ),
                      const Spacer(),
                      Text(
                        '?${option.totalCost} ? ${option.totalDuration} ??',
                        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF111827)),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${option.poiCount} ??? ? ${option.totalDistance.toStringAsFixed(1)} km',
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
            '?????${selectedOption.strategyType}',
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
    if (provider != null && provider.isNotEmpty) parts.add(provider == 'amap' ? '高德' : provider);
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
        final enabled = preview['enabled'] == true;
        final provider = preview['provider']?.toString() ?? 'local';

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
                        child: _RoutePreviewMapCanvas(
                          preview: preview,
                          points: points,
                          enabled: enabled,
                          provider: provider,
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        _buildSummaryTag('节点 ${points.length}'),
                        _buildSummaryTag(enabled ? '已联动地图' : '本地预览'),
                        _buildSummaryTag(provider == 'amap' ? '高德' : provider),
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

    final bounds = preview['bounds'];
    final minLat = (bounds is Map ? (bounds['min_latitude'] as num?)?.toDouble() : null) ?? 0.0;
    final maxLat = (bounds is Map ? (bounds['max_latitude'] as num?)?.toDouble() : null) ?? 0.0;
    final minLng = (bounds is Map ? (bounds['min_longitude'] as num?)?.toDouble() : null) ?? 0.0;
    final maxLng = (bounds is Map ? (bounds['max_longitude'] as num?)?.toDouble() : null) ?? 0.0;
    final latSpan = (maxLat - minLat).abs() < 0.000001 ? 0.001 : (maxLat - minLat);
    final lngSpan = (maxLng - minLng).abs() < 0.000001 ? 0.001 : (maxLng - minLng);

    return markers.asMap().entries.map((entry) {
      final marker = entry.value;
      final lat = (marker['latitude'] as num?)?.toDouble() ?? 0.0;
      final lng = (marker['longitude'] as num?)?.toDouble() ?? 0.0;
      final x = ((lng - minLng) / lngSpan).clamp(0.08, 0.92);
      final y = (1 - ((lat - minLat) / latSpan)).clamp(0.10, 0.90);
      return _MapPreviewPoint(
        label: '${marker['label'] ?? entry.key + 1}',
        name: marker['name']?.toString() ?? '',
        address: marker['address']?.toString() ?? '',
        position: Offset(x.toDouble(), y.toDouble()),
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
  final Offset position;

  const _MapPreviewPoint({
    required this.label,
    required this.name,
    required this.address,
    required this.position,
  });
}

class _RoutePreviewMapCanvas extends StatelessWidget {
  final Map<String, dynamic> preview;
  final List<_MapPreviewPoint> points;
  final bool enabled;
  final String provider;

  const _RoutePreviewMapCanvas({
    required this.preview,
    required this.points,
    required this.enabled,
    required this.provider,
  });

  @override
  Widget build(BuildContext context) {
    if (points.isEmpty) {
      return Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF122636), Color(0xFF203447)],
          ),
        ),
        child: Center(
          child: Text(
            enabled ? '地图点位准备中' : '暂无地图点位',
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.86),
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      );
    }

    return CustomPaint(
      painter: _RoutePreviewMapPainter(
        points: points,
        enabled: enabled,
        provider: provider,
      ),
      child: Stack(
        children: [
          Positioned(
            left: 16,
            top: 16,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.18),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                provider == 'amap' ? '高德联动' : '本地预览',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.92),
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
          Positioned(
            left: 16,
            bottom: 16,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.18),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                '${points.length} 个站点',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.92),
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _RoutePreviewMapPainter extends CustomPainter {
  final List<_MapPreviewPoint> points;
  final bool enabled;
  final String provider;

  const _RoutePreviewMapPainter({
    required this.points,
    required this.enabled,
    required this.provider,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    final bgPaint = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFF122636), Color(0xFF223A4C), Color(0xFF142837)],
      ).createShader(rect);
    canvas.drawRect(rect, bgPaint);

    final gridPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.06)
      ..strokeWidth = 1;
    for (var x = 0.0; x <= size.width; x += size.width / 6) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), gridPaint);
    }
    for (var y = 0.0; y <= size.height; y += size.height / 5) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    final lanePaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.08)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 10
      ..strokeCap = StrokeCap.round;
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(size.width * 0.1, size.height * 0.18, size.width * 0.78, size.height * 0.56),
        const Radius.circular(26),
      ),
      lanePaint,
    );

    final linePoints = points
        .map(
          (point) => Offset(
            size.width * point.position.dx,
            size.height * point.position.dy,
          ),
        )
        .toList();

    if (linePoints.length > 1) {
      final linePaint = Paint()
        ..color = const Color(0xFFF2C230)
        ..style = PaintingStyle.stroke
        ..strokeWidth = compactStroke(size.width)
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round;
      final path = Path()..moveTo(linePoints.first.dx, linePoints.first.dy);
      for (var i = 1; i < linePoints.length; i++) {
        final prev = linePoints[i - 1];
        final current = linePoints[i];
        final control1 = Offset((prev.dx + current.dx) / 2, prev.dy);
        final control2 = Offset((prev.dx + current.dx) / 2, current.dy);
        path.cubicTo(control1.dx, control1.dy, control2.dx, control2.dy, current.dx, current.dy);
      }
      canvas.drawPath(path, linePaint);
    }

    for (var i = 0; i < linePoints.length; i++) {
      final point = linePoints[i];
      final shadowPaint = Paint()
        ..color = Colors.black.withValues(alpha: 0.28)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8);
      canvas.drawCircle(point.translate(2, 5), 10, shadowPaint);

      final outerPaint = Paint()..color = Colors.white;
      canvas.drawCircle(point, 13, outerPaint);

      final innerPaint = Paint()
        ..color = i == 0 ? const Color(0xFF34D399) : const Color(0xFFF2C230);
      canvas.drawCircle(point, 10, innerPaint);

      final labelPainter = TextPainter(
        text: TextSpan(
          text: points[i].label,
          style: const TextStyle(
            color: Color(0xFF111827),
            fontSize: 10,
            fontWeight: FontWeight.w800,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      final labelOffset = Offset(point.dx - labelPainter.width / 2, point.dy - labelPainter.height / 2);
      labelPainter.paint(canvas, labelOffset);
    }

    if (!enabled) {
      final hintPainter = TextPainter(
        text: TextSpan(
          text: provider == 'amap' ? '地图数据未完全联动，当前展示本地预览' : '本地地图预览',
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.72),
            fontSize: 12,
            fontWeight: FontWeight.w600,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout(maxWidth: size.width * 0.72);
      hintPainter.paint(canvas, Offset(size.width * 0.18, size.height * 0.08));
    }
  }

  double compactStroke(double width) {
    if (width < 280) return 4.0;
    if (width < 360) return 4.5;
    return 5.0;
  }

  @override
  bool shouldRepaint(covariant _RoutePreviewMapPainter oldDelegate) {
    return oldDelegate.points != points ||
        oldDelegate.enabled != enabled ||
        oldDelegate.provider != provider;
  }
}
