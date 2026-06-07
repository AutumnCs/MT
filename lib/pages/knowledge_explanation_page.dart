import 'package:flutter/material.dart';

import '../models/route_models.dart';

class KnowledgeExplanationPage extends StatelessWidget {
  final RouteResponse routeResponse;
  final String originalQuery;

  const KnowledgeExplanationPage({
    super.key,
    required this.routeResponse,
    required this.originalQuery,
  });

  @override
  Widget build(BuildContext context) {
    final parsedSummary = (routeResponse.intentSummary ?? '').trim();
    final rawQuery = originalQuery.trim().isEmpty
        ? (routeResponse.originalQuery ?? '').trim()
        : originalQuery.trim();
    final modification = routeResponse.trace?['modification'];
    final hasModification = modification is Map && modification['is_modification'] == true;

    return Scaffold(
      backgroundColor: const Color(0xFFF6F7FB),
      appBar: AppBar(
        backgroundColor: const Color(0xFFF6F7FB),
        foregroundColor: const Color(0xFF111827),
        elevation: 0,
        title: const Text('知识解释'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _buildHeroCard(parsedSummary, rawQuery),
          const SizedBox(height: 18),
          _buildAlgorithmChainSection(),
          if (hasModification) ...[
            const SizedBox(height: 18),
            _buildModificationSection(),
          ],
          const SizedBox(height: 18),
          _buildScoringSection(),
          const SizedBox(height: 18),
          _buildRouteEvidenceSection(),
          const SizedBox(height: 18),
          _buildExplainSection(),
          const SizedBox(height: 18),
          _buildCurrentRouteSection(),
          const SizedBox(height: 18),
          _buildHowToAdjustSection(),
        ],
      ),
    );
  }

  Map<String, dynamic> get _trace => routeResponse.trace ?? const {};

  List<String> _stringList(dynamic value) {
    if (value is List) {
      return value.where((item) => item != null).map((item) => item.toString()).toList();
    }
    return const [];
  }

  String _traceText(String key, {String fallback = '未记录'}) {
    final value = _trace[key];
    if (value == null) return fallback;
    if (value is List) return value.isEmpty ? fallback : value.join('、');
    if (value is Map) return value.isEmpty ? fallback : value.toString();
    final text = value.toString().trim();
    return text.isEmpty ? fallback : text;
  }

  Widget _buildAlgorithmChainSection() {
    final candidateCount = _traceText('candidate_count');
    final rankingCount = _traceText('ranking_candidate_count');
    final selectedIds = _stringList(_trace['selected_poi_ids']);
    final contextBias = _stringList(_trace['context_bias']);
    final profileBias = _stringList(_trace['profile_bias']);
    final areaClusters = _stringList(_trace['area_clusters']);

    final steps = [
      _PipelineStep(
        title: '理解需求',
        body: '先把口语输入转成城市、预算、时间、偏好、避开项和必去点。解析来源：${routeResponse.parseSource ?? _traceText('parse_source')}。',
        icon: Icons.psychology_alt_outlined,
      ),
      _PipelineStep(
        title: '结合记忆',
        body: contextBias.isEmpty && profileBias.isEmpty
            ? '本次没有明显历史偏好参与，主要按当前输入推荐。'
            : '本次加入了上下文偏好：${[...contextBias, ...profileBias].join('、')}。',
        icon: Icons.history_outlined,
      ),
      _PipelineStep(
        title: '召回与粗排',
        body: '系统不会把所有地点一次性丢给大模型，而是先从地图/POI库里召回候选，再按类别、语义、距离、预算、人流风险粗排。进入排序链路的候选数：$rankingCount。',
        icon: Icons.manage_search_outlined,
      ),
      _PipelineStep(
        title: '路线搜索',
        body: '再用路线搜索选择站点和顺序，优先让转场顺、时间够、预算不炸。最终选中 ${selectedIds.length} 个站点，主要区域：${areaClusters.isEmpty ? '未记录' : areaClusters.join('、')}。',
        icon: Icons.route_outlined,
      ),
      _PipelineStep(
        title: '生成解释',
        body: '最后才把路线结果组织成自然语言解释。大模型主要参与意图理解和表达，不负责逐个读取全部地点。',
        icon: Icons.auto_awesome_outlined,
      ),
    ];

    return _SectionCard(
      title: '本次算法链路',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildMetricGrid([
            _MetricData('候选池', candidateCount, Icons.dataset_outlined),
            _MetricData('精排候选', rankingCount, Icons.filter_alt_outlined),
            _MetricData('选中站点', '${selectedIds.length}', Icons.place_outlined),
            _MetricData('地图来源', _traceText('map_provider', fallback: 'local'), Icons.map_outlined),
          ]),
          const SizedBox(height: 14),
          ...steps.map(
            (step) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: _PipelineCard(step: step),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildModificationSection() {
    final modification = _trace['modification'];
    if (modification is! Map || modification['is_modification'] != true) {
      return const SizedBox.shrink();
    }

    final added = _stringList(modification['added_poi_ids']);
    final removed = _stringList(modification['removed_poi_ids']);
    final kept = _stringList(modification['kept_poi_ids']);
    final changed = modification['changed'] == true;
    final query = (modification['modification_query'] ?? '').toString();

    return _SectionCard(
      title: '这次是否真的修改了',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _StatusBanner(
            ok: changed,
            title: changed ? '已重新规划并产生变化' : '已重新计算，但站点没有变化',
            body: changed
                ? '系统根据“$query”重新召回、排序和规划，下面是站点变化。'
                : '这通常说明新约束下原方案仍然得分最高，或候选库里缺少更合适的替换点。',
          ),
          const SizedBox(height: 12),
          _buildMetricGrid([
            _MetricData('新增', '${added.length}', Icons.add_location_alt_outlined),
            _MetricData('移除', '${removed.length}', Icons.wrong_location_outlined),
            _MetricData('保留', '${kept.length}', Icons.check_circle_outline),
          ]),
          if (added.isNotEmpty || removed.isNotEmpty) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                ...added.map((id) => _miniChip(Icons.add, '新增 $id')),
                ...removed.map((id) => _miniChip(Icons.remove, '移除 $id')),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildScoringSection() {
    final routeScore = routeResponse.routeScore == null
        ? '未记录'
        : routeResponse.routeScore!.toStringAsFixed(2);
    final travelRatio = routeResponse.travelTimeRatio == null
        ? '未记录'
        : '${(routeResponse.travelTimeRatio! * 100).round()}%';

    return _SectionCard(
      title: '评分标准',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildMetricGrid([
            _MetricData('路线分', routeScore, Icons.stacked_line_chart_outlined),
            _MetricData('路上占比', travelRatio, Icons.timer_outlined),
            _MetricData('总距离', '${routeResponse.totalDistance.toStringAsFixed(1)}km', Icons.social_distance_outlined),
            _MetricData('预计花费', '${routeResponse.totalCost}元', Icons.payments_outlined),
          ]),
          const SizedBox(height: 14),
          const Text(
            'POI排序主要看：偏好匹配、语义匹配、类别匹配、评分、预算、游玩时长，以及排队/拥挤/价格惩罚。路线规划再看：总时间是否合适、交通时间是否过高、站点是否顺路、类别覆盖、营业时间和预算。',
            style: TextStyle(
              fontSize: 13,
              color: Color(0xFF374151),
              height: 1.6,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRouteEvidenceSection() {
    final stops = routeResponse.stops;
    return _SectionCard(
      title: '为什么选这些点',
      child: Column(
        children: stops
            .map(
              (stop) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _StopReasonCard(stop: stop),
              ),
            )
            .toList(),
      ),
    );
  }

  Widget _buildMetricGrid(List<_MetricData> metrics) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final columns = constraints.maxWidth > 520 ? 4 : 2;
        return GridView.count(
          crossAxisCount: columns,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 10,
          crossAxisSpacing: 10,
          childAspectRatio: columns == 4 ? 1.45 : 1.75,
          children: metrics.map((item) => _MetricTile(data: item)).toList(),
        );
      },
    );
  }

  Widget _buildHeroCard(String parsedSummary, String rawQuery) {
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFFE27A), Color(0xFFFFF7D6)],
        ),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '系统会先理解你，再去规划路线',
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w800,
              color: Color(0xFF111827),
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            '这一页是给你看的，不是内部调试页。我们会把你的口语表达归到更稳定的偏好和约束上。',
            style: TextStyle(
              fontSize: 14,
              color: Color(0xFF4B5563),
              height: 1.6,
            ),
          ),
          const SizedBox(height: 14),
          _buildPill('原始输入', rawQuery.isEmpty ? '未填写' : rawQuery),
          const SizedBox(height: 10),
          _buildPill('系统理解', parsedSummary.isEmpty ? '当前结果页已完成路线解释' : parsedSummary),
        ],
      ),
    );
  }

  Widget _buildPill(String label, String value) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: Color(0xFF92400E),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: Color(0xFF111827),
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildExplainSection() {
    final items = [
      _KnowledgeItem(
        title: '拍照 / 打卡 / 出片',
        summary: '会优先理解成“拍照偏好”，系统更愿意挑更适合拍照和分享的站点。',
        icon: Icons.camera_alt_outlined,
      ),
      _KnowledgeItem(
        title: '吃点好的 / 吃好点 / 美食',
        summary: '会被归到“美食偏好”，路线会更重视餐饮质量和用餐体验。',
        icon: Icons.restaurant_outlined,
      ),
      _KnowledgeItem(
        title: '不要排队 / 别等太久',
        summary: '会被理解为“排队约束”，系统会尽量减少热门且等待时间长的点。',
        icon: Icons.groups_outlined,
      ),
      _KnowledgeItem(
        title: '太远了 / 别太绕 / 换近一点',
        summary: '会被归到“更紧凑、更轻松”的路线诉求，尽量降低转场压力。',
        icon: Icons.route_outlined,
      ),
      _KnowledgeItem(
        title: '室内 / 避雨 / 雨天',
        summary: '会优先理解成“雨天友好”，更倾向室内或可控性更高的点。',
        icon: Icons.cloud_outlined,
      ),
    ];

    return _SectionCard(
      title: '常见表达怎么理解',
      child: Column(
        children: items
            .map(
              (item) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _KnowledgeCard(item: item),
              ),
            )
            .toList(),
      ),
    );
  }

  Widget _buildCurrentRouteSection() {
    final preferences = routeResponse.appliedPreferences;
    final warnings = routeResponse.warnings;
    return _SectionCard(
      title: '当前路线里识别到的内容',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            routeResponse.routeExplanation,
            style: const TextStyle(
              fontSize: 14,
              color: Color(0xFF374151),
              height: 1.65,
            ),
          ),
          if (preferences.isNotEmpty) ...[
            const SizedBox(height: 14),
            const Text(
              '当前偏好',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: Color(0xFF111827),
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: preferences
                  .map(
                    (item) => _miniChip(
                      Icons.tag_outlined,
                      item,
                    ),
                  )
                  .toList(),
            ),
          ],
          if (warnings.isNotEmpty) ...[
            const SizedBox(height: 14),
            const Text(
              '系统提醒',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: Color(0xFF111827),
              ),
            ),
            const SizedBox(height: 8),
            ...warnings.map(
              (warning) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.info_outline, size: 16, color: Color(0xFFD97706)),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        warning,
                        style: const TextStyle(
                          fontSize: 13,
                          color: Color(0xFF92400E),
                          height: 1.5,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildHowToAdjustSection() {
    final tips = [
      '想更轻松：试试“再慢一点 / 少走路 / 别太绕”',
      '想更省钱：试试“预算低一点 / 便宜点 / 控制成本”',
      '想少排队：试试“不要排队 / 别等太久 / 避开人多”',
      '想更适合拍照：试试“多一点拍照点 / 出片 / 打卡”',
    ];

    return _SectionCard(
      title: '如果你想改',
      child: Column(
        children: tips
            .map(
              (tip) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF8FAFC),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: const Color(0xFFE5E7EB)),
                  ),
                  child: Text(
                    tip,
                    style: const TextStyle(
                      fontSize: 13,
                      color: Color(0xFF374151),
                      height: 1.5,
                    ),
                  ),
                ),
              ),
            )
            .toList(),
      ),
    );
  }

  Widget _miniChip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: const Color(0xFFFDE68A)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: const Color(0xFFD97706)),
          const SizedBox(width: 6),
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: Color(0xFF92400E),
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  final String title;
  final Widget child;

  const _SectionCard({
    required this.title,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
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
          Text(
            title,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: Color(0xFF111827),
            ),
          ),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }
}

class _KnowledgeItem {
  final String title;
  final String summary;
  final IconData icon;

  const _KnowledgeItem({
    required this.title,
    required this.summary,
    required this.icon,
  });
}

class _KnowledgeCard extends StatelessWidget {
  final _KnowledgeItem item;

  const _KnowledgeCard({
    required this.item,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: const Color(0xFFFFF3C4),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(item.icon, size: 18, color: const Color(0xFFD97706)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.title,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF111827),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  item.summary,
                  style: const TextStyle(
                    fontSize: 13,
                    color: Color(0xFF4B5563),
                    height: 1.55,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricData {
  final String label;
  final String value;
  final IconData icon;

  const _MetricData(this.label, this.value, this.icon);
}

class _MetricTile extends StatelessWidget {
  final _MetricData data;

  const _MetricTile({
    required this.data,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Icon(data.icon, size: 18, color: const Color(0xFF2563EB)),
          const SizedBox(height: 8),
          Text(
            data.value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w800,
              color: Color(0xFF111827),
            ),
          ),
          Text(
            data.label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 11,
              color: Color(0xFF6B7280),
            ),
          ),
        ],
      ),
    );
  }
}

class _PipelineStep {
  final String title;
  final String body;
  final IconData icon;

  const _PipelineStep({
    required this.title,
    required this.body,
    required this.icon,
  });
}

class _PipelineCard extends StatelessWidget {
  final _PipelineStep step;

  const _PipelineCard({
    required this.step,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: const Color(0xFFEFF6FF),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(step.icon, size: 18, color: const Color(0xFF2563EB)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  step.title,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF111827),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  step.body,
                  style: const TextStyle(
                    fontSize: 13,
                    color: Color(0xFF4B5563),
                    height: 1.55,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _StatusBanner extends StatelessWidget {
  final bool ok;
  final String title;
  final String body;

  const _StatusBanner({
    required this.ok,
    required this.title,
    required this.body,
  });

  @override
  Widget build(BuildContext context) {
    final color = ok ? const Color(0xFF059669) : const Color(0xFFD97706);
    final background = ok ? const Color(0xFFECFDF5) : const Color(0xFFFFFBEB);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.22)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(ok ? Icons.check_circle_outline : Icons.info_outline, color: color, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w800,
                    color: color,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  body,
                  style: const TextStyle(
                    fontSize: 13,
                    color: Color(0xFF374151),
                    height: 1.5,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _StopReasonCard extends StatelessWidget {
  final RouteStop stop;

  const _StopReasonCard({
    required this.stop,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(18),
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
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF111827),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '${stop.arrivalTime}-${stop.departureTime}',
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: Color(0xFF2563EB),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            '${stop.poi.categoryLabel} · 停留 ${stop.stayMinutes} 分钟 · 人均约 ${stop.poi.price} 元',
            style: const TextStyle(
              fontSize: 12,
              color: Color(0xFF6B7280),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            stop.reason.isEmpty ? '匹配当前偏好，并兼顾路线顺序和转场成本。' : stop.reason,
            style: const TextStyle(
              fontSize: 13,
              color: Color(0xFF4B5563),
              height: 1.5,
            ),
          ),
          if (stop.riskAlert != null && stop.riskAlert!.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              stop.riskAlert!,
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: Color(0xFFD97706),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
