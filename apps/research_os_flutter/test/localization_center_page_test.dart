import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:research_os_flutter/src/features/localization/localization_catalog_store.dart';
import 'package:research_os_flutter/src/features/localization/localization_center_page.dart';

void main() {
  setUp(() async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
    await SharedPreferences.getInstance();
  });

  testWidgets(
    'Localization Center loads bundled locale, searches rows, and shows quality gate',
    (tester) async {
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

      await tester.enterText(find.byKey(const Key('localization-search')), 'evidence');
      await tester.pump();

      expect(find.byKey(const Key('localization-row-nav.research')), findsNothing);
      expect(find.byKey(const Key('localization-row-nav.evidence')), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  test('locale preference and local drafts survive store recreation', () async {
    const store = LocalizationCatalogStore();
    await store.savePreferredLocale('en');
    await store.saveDraft('en', <String, String>{
      'nav.research': 'Research work',
    });

    const reloadedStore = LocalizationCatalogStore();
    expect(await reloadedStore.loadPreferredLocale(), 'en');
    expect(
      await reloadedStore.loadDraft('en'),
      <String, String>{'nav.research': 'Research work'},
    );
  });

  test('catalog store rejects unsupported locales', () async {
    const store = LocalizationCatalogStore();
    await expectLater(store.loadCatalog('fr'), throwsArgumentError);
    await expectLater(store.savePreferredLocale('fr'), throwsArgumentError);
  });
}
