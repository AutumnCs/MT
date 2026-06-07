import 'package:flutter_test/flutter_test.dart';
import 'package:meituanagent/main.dart';

void main() {
  testWidgets('planner home renders', (WidgetTester tester) async {
    await tester.pumpWidget(const MeituanAgentApp());

    expect(find.text('现在就出发'), findsOneWidget);
    expect(find.text('生成路线'), findsOneWidget);
  });
}
