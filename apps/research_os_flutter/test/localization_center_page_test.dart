import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:research_os_flutter/src/features/localization/localization_center_page.dart';

void main() {
  testWidgets('Localization Center renders locale, search, and quality gate', (tester) async {
    tester.view.physicalSize = const Size(900, 1200);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      const MaterialApp(home: LocalizationCenterPage()),
    );

    expect(find.byKey(const Key('localization-center-page')), findsOneWidget);
    expect(find.text('Localization Center'), findsOneWidget);
    expect(find.byKey(const Key('localization-locale-picker')), findsOneWidget);
    expect(find.byKey(const Key('localization-search')), findsOneWidget);
    expect(find.textContaining('Quality gate: PASS'), findsOneWidget);
    expect(find.byKey(const Key('localization-row-nav.home')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Localization Center search filters catalog rows', (tester) async {
    await tester.view.setPhysicalSize(const Size(900, 1200));
    await tester.view.setDevicePixelRatio(1);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      const MaterialApp(home: LocalizationCenterPage()),
    );

    await tester.enterText(find.byKey(const Key('localization-search')), 'evidence');
    await tester.pump();

    expect(find.byKey(const Key('localization-row-nav.home')), findsNothing);
    expect(find.byKey(const Key('localization-row-evidence.verify')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
