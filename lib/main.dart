import 'package:flutter/material.dart';

import 'models/route_models.dart';
import 'pages/clarification_page.dart';
import 'pages/route_result_page.dart';
import 'services/route_api_service.dart';

void main() {
  runApp(const MeituanAgentApp());
}

class MeituanAgentApp extends StatelessWidget {
  const MeituanAgentApp({super.key});

  @override
  Widget build(BuildContext context) {
    const seed = Color(0xFFF2C230);

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: '现在就出发',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: seed,
          brightness: Brightness.light,
        ),
        scaffoldBackgroundColor: const Color(0xFFF6F7FB),
        useMaterial3: true,
        fontFamily: 'Microsoft YaHei',
      ),
      home: const PlannerInputPage(),
    );
  }
}

class PlannerInputPage extends StatefulWidget {
  const PlannerInputPage({super.key});

  @override
  State<PlannerInputPage> createState() => _PlannerInputPageState();
}

class _PlannerInputPageState extends State<PlannerInputPage> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final GlobalKey _inputSectionKey = GlobalKey();
  final GlobalKey _ideasSectionKey = GlobalKey();
  final GlobalKey _citySectionKey = GlobalKey();
  final GlobalKey _featureSectionKey = GlobalKey();

  final Set<String> _selectedPreferences = {};
  bool _isLoading = false;
  String? _loadingMessage;
  String _selectedCity = '广州';
  int _selectedNavIndex = 0;

  static const List<_CityOption> _cityOptions = [
    _CityOption(
      name: '广州',
      subtitle: '花城 / 珠江 / 老西关',
      landmarks: ['广州塔', '永庆坊', '珠江夜游', '沙面'],
      badge: '双城之一',
      icon: Icons.location_city_outlined,
    ),
    _CityOption(
      name: '上海',
      subtitle: '外滩 / 海派 / 夜游',
      landmarks: ['外滩', '武康路', '豫园', '陆家嘴'],
      badge: '双城之一',
      icon: Icons.location_city_outlined,
    ),
  ];

  static const List<_PreferenceItem> _preferenceItems = [
    _PreferenceItem(label: '约会', icon: Icons.favorite_border),
    _PreferenceItem(label: '拍照', icon: Icons.photo_camera_outlined),
    _PreferenceItem(label: '不想排队', icon: Icons.groups_outlined),
    _PreferenceItem(label: '性价比', icon: Icons.price_check_outlined),
    _PreferenceItem(label: '轻松路线', icon: Icons.self_improvement_outlined),
    _PreferenceItem(label: '美食', icon: Icons.restaurant_outlined),
    _PreferenceItem(label: '文艺', icon: Icons.palette_outlined),
    _PreferenceItem(label: '夜景', icon: Icons.nights_stay_outlined),
  ];

  @override
  void dispose() {
    _scrollController.dispose();
    _controller.dispose();
    super.dispose();
  }

  _CityOption get _currentCity => _cityOptions.firstWhere((item) => item.name == _selectedCity);

  void _togglePreference(String label) {
    setState(() {
      if (_selectedPreferences.contains(label)) {
        _selectedPreferences.remove(label);
      } else {
        _selectedPreferences.add(label);
        _appendPreferenceToQuery(label);
      }
    });
  }

  void _appendPreferenceToQuery(String label) {
    final currentText = _controller.text.trim();
    if (currentText.contains(label)) {
      return;
    }
    _controller.text = currentText.isEmpty ? label : '$currentText，$label';
    _controller.selection = TextSelection.fromPosition(
      TextPosition(offset: _controller.text.length),
    );
  }

  void _handleCityChange(String city) {
    setState(() {
      _selectedCity = city;
    });
  }

  void _scrollToKey(GlobalKey key) {
    final context = key.currentContext;
    if (context == null) return;
    Scrollable.ensureVisible(
      context,
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOutCubic,
      alignment: 0.08,
    );
  }

  void _scrollToInput() => _scrollToKey(_inputSectionKey);
  void _scrollToIdeas() => _scrollToKey(_ideasSectionKey);
  void _scrollToCity() => _scrollToKey(_citySectionKey);
  void _scrollToFeatures() => _scrollToKey(_featureSectionKey);

  void _handleBottomNavTap(int index) {
    setState(() {
      _selectedNavIndex = index;
    });

    switch (index) {
      case 0:
        _scrollToTop();
        break;
      case 1:
        _scrollToInput();
        break;
      case 2:
        _scrollToIdeas();
        break;
      case 3:
        _scrollToFeatures();
        break;
    }
  }

  void _scrollToTop() {
    _scrollController.animateTo(
      0,
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOutCubic,
    );
  }

  void _applyIdea(_SuggestionIdea idea) {
    setState(() {
      _selectedCity = idea.city;
      _controller.text = idea.text;
      _controller.selection = TextSelection.fromPosition(
        TextPosition(offset: _controller.text.length),
      );
    });
    _scrollToInput();
  }

  List<_SuggestionIdea> _buildIdeas() {
    if (_selectedCity == '上海') {
      return const [
        _SuggestionIdea(
          title: '外滩夜游 + 咖啡',
          subtitle: 'Views & breezes',
          text: '想在上海安排一个轻松的夜游路线，顺便喝杯咖啡，不要太赶，晚上想看夜景。',
          city: '上海',
          icon: Icons.nights_stay_outlined,
          gradient: [Color(0xFF0F172A), Color(0xFF334155)],
        ),
        _SuggestionIdea(
          title: '海派文化半日',
          subtitle: 'History & style',
          text: '想在上海来一个半日路线，想看展、拍照、吃点好的，预算 200 左右。',
          city: '上海',
          icon: Icons.account_balance_outlined,
          gradient: [Color(0xFF1E3A8A), Color(0xFF0EA5E9)],
        ),
      ];
    }

    return const [
      _SuggestionIdea(
        title: '荔湾隐秘角落',
        subtitle: 'Culture & history',
        text: '在荔湾区过一个轻松的一天，想逛老街、喝咖啡、吃点粤式小吃，不要太累。',
        city: '广州',
        icon: Icons.location_on_outlined,
        gradient: [Color(0xFF3F3CBB), Color(0xFF1D4ED8)],
      ),
      _SuggestionIdea(
        title: '珠江夜游步',
        subtitle: 'Views & breezes',
        text: '广州想安排一个夜游路线，想看夜景、拍照、吃饭，预算 200，别太绕。',
        city: '广州',
        icon: Icons.wb_twilight_outlined,
        gradient: [Color(0xFF0F172A), Color(0xFF334155)],
      ),
    ];
  }

  List<_FeatureTile> _buildFeatureTiles() {
    return const [
      _FeatureTile(
        title: '智能排期',
        subtitle: '根据时间窗口自动分配停留和转场',
        icon: Icons.schedule_outlined,
      ),
      _FeatureTile(
        title: '情境路线',
        subtitle: '按约会、亲子、朋友局、夜景等场景生成',
        icon: Icons.alt_route_outlined,
      ),
      _FeatureTile(
        title: '多重约束',
        subtitle: '预算、距离、排队、室内外都能一起考虑',
        icon: Icons.rule_outlined,
      ),
    ];
  }

  Future<void> _generateRoute() async {
    final query = _controller.text.trim();
    if (query.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('请先输入你的行程想法'),
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }

    FocusScope.of(context).unfocus();

    setState(() {
      _isLoading = true;
      _loadingMessage = '正在分析需求...';
    });

    await Future.delayed(const Duration(milliseconds: 560));
    if (!mounted) return;

    setState(() => _loadingMessage = '正在生成路线...');

    try {
      final apiService = RouteApiService();
      ParsedIntent? parsedIntent;
      try {
        parsedIntent = await apiService.parseIntent(
          query: query,
          city: _selectedCity,
        );
      } catch (_) {
        parsedIntent = null;
      }

      final parsedPreferences = parsedIntent?.preferences ?? const <String>[];
      final parsedCity = parsedIntent?.city ?? '';
      final effectiveCity = parsedCity.isNotEmpty ? parsedCity : _selectedCity;
      final mergedPreferences = <String>{
        ..._selectedPreferences,
        ...parsedPreferences,
      }.toList();

      final request = RouteRequest(
        query: query,
        preferences: mergedPreferences,
        city: effectiveCity,
      );

      final routeResponse = await apiService.generateRouteStream(
        request,
        onProgress: (message) {
          if (!mounted) return;
          setState(() => _loadingMessage = message);
        },
      );

      if (!mounted) return;
      setState(() => _isLoading = false);

      final nextPage = routeResponse.clarificationNeeded
          ? ClarificationPage(
              clarificationResponse: routeResponse,
              initialRequest: request,
              originalQuery: query,
              currentCity: effectiveCity,
            )
          : RouteResultPage(
              routeResponse: routeResponse,
              originalQuery: query,
              currentCity: effectiveCity,
            );

      Navigator.push(
        context,
        PageRouteBuilder(
          transitionDuration: const Duration(milliseconds: 260),
          reverseTransitionDuration: const Duration(milliseconds: 220),
          pageBuilder: (context, animation, secondaryAnimation) => nextPage,
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
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('生成路线失败：$e'),
          behavior: SnackBarBehavior.floating,
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          Container(
            decoration: const BoxDecoration(
              gradient: RadialGradient(
                center: Alignment.topCenter,
                radius: 1.25,
                colors: [Color(0xFFFFF3C4), Color(0xFFF6F7FB), Color(0xFFEEF2F9)],
              ),
            ),
            child: SafeArea(
              child: ListView(
                controller: _scrollController,
                padding: const EdgeInsets.fromLTRB(18, 14, 18, 24),
                children: [
                  _buildTopBar(),
                  const SizedBox(height: 16),
                  _buildHeroCard(),
                  const SizedBox(height: 16),
                  _buildCityCard(key: _citySectionKey),
                  const SizedBox(height: 16),
                  _buildInputCard(),
                  const SizedBox(height: 16),
                  _buildPreferenceCard(),
                  const SizedBox(height: 16),
                  _buildIdeasCard(),
                  const SizedBox(height: 16),
                  _buildFeatureCard(),
                  const SizedBox(height: 16),
                  _buildBottomNav(),
                ],
              ),
            ),
          ),
          if (_isLoading) _buildLoadingOverlay(),
        ],
      ),
    );
  }

  Widget _buildTopBar() {
    return Row(
      children: [
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.95),
            borderRadius: BorderRadius.circular(16),
            boxShadow: const [
              BoxShadow(
                color: Color.fromRGBO(15, 23, 42, 0.06),
                blurRadius: 18,
                offset: Offset(0, 8),
              ),
            ],
          ),
          child: const Icon(Icons.route_outlined, color: Color(0xFF111827)),
        ),
        const SizedBox(width: 12),
        const Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '现在就出发',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                  color: Color(0xFF111827),
                ),
              ),
              SizedBox(height: 2),
              Text(
                '一句话，AI 帮你安排路线',
                style: TextStyle(
                  fontSize: 12,
                  color: Color(0xFF6B7280),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: 12),
        InkWell(
          onTap: _scrollToCity,
          borderRadius: BorderRadius.circular(999),
          child: _buildCityPill(_currentCity.name),
        ),
      ],
    );
  }

  Widget _buildCityPill(String city) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.95),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: const Color(0xFFFDE68A)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.place_outlined, size: 16, color: Color(0xFF8A5A00)),
          const SizedBox(width: 6),
          Text(
            city,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w800,
              color: Color(0xFF8A5A00),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeroCard() {
    return Container(
      padding: const EdgeInsets.fromLTRB(22, 22, 22, 20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFFF2BF), Color(0xFFFFF9E8), Color(0xFFF6F7FB)],
        ),
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: const Color(0xFFF8E8A3)),
        boxShadow: const [
          BoxShadow(
            color: Color.fromRGBO(157, 122, 22, 0.10),
            blurRadius: 24,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.78),
              borderRadius: BorderRadius.circular(999),
            ),
            child: const Text(
              'AI Route Planner',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w800,
                color: Color(0xFF8A5A00),
              ),
            ),
          ),
          const SizedBox(height: 16),
          const Text(
            '输入你的行程想法，AI 帮你规划',
            style: TextStyle(
              fontSize: 29,
              height: 1.15,
              fontWeight: FontWeight.w900,
              color: Color(0xFF111827),
            ),
          ),
          const SizedBox(height: 10),
          const Text(
            '说一段自然语言就能开始。系统会先理解你的城市、预算、节奏和偏好，再给出可执行路线。',
            style: TextStyle(
              fontSize: 13,
              height: 1.5,
              color: Color(0xFF6B7280),
            ),
          ),
          const SizedBox(height: 18),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: const [
              _HeroStatChip(icon: Icons.alt_route_outlined, label: '路线对比'),
              _HeroStatChip(icon: Icons.chat_bubble_outline, label: '一轮澄清'),
              _HeroStatChip(icon: Icons.map_outlined, label: '地图预览'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildCityCard({Key? key}) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(26),
        boxShadow: const [
          BoxShadow(
            color: Color.fromRGBO(15, 23, 42, 0.06),
            blurRadius: 22,
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
                  color: const Color(0xFFF2C230).withValues(alpha: 0.16),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(Icons.place_outlined, color: Color(0xFF8A5A00), size: 18),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '当前城市',
                      style: TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w800,
                        color: Color(0xFF111827),
                      ),
                    ),
                    SizedBox(height: 2),
                    Text(
                      '系统会优先匹配这个城市下的 POI 和路线',
                      style: TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                    ),
                  ],
                ),
              ),
              TextButton(
                onPressed: _scrollToIdeas,
                child: const Text('推荐灵感'),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: _cityOptions.map((city) {
              final selected = city.name == _selectedCity;
              return GestureDetector(
                onTap: () => _handleCityChange(city.name),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 180),
                  curve: Curves.easeOutCubic,
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                  decoration: BoxDecoration(
                    color: selected ? const Color(0xFFFFF7D6) : const Color(0xFFF8FAFC),
                    borderRadius: BorderRadius.circular(18),
                    border: Border.all(
                      color: selected ? const Color(0xFFF2C230) : const Color(0xFFE5E7EB),
                      width: selected ? 1.4 : 1,
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(city.icon, size: 16, color: selected ? const Color(0xFF8A5A00) : const Color(0xFF6B7280)),
                          const SizedBox(width: 8),
                          Text(
                            city.name,
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w800,
                              color: selected ? const Color(0xFF8A5A00) : const Color(0xFF111827),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        city.subtitle,
                        style: const TextStyle(fontSize: 11, color: Color(0xFF6B7280)),
                      ),
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildInputCard() {
    final hint = _selectedCity == '上海'
        ? '例如：在外滩附近过轻松的一天，想喝咖啡、看夜景、吃点好的'
        : '例如：在荔湾区过轻松的一天，想喝咖啡、看展、吃点粤式小吃';

    return Container(
      key: _inputSectionKey,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(26),
        boxShadow: const [
          BoxShadow(
            color: Color.fromRGBO(15, 23, 42, 0.06),
            blurRadius: 22,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '说出你的行程需求',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: Color(0xFF111827),
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            '时间、预算、偏好、避让项都可以直接说，系统会帮你整理成路线。',
            style: TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
          ),
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.fromLTRB(10, 10, 10, 10),
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(22),
              border: Border.all(color: const Color(0xFFE5E7EB)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: const Color(0xFFE5E7EB)),
                  ),
                  child: const Icon(Icons.mic_none_outlined, color: Color(0xFF6B7280), size: 20),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: TextField(
                    controller: _controller,
                    minLines: 3,
                    maxLines: 6,
                    onSubmitted: (_) => _generateRoute(),
                    textInputAction: TextInputAction.done,
                    decoration: InputDecoration(
                      hintText: hint,
                      hintStyle: const TextStyle(color: Color(0xFF9CA3AF), height: 1.35),
                      border: InputBorder.none,
                      contentPadding: const EdgeInsets.only(top: 6, bottom: 6),
                    ),
                    style: const TextStyle(fontSize: 15, color: Color(0xFF111827), height: 1.4),
                  ),
                ),
                const SizedBox(width: 10),
                GestureDetector(
                  onTap: _isLoading ? null : _generateRoute,
                  child: Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: const Color(0xFF6B7280),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: const Icon(Icons.send_rounded, color: Colors.white, size: 20),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _buildMiniNote('支持自然语言'),
              _buildMiniNote('支持补充修改'),
              _buildMiniNote('先问一个关键问题'),
            ],
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: _isLoading ? null : _generateRoute,
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(54),
                backgroundColor: const Color(0xFFF2C230),
                foregroundColor: const Color(0xFF111827),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
              ),
              child: const Text(
                '生成专属路线',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMiniNote(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Text(
        text,
        style: const TextStyle(fontSize: 12, color: Color(0xFF4B5563), fontWeight: FontWeight.w600),
      ),
    );
  }

  Widget _buildPreferenceCard() {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(26),
        boxShadow: const [
          BoxShadow(
            color: Color.fromRGBO(15, 23, 42, 0.06),
            blurRadius: 22,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '快速偏好',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: Color(0xFF111827)),
          ),
          const SizedBox(height: 6),
          const Text(
            '点选后会自动补进输入框，也会帮助系统更快理解你的需求。',
            style: TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: _preferenceItems.map((item) {
              final selected = _selectedPreferences.contains(item.label);
              return FilterChip(
                selected: selected,
                label: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      item.icon,
                      size: 16,
                      color: selected ? const Color(0xFF111827) : const Color(0xFF6B7280),
                    ),
                    const SizedBox(width: 4),
                    Text(item.label),
                  ],
                ),
                onSelected: (_) => _togglePreference(item.label),
                backgroundColor: const Color(0xFFF3F4F6),
                selectedColor: const Color(0xFFFEF3C7),
                checkmarkColor: const Color(0xFF111827),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                side: BorderSide.none,
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildIdeasCard() {
    final ideas = _buildIdeas();
    return Container(
      key: _ideasSectionKey,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(26),
        boxShadow: const [
          BoxShadow(
            color: Color.fromRGBO(15, 23, 42, 0.06),
            blurRadius: 22,
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
                  '推荐灵感',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: Color(0xFF111827)),
                ),
              ),
              TextButton(onPressed: _scrollToInput, child: const Text('开始规划')),
            ],
          ),
          const SizedBox(height: 8),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: ideas
                  .map(
                    (idea) => Padding(
                      padding: const EdgeInsets.only(right: 12),
                      child: _SuggestionCard(
                        idea: idea,
                        onTap: () => _applyIdea(idea),
                      ),
                    ),
                  )
                  .toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFeatureCard() {
    final features = _buildFeatureTiles();
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(26),
        boxShadow: const [
          BoxShadow(
            color: Color.fromRGBO(15, 23, 42, 0.06),
            blurRadius: 22,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '我能为你做什么',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: Color(0xFF111827)),
          ),
          const SizedBox(height: 6),
          const Text(
            '理解需求、路径规划、条件约束、结果解释，全部都能串起来。',
            style: TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: features
                .map(
                  (feature) => SizedBox(width: 160, child: _FeatureCard(feature: feature, onTap: _scrollToInput)),
                )
                .toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildBottomNav() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(
            color: Color.fromRGBO(15, 23, 42, 0.06),
            blurRadius: 18,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          _NavItem(
            icon: Icons.explore,
            label: '发现',
            selected: _selectedNavIndex == 0,
            onTap: () => _handleBottomNavTap(0),
          ),
          _NavItem(
            icon: Icons.route_outlined,
            label: '路线',
            selected: _selectedNavIndex == 1,
            onTap: () => _handleBottomNavTap(1),
          ),
          _NavItem(
            icon: Icons.bookmark_outline,
            label: '收藏',
            selected: _selectedNavIndex == 2,
            onTap: () => _handleBottomNavTap(2),
          ),
          _NavItem(
            icon: Icons.person_outline,
            label: '我的',
            selected: _selectedNavIndex == 3,
            onTap: () => _handleBottomNavTap(3),
          ),
        ],
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
}

class _HeroStatChip extends StatelessWidget {
  final IconData icon;
  final String label;

  const _HeroStatChip({
    required this.icon,
    required this.label,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.75),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: const Color(0xFFF3D97A)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 15, color: const Color(0xFF8A5A00)),
          const SizedBox(width: 6),
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: Color(0xFF8A5A00),
            ),
          ),
        ],
      ),
    );
  }
}

class _CityOption {
  final String name;
  final String subtitle;
  final List<String> landmarks;
  final String badge;
  final IconData icon;

  const _CityOption({
    required this.name,
    required this.subtitle,
    required this.landmarks,
    required this.badge,
    this.icon = Icons.location_city_outlined,
  });
}

class _PreferenceItem {
  final String label;
  final IconData icon;

  const _PreferenceItem({
    required this.label,
    required this.icon,
  });
}

class _SuggestionIdea {
  final String title;
  final String subtitle;
  final String text;
  final String city;
  final IconData icon;
  final List<Color> gradient;

  const _SuggestionIdea({
    required this.title,
    required this.subtitle,
    required this.text,
    required this.city,
    required this.icon,
    required this.gradient,
  });
}

class _SuggestionCard extends StatelessWidget {
  final _SuggestionIdea idea;
  final VoidCallback onTap;

  const _SuggestionCard({
    required this.idea,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(24),
      child: Container(
        width: 220,
        height: 170,
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: idea.gradient,
          ),
          borderRadius: BorderRadius.circular(24),
          boxShadow: const [
            BoxShadow(
              color: Color.fromRGBO(15, 23, 42, 0.14),
              blurRadius: 20,
              offset: Offset(0, 10),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.16),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Icon(idea.icon, color: Colors.white, size: 20),
                  ),
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.18),
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: const Text(
                      '推荐',
                      style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: Colors.white),
                    ),
                  ),
                ],
              ),
              const Spacer(),
              Text(
                idea.title,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w900,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                idea.subtitle,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: Colors.white.withValues(alpha: 0.86),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                idea.text,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.white.withValues(alpha: 0.90),
                  height: 1.45,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _FeatureTile {
  final String title;
  final String subtitle;
  final IconData icon;

  const _FeatureTile({
    required this.title,
    required this.subtitle,
    required this.icon,
  });
}

class _FeatureCard extends StatelessWidget {
  final _FeatureTile feature;
  final VoidCallback onTap;

  const _FeatureCard({
    required this.feature,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(22),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xFFF8FAFC),
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: const Color(0xFFE5E7EB)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: const Color(0xFFF2C230).withValues(alpha: 0.18),
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(feature.icon, size: 20, color: const Color(0xFF111827)),
            ),
            const SizedBox(height: 12),
            Text(
              feature.title,
              style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w800,
                color: Color(0xFF111827),
              ),
            ),
            const SizedBox(height: 6),
            Text(
              feature.subtitle,
              style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280), height: 1.45),
            ),
          ],
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _NavItem({
    required this.icon,
    required this.label,
    required this.onTap,
    this.selected = false,
  });

  @override
  Widget build(BuildContext context) {
    final fg = selected ? const Color(0xFF111827) : const Color(0xFF9CA3AF);
    final bg = selected ? const Color(0xFFF2C230) : Colors.transparent;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 20, color: fg),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(fontSize: 11, color: fg, fontWeight: selected ? FontWeight.w700 : FontWeight.w500),
            ),
          ],
        ),
      ),
    );
  }
}
