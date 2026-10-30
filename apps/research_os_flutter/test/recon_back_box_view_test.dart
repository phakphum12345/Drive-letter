import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:research_os_flutter/src/api/research_os_api_client.dart';
import 'package:research_os_flutter/src/features/control_center/recon_back_box_view.dart';

class _FakeApiClient extends ResearchOSApiClient {
  _FakeApiClient() : super(baseUrl: 'http://127.0.0.1:8787');

  final requestedDashboardRepositories = <String>[];

  @override
  Future<Map<String, dynamic>> getPublicGitHubRepositories(String owner) async =>
      <String, dynamic>{
        'owner': owner,
        'visibility_filter': 'public_only',
        'repositories': <Map<String, dynamic>>[
          <String, dynamic>{
            'full_name': owner == 'phakphum12345'
                ? '$owner/Drive-letter'
                : '$owner/sample-public',
          },
        ],
      };

  @override
  Future<Map<String, dynamic>> getPublicGitHubDashboard({
    required String repository,
  }) async {
    requestedDashboardRepositories.add(repository);
    return <String, dynamic>{
      'workflow_runs': <Map<String, dynamic>>[
        <String, dynamic>{'name': 'CI', 'head_sha': 'abc123', 'conclusion': 'success'},
        <String, dynamic>{'name': 'Optional check', 'head_sha': 'def456', 'conclusion': 'skipped'},
      ],
      'pull_requests': <Map<String, dynamic>>[],
    };
  }

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


  testWidgets('custom public GitHub organization can be loaded and applied', (tester) async {
    final api = _FakeApiClient();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: ReconBackBoxView(apiClient: api)),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const Key('recon-back-box-custom-owner')),
      'octo-org',
    );
    await tester.tap(find.byKey(const Key('recon-back-box-load-owner')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('recon-back-box-repository-selector')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('octo-org/sample-public').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('recon-back-box-apply-target')));
    await tester.pumpAndSettle();
    await tester.drag(find.byType(ListView).first, const Offset(0, -520));
    await tester.pumpAndSettle();

    expect(find.text('Repository: octo-org/sample-public'), findsOneWidget);
    expect(api.requestedDashboardRepositories, contains('octo-org/sample-public'));
  });

  testWidgets('Recon Back Box is integrated and preserves skipped semantics', (tester) async {
    final api = _FakeApiClient();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ReconBackBoxView(apiClient: api),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Recon Back Box'), findsOneWidget);
    expect(find.byKey(const Key('recon-back-box-owner-selector')), findsOneWidget);
    expect(find.byKey(const Key('recon-back-box-repository-selector')), findsOneWidget);
    await tester.drag(find.byType(ListView).first, const Offset(0, -520));
    await tester.pumpAndSettle();
    expect(find.text('Skipped: 1'), findsOneWidget);
    expect(find.textContaining('Skipped, missing, stale and unknown evidence are not PASS'), findsOneWidget);
    await tester.drag(find.byType(ListView).first, const Offset(0, 520));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('recon-back-box-owner-selector')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('phakphoum38-stack').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('recon-back-box-repository-selector')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('phakphoum38-stack/sample-public').last);
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('recon-back-box-apply-target')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('recon-back-box-apply-target')));
    await tester.pumpAndSettle();
    await tester.drag(find.byType(ListView).first, const Offset(0, -520));
    await tester.pumpAndSettle();
    expect(find.text('Repository: phakphoum38-stack/sample-public'), findsOneWidget);
    expect(api.requestedDashboardRepositories, contains('phakphoum38-stack/sample-public'));

    await tester.tap(find.text('Config'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('recon-back-box-config-editor')), findsOneWidget);

    await tester.tap(find.text('Learning & Evidence'));
    await tester.pumpAndSettle();
    expect(find.text('Website Learning'), findsOneWidget);
    expect(find.text('Source URL (HTTPS)'), findsOneWidget);
  });
}
