import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:research_os_flutter/src/features/localization/localization_center_page.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues(<String, Object>{}));

  testWidgets('Localization Center renders bundled locale, search, and quality gate', (tester) async {
    tester.view.physicalSize = const Size(900, 1200);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(const MaterialApp(home: LocalizationCenterPage()));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('localization-center-page')), findsOneWidget);
    expect(find.text('Localization Center'), findsOneWidget);
    expect(find.byKey(const Key('localization-locale-picker')), findsOneWidget);
    expect(find.byKey(const Key('localization-search')), findsOneWidget);
    expect(find.textContaining('Quality gate: PASS'), findsOneWidget);
    expect(find.byKey(const Key('localization-row-nav.research')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Localization Center search filters catalog rows', (tester) async {
    tester.view.physicalSize = const Size(900, 1200);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(const MaterialApp(home: LocalizationCenterPage()));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('localization-search')), 'evidence');
    await tester.pump();

    expect(find.byKey(const Key('localization-row-nav.research')), findsNothing);
    expect(find.byKey(const Key('localization-row-nav.evidence')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('locale preference and draft survive page recreation', (tester) async {
    tester.view.physicalSize = const Size(900, 1200);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(const MaterialApp(home: LocalizationCenterPage()));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const Key('localization-value-th-nav.research')),
      'การค้นคว้า',
    );
    await tester.pumpAndSettle();

    await tester.pumpWidget(const MaterialApp(home: SizedBox.shrink()));
    await tester.pump();
    await tester.pumpWidget(const MaterialApp(home: LocalizationCenterPage()));
    await tester.pumpAndSettle();

    expect(find.text('การค้นคว้า'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
