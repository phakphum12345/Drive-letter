import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../lib/src/api/research_os_api_client.dart';
import '../lib/src/features/control_center/recon_back_box_view.dart';

class _FakeApiClient extends ResearchOSApiClient {
  _FakeApiClient() : super(baseUrl: 'http://127.0.0.1:8787');

  @override
  Future<Map<String, dynamic>> getGitHubDashboard({
    String? repository,
    String? accountId,
  }) async => <String, dynamic>{
        'workflow_runs': <Map<String, dynamic>>[
          <String, dynamic>{'name': 'CI', 'head_sha': 'abc123', 'conclusion': 'success'},
          <String, dynamic>{'name': 'Optional check', 'head_sha': 'def456', 'conclusion': 'skipped'},
        ],
        'pull_requests': <Map<String, dynamic>>[],
      };

  @override
  Future<Map<String, dynamic>> getKnowledgeArtifacts() async =>
      <String, dynamic>{'artifacts': <Map<String, dynamic>>[]};
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues(<String, Object>{});
  });

  testWidgets('Recon Back Box is integrated and preserves skipped semantics', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ReconBackBoxView(apiClient: _FakeApiClient()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Recon Back Box'), findsOneWidget);
    expect(find.text('Skipped: 1'), findsOneWidget);
    expect(find.textContaining('Skipped, missing, stale and unknown evidence are not PASS'), findsOneWidget);

    await tester.tap(find.text('Config'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('recon-back-box-config-editor')), findsOneWidget);

    await tester.tap(find.text('Learning & Evidence'));
    await tester.pumpAndSettle();
    expect(find.text('Website Learning'), findsOneWidget);
    expect(find.text('Evidence & Provenance'), findsOneWidget);
  });
}
