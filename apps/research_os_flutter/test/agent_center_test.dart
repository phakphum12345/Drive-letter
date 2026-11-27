import 'dart:async';

import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:research_os_flutter/src/api/research_os_api_client.dart';
import 'package:research_os_flutter/src/features/agents/agent_center_page.dart';

class FakeAgentApiClient extends ResearchOSApiClient {
  FakeAgentApiClient() : super(baseUrl: 'http://127.0.0.1:8787');

  final List<Map<String, dynamic>> runs = <Map<String, dynamic>>[];
  bool executed = false;
  bool confirmed = false;
  bool cancelled = false;
  bool retried = false;
  bool knowledgeSearched = false;
  int executeCalls = 0;
  int confirmCalls = 0;
  Object? actionError;
  Completer<void>? executeGate;

  @override
  Future<Map<String, dynamic>> getOrchestrations({
    String? status,
    String? query,
    String? agent,
    int? limit,
  }) async => <String, dynamic>{'runs': runs, 'count': runs.length};

  @override
  Future<Map<String, dynamic>> getV2Workspaces() async => <String, dynamic>{
        'api_version': 'v2',
        'workspaces': <Map<String, dynamic>>[
          <String, dynamic>{'workspace_id': 'research', 'name': 'Research workspace'},
        ],
        'count': 1,
      };

  @override
  Future<Map<String, dynamic>> searchWorkspaceKnowledge(
    String workspaceId, {
    String query = '',
    int pageSize = 25,
    String? cursor,
  }) async {
    knowledgeSearched = true;
    return <String, dynamic>{
      'api_version': 'v2',
      'workspace_id': workspaceId,
      'items': <Map<String, dynamic>>[
        <String, dynamic>{
          'record_id': 'research_artifact:art-1',
          'title': 'Evidence Note',
          'kind': 'research_artifact',
          'score': 3,
          'provenance': <String, dynamic>{
            'source_type': 'research_artifact',
            'source_id': 'art-1',
          },
        },
      ],
      'page': <String, dynamic>{
        'page_size': pageSize,
        'returned': 1,
        'next_cursor': null,
      },
    };
  }

  @override
  Future<Map<String, dynamic>> getAgents() async => <String, dynamic>{
        'agents': <Map<String, dynamic>>[
          <String, dynamic>{
            'agent_id': 'v2_agent_center_engineer',
            'name': 'V2 Agent Center Engineer',
            'permission_profile': 'write_confirmed',
            'health': <String, dynamic>{'status': 'ready', 'ready': true},
          },
        ],
        'count': 1,
      };

  @override
  Future<Map<String, dynamic>> getOrchestrationTimeline(String runId) async =>
      <String, dynamic>{
        'run_id': runId,
        'events': <Map<String, dynamic>>[
          <String, dynamic>{
            'event_type': 'run.created',
            'run_status': 'planned',
            'step_id': null,
          },
        ],
      };

  @override
  Future<Map<String, dynamic>> createOrchestration({
    required String objective,
    required List<Map<String, Object?>> steps,
  }) async {
    final run = <String, dynamic>{
      'run_id': 'run-12345678',
      'objective': objective,
      'status': 'planned',
      'steps': steps
          .map((step) => <String, dynamic>{
                ...step,
                'status': 'planned',
                'depends_on': step['depends_on'] ?? <String>[],
              })
          .toList(),
    };
    runs
      ..clear()
      ..add(run);
    return <String, dynamic>{'run': run};
  }

  @override
  Future<Map<String, dynamic>> executeOrchestration(
    String runId, {
    bool confirmed = false,
  }) async {
    executeCalls++;
    if (actionError != null) throw actionError!;
    executed = true;
    if (executeGate != null) await executeGate!.future;
    runs.first['status'] = 'awaiting_confirmation';
    return <String, dynamic>{'run': runs.first};
  }

  @override
  Future<Map<String, dynamic>> confirmOrchestration(String runId) async {
    confirmCalls++;
    if (actionError != null) throw actionError!;
    confirmed = true;
    runs.first['status'] = 'completed';
    final steps = runs.first['steps'] as List<dynamic>;
    for (final step in steps.whereType<Map<String, dynamic>>()) {
      step['status'] = 'completed';
    }
    return <String, dynamic>{'run': runs.first};
  }

  @override
  Future<Map<String, dynamic>> cancelOrchestration(String runId) async {
    cancelled = true;
    runs.first['status'] = 'cancelled';
    return <String, dynamic>{'run': runs.first};
  }

  @override
  Future<Map<String, dynamic>> retryOrchestration(
    String runId, {
    String? stepId,
  }) async {
    retried = true;
    runs.first['status'] = 'planned';
    return <String, dynamic>{'run': runs.first};
  }

  @override
  void close() {}
}

void configureView(WidgetTester tester, {double height = 1200}) {
  tester.view.physicalSize = Size(1200, height);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

Widget testApp(ResearchOSApiClient api) => MaterialApp(
      home: Scaffold(
        body: AgentCenterPage(apiClient: api),
      ),
    );

void main() {
  testWidgets('Agent Center creates executes and confirms orchestration',
      (tester) async {
    final api = FakeAgentApiClient();
    configureView(tester);

    await tester.pumpWidget(testApp(api));
    await tester.pumpAndSettle();

    expect(find.text('No orchestration runs yet'), findsOneWidget);
    await tester.tap(find.byKey(const Key('create-orchestration-button')));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const Key('orchestration-objective')),
      'Build a research summary',
    );
    await tester.enterText(
      find.byKey(const Key('orchestration-step-1')),
      'Research source material',
    );
    await tester.enterText(
      find.byKey(const Key('orchestration-step-2')),
      'Create final document',
    );
    await tester.tap(find.byKey(const Key('submit-orchestration')));
    await tester.pumpAndSettle();

    expect(find.text('Build a research summary'), findsOneWidget);
    expect(find.byKey(const Key('orchestration-dependency-graph')), findsOneWidget);
    expect(find.text('planned'), findsWidgets);
    expect(api.runs.single['steps'], hasLength(2));

    await tester.ensureVisible(find.byKey(const Key('execute-run-12345678')));
    await tester.tap(find.byKey(const Key('execute-run-12345678')));
    await tester.pumpAndSettle();
    expect(api.executed, isTrue);
    expect(find.text('awaiting_confirmation'), findsOneWidget);
    expect(find.byKey(const Key('approval-run-12345678')), findsOneWidget);

    await tester.ensureVisible(find.byKey(const Key('confirm-run-12345678')));
    await tester.tap(find.byKey(const Key('confirm-run-12345678')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('orchestration-confirmation-preview')), findsOneWidget);
    expect(find.byKey(const Key('confirmation-preview-objective')), findsOneWidget);
    expect(find.textContaining('Research source material'), findsOneWidget);
    expect(api.confirmCalls, 0);
    await tester.tap(find.byKey(const Key('confirm-preview-submit')));
    await tester.pumpAndSettle();
    expect(api.confirmed, isTrue);
    expect(find.text('completed'), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Agent Center V2 exposes workspace knowledge with provenance',
      (tester) async {
    final api = FakeAgentApiClient();
    configureView(tester);
    final semantics = tester.ensureSemantics();

    await tester.pumpWidget(testApp(api));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('workspace-selector')), findsOneWidget);
    expect(find.text('Research workspace'), findsOneWidget);
    expect(find.bySemanticsLabel('Search workspace knowledge'), findsNWidgets(2));

    await tester.enterText(
      find.byKey(const Key('knowledge-search-query')),
      'evidence',
    );
    await tester.tap(find.byKey(const Key('knowledge-search-button')));
    await tester.pumpAndSettle();

    expect(api.knowledgeSearched, isTrue);
    expect(find.text('Evidence Note'), findsOneWidget);
    expect(
      find.text('research_artifact • source: research_artifact / art-1'),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
    semantics.dispose();
  });

  testWidgets('Agent Center V2 exposes timeline health and cancellation controls',
      (tester) async {
    final api = FakeAgentApiClient();
    api.runs.add(<String, dynamic>{
      'run_id': 'run-v2controls',
      'objective': 'Validate V2 controls',
      'status': 'planned',
      'steps': <Map<String, dynamic>>[
        <String, dynamic>{
          'step_id': 'step-1',
          'requested_agent': 'v2_agent_center_engineer',
          'status': 'planned',
          'depends_on': <String>[],
        },
      ],
    });
    configureView(tester, height: 1400);

    await tester.pumpWidget(testApp(api));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('orchestration-dependency-graph')), findsOneWidget);
    expect(find.byKey(const Key('cancel-run-v2controls')), findsOneWidget);

    await tester.ensureVisible(find.byKey(const Key('load-agent-health')));
    await tester.tap(find.byKey(const Key('load-agent-health')));
    await tester.pumpAndSettle();
    expect(find.text('V2 Agent Center Engineer'), findsOneWidget);
    expect(find.text('ready'), findsOneWidget);

    await tester.ensureVisible(find.byKey(const Key('timeline-run-v2controls')));
    await tester.tap(find.byKey(const Key('timeline-run-v2controls')));
    await tester.pumpAndSettle();
    expect(find.text('run.created'), findsOneWidget);
    await tester.tap(find.text('Close'));
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.byKey(const Key('cancel-run-v2controls')));
    await tester.tap(find.byKey(const Key('cancel-run-v2controls')));
    await tester.pumpAndSettle();
    expect(api.cancelled, isTrue);
    expect(find.text('cancelled'), findsOneWidget);
    expect(tester.takeException(), isNull);
  }); 
  testWidgets('Agent Center exposes only lifecycle-valid controls', (tester) async {
    final api = FakeAgentApiClient();
    api.runs.addAll([
      <String, dynamic>{
        'run_id': 'run-interrupted',
        'objective': 'Recover interrupted workflow',
        'status': 'interrupted',
        'steps': <Map<String, dynamic>>[
          <String, dynamic>{
            'step_id': 'step-1',
            'objective': 'Continue saved work',
            'status': 'interrupted',
            'depends_on': <String>[],
          },
        ],
      },
      <String, dynamic>{
        'run_id': 'run-completed',
        'objective': 'Already completed',
        'status': 'completed',
        'steps': <Map<String, dynamic>>[],
      },
      <String, dynamic>{
        'run_id': 'run-failed-exhausted',
        'objective': 'Retry limit reached',
        'status': 'failed',
        'steps': <Map<String, dynamic>>[
          <String, dynamic>{
            'step_id': 'step-failed',
            'objective': 'Exhausted step',
            'status': 'failed',
            'attempt_count': 3,
            'max_attempts': 3,
          },
        ],
      },
    ]);
    configureView(tester, height: 1600);

    await tester.pumpWidget(testApp(api));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('continue-run-interrupted')), findsOneWidget);
    expect(find.byKey(const Key('resume-run-interrupted')), findsNothing);
    expect(find.byKey(const Key('execute-run-interrupted')), findsNothing);
    await tester.ensureVisible(find.byKey(const Key('continue-run-interrupted')));
    await tester.tap(find.byKey(const Key('continue-run-interrupted')));
    await tester.pumpAndSettle();
    expect(api.executeCalls, 1);
    expect(find.byKey(const Key('execute-run-completed')), findsNothing);
    expect(find.byKey(const Key('cancel-run-completed')), findsNothing);
    expect(find.byKey(const Key('retry-run-failed-exhausted')), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Agent Center reports Owner authorization errors clearly', (tester) async {
    final api = FakeAgentApiClient()
      ..actionError = const ResearchOSApiException(
        'Research OS API error 403: owner_authorization_required',
        statusCode: 403,
      );
    api.runs.add(<String, dynamic>{
      'run_id': 'run-owner-only',
      'objective': 'Owner-only workflow',
      'status': 'planned',
      'steps': <Map<String, dynamic>>[
        <String, dynamic>{
          'step_id': 'step-1',
          'objective': 'Wait for authorized execution',
          'status': 'planned',
        },
      ],
    });
    configureView(tester, height: 1400);

    await tester.pumpWidget(testApp(api));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('execute-run-owner-only')));
    await tester.tap(find.byKey(const Key('execute-run-owner-only')));
    await tester.pumpAndSettle();

    expect(find.textContaining('ไม่มีสิทธิ์ Owner'), findsOneWidget);
    expect(api.executeCalls, 1);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Agent Center prevents duplicate execution requests', (tester) async {
    final api = FakeAgentApiClient()..executeGate = Completer<void>();
    api.runs.add(<String, dynamic>{
      'run_id': 'run-single-flight',
      'objective': 'Single execution',
      'status': 'planned',
      'steps': <Map<String, dynamic>>[
        <String, dynamic>{
          'step_id': 'step-1',
          'objective': 'Run once',
          'status': 'planned',
        },
      ],
    });
    configureView(tester, height: 1400);

    await tester.pumpWidget(testApp(api));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('execute-run-single-flight')));
    await tester.tap(find.byKey(const Key('execute-run-single-flight')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('execute-run-single-flight')));
    await tester.pump();

    expect(api.executeCalls, 1);
    api.executeGate!.complete();
    await tester.pumpAndSettle();
    expect(api.executeCalls, 1);
    expect(tester.takeException(), isNull);
  });

}
