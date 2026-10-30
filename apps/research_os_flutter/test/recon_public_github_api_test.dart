import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:research_os_flutter/src/api/research_os_api_client.dart';

void main() {
  test('public organization discovery uses unauthenticated GitHub API', () async {
    final requests = <http.Request>[];
    final client = MockClient((request) async {
      requests.add(request);
      expect(request.headers.containsKey('authorization'), isFalse);
      if (request.url.path == '/users/octo-org') {
        return http.Response('{"message":"Not Found"}', 404);
      }
      if (request.url.path == '/orgs/octo-org') {
        return http.Response('{"type":"Organization"}', 200);
      }
      if (request.url.path == '/orgs/octo-org/repos') {
        return http.Response(jsonEncode([
          {'full_name': 'octo-org/app', 'private': false, 'default_branch': 'main'},
        ]), 200);
      }
      return http.Response('unexpected request', 500);
    });
    final api = ResearchOSApiClient(baseUrl: 'https://unused.example', client: client);
    final result = await api.getPublicGitHubRepositories('octo-org');
    expect(result['owner_type'], 'organization');
    expect(result['visibility_filter'], 'public_only');
    expect((result['repositories'] as List).single['full_name'], 'octo-org/app');
    expect(requests.map((request) => request.url.path),
        contains('/orgs/octo-org/repos'));
    api.close();
  });

  test('dashboard reads public metadata, commits, PRs and workflow runs', () async {
    final paths = <String>[];
    final client = MockClient((request) async {
      paths.add(request.url.path);
      expect(request.headers.containsKey('authorization'), isFalse);
      switch (request.url.path) {
        case '/repos/octo/app':
          return http.Response(jsonEncode({
            'full_name': 'octo/app',
            'private': false,
            'visibility': 'public',
            'default_branch': 'trunk',
          }), 200);
        case '/repos/octo/app/commits':
        case '/repos/octo/app/pulls':
          return http.Response('[]', 200);
        case '/repos/octo/app/actions/runs':
          return http.Response('{"workflow_runs":[]}', 200);
        default:
          return http.Response('unexpected request', 500);
      }
    });
    final api = ResearchOSApiClient(baseUrl: 'https://unused.example', client: client);
    final result = await api.getPublicGitHubDashboard(repository: 'octo/app');
    expect(result['read_only'], isTrue);
    expect((result['repository'] as Map)['default_branch'], 'trunk');
    expect(result['commits'], isEmpty);
    expect(result['pull_requests'], isEmpty);
    expect(result['workflow_runs'], isEmpty);
    expect(paths, containsAll([
      '/repos/octo/app',
      '/repos/octo/app/commits',
      '/repos/octo/app/pulls',
      '/repos/octo/app/actions/runs',
    ]));
    api.close();
  });

  test('rejects private repositories and malformed targets', () async {
    var requests = 0;
    final client = MockClient((request) async {
      requests++;
      if (request.url.path == '/repos/octo/private') {
        return http.Response('{"private":true,"visibility":"private"}', 200);
      }
      return http.Response('[]', 200);
    });
    final api = ResearchOSApiClient(baseUrl: 'https://unused.example', client: client);
    await expectLater(
      api.getPublicGitHubDashboard(repository: 'not-a-repository'),
      throwsA(isA<ResearchOSApiException>()),
    );
    await expectLater(
      api.getPublicGitHubDashboard(repository: 'octo/private'),
      throwsA(isA<ResearchOSApiException>()),
    );
    expect(requests, 1);
    api.close();
  });

  test('GitHub Actions data remains unknown when its public endpoint is unavailable', () async {
    final client = MockClient((request) async {
      if (request.url.path == '/repos/octo/app') {
        return http.Response('{"full_name":"octo/app","private":false}', 200);
      }
      if (request.url.path == '/repos/octo/app/commits' ||
          request.url.path == '/repos/octo/app/pulls') {
        return http.Response('[]', 200);
      }
      return http.Response('{"message":"Not Found"}', 404);
    });
    final api = ResearchOSApiClient(baseUrl: 'https://unused.example', client: client);
    final result = await api.getPublicGitHubDashboard(repository: 'octo/app');
    expect(result['workflow_runs'], isNull);
    expect(result['workflow_runs_error'], isNotNull);
    api.close();
  });
}
