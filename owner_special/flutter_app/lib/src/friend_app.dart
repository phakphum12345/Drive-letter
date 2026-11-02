import 'package:flutter/material.dart';

import 'friend_app_shell.dart';
import 'contracts/control_center_capabilities.dart';
import 'contracts/owner_friend_capability_adapter.dart';
import 'contracts/owner_research_capability_adapter.dart';
import 'package:research_os_contracts/research_os_contracts.dart';
import 'friend_module_shell.dart';
import 'friend_theme.dart';
import 'google_identity_page.dart';
import 'launch_desk_page.dart';
import 'mission_control_desktop_page.dart';
import 'native_core_workspace_page.dart';
import 'owner_api.dart';
import 'research_os_ai_chat_page.dart';
import 'team_center.dart';

class OwnerFriendApp extends StatefulWidget {
  const OwnerFriendApp({required this.api, this.startup, this.startupError, this.researchCapabilities, super.key});
  final OwnerFriendApi api;
  final Map<String, dynamic>? startup;
  final String? startupError;
  final ResearchOSCapabilities? researchCapabilities;

  @override
  State<OwnerFriendApp> createState() => _OwnerFriendAppState();
}

class _OwnerFriendAppState extends State<OwnerFriendApp> {
  int _index = 0;
  TeamRecord _currentTeam = const TeamRecord(id: 'research', name: 'Research Team');

  void _onTeamChanged(TeamRecord team) => setState(() => _currentTeam = team);

  @override
  Widget build(BuildContext context) {
    final ownerCapabilities = OwnerFriendCapabilityAdapter(widget.api);
    final capabilities = ControlCenterCapabilities(
      owner: ownerCapabilities,
      research: widget.researchCapabilities ?? OwnerResearchCapabilityAdapter(widget.api),
    );
    final pages = <Widget>[
      MissionControlDesktopPage(projection: null),
      ResearchOsAiChatPage(api: widget.api, teamName: _currentTeam.name),
      LaunchDeskPage(api: widget.api),
      _CapabilitiesPage(api: widget.api, startup: widget.startup),
      _MemoryPage(api: widget.api),
      _ProviderPage(api: widget.api),
      _TeamPage(team: _currentTeam),
      GoogleIdentityPage(api: widget.api),
    ];

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Research OS',
      theme: FriendTheme.build(),
      home: FriendAppShell(
        index: _index,
        onIndexChanged: (value) => setState(() => _index = value),
        pages: pages,
        controlCenter: NativeCoreWorkspacePage(api: widget.api, runtimeCapability: capabilities.runtime, onNavigate: (value) => setState(() => _index = value)),
        teamCenter: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 360),
          child: TeamCenter(onChanged: _onTeamChanged),
        ),
        status: _StatusPill(api: widget.api),
      ),
    );
  }
}

class _StatusPill extends StatefulWidget {
  const _StatusPill({required this.api});
  final OwnerFriendApi api;
  @override
  State<_StatusPill> createState() => _StatusPillState();
}

class _StatusPillState extends State<_StatusPill> {
  bool? _connected;
  @override
  void initState() { super.initState(); _probe(); }

  Future<void> _probe() async {
    try {
      final result = await widget.api.health().timeout(const Duration(seconds: 8));
      if (mounted) setState(() => _connected = result['status'] == 'ok');
    } catch (_) {
      if (mounted) setState(() => _connected = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final connected = _connected == true;
    final color = _connected == null ? theme.colorScheme.onSurfaceVariant : connected ? const Color(0xFF34D399) : const Color(0xFFF59E0B);
    final label = _connected == null ? 'Checking' : connected ? 'Connected' : 'Offline';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(color: color.withValues(alpha: .10), borderRadius: BorderRadius.circular(999)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Container(width: 6, height: 6, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 7),
        Text(label, style: theme.textTheme.labelMedium?.copyWith(color: color, fontWeight: FontWeight.w700)),
      ]),
    );
  }
}

class _TeamPage extends StatelessWidget {
  const _TeamPage({required this.team});
  final TeamRecord team;

  @override
  Widget build(BuildContext context) {
    return FriendModuleShell(
      title: 'Team Workspace',
      child: ListView(children: [
        Card(child: ListTile(leading: const Icon(Icons.groups_outlined), title: Text(team.name), subtitle: Text('Team ID: ${team.id}'))),
        const SizedBox(height: 16),
        const Wrap(spacing: 8, runSpacing: 8, children: [Chip(label: Text('Chat')), Chip(label: Text('Agents')), Chip(label: Text('Memory')), Chip(label: Text('Files')), Chip(label: Text('Tasks'))]),
      ]),
    );
  }
}

class _CapabilitiesPage extends StatelessWidget {
  const _CapabilitiesPage({required this.api, this.startup});
  final OwnerFriendApi api;
  final Map<String, dynamic>? startup;
  @override
  Widget build(BuildContext context) {
    return FriendModuleShell(title: 'Capabilities', child: FutureBuilder<Map<String, dynamic>>(
      future: startup?['status'] is Map ? Future<Map<String, dynamic>>.value(Map<String, dynamic>.from(startup!['status'] as Map)) : api.status(),
      builder: (context, snapshot) {
        if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
        final status = snapshot.data!;
        final profiles = Map<String, dynamic>.from(status['brain_profiles'] as Map? ?? const <String, dynamic>{});
        final helper = Map<String, dynamic>.from(status['helper_scheduler'] as Map? ?? const <String, dynamic>{});
        final capabilities = (status['capabilities'] as List? ?? const <Object>[]).map((item) => item.toString()).toList();
        return ListView(children: [Text('Brain: ${profiles.entries.map((entry) => '${entry.key}=${entry.value}').join(' • ')}'), Text('Helpers: logical ${helper['max_logical_helpers'] ?? '-'} • active ${helper['max_active_workers'] ?? '-'}'), const SizedBox(height: 16), Wrap(spacing: 8, runSpacing: 8, children: capabilities.map((name) => Chip(label: Text(name))).toList())]);
      },
    ));
  }
}

class _MemoryPage extends StatelessWidget {
  const _MemoryPage({required this.api});
  final OwnerFriendApi api;
  @override
  Widget build(BuildContext context) => FriendModuleShell(title: 'Memory', child: FutureBuilder<Map<String, dynamic>>(future: api.memory(), builder: (context, snapshot) {
    if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
    final items = snapshot.data!['items'] as List? ?? const <Object>[];
    if (items.isEmpty) return const Center(child: Text('ยังไม่มีความจำใน profile/session นี้'));
    return ListView.builder(itemCount: items.length, itemBuilder: (context, index) { final item = Map<String, dynamic>.from(items[index] as Map); return ListTile(title: Text(item['kind']?.toString() ?? ''), subtitle: Text(item['text']?.toString() ?? '')); });
  }));
}

class _ProviderPage extends StatefulWidget {
  const _ProviderPage({required this.api});
  final OwnerFriendApi api;
  @override
  State<_ProviderPage> createState() => _ProviderPageState();
}

class _ProviderPageState extends State<_ProviderPage> {
  final _baseUrl = TextEditingController();
  final _model = TextEditingController();
  final _apiKey = TextEditingController();
  Map<String, dynamic>? _status;
  String _message = '';
  bool _busy = false;

  @override
  void initState() { super.initState(); _load(); }
  @override
  void dispose() { _baseUrl.dispose(); _model.dispose(); _apiKey.dispose(); super.dispose(); }
  Future<void> _load() async { try { final status = await widget.api.providerStatus(); if (!mounted) return; setState(() { _status = status; _baseUrl.text = status['base_url']?.toString() ?? ''; _model.text = status['model']?.toString() ?? ''; }); } catch (error) { if (mounted) setState(() => _message = '$error'); } }
  Future<void> _saveAndTest() async {
    if (_busy) return;
    setState(() { _busy = true; _message = ''; });
    try {
      final saved = await widget.api.configureProvider(baseUrl: _baseUrl.text.trim(), model: _model.text.trim(), apiKey: _apiKey.text.trim().isEmpty ? null : _apiKey.text.trim());
      _apiKey.clear();
      final tested = await widget.api.testProvider();
      final refreshed = await widget.api.providerStatus();
      if (!mounted) return;
      setState(() { _status = refreshed; final connected = tested['connected'] == true; final stored = refreshed['credential_present'] == true; _message = connected && stored ? 'Provider connected • API key stored securely' : connected ? 'Provider connected • credential status unavailable' : 'Provider test failed: ${tested['error'] ?? 'unknown'}'; });
      assert(saved.isNotEmpty);
    } catch (error) { if (mounted) setState(() => _message = '$error'); }
    finally { if (mounted) setState(() => _busy = false); }
  }
  @override
  Widget build(BuildContext context) {
    final credentialPresent = _status?['credential_present'] == true;
    return FriendModuleShell(title: 'Provider', child: ListView(children: [
      Text('Credential: ${credentialPresent ? 'stored securely' : 'not configured'} • backend: ${_status?['secret_backend'] ?? '-'}'), const SizedBox(height: 20),
      TextField(key: const Key('provider-base-url'), controller: _baseUrl, decoration: const InputDecoration(labelText: 'Base URL')), const SizedBox(height: 12),
      TextField(key: const Key('provider-model'), controller: _model, decoration: const InputDecoration(labelText: 'Model')), const SizedBox(height: 12),
      TextField(key: const Key('provider-api-key'), controller: _apiKey, obscureText: true, decoration: InputDecoration(labelText: credentialPresent ? 'API key (stored securely — leave blank to keep it)' : 'API key (enter once to store securely)', hintText: credentialPresent ? 'Stored securely; no need to enter it again' : null)),
      const SizedBox(height: 8), Text(credentialPresent ? 'The key is intentionally cleared from the field after saving. Research OS keeps it in the secure ${_status?['secret_backend'] ?? 'credential'} backend.' : 'Enter the key here only. It will be stored server-side and never displayed again.', style: Theme.of(context).textTheme.bodySmall), const SizedBox(height: 16),
      FilledButton.icon(key: const Key('provider-save-test'), onPressed: _busy ? null : _saveAndTest, icon: _busy ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.link), label: Text(_busy ? 'Testing...' : 'Save & Test Connection')),
      if (_message.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 16), child: SelectableText(_message, key: const Key('provider-message'))),
    ]));
  }
}
