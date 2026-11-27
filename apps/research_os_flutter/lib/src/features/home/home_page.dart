import 'package:material_ui/material_ui.dart';

import '../../api/research_os_api_client.dart';

class HomePage extends StatefulWidget {
  const HomePage({required this.apiClient, this.onNavigate, super.key});

  final ResearchOSApiClient apiClient;
  final ValueChanged<int>? onNavigate;

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  bool _loading = true;
  String? _error;
  Map<String, dynamic>? _health;
  Map<String, dynamic>? _providers;
  Map<String, dynamic>? _agents;
  Map<String, dynamic>? _workflows;
  Map<String, dynamic>? _projects;
  Map<String, dynamic>? _knowledge;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait<Object?>(<Future<Object?>>[
        widget.apiClient.getHealth(),
        widget.apiClient.getProviders(),
        _tryLoad(widget.apiClient.getAgents),
        _tryLoad(() => widget.apiClient.getOrchestrations(limit: 8)),
        _tryLoad(widget.apiClient.getProjects),
        _tryLoad(widget.apiClient.getKnowledgeArtifacts),
      ]);
      if (!mounted) return;
      setState(() {
        _health = results[0] as Map<String, dynamic>;
        _providers = results[1] as Map<String, dynamic>;
        _agents = results[2] as Map<String, dynamic>?;
        _workflows = results[3] as Map<String, dynamic>?;
        _projects = results[4] as Map<String, dynamic>?;
        _knowledge = results[5] as Map<String, dynamic>?;
        _loading = false;
      });
    } on Object catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _loading = false;
      });
    }
  }

  Future<Map<String, dynamic>?> _tryLoad(
    Future<Map<String, dynamic>> Function() load,
  ) async {
    try {
      return await load();
    } on Object {
      // Optional dashboard panels degrade independently; the primary
      // health/provider state remains visible when one capability is offline.
      return null;
    }
  }

  List<Map<String, dynamic>> _items(
    Map<String, dynamic>? payload,
    List<String> keys,
  ) {
    if (payload == null) return const <Map<String, dynamic>>[];
    for (final key in keys) {
      final value = payload[key];
      if (value is List) {
        return value.whereType<Map>().map(
          (item) => Map<String, dynamic>.from(item),
        ).toList();
      }
    }
    return const <Map<String, dynamic>>[];
  }

  String _countLabel(Map<String, dynamic>? payload, List<String> keys) {
    if (payload == null) return 'Unavailable';
    return '${_items(payload, keys).length}';
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final activeProvider = _providers?['active']?.toString() ?? 'unknown';
    final apiReady = _health?['status']?.toString() == 'ok';

    return Scaffold(
      appBar: AppBar(
        title: const Text('Overview'),
        actions: <Widget>[
          IconButton(
            tooltip: 'Refresh dashboard',
            onPressed: _loading ? null : _refresh,
            icon: const Icon(Icons.refresh),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 18, 24, 32),
            children: <Widget>[
              Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: <Color>[
                    scheme.primaryContainer,
                    scheme.primaryContainer.withValues(alpha: .58),
                  ],
                ),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Row(
                children: <Widget>[
                  Container(
                    width: 54,
                    height: 54,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: scheme.primary,
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Text(
                      'R',
                      style: TextStyle(
                        color: scheme.onPrimary,
                        fontSize: 26,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ),
                  const SizedBox(width: 18),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          'Research OS',
                          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                                fontWeight: FontWeight.w800,
                              ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'AI • Memory • Knowledge • Agents • Workspace',
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      ],
                    ),
                  ),
                  Flexible(
                    child: Align(
                      alignment: Alignment.centerRight,
                      child: _HealthBadge(ready: apiReady),
                    ),
                  ),
                ],
              ),
            ),
            if (_loading) ...<Widget>[
              const SizedBox(height: 14),
              const LinearProgressIndicator(),
            ],
            if (_error != null) ...<Widget>[
              const SizedBox(height: 16),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(18),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Icon(Icons.error_outline, color: scheme.error),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            const Text(
                              'Research OS API unavailable',
                              style: TextStyle(fontWeight: FontWeight.w700),
                            ),
                            const SizedBox(height: 6),
                            Text(_error!),
                          ],
                        ),
                      ),
                      TextButton(onPressed: _refresh, child: const Text('Retry')),
                    ],
                  ),
                ),
              ),
            ],
            const SizedBox(height: 24),
            _SectionHeader(
              title: 'System status',
              subtitle: 'Current health of the local Research OS workspace',
            ),
            const SizedBox(height: 12),
            LayoutBuilder(
              builder: (context, constraints) {
                final columns = constraints.maxWidth >= 1050
                    ? 4
                    : constraints.maxWidth >= 650
                        ? 2
                        : 1;
                return GridView.count(
                  crossAxisCount: columns,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  mainAxisSpacing: 12,
                  crossAxisSpacing: 12,
                  mainAxisExtent: 140,
                  children: <Widget>[
                    _StatusCard(
                      icon: Icons.dns_outlined,
                      title: 'Local API',
                      value: apiReady ? 'Online' : 'Offline',
                      detail: _health?['version']?.toString() ?? 'Research OS API',
                    ),
                    _StatusCard(
                      icon: Icons.smart_toy_outlined,
                      title: 'AI Provider',
                      value: activeProvider,
                      detail: 'Active inference provider',
                    ),
                    _StatusCard(
                      icon: Icons.memory_outlined,
                      title: 'Memory',
                      value: _health?['memory'] == true ? 'Ready' : 'Unknown',
                      detail: 'Local knowledge memory',
                    ),
                    _StatusCard(
                      icon: Icons.apps_outlined,
                      title: 'Workspace',
                      value: _health?['google_workspace'] == true ? 'Available' : 'Not ready',
                      detail: 'Google Workspace connector',
                    ),
                  ],
                );
              },
            ),
            const SizedBox(height: 26),
            _SectionHeader(
              title: 'Live workspace activity',
              subtitle: 'Counts are read from Research OS APIs. Unavailable means the endpoint could not be observed.',
            ),
            const SizedBox(height: 12),
            LayoutBuilder(
              builder: (context, constraints) {
                final columns = constraints.maxWidth >= 900 ? 4 : constraints.maxWidth >= 560 ? 2 : 1;
                return GridView.count(
                  crossAxisCount: columns,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  mainAxisSpacing: 10,
                  crossAxisSpacing: 10,
                  mainAxisExtent: 116,
                  children: <Widget>[
                    _LiveMetric(title: 'Agents', value: _countLabel(_agents, const ['agents']), icon: Icons.smart_toy_outlined),
                    _LiveMetric(title: 'Workflow runs', value: _countLabel(_workflows, const ['runs']), icon: Icons.account_tree_outlined),
                    _LiveMetric(title: 'Projects', value: _countLabel(_projects, const ['projects']), icon: Icons.folder_outlined),
                    _LiveMetric(title: 'Knowledge items', value: _countLabel(_knowledge, const ['artifacts']), icon: Icons.local_library_outlined),
                  ],
                );
              },
            ),
            const SizedBox(height: 26),
            _SectionHeader(
              title: 'Open a tool',
              subtitle: 'Go directly to a working area instead of navigating through documentation.',
            ),
            const SizedBox(height: 12),
            LayoutBuilder(
              builder: (context, constraints) {
                final columns = constraints.maxWidth >= 980 ? 3 : constraints.maxWidth >= 620 ? 2 : 1;
                final width = (constraints.maxWidth - ((columns - 1) * 12)) / columns;
                return Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: <Widget>[
                    _WorkspaceCard(Icons.chat_bubble_outline, 'Talk to Friend', 'Start a conversation with the configured AI provider', onTap: () => widget.onNavigate?.call(1)),
                    _WorkspaceCard(Icons.smart_toy_outlined, 'Agent Center', 'Create, review and control agent workflows', onTap: () => widget.onNavigate?.call(2)),
                    _WorkspaceCard(Icons.account_tree_outlined, 'Workflows', 'Inspect runs, steps, approvals and timelines', onTap: () => widget.onNavigate?.call(15)),
                    _WorkspaceCard(Icons.local_library_outlined, 'Knowledge Library', 'Search and inspect saved research artifacts', onTap: () => widget.onNavigate?.call(3)),
                    _WorkspaceCard(Icons.folder_open_outlined, 'Projects', 'Open project workspaces and their current state', onTap: () => widget.onNavigate?.call(14)),
                    _WorkspaceCard(Icons.link_outlined, 'Connections', 'Manage GitHub and Google Workspace', onTap: () => widget.onNavigate?.call(6)),
                    _WorkspaceCard(Icons.monitor_heart_outlined, 'System Monitor', 'Inspect runtime health and service status', onTap: () => widget.onNavigate?.call(8)),
                    _WorkspaceCard(Icons.tune_outlined, 'Control Center', 'Inspect runtime state, evidence and audit history', onTap: () => widget.onNavigate?.call(16)),
                  ].map((card) => SizedBox(width: width, child: card)).toList(),
                );
              },
            ),
            const SizedBox(height: 26),
            _SectionHeader(
              title: 'Recent workflow runs',
              subtitle: 'Latest records returned by the orchestration service.',
            ),
            const SizedBox(height: 10),
            if (_workflows == null)
              const Card(
                child: ListTile(
                  key: Key('home-workflows-unavailable'),
                  leading: Icon(Icons.cloud_off_outlined),
                  title: Text('Workflow service unavailable'),
                  subtitle: Text('Other Research OS tools remain available.'),
                ),
              )
            else if (_items(_workflows, const ['runs']).isEmpty)
              const Card(
                child: ListTile(
                  key: Key('home-no-workflows'),
                  leading: Icon(Icons.inbox_outlined),
                  title: Text('No workflow runs yet'),
                  subtitle: Text('Open Agent Center to create your first workflow.'),
                ),
              )
            else
              ..._items(_workflows, const ['runs']).take(5).map((run) {
                final id = run['run_id']?.toString() ?? 'unknown';
                final objective = run['objective']?.toString() ?? 'Untitled workflow';
                final status = run['status']?.toString() ?? 'UNKNOWN';
                return Card(
                  child: ListTile(
                    key: Key('home-workflow-$id'),
                    leading: const Icon(Icons.route_outlined),
                    title: Text(objective, maxLines: 1, overflow: TextOverflow.ellipsis),
                    subtitle: Text('Run $id'),
                    trailing: Chip(label: Text(status)),
                    onTap: () => widget.onNavigate?.call(15),
                  ),
                );
              }),
          ],
        ),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, required this.subtitle});
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(title, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
        const SizedBox(height: 3),
        Text(subtitle, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
      ],
    );
  }
}

class _HealthBadge extends StatelessWidget {
  const _HealthBadge({required this.ready});
  final bool ready;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: scheme.surface.withValues(alpha: .75),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(Icons.circle, size: 9, color: ready ? Colors.green : scheme.error),
          const SizedBox(width: 7),
          Flexible(
            child: Text(
              ready ? 'System ready' : 'API offline',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }
}

class _StatusCard extends StatelessWidget {
  const _StatusCard({required this.icon, required this.title, required this.value, required this.detail});
  final IconData icon;
  final String title;
  final String value;
  final String detail;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Container(
                  width: 36,
                  height: 36,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(color: scheme.secondaryContainer, borderRadius: BorderRadius.circular(10)),
                  child: Icon(icon, size: 20, color: scheme.onSecondaryContainer),
                ),
                const Spacer(),
                Icon(Icons.circle, size: 8, color: scheme.primary),
              ],
            ),
            const Spacer(),
            Text(title, style: Theme.of(context).textTheme.labelMedium?.copyWith(color: scheme.onSurfaceVariant)),
            const SizedBox(height: 2),
            Text(value, maxLines: 1, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
            Text(detail, maxLines: 1, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

class _LiveMetric extends StatelessWidget {
  const _LiveMetric({required this.title, required this.value, required this.icon});

  final String title;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: <Widget>[
            Icon(icon, color: theme.colorScheme.primary, size: 24),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(title, style: theme.textTheme.labelMedium),
                  const SizedBox(height: 4),
                  Text(value, key: Key('home-metric-${title.toLowerCase().replaceAll(' ', '-')}'), style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _WorkspaceCard extends StatelessWidget {
  const _WorkspaceCard(this.icon, this.title, this.subtitle, {this.onTap});

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final slug = title
        .toLowerCase()
        .replaceAll(RegExp(r'[^a-z0-9]+'), '-')
        .replaceAll(RegExp(r'^-|-\$'), '');
    return Card(
      child: InkWell(
        key: Key('home-workspace-$slug'),
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Row(
            children: <Widget>[
              Container(
                width: 44,
                height: 44,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: scheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(13),
                ),
                child: Icon(icon, color: scheme.primary),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
