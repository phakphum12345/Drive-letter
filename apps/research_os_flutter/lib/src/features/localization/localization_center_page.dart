import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Local-first translation workspace. Edits remain in memory until exported.
class LocalizationCenterPage extends StatefulWidget {
  const LocalizationCenterPage({super.key});

  @override
  State<LocalizationCenterPage> createState() => _LocalizationCenterPageState();
}

class _LocalizationCenterPageState extends State<LocalizationCenterPage> {
  static const Map<String, String> _source = <String, String>{
    'app.title': 'Research OS',
    'nav.home': 'Home',
    'nav.research': 'Research',
    'nav.evidence': 'Evidence',
    'nav.settings': 'Settings',
    'status.ready': 'Ready',
    'action.save': 'Save changes',
    'action.cancel': 'Cancel',
    'research.prompt': 'Describe the research you want to investigate',
    'research.start': 'Start research',
    'evidence.verify': 'Verify evidence',
    'account.sign_in': 'Sign in',
  };

  final Map<String, String> _thai = <String, String>{
    'app.title': 'Research OS',
    'nav.home': 'หน้าหลัก',
    'nav.research': 'งานวิจัย',
    'nav.evidence': 'หลักฐาน',
    'nav.settings': 'การตั้งค่า',
    'status.ready': 'พร้อมใช้งาน',
    'action.save': 'บันทึกการเปลี่ยนแปลง',
    'action.cancel': 'ยกเลิก',
    'research.prompt': 'อธิบายเรื่องที่ต้องการค้นคว้า',
    'research.start': 'เริ่มค้นคว้า',
    'evidence.verify': 'ตรวจสอบหลักฐาน',
    'account.sign_in': 'เข้าสู่ระบบ',
  };

  final TextEditingController _search = TextEditingController();
  String _locale = 'th';
  String _status = 'Draft only · changes are not saved to the repository';
  Map<String, String> get _target => _locale == 'th' ? _thai : _english;
  final Map<String, String> _english = <String, String>{
    'app.title': 'Research OS',
    'nav.home': 'Home',
    'nav.research': 'Research',
    'nav.evidence': 'Evidence',
    'nav.settings': 'Settings',
    'status.ready': 'Ready',
    'action.save': 'Save changes',
    'action.cancel': 'Cancel',
    'research.prompt': 'Describe the research you want to investigate',
    'research.start': 'Start research',
    'evidence.verify': 'Verify evidence',
    'account.sign_in': 'Sign in',
  };

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
          .map((m) => m.group(1))
          .toSet();
      final targetVars = RegExp(r'\{([A-Za-z_][A-Za-z0-9_.-]*)\}')
          .allMatches(value)
          .map((m) => m.group(1))
          .toSet();
      if (sourceVars.length != targetVars.length ||
          !sourceVars.containsAll(targetVars) ||
          !targetVars.containsAll(sourceVars)) {
        issues.add('Placeholder mismatch: $key');
      }
    }
    for (final key in target.keys) {
      if (!_source.containsKey(key)) issues.add('Unknown key: $key');
    }
    return issues;
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
              hintText: '{"nav.home": "หน้าหลัก"}',
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
        _target
          ..clear()
          ..addAll(decoded.map((key, value) => MapEntry(key, value as String)));
        _status = 'Imported JSON into this session. Export to keep a copy.';
      });
    } on FormatException catch (error) {
      setState(() => _status = 'Import failed: ${error.message}');
    }
    controller.dispose();
  }

  Future<void> _exportJson() async {
    final output = const JsonEncoder.withIndent('  ').convert(_target);
    await Clipboard.setData(ClipboardData(text: output));
    if (!mounted) return;
    setState(() => _status = 'JSON copied to clipboard. Repository files were not changed.');
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Translation JSON copied to clipboard')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final target = _target;
    final issues = _issues;
    final query = _search.text.trim().toLowerCase();
    final keys = _source.keys.where((key) =>
        query.isEmpty ||
        key.toLowerCase().contains(query) ||
        _source[key]!.toLowerCase().contains(query) ||
        (target[key] ?? '').toLowerCase().contains(query)).toList();
    final completed = _source.keys.where((key) => (target[key] ?? '').trim().isNotEmpty).length;
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
            tooltip: 'Export JSON to clipboard',
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
                  Text('Translation workspace', style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 6),
                  const Text('Edit a local draft, review catalog quality, then export JSON. This screen does not write to GitHub or production.'),
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
                        onChanged: (value) => setState(() {
                          _locale = value ?? 'th';
                          _status = 'Switched target locale to $_locale.';
                        }),
                      ),
                      Chip(label: Text('$completed / ${_source.length} translated')),
                      Chip(
                        avatar: Icon(issues.isEmpty ? Icons.check_circle_outline : Icons.warning_amber_outlined,
                            color: issues.isEmpty ? Colors.green : scheme.error),
                        label: Text(issues.isEmpty ? 'Quality gate: PASS' : 'Quality gate: FAIL (${issues.length})'),
                      ),
                    ],
                  ),
                  LinearProgressIndicator(value: _source.isEmpty ? 0 : completed / _source.length),
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
                    Text('Quality gate findings', style: Theme.of(context).textTheme.titleMedium),
                    for (final issue in issues.take(8)) Text('• $issue'),
                    if (issues.length > 8) Text('… and ${issues.length - 8} more'),
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
                    Text(_source[key]!, style: Theme.of(context).textTheme.bodySmall),
                    const SizedBox(height: 10),
                    TextFormField(
                      key: Key('localization-value-$key'),
                      initialValue: target[key] ?? '',
                      decoration: InputDecoration(
                        labelText: 'Translation',
                        border: const OutlineInputBorder(),
                        errorText: (target[key] ?? '').trim().isEmpty ? 'Translation is empty' : null,
                      ),
                      onChanged: (value) => setState(() => target[key] = value),
                    ),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 10),
          const Text('Source of truth: the versioned JSON catalogs in the repository. This in-app draft is session-only until exported and reviewed.'),
        ],
      ),
    );
  }
}
