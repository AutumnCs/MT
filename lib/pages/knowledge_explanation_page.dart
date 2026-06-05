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
          _buildExplainSection(),
          const SizedBox(height: 18),
          _buildCurrentRouteSection(),
          const SizedBox(height: 18),
          _buildHowToAdjustSection(),
        ],
      ),
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
