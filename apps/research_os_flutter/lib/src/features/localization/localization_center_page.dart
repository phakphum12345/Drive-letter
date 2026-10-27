import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'localization_catalog_store.dart';

/// Local-first translation workspace. Drafts persist on this device only.
class LocalizationCenterPage extends StatefulWidget {
  const LocalizationCenterPage({super.key});

  @override
  State<LocalizationCenterPage> createState() => _LocalizationCenterPageState();
}

class _LocalizationCenterPageState extends State<LocalizationCenterPage> {
  final LocalizationCatalogStore _store = const LocalizationCatalogStore();
  final TextEditingController _search = TextEditingController();
  final Map<String, Map<String, String>> _catalogs =
      <String, Map<String, String>>{};

  String _locale = 'th';
  String _status = 'Loading versioned locale catalogs…';
  bool _loading = true;
  Map<String, String> _source = <String, String>{};

  Map<String, String> get _target => _catalogs[_locale] ?? <String, String>{};

  @override
  void initState() {
    super.initState();
    unawaited(_initialize());
  }

  Future<void> _initialize() async {
    try {
      final locale = await _store.loadPreferredLocale();
      final source = await _store.loadCatalog('en');
      final english = await _store.loadCatalog('en');
      final thai = await _store.loadCatalog('th');
      final englishDraft = await _store.loadDraft('en');
      final thaiDraft = await _store.loadDraft('th');
      if (!mounted) return;
      setState(() {
        _source = source;
        _catalogs
          ..['en'] = englishDraft ?? english
          ..['th'] = thaiDraft ?? thai;
        _locale = locale;
        _loading = false;
        _status = 'Catalogs loaded from versioned app assets. Drafts save locally on this device.';
      });
    } on Object catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _status = 'Could not load locale catalogs: $error';
      });
    }
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  List<String> get _issues {
    final target = _target;
    final issues = <String>[];
    for (final key in _source.keys) {
      final value = target[key] ?? '';
      if (value.trim().isEmpty) issues.add('Empty translation: $key');
      final sourceVars = RegExp(r'\{([A-Za-z_][A-Za-z0-9_.-]*)\}')
          .allMatches(_source[key]!)
          .map((match) => match.group(1))
          .toSet();
      final targetVars = RegExp(r'\{([A-Za-z_][A-Za-z0-9_.-]*)\}')
          .allMatches(value)
          .map((match) => match.group(1))
          .toSet();
      if (!sourceVars.containsAll(targetVars) ||
          !targetVars.containsAll(sourceVars)) {
        issues.add('Placeholder mismatch: $key');
      }
    }
    for (final key in target.keys) {
      if (!_source.containsKey(key)) issues.add('Unknown key: $key');
    }
    return issues;
  }

  Future<void> _persistDraft() async {
    try {
      await _store.saveDraft(_locale, Map<String, String>.from(_target));
      if (!mounted) return;
      setState(() => _status = 'Draft saved locally for locale "$_locale". Repository files are unchanged.');
    } on Object catch (error) {
      if (!mounted) return;
      setState(() => _status = 'Local draft save failed: $error');
    }
  }

  Future<void> _switchLocale(String value) async {
    if (value == _locale) return;
    await _persistDraft();
    final base = await _store.loadCatalog(value);
    final draft = await _store.loadDraft(value);
    if (!mounted) return;
    setState(() {
      _catalogs[value] = draft ?? _catalogs[value] ?? base;
      _locale = value;
      _status = 'Switched to "$value". Drafts remain local to this device.';
    });
    await _store.savePreferredLocale(value);
  }

  Future<void> _importJson() async {
    final controller = TextEditingController();
    final input = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Import translation JSON'),
        content: SizedBox(
          width: 560,
          child: TextField(
            controller: controller,
            minLines: 8,
            maxLines: 14,
            decoration: const InputDecoration(
              hintText: '{"nav.research": "งานวิจัย"}',
              border: OutlineInputBorder(),
            ),
          ),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text),
            child: const Text('Import'),
          ),
        ],
      ),
    );
    if (input == null || !mounted) {
      controller.dispose();
      return;
    }
    try {
      final decoded = jsonDecode(input);
      if (decoded is! Map<String, dynamic> ||
          decoded.values.any((value) => value is! String)) {
        throw const FormatException('Expected a JSON object with string values.');
      }
      setState(() {
        _catalogs[_locale] =
            decoded.map((key, value) => MapEntry(key, value as String));
        _status = 'Imported JSON into the local draft. Review quality findings before export.';
      });
      await _persistDraft();
    } on FormatException catch (error) {
      setState(() => _status = 'Import failed: ${error.message}');
    }
    controller.dispose();
  }

  Future<void> _exportJson() async {
    final issues = _issues;
    if (issues.isNotEmpty) {
      setState(() => _status = 'Export blocked: fix ${issues.length} quality finding(s) first.');
      return;
    }
    final output = const JsonEncoder.withIndent('  ').convert(_target);
    await Clipboard.setData(ClipboardData(text: output));
    if (!mounted) return;
    setState(() => _status = 'Validated JSON copied to clipboard. Repository files were not changed.');    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Validated translation JSON copied to clipboard')),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(
        key: const Key('localization-center-page'),
        appBar: AppBar(title: const Text('Localization Center')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    final target = _target;
    final issues = _issues;
    final query = _search.text.trim().toLowerCase();
    final keys = _source.keys.where((key) =>
        query.isEmpty ||
        key.toLowerCase().contains(query) ||
        _source[key]!.toLowerCase().contains(query) ||
        (target[key] ?? '').toLowerCase().contains(query)).toList();
    final completed = _source.keys
        .where((key) => (target[key] ?? '').trim().isNotEmpty)
        .length;
    final scheme = Theme.of(context).colorScheme;

    return Scaffold(
      key: const Key('localization-center-page'),
      appBar: AppBar(
        title: const Text('Localization Center'),
        actions: <Widget>[
          IconButton(
            tooltip: 'Import JSON',
            onPressed: _importJson,
            icon: const Icon(Icons.file_upload_outlined),
          ),
          IconButton(
            tooltip: 'Export validated JSON to clipboard',
            onPressed: _exportJson,
            icon: const Icon(Icons.copy_all_outlined),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: <Widget>[
          Card(
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text('Translation workspace',
                      style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 6),
                  const Text(
                    'Edit versioned locale catalogs, review catalog quality, then export JSON. Drafts persist locally and never write to GitHub or production.',
                  ),
                  const SizedBox(height: 16),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: <Widget>[
                      DropdownButton<String>(
                        key: const Key('localization-locale-picker'),
                        value: _locale,
                        items: const <DropdownMenuItem<String>>[
                          DropdownMenuItem(value: 'th', child: Text('Thai (th)')),
                          DropdownMenuItem(value: 'en', child: Text('English (en)')),
                        ],
                        onChanged: (value) {
                          if (value != null) unawaited(_switchLocale(value));
                        },
                      ),
                      Chip(label: Text('$completed / ${_source.length} translated')),
                      Chip(
                        avatar: Icon(
                          issues.isEmpty
                              ? Icons.check_circle_outline
                              : Icons.warning_amber_outlined,
                          color: issues.isEmpty ? Colors.green : scheme.error,
                        ),
                        label: Text(
                          issues.isEmpty
                              ? 'Quality gate: PASS'
                              : 'Quality gate: FAIL (${issues.length})',
                        ),
                      ),
                    ],
                  ),
                  LinearProgressIndicator(
                    value: _source.isEmpty ? 0 : completed / _source.length,
                  ),
                  const SizedBox(height: 8),
                  Text(_status, style: Theme.of(context).textTheme.bodySmall),
                ],
              ),
            ),
          ),
          const SizedBox(height: 14),
          TextField(
            key: const Key('localization-search'),
            controller: _search,
            decoration: const InputDecoration(
              prefixIcon: Icon(Icons.search),
              labelText: 'Search keys and translations',
              border: OutlineInputBorder(),
            ),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 12),
          if (issues.isNotEmpty)
            Card(
              color: scheme.errorContainer,
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text('Quality gate findings',
                        style: Theme.of(context).textTheme.titleMedium),
                    for (final issue in issues.take(8)) Text('• $issue'),
                    if (issues.length > 8)
                      Text('… and ${issues.length - 8} more'),
                    if (target.keys.any((key) => !_source.containsKey(key)))
                      Align(
                        alignment: Alignment.centerLeft,
                        child: TextButton.icon(
                          onPressed: () {
                            setState(() => target.removeWhere(
                                (key, value) => !_source.containsKey(key)));
                            unawaited(_persistDraft());
                          },
                          icon: const Icon(Icons.delete_outline),
                          label: const Text('Remove unknown keys'),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          for (final key in keys)
            Card(
              key: Key('localization-row-$key'),
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(key, style: Theme.of(context).textTheme.labelLarge),
                    const SizedBox(height: 5),
                    Text(_source[key]!,
                        style: Theme.of(context).textTheme.bodySmall),
                    const SizedBox(height: 10),
                    TextFormField(
                      key: Key('localization-value-$_locale-$key'),
                      initialValue: target[key] ?? '',
                      decoration: InputDecoration(
                        labelText: 'Translation',
                        border: const OutlineInputBorder(),
                        errorText: (target[key] ?? '').trim().isEmpty
                            ? 'Translation is empty'
                            : null,
                      ),
                      onChanged: (value) {
                        setState(() => target[key] = value);
                        unawaited(_persistDraft());
                      },
                    ),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 10),
          const Text(
            'Source of truth: versioned JSON catalogs. Draft edits are stored only in this browser/device until explicitly reviewed and copied out.',
          ),
        ],
      ),
    );
  }
}