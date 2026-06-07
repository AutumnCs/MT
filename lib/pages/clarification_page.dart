import 'package:flutter/material.dart';

import '../models/route_models.dart';
import '../services/route_api_service.dart';
import 'route_result_page.dart';

class ClarificationPage extends StatefulWidget {
  final RouteResponse clarificationResponse;
  final String originalQuery;
  final String currentCity;
  final RouteRequest? initialRequest;
  final Map<String, dynamic>? currentRoute;
  final bool isModification;

  const ClarificationPage({
    super.key,
    required this.clarificationResponse,
    required this.originalQuery,
    required this.currentCity,
    this.initialRequest,
    this.currentRoute,
    this.isModification = false,
  });

  @override
  State<ClarificationPage> createState() => _ClarificationPageState();
}

class _ClarificationPageState extends State<ClarificationPage> {
  late RouteResponse _currentClarification;
  final TextEditingController _customController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final GlobalKey _confirmKey = GlobalKey();
  bool _isLoading = false;
  String? _loadingMessage;
  String? _selectedOption;

  @override
  void initState() {
    super.initState();
    _currentClarification = widget.clarificationResponse;
  }

  @override
  void dispose() {
    _customController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _selectOption(String option) {
    setState(() {
      _selectedOption = option;
      if (_customController.text.trim().isNotEmpty) {
        _customController.clear();
      }
    });
    _scrollToConfirm();
  }

  void _scrollToConfirm() {
    final context = _confirmKey.currentContext;
    if (context == null) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      Scrollable.ensureVisible(
        context,
        duration: const Duration(milliseconds: 260),
        curve: Curves.easeOutCubic,
        alignment: 0.18,
      );
    });
  }

  Future<void> _continueWithSelectedOption() async {
    final selected = _selectedOption;
    if (selected == null || selected.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('先选一个最接近的答案'),
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }
    await _submitAnswer(selected);
  }

  Future<void> _submitAnswer(String answer) async {
    final trimmed = answer.trim();
    if (trimmed.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('请先补充一个关键点'),
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }

    setState(() {
      _isLoading = true;
      _loadingMessage = '正在补全你的意图...';
    });

    await Future.delayed(const Duration(milliseconds: 240));
    if (!mounted) return;

    try {
      final apiService = RouteApiService();
      final query = '${widget.originalQuery}，$trimmed';
      final response = widget.isModification
          ? await apiService.modifyRoute(
              ModifyRequest(
                query: query,
                originalQuery: widget.originalQuery,
                currentRoute: widget.currentRoute,
              ),
            )
          : await apiService.generateRoute(
              RouteRequest(
                query: query,
                preferences: widget.initialRequest?.preferences,
                city: widget.initialRequest?.city ?? widget.currentCity,
              ),
            );

      if (!mounted) return;

      if (response.clarificationNeeded) {
        setState(() {
          _currentClarification = response;
          _isLoading = false;
          _loadingMessage = null;
          _customController.clear();
          _selectedOption = null;
        });
        _scrollController.animateTo(
          0,
          duration: const Duration(milliseconds: 240),
          curve: Curves.easeOutCubic,
        );
        return;
      }

      setState(() => _isLoading = false);
      Navigator.pushReplacement(
        context,
        _buildRouteTransition(
          RouteResultPage(
            routeResponse: response,
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

  PageRouteBuilder<void> _buildRouteTransition(Widget child) {
    return PageRouteBuilder<void>(
      transitionDuration: const Duration(milliseconds: 260),
      reverseTransitionDuration: const Duration(milliseconds: 220),
      pageBuilder: (context, animation, secondaryAnimation) => child,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        final fade = CurvedAnimation(parent: animation, curve: Curves.easeOutCubic);
        final slide = Tween<Offset>(
          begin: const Offset(0.0, 0.03),
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
    final route = _currentClarification;
    final question = route.clarificationQuestion ?? '请补充一点信息';
    final reason = route.clarificationReason ?? '当前需求还不够明确，补一个最关键的问题后再继续生成。';
    final options = route.clarificationOptions;
    final modeLabel = widget.isModification ? '修改路线' : '首次生成';

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
                  _buildHeader(modeLabel),
                  Expanded(
                    child: ListView(
                      controller: _scrollController,
                      padding: const EdgeInsets.fromLTRB(18, 14, 18, 20),
                      children: [
                        _buildHeroCard(question, reason, modeLabel),
                        const SizedBox(height: 16),
                        _buildStepBlock(
                          '1',
                          '先选一个最接近的答案',
                          '减少来回打字，系统会根据这个关键点继续往下生成。',
                        ),
                        const SizedBox(height: 12),
                        _buildQuickOptions(options),
                        const SizedBox(height: 14),
                        _buildSelectionBar(),
                        const SizedBox(height: 16),
                        _buildStepBlock(
                          '2',
                          '确认后继续',
                          '如果上面的选项都不完全合适，也可以直接补一句更自然的话。',
                        ),
                        const SizedBox(height: 12),
                        _buildCustomAnswerCard(),
                        const SizedBox(height: 16),
                        _buildTipsCard(),
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

  Widget _buildHeader(String modeLabel) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.arrow_back_ios_new, color: Color(0xFF111827)),
            onPressed: () => Navigator.pop(context),
          ),
          const Expanded(
            child: Column(
              children: [
                Text(
                  '先补一个关键点',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF111827),
                  ),
                ),
                SizedBox(height: 2),
                Text(
                  '单问补全，不做多轮追问',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 12,
                    color: Color(0xFF6B7280),
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 48),
        ],
      ),
    );
  }

  Widget _buildHeroCard(String question, String reason, String modeLabel) {
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFFE27A), Color(0xFFFFF3C4)],
        ),
        borderRadius: BorderRadius.circular(28),
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
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.58),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(Icons.help_outline, color: Color(0xFF92400E)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  widget.isModification ? '我先确认你想怎么改' : '我只问你一个最关键的问题',
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF111827),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            question,
            style: const TextStyle(
              fontSize: 17,
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
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _buildModeBadge(modeLabel),
              _buildModeBadge('只问一次'),
              _buildModeBadge('继续生成'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildModeBadge(String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.76),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: const Color(0xFFFDE68A)),
      ),
      child: Text(
        label,
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          color: Color(0xFF92400E),
        ),
      ),
    );
  }

  Widget _buildStepBlock(String step, String title, String subtitle) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.95),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Row(
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(
              color: const Color(0xFFF2C230),
              borderRadius: BorderRadius.circular(12),
            ),
            alignment: Alignment.center,
            child: Text(
              step,
              style: const TextStyle(
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
                  title,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF111827),
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: const TextStyle(
                    fontSize: 12,
                    color: Color(0xFF6B7280),
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuickOptions(List<String> options) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(26),
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
            '快速选项',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: Color(0xFF111827),
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            '点一下最接近的答案，系统会自动继续往下补全。',
            style: TextStyle(
              fontSize: 13,
              color: Color(0xFF6B7280),
              height: 1.45,
            ),
          ),
          const SizedBox(height: 14),
          if (options.isEmpty)
            const Text(
              '当前暂时没有给出选项，你也可以直接自己补一句。',
              style: TextStyle(color: Color(0xFF6B7280)),
            )
          else
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: options.map((option) {
                final selected = _selectedOption == option;
                final icon = _optionIcon(option);
                return AnimatedScale(
                  scale: selected ? 1.02 : 1.0,
                  duration: const Duration(milliseconds: 180),
                  curve: Curves.easeOutCubic,
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 180),
                    curve: Curves.easeOutCubic,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(20),
                      boxShadow: selected
                          ? const [
                              BoxShadow(
                                color: Color.fromRGBO(242, 194, 48, 0.22),
                                blurRadius: 16,
                                offset: Offset(0, 6),
                              ),
                            ]
                          : const [],
                    ),
                    child: ChoiceChip(
                      selected: selected,
                      showCheckmark: false,
                      avatar: Icon(
                        icon,
                        size: 16,
                        color: selected ? const Color(0xFF92400E) : const Color(0xFF6B7280),
                      ),
                      label: Text(option),
                      onSelected: (_) => _selectOption(option),
                      backgroundColor: const Color(0xFFF8FAFC),
                      selectedColor: const Color(0xFFFFE8A3),
                      side: BorderSide(
                        color: selected ? const Color(0xFFF2C230) : const Color(0xFFE5E7EB),
                        width: selected ? 1.5 : 1,
                      ),
                      labelStyle: TextStyle(
                        color: selected ? const Color(0xFF92400E) : const Color(0xFF374151),
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                      ),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(999),
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
        ],
      ),
    );
  }

  IconData _optionIcon(String option) {
    if (option.contains('美食') || option.contains('吃')) return Icons.restaurant_outlined;
    if (option.contains('拍照') || option.contains('出片')) return Icons.camera_alt_outlined;
    if (option.contains('轻松') || option.contains('松弛') || option.contains('慢')) return Icons.self_improvement_outlined;
    if (option.contains('室内') || option.contains('雨')) return Icons.cloud_outlined;
    if (option.contains('约会') || option.contains('情侣')) return Icons.favorite_outline;
    if (option.contains('亲子') || option.contains('遛娃') || option.contains('孩子')) return Icons.child_care_outlined;
    if (option.contains('朋友')) return Icons.groups_outlined;
    if (option.contains('夜景')) return Icons.nights_stay_outlined;
    if (option.contains('排队') || option.contains('拥挤')) return Icons.groups_2_outlined;
    return Icons.tune_outlined;
  }

  Widget _buildSelectionBar() {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 220),
      switchInCurve: Curves.easeOutCubic,
      switchOutCurve: Curves.easeInCubic,
      child: _selectedOption == null
          ? Container(
              key: const ValueKey('none'),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              decoration: BoxDecoration(
                color: const Color(0xFFF8FAFC),
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: const Color(0xFFE5E7EB)),
              ),
              child: const Row(
                children: [
                  Icon(Icons.touch_app_outlined, size: 18, color: Color(0xFF6B7280)),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '先选一个最接近的答案，或者直接补一句更自然的话。',
                      style: TextStyle(fontSize: 13, color: Color(0xFF6B7280)),
                    ),
                  ),
                ],
              ),
            )
          : Container(
              key: const ValueKey('selected'),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFFFFFBEB),
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: const Color(0xFFF2C230)),
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF2C230).withValues(alpha: 0.22),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(Icons.check_circle_outline, size: 18, color: Color(0xFF92400E)),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      '已选：$_selectedOption',
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF92400E),
                      ),
                    ),
                  ),
                  FilledButton(
                    onPressed: _isLoading ? null : _continueWithSelectedOption,
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(0xFFF2C230),
                      foregroundColor: const Color(0xFF111827),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    ),
                    child: const Text(
                      '用这个继续',
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
                    ),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _buildCustomAnswerCard() {
    return Container(
      key: _confirmKey,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.97),
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
            '或者自己补一句',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: Color(0xFF111827),
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            '如果上面的选项不完全合适，直接用更自然的话补充也可以。',
            style: TextStyle(
              fontSize: 13,
              color: Color(0xFF6B7280),
              height: 1.45,
            ),
          ),
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: const Color(0xFFE5E7EB)),
            ),
            child: TextField(
              controller: _customController,
              minLines: 2,
              maxLines: 4,
              onChanged: (value) {
                if (value.trim().isEmpty) return;
                if (_selectedOption != null) {
                  setState(() => _selectedOption = null);
                }
              },
              decoration: InputDecoration(
                hintText: '例如：更偏室内一点，别太远，预算低一点',
                filled: true,
                fillColor: Colors.transparent,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(16),
                  borderSide: BorderSide.none,
                ),
                contentPadding: const EdgeInsets.all(16),
              ),
            ),
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: _isLoading ? null : () => _submitAnswer(_customController.text),
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(50),
                backgroundColor: const Color(0xFF111827),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              ),
              child: const Text(
                '继续生成',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTipsCard() {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '为什么要先问这一句？',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w800,
              color: Color(0xFF111827),
            ),
          ),
          SizedBox(height: 8),
          Text(
            '因为你的需求已经足够接近路线，但还差一个决定风格的关键点。问完这一句，后面就能更准确地排出你想要的结果。',
            style: TextStyle(
              fontSize: 13,
              color: Color(0xFF6B7280),
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoadingOverlay() {
    return Container(
      color: Colors.black.withValues(alpha: 0.26),
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
              const CircularProgressIndicator(color: Color(0xFFF2C230)),
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
