import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../api/research_os_api_client.dart';

/// Recon Back Box is part of the existing Control Center, not a second runtime.
class ReconBackBoxView extends StatefulWidget {
  const ReconBackBoxView({required this.apiClient, super.key});
  final ResearchOSApiClient apiClient;
  @override
  State<ReconBackBoxView> createState() => _ReconBackBoxViewState();
}

class _ReconBackBoxViewState extends State<ReconBackBoxView> {
  static const repository = 'phakphum12345/Drive-letter';
  static const _configKey = 'research_os.recon_back_box.config.v1';
  static const _learningKey = 'research_os.recon_back_box.learning.v1';
  static const _defaultConfig = <String, Object?>{
    'schema_version': 1,
    'config_id': 'research-os-recon-back-box',
    'mode': 'observe',
    'repository': repository,
    'hash_algorithm': 'sha256',
    'deduplicate': true,
    'overwrite_allowed': false,
    'delete_allowed': false,
    'authority': 'FINAL_GATE',
    'skipped_is_pass': false,
    'unknown_is_pass': false,
    'website_learning': <String, Object?>{
      'levels': <String>['general', 'structured', 'advanced', 'validation'],
      'crawler_enabled': false,
      'allowed_domains': <String>[],
      'respect_robots_txt': true,
      'require_source_url': true,
      'require_retrieved_at': true,
      'require_content_hash': true,
    },
  };

  final _config = TextEditingController();
  final _url = TextEditingController();
  final _topic = TextEditingController();
  final _notes = TextEditingController();
  bool _loading = false;
  String? _githubError;
  String? _artifactError;
  DateTime? _observedAt;
  Map<String, dynamic>? _github;
  List<Map<String, dynamic>> _artifacts = [];
  List<Map<String, dynamic>> _learning = [];

  @override
  void initState() {
    super.initState();
    _config.text = JsonEncoder.withIndent('  ').convert(_defaultConfig);
    _loadLocal();
    _refresh();
  }

  @override
  void dispose() {
    _config.dispose();
    _url.dispose();
    _topic.dispose();
    _notes.dispose();
    super.dispose();
  }

  List<Map<String, dynamic>> _items(Object? value) => value is List
      ? value.whereType<Map>().map((x) => Map<String, dynamic>.from(x)).toList()
      : <Map<String, dynamic>>[];

  Future<void> _loadLocal() async {
    final prefs = await SharedPreferences.getInstance();
    final config = prefs.getString(_configKey);
    final raw = prefs.getString(_learningKey);
    if (!mounted) return;
    setState(() {
      if (config != null && config.isNotEmpty) _config.text = config;
      if (raw != null) {
        try { _learning = _items(jsonDecode(raw)); } on FormatException { _learning = []; }
      }
    });
  }

  Future<void> _refresh() async {
    if (_loading) return;
    setState(() { _loading = true; _githubError = null; _artifactError = null; });
    try {
      final values = await Future.wait<Map<String, dynamic>>([
        widget.apiClient.getGitHubDashboard(repository: repository),
        widget.apiClient.getKnowledgeArtifacts(),
      ]);
      if (!mounted) return;
      setState(() {
        _github = values[0];
        _artifacts = _items(values[1]['artifacts']);
        _observedAt = DateTime.now().toUtc();
      });
    } on Object {
      try {
        final value = await widget.apiClient.getGitHubDashboard(repository: repository);
        if (mounted) setState(() => _github = value);
      } on Object catch (e) { if (mounted) setState(() => _githubError = e.toString()); }
      try {
        final value = await widget.apiClient.getKnowledgeArtifacts();
        if (mounted) setState(() => _artifacts = _items(value['artifacts']));
      } on Object catch (e) { if (mounted) setState(() => _artifactError = e.toString()); }
      if (mounted) setState(() => _observedAt = DateTime.now().toUtc());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  List<Map<String, dynamic>> get _runs => _items(_github?['workflow_runs']);
  List<Map<String, dynamic>> get _pulls => _items(_github?['pull_requests']);

  Future<void> _copy(String text, String message) async {
    await Clipboard.setData(ClipboardData(text: text));
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _saveConfig() async {
    try {
      final decoded = jsonDecode(_config.text);
      if (decoded is! Map || decoded['schema_version'] != 1 || decoded['config_id'] is! String) {
        throw const FormatException('schema_version=1 and config_id are required');
      }
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_configKey, JsonEncoder.withIndent('  ').convert(decoded));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Saved locally only; repository unchanged.')),
        );
      }
    } on Object catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Invalid config: $e')));
    }
  }

  Future<void> _addLearning() async {
    final uri = Uri.tryParse(_url.text.trim());
    if (uri == null || uri.scheme != 'https' || uri.host.isEmpty ||
        _topic.text.trim().isEmpty || _notes.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('HTTPS URL, topic and notes are required.')),
      );
      return;
    }
    final next = <Map<String, dynamic>>[
      <String, dynamic>{
        'source_url': uri.toString(),
        'topic': _topic.text.trim(),
        'notes': _notes.text.trim(),
        'level': 'general',
        'retrieved_at': DateTime.now().toUtc().toIso8601String(),
        'verification': 'user-entered; not independently verified',
      },
      ..._learning,
    ];
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_learningKey, jsonEncode(next));
    if (!mounted) return;
    setState(() { _learning = next; _url.clear(); _topic.clear(); _notes.clear(); });
  }

  @override
  Widget build(BuildContext context) {
    final runs = _runs;
    final pulls = _pulls;
    return DefaultTabController(
      length: 5,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 12, 8),
            child: Row(children: [
              Container(
                width: 42, height: 42,
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.inventory_2_outlined),
              ),
              const SizedBox(width: 12),
              const Expanded(child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Recon Back Box', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
                  Text('Workflow • Artifacts • Config • Learning • Evidence'),
                ],
              )),
              IconButton(
                tooltip: 'Refresh',
                onPressed: _loading ? null : _refresh,
                icon: _loading
                    ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.refresh),
              ),
            ]),
          ),
          if (_loading) const LinearProgressIndicator(minHeight: 2),
          const TabBar(isScrollable: true, tabs: [
            Tab(icon: Icon(Icons.dashboard_outlined), text: 'Overview'),
            Tab(icon: Icon(Icons.account_tree_outlined), text: 'Runs & PRs'),
            Tab(icon: Icon(Icons.inventory_2_outlined), text: 'Artifacts'),
            Tab(icon: Icon(Icons.tune_outlined), text: 'Config'),
            Tab(icon: Icon(Icons.school_outlined), text: 'Learning & Evidence'),
          ]),
          Expanded(child: TabBarView(children: [
            _overview(context, runs, pulls),
            _runsView(context, runs, pulls),
            _artifactsView(context),
            _configView(context),
            _learningView(context),
          ])),
        ],
      ),
    );
  }

  Widget _overview(BuildContext context, List<Map<String, dynamic>> runs, List<Map<String, dynamic>> pulls) {
    final successes = runs.where((x) => x['conclusion'] == 'success').length;
    final skipped = runs.where((x) => x['conclusion'] == 'skipped').length;
    final failures = runs.where((x) => ['failure', 'cancelled', 'timed_out'].contains(x['conclusion'])).length;
    return ListView(padding: const EdgeInsets.all(16), children: [
      Wrap(spacing: 10, runSpacing: 10, children: [
        _Metric('API source', _github == null ? 'UNKNOWN' : 'OBSERVED', Icons.cloud_done_outlined),
        _Metric('Workflow runs', runs.length.toString(), Icons.account_tree_outlined),
        _Metric('Open PRs', pulls.length.toString(), Icons.merge_type_outlined),
        _Metric('Knowledge artifacts', _artifacts.length.toString(), Icons.inventory_2_outlined),
      ]),
      const SizedBox(height: 12),
      Card(child: ListTile(
        leading: Icon(_github == null ? Icons.help_outline : Icons.fact_check_outlined),
        title: Text(_githubError ?? 'Repository: $repository'),
        subtitle: Text(_observedAt == null ? 'Observation time UNKNOWN' : 'Observed at ${_observedAt!.toIso8601String()}'),
      )),
      Card(child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Evidence-aware status', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Wrap(spacing: 8, children: [
            Chip(label: Text('Success: $successes')),
            Chip(label: Text('Skipped: $skipped')),
            Chip(label: Text('Failed: $failures')),
          ]),
          const SizedBox(height: 8),
          const Text('Skipped, missing, stale and unknown evidence are not PASS. FINAL_GATE remains the only authority.'),
        ]),
      )),
      const Card(child: ListTile(
        leading: Icon(Icons.security_outlined),
        title: Text('Safety boundary'),
        subtitle: Text('Uses the authenticated Research OS API. No GitHub token is stored in this UI. No merge, deploy or repository-write action is provided.'),
      )),
      if (_githubError != null || _artifactError != null)
        Card(child: ListTile(
          leading: const Icon(Icons.info_outline),
          title: const Text('Some sources are unavailable'),
          subtitle: Text('${_githubError ?? ''}\n${_artifactError ?? ''}'),
        )),
    ]);
  }

  Widget _runsView(BuildContext context, List<Map<String, dynamic>> runs, List<Map<String, dynamic>> pulls) {
    return ListView(padding: const EdgeInsets.all(16), children: [
      Text('Workflow runs', style: Theme.of(context).textTheme.titleLarge),
      if (_githubError != null) _notice('Workflow data unavailable', _githubError!),
      if (runs.isEmpty && _githubError == null) _notice('UNKNOWN', 'No workflow run records returned. This does not prove there are no runs.'),
      ...runs.map((item) {
        final result = (item['conclusion'] ?? item['status'] ?? 'UNKNOWN').toString();
        final icon = result == 'success' ? Icons.check_circle_outline : result == 'skipped' ? Icons.skip_next_outlined : Icons.help_outline;
        return Card(child: ListTile(
          leading: Icon(icon),
          title: Text((item['name'] ?? item['display_title'] ?? 'Workflow').toString()),
          subtitle: Text('SHA: ${item['head_sha'] ?? item['sha'] ?? 'UNKNOWN'}\nStatus: $result'),
          isThreeLine: true,
        ));
      }),
      const SizedBox(height: 16),
      Text('Pull requests', style: Theme.of(context).textTheme.titleLarge),
      if (pulls.isEmpty) _notice('UNKNOWN', 'No PR records returned.'),
      ...pulls.map((item) => Card(child: ListTile(
        leading: const Icon(Icons.merge_type_outlined),
        title: Text('#${item['number'] ?? '?'} ${item['title'] ?? 'Pull request'}'),
        subtitle: Text('State: ${item['state'] ?? 'UNKNOWN'} • Draft: ${item['draft'] ?? 'UNKNOWN'}'),
      ))),
    ]);
  }

  Widget _artifactsView(BuildContext context) => ListView(padding: const EdgeInsets.all(16), children: [
    Text('Research OS knowledge artifacts', style: Theme.of(context).textTheme.titleLarge),
    const SizedBox(height: 6),
    const Text('GitHub Actions artifact download and retention metadata are not currently exposed by the Research OS API; this panel does not infer them.'),
    if (_artifactError != null) _notice('Artifact source unavailable', _artifactError!),
    if (_artifacts.isEmpty && _artifactError == null) _notice('UNKNOWN', 'No knowledge artifacts returned; this does not prove the store is empty.'),
    ..._artifacts.map((item) => Card(child: ListTile(
      leading: const Icon(Icons.description_outlined),
      title: Text((item['title'] ?? item['artifact_id'] ?? 'Artifact').toString()),
      subtitle: Text('ID: ${item['artifact_id'] ?? 'UNKNOWN'}\nStatus: ${item['status'] ?? 'UNKNOWN'}\nPath: ${item['path'] ?? 'UNKNOWN'}'),
      isThreeLine: true,
    ))),
  ]);

  Widget _configView(BuildContext context) => ListView(padding: const EdgeInsets.all(16), children: [
    Text('Config Center', style: Theme.of(context).textTheme.titleLarge),
    const SizedBox(height: 6),
    const Text('Saved in this Research OS client only. It does not commit to GitHub or change server policy.'),
    const SizedBox(height: 12),
    TextField(
      key: const Key('recon-back-box-config-editor'),
      controller: _config,
      minLines: 12,
      maxLines: 22,
      autocorrect: false,
      enableSuggestions: false,
      style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
      decoration: const InputDecoration(labelText: 'Config JSON', alignLabelWithHint: true, border: OutlineInputBorder()),
    ),
    const SizedBox(height: 12),
    Wrap(spacing: 8, runSpacing: 8, children: [
      FilledButton.icon(onPressed: _saveConfig, icon: const Icon(Icons.save_outlined), label: const Text('Save locally')),
      OutlinedButton.icon(
        onPressed: () => _copy(_config.text, 'Config JSON copied'),
        icon: const Icon(Icons.copy_all_outlined),
        label: const Text('Copy JSON'),
      ),
      OutlinedButton.icon(
        onPressed: () => setState(() => _config.text = JsonEncoder.withIndent('  ').convert(_defaultConfig)),
        icon: const Icon(Icons.restart_alt),
        label: const Text('Reset draft'),
      ),
    ]),
  ]);

  Widget _learningView(BuildContext context) => ListView(padding: const EdgeInsets.all(16), children: [
    Text('Website Learning', style: Theme.of(context).textTheme.titleLarge),
    const SizedBox(height: 6),
    const Text('General → Structured → Advanced → Validation. Crawling remains disabled; notes are labeled user-entered until independently verified.'),
    const SizedBox(height: 12),
    TextField(controller: _url, decoration: const InputDecoration(labelText: 'Source URL (HTTPS)', border: OutlineInputBorder())),
    const SizedBox(height: 8),
    TextField(controller: _topic, decoration: const InputDecoration(labelText: 'Topic / Domain', border: OutlineInputBorder())),
    const SizedBox(height: 8),
    TextField(controller: _notes, minLines: 2, maxLines: 5, decoration: const InputDecoration(labelText: 'Notes / claims to validate', border: OutlineInputBorder())),
    const SizedBox(height: 8),
    Wrap(spacing: 8, children: [
      FilledButton.icon(onPressed: _addLearning, icon: const Icon(Icons.add), label: const Text('Add note')),
      OutlinedButton.icon(
        onPressed: () => _copy(JsonEncoder.withIndent('  ').convert(<String, Object?>{'schema': 'RECON_WEBSITE_LEARNING_LEDGER_V1', 'entries': _learning}), 'Learning ledger copied'),
        icon: const Icon(Icons.copy_all_outlined),
        label: const Text('Export ledger JSON'),
      ),
    ]),
    const SizedBox(height: 16),
    Text('Local ledger (${_learning.length})', style: Theme.of(context).textTheme.titleMedium),
    if (_learning.isEmpty) _notice('No entries yet', 'Add a source URL, topic and notes.'),
    ..._learning.map((item) => Card(child: ListTile(
      leading: const Icon(Icons.school_outlined),
      title: Text((item['topic'] ?? 'Untitled').toString()),
      subtitle: Text('${item['level'] ?? 'general'} • ${item['source_url'] ?? 'No source'}\n${item['notes'] ?? ''}\n${item['verification'] ?? 'UNKNOWN'}'),
      isThreeLine: true,
    ))),
    const SizedBox(height: 18),
    Text('Evidence & Provenance', style: Theme.of(context).textTheme.titleMedium),
    Card(child: Padding(
      padding: const EdgeInsets.all(14),
      child: SelectableText(JsonEncoder.withIndent('  ').convert(<String, Object?>{
        'repository': repository,
        'authority': 'FINAL_GATE',
        'source': 'Research OS authenticated API',
        'skipped_is_pass': false,
        'unknown_is_pass': false,
        'github_actions_artifacts': 'not exposed by current Research OS API',
      })),
    )),
  ]);

  Widget _notice(String title, String message) => Card(
    child: ListTile(leading: const Icon(Icons.info_outline), title: Text(title), subtitle: SelectableText(message)),
  );
}

class _Metric extends StatelessWidget {
  const _Metric(this.label, this.value, this.icon);
  final String label;
  final String value;
  final IconData icon;
  @override
  Widget build(BuildContext context) => SizedBox(
    width: 190,
    child: Card(margin: EdgeInsets.zero, child: Padding(
      padding: const EdgeInsets.all(14),
      child: Row(children: [
        Icon(icon),
        const SizedBox(width: 10),
        Expanded(child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(label, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 4),
            Text(value, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
          ],
        )),
      ]),
    )),
  );
}
