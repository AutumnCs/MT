import 'package:flutter/material.dart';

import 'models/route_models.dart';
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
  final Set<String> _selectedPreferences = {};

  static const _examples = <String>[
    '周六下午两点从广州塔出发，预算 200，想约会，想喝咖啡、看展、吃饭，不想太累，晚上 9 点前结束。',
    '今晚下班后想吃点好的再散步，预算 180，不想排太久队。',
    '周末带朋友逛上海，想拍照、喝咖啡，顺便吃饭，路线不要太绕。',
  ];

  static const _preferenceChips = <Map<String, dynamic>>[
    {'label': '约会', 'icon': Icons.favorite_outline},
    {'label': '拍照', 'icon': Icons.camera_alt_outlined},
    {'label': '不想排队', 'icon': Icons.groups_outlined},
    {'label': '性价比', 'icon': Icons.savings_outlined},
    {'label': '轻松路线', 'icon': Icons.self_improvement_outlined},
    {'label': '美食', 'icon': Icons.restaurant_outlined},
    {'label': '文艺', 'icon': Icons.palette_outlined},
    {'label': '夜景', 'icon': Icons.nights_stay_outlined},
  ];

  bool _isLoading = false;
  String? _loadingMessage;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _togglePreference(String label) {
    setState(() {
      if (_selectedPreferences.contains(label)) {
        _selectedPreferences.remove(label);
      } else {
        _selectedPreferences.add(label);
      }
      _appendLatestPreference(label);
    });
  }

  void _appendLatestPreference(String label) {
    final currentText = _controller.text.trim();
    if (!_selectedPreferences.contains(label)) {
      return;
    }
    if (currentText.contains(label)) {
      return;
    }

    _controller.text = currentText.isEmpty ? label : '$currentText，$label';
    _controller.selection = TextSelection.fromPosition(
      TextPosition(offset: _controller.text.length),
    );
  }

  Future<void> _generateRoute() async {
    final query = _controller.text.trim();
    if (query.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('请输入你的行程需求'),
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }

    setState(() {
      _isLoading = true;
      _loadingMessage = '正在分析需求...';
    });

    await Future.delayed(const Duration(milliseconds: 700));
    if (!mounted) {
      return;
    }
    setState(() => _loadingMessage = '正在生成路线...');

    try {
      final request = RouteRequest(
        query: query,
        preferences: _selectedPreferences.toList(),
      );

      final apiService = RouteApiService();
      final routeResponse = await apiService.generateRoute(request);

      if (!mounted) {
        return;
      }

      setState(() => _isLoading = false);
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (context) => RouteResultPage(
            routeResponse: routeResponse,
            originalQuery: query,
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
          DecoratedBox(
            decoration: const BoxDecoration(
              gradient: RadialGradient(
                center: Alignment.topCenter,
                radius: 1.25,
                colors: [Color(0xFFFFF3C4), Color(0xFFF6F7FB), Color(0xFFEEF2F9)],
              ),
            ),
            child: SafeArea(
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  const _HeroCard(),
                  const SizedBox(height: 18),
                  _buildPreferenceSection(),
                  const SizedBox(height: 18),
                  _buildInputSection(),
                  const SizedBox(height: 18),
                  _buildExamplesSection(),
                ],
              ),
            ),
          ),
          if (_isLoading) _buildLoadingOverlay(),
        ],
      ),
    );
  }

  Widget _buildPreferenceSection() {
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
            '快速偏好',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: Color(0xFF111827),
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: _preferenceChips.map((chip) {
              final isSelected = _selectedPreferences.contains(chip['label']);
              return FilterChip(
                selected: isSelected,
                label: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      chip['icon'],
                      size: 16,
                      color: isSelected ? const Color(0xFF111827) : const Color(0xFF6B7280),
                    ),
                    const SizedBox(width: 4),
                    Text(chip['label']),
                  ],
                ),
                onSelected: (_) => _togglePreference(chip['label']),
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

  Widget _buildInputSection() {
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
            '输入你的需求',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: Color(0xFF111827),
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _controller,
            minLines: 5,
            maxLines: 8,
            decoration: InputDecoration(
              hintText: '比如：周六下午两点从广州塔出发，预算 200，想喝咖啡、看展、吃饭，不想太累',
              filled: true,
              fillColor: const Color(0xFFF8FAFC),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(18),
                borderSide: BorderSide.none,
              ),
              contentPadding: const EdgeInsets.all(18),
            ),
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _isLoading ? null : _generateRoute,
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(54),
              backgroundColor: const Color(0xFFF2C230),
              foregroundColor: const Color(0xFF111827),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
            ),
            child: const Text(
              '生成路线',
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildExamplesSection() {
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
            '示例需求',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: Color(0xFF111827),
            ),
          ),
          const SizedBox(height: 12),
          ..._examples.map(
            (example) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: InkWell(
                onTap: () {
                  setState(() {
                    _controller.text = example;
                    _controller.selection = TextSelection.fromPosition(
                      TextPosition(offset: example.length),
                    );
                  });
                },
                borderRadius: BorderRadius.circular(16),
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF8FAFC),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: const Color(0xFFE5E7EB)),
                  ),
                  child: Text(
                    example,
                    style: const TextStyle(
                      fontSize: 14,
                      color: Color(0xFF374151),
                      height: 1.5,
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
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

class _HeroCard extends StatelessWidget {
  const _HeroCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF111827), Color(0xFF1F2937), Color(0xFF0F172A)],
        ),
        borderRadius: BorderRadius.circular(28),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: const [
          Text(
            '现在就出发',
            style: TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.w800,
              color: Colors.white,
            ),
          ),
          SizedBox(height: 8),
          Text(
            'AI 本地路线规划',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: Color(0xFFFDE68A),
            ),
          ),
          SizedBox(height: 12),
          Text(
            '直接用自然语言说出你的出行需求，我们会帮你把咖啡、看展、吃饭、散步等目标串成一条可执行路线。',
            style: TextStyle(
              fontSize: 14,
              height: 1.6,
              color: Color(0xFFE5E7EB),
            ),
          ),
        ],
      ),
    );
  }
}
