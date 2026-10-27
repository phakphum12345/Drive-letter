import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:research_os_flutter/src/features/localization/localization_center_page.dart';
import 'package:research_os_flutter/src/features/localization/localization_catalog_store.dart';

Future<void> pumpLocalizationCenter(WidgetTester tester) async {
  await tester.pumpWidget(const MaterialApp(home: LocalizationCenterPage()));
  for (var attempt = 0;
      attempt < 20 &&
          find.byType(CircularProgressIndicator).evaluate().isNotEmpty;
      attempt++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
  expect(
    find.byType(CircularProgressIndicator),
    findsNothing,
    reason: 'Localization catalogs should finish loading within the bounded test window.',
  );
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues(<String, Object>{}));

  testWidgets('Localization Center renders bundled locale, search, and quality gate', (tester) async {
    tester.view.physicalSize = const Size(900, 1200);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await pumpLocalizationCenter(tester);

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
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    await tester.pumpWidget(const MaterialApp(home: SizedBox.shrink()));
    await tester.pump();
    await tester.pumpWidget(const MaterialApp(home: LocalizationCenterPage()));
    await tester.pumpAndSettle();

    final localePicker = find.byKey(const Key('localization-locale-picker'));
    await tester.tap(localePicker);
    await tester.pumpAndSettle();
    await tester.tap(find.text('English (en)').last);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('localization-value-en-nav.research')),
      'Research work',
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    await tester.pumpWidget(const MaterialApp(home: SizedBox.shrink()));
    await tester.pump();
    await tester.pumpWidget(const MaterialApp(home: LocalizationCenterPage()));
    await tester.pumpAndSettle();

    expect(tester.widget<DropdownButton<String>>(localePicker).value, 'en');
    expect(find.text('Research work'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  test('catalog store rejects unsupported locales', () async {
    await expectLater(
      const LocalizationCatalogStore().loadCatalog('fr'),
      throwsArgumentError,
    );
    await expectLater(
      const LocalizationCatalogStore().savePreferredLocale('fr'),
      throwsArgumentError,
    );
  });

}
