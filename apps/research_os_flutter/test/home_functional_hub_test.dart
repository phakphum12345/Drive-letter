import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:research_os_flutter/src/api/research_os_api_client.dart';
import 'package:research_os_flutter/src/features/home/home_page.dart';

class FakeHomeApiClient extends ResearchOSApiClient {
  FakeHomeApiClient() : super(baseUrl: 'http://127.0.0.1:8787');

  @override
  Future<Map<String, dynamic>> getHealth() async => <String, dynamic>{
        'status': 'ok',
        'version': 'test',
        'memory': true,
        'google_workspace': true,
      };

  @override
  Future<Map<String, dynamic>> getProviders() async =>
      <String, dynamic>{'active': 'ollama'};

  @override
  Future<Map<String, dynamic>> getAgents() async => <String, dynamic>{
        'agents': <Map<String, dynamic>>[
          <String, dynamic>{'agent_id': 'researcher'},
          <String, dynamic>{'agent_id': 'writer'},
        ],
      };

  @override
  Future<Map<String, dynamic>> getOrchestrations({
    String? status,
    String? query,
    String? agent,
    int? limit,
  }) async =>
      <String, dynamic>{
        'runs': <Map<String, dynamic>>[
          <String, dynamic>{
            'run_id': 'run-home-1',
            'objective': 'Prepare research brief',
            'status': 'planned',
          },
        ],
      };

  @override
  Future<Map<String, dynamic>> getProjects() async =>
      <String, dynamic>{'projects': <Map<String, dynamic>>[
        <String, dynamic>{'project_id': 'project-1'},
      ]};

  @override
  Future<Map<String, dynamic>> getKnowledgeArtifacts() async =>
      <String, dynamic>{'artifacts': <Map<String, dynamic>>[
        <String, dynamic>{'artifact_id': 'artifact-1'},
        <String, dynamic>{'artifact_id': 'artifact-2'},
        <String, dynamic>{'artifact_id': 'artifact-3'},
      ]};

  @override
  void close() {}
}

class OfflineOptionalHomeApiClient extends FakeHomeApiClient {
  @override
  Future<Map<String, dynamic>> getAgents() async {
    throw const ResearchOSApiException('agent endpoint unavailable');
  }
}

void configureHomeViewport(WidgetTester tester) {
  tester.view.physicalSize = const Size(1280, 1400);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

void main() {
  testWidgets('Home hub loads live counts, recent runs and opens real workspaces',
      (tester) async {
    configureHomeViewport(tester);
    final api = FakeHomeApiClient();
    final destinations = <int>[];

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: HomePage(apiClient: api, onNavigate: destinations.add),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('home-metric-agents')), findsOneWidget);
    expect(find.byKey(const Key('home-metric-workflow-runs')), findsOneWidget);
    expect(find.byKey(const Key('home-metric-projects')), findsOneWidget);
    expect(find.byKey(const Key('home-metric-knowledge-items')), findsOneWidget);
    expect(find.text('2'), findsOneWidget);
    expect(find.text('3'), findsOneWidget);
    expect(find.text('Prepare research brief'), findsOneWidget);
    expect(find.byKey(const Key('home-workflow-run-home-1')), findsOneWidget);

    await tester.ensureVisible(find.byKey(const Key('home-workspace-agent-center')));
    await tester.tap(find.byKey(const Key('home-workspace-agent-center')));
    await tester.pumpAndSettle();
    expect(destinations, <int>[2]);

    await tester.ensureVisible(find.byKey(const Key('home-workflow-run-home-1')));
    await tester.tap(find.byKey(const Key('home-workflow-run-home-1')));
    await tester.pumpAndSettle();
    expect(destinations, <int>[2, 15]);
    expect(tester.takeException(), isNull);
  });

  testWidgets('optional dashboard endpoint failure does not hide working tools',
      (tester) async {
    configureHomeViewport(tester);

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: HomePage(apiClient: OfflineOptionalHomeApiClient()),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Unavailable'), findsOneWidget);
    expect(find.text('Talk to Friend'), findsOneWidget);
    expect(find.text('Agent Center'), findsOneWidget);
    expect(find.byKey(const Key('home-workflows-unavailable')), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
