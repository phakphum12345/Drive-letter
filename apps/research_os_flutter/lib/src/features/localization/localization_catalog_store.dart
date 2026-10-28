import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Loads versioned locale catalogs and stores user drafts locally only.
class LocalizationCatalogStore {
  const LocalizationCatalogStore();

  static const supportedLocales = <String>['en', 'th'];
  static const _localePreferenceKey = 'research_os.locale';
  static const _draftPrefix = 'research_os.localization.draft.';

  Future<String> loadPreferredLocale() async {
    final preferences = await SharedPreferences.getInstance();
    final locale = preferences.getString(_localePreferenceKey) ?? 'th';
    return supportedLocales.contains(locale) ? locale : 'th';
  }

  Future<void> savePreferredLocale(String locale) async {
    if (!supportedLocales.contains(locale)) {
      throw ArgumentError.value(locale, 'locale', 'Unsupported locale');
    }
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(_localePreferenceKey, locale);
  }

  Future<Map<String, String>> loadCatalog(String locale) async {
    if (!supportedLocales.contains(locale)) {
      throw ArgumentError.value(locale, 'locale', 'Unsupported locale');
    }
    final raw = await rootBundle.loadString('assets/locales/$locale.json');
    final decoded = jsonDecode(raw);
    if (decoded is! Map<String, dynamic> ||
        decoded.values.any((value) => value is! String)) {
      throw const FormatException('Locale catalog must be a JSON object of strings.');
    }
    return decoded.map((key, value) => MapEntry(key, value as String));
  }

  Future<Map<String, String>?> loadDraft(String locale) async {
    final preferences = await SharedPreferences.getInstance();
    final raw = preferences.getString('$_draftPrefix$locale');
    if (raw == null) return null;
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map<String, dynamic> ||
          decoded.values.any((value) => value is! String)) {
        return null;
      }
      return decoded.map((key, value) => MapEntry(key, value as String));
    } on FormatException {
      return null;
    }
  }

  Future<void> saveDraft(String locale, Map<String, String> draft) async {
    if (!supportedLocales.contains(locale)) {
      throw ArgumentError.value(locale, 'locale', 'Unsupported locale');
    }
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(
      '$_draftPrefix$locale',
      const JsonEncoder.withIndent('  ').convert(draft),
    );
  }

  Future<void> clearDraft(String locale) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.remove('$_draftPrefix$locale');
  }
}
