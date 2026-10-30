import 'dart:convert';

import 'package:http/http.dart' as http;

class ResearchOSApiException implements Exception {
  const ResearchOSApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

class ResearchOSApiClient {
  ResearchOSApiClient({
    required this.baseUrl,
    http.Client? client,
    this.preferredProvider,
  }) : _client = client ?? http.Client();

  final String baseUrl;
  final String? preferredProvider;
  final http.Client _client;
  String? _sessionToken;

  Uri _uri(String path) => Uri.parse('$baseUrl$path');

  void setSession(String token) {
    final value = token.trim();
    if (value.isEmpty) {
      throw const ResearchOSApiException('Research OS session token is empty.');
    }
    _sessionToken = value;
  }

  void clearSession() => _sessionToken = null;

  Future<Map<String, dynamic>> getAuthStatus() =>
      _getJson('/v1/auth/status');

  Future<Map<String, dynamic>> getIdentityProviders() =>
      _getJson('/v1/auth/providers');

  Future<Map<String, dynamic>> startPairing() =>
      _postJson('/v1/auth/pairing/start', const <String, Object?>{});

  Future<Map<String, dynamic>> getPairingStatus(
    String pairingId,
    String pairingSecret,
  ) async {
    final uri = _uri('/v1/auth/pairing/status').replace(
      queryParameters: <String, String>{
        'pairing_id': pairingId,
        'secret': pairingSecret,
      },
    );
    final response = await _client.get(uri);
    return _decode(response);
  }

  Future<Map<String, dynamic>> cancelPairing(
    String pairingId,
    String pairingSecret,
  ) =>
      _postJson('/v1/auth/pairing/cancel', <String, Object?>{
        'pairing_id': pairingId,
        'pairing_secret': pairingSecret,
      });

  Future<Map<String, dynamic>> startProviderLogin(String provider) =>
      _postJson('/v1/auth/providers/login', <String, Object?>{
        'provider': provider,
      });

  Future<Map<String, dynamic>> exchangeProviderHandoff(String state) async {
    final response = await _client.post(
      _uri('/v1/auth/providers/handoff'),
      headers: <String, String>{
        'Content-Type': 'application/json',
        'X-Research-OS-OAuth-State': state,
      },
      body: '{}',
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> signOut() =>
      _postJson('/v1/auth/signout', const <String, Object?>{});

  Future<Map<String, dynamic>> getHealth() => _getJson('/health');
  Future<Map<String, dynamic>> getProjects() => _getJson('/v1/projects');
  Future<Map<String, dynamic>> getProviders() => _getJson('/v1/providers');
  Future<Map<String, dynamic>> getAIProviderConnections() =>
      _getJson('/v1/ai/connections');
  Future<Map<String, dynamic>> getKnowledgeArtifacts() =>
      _getJson('/v1/knowledge/artifacts');
  Future<Map<String, dynamic>> getKnowledgeGraph() =>
      _getJson('/v1/knowledge/graph');

  Future<Map<String, dynamic>> getBrainCapacity() =>
      _getJson('/v1/brain/capacity');
  Future<Map<String, dynamic>> getBrainSkills() =>
      _getJson('/v1/brain/skills');
  Future<Map<String, dynamic>> getBrainProviders() =>
      _getJson('/v1/brain/providers');

  Future<Map<String, dynamic>> getGoogleIdentityStatus() =>
      _getJson('/v1/auth/google/status');
  Future<Map<String, dynamic>> startGoogleIdentitySignIn() =>
      _postJson('/v1/auth/google/start', const <String, Object?>{});
  Future<Map<String, dynamic>> exchangeGoogleIdentityHandoff(
    String state,
  ) async {
    final response = await _client.post(
      _uri('/v1/auth/google/handoff'),
      headers: <String, String>{
        'Content-Type': 'application/json',
        'X-Research-OS-OAuth-State': state,
      },
      body: '{}',
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> signOutGoogleIdentity() =>
      _postJson('/v1/auth/google/signout', const <String, Object?>{});

  Future<Map<String, dynamic>> getGoogleWorkspaceDashboard() =>
      _getJson('/v1/google-workspace/dashboard');
  Future<Map<String, dynamic>> getGoogleWorkspaceOAuthStatus() =>
      _getJson('/v1/google-workspace/oauth/status');
  Future<Map<String, dynamic>> startGoogleWorkspaceOAuth() =>
      _postJson('/v1/google-workspace/oauth/start', const <String, Object?>{});
  Future<Map<String, dynamic>> disconnectGoogleWorkspace() =>
      _postJson('/v1/google-workspace/oauth/disconnect', const <String, Object?>{});
  Future<Map<String, dynamic>> setGoogleWorkspaceServices(List<String> services) =>
      _postJson('/v1/google-workspace/services', <String, Object?>{
        'enabled_services': services,
      });

  Future<Map<String, dynamic>> getAgents() => _getJson('/v1/agents');
  Future<Map<String, dynamic>> getAgentReadiness() =>
      _getJson('/v1/agents/readiness');

  Future<Map<String, dynamic>> discoverAgents({String? capability}) async {
    final value = capability?.trim();
    if (value == null || value.isEmpty) {
      return _getJson('/v1/agents/discover');
    }
    final uri = _uri('/v1/agents/discover').replace(
      queryParameters: <String, String>{'capability': value},
    );
    final response = await _client.get(uri);
    return _decode(response);
  }

  Future<Map<String, dynamic>> getV2Workspaces() => _getJson('/v2/workspaces');

  Future<Map<String, dynamic>> searchWorkspaceKnowledge(
    String workspaceId, {
    String query = '',
    int pageSize = 25,
    String? cursor,
  }) async {
    final params = <String, String>{
      'q': query.trim(),
      'page_size': '$pageSize',
      if (cursor != null && cursor.trim().isNotEmpty) 'cursor': cursor.trim(),
    };
    final uri = _uri(
      '/v2/workspaces/${Uri.encodeComponent(workspaceId)}/knowledge',
    ).replace(queryParameters: params);
    final response = await _client.get(uri);
    return _decode(response);
  }

  Future<Map<String, dynamic>> getOrchestrations({
    String? status,
    String? query,
    String? agent,
    int? limit,
  }) async {
    final params = <String, String>{};
    if (status != null && status.trim().isNotEmpty) {
      params['status'] = status.trim();
    }
    if (query != null && query.trim().isNotEmpty) params['q'] = query.trim();
    if (agent != null && agent.trim().isNotEmpty) params['agent'] = agent.trim();
    if (limit != null) params['limit'] = '$limit';
    final uri = _uri('/v1/agents/orchestrations').replace(
      queryParameters: params.isEmpty ? null : params,
    );
    final response = await _client.get(uri);
    return _decode(response);
  }

  Future<Map<String, dynamic>> getOrchestration(String runId) =>
      _getJson('/v1/agents/orchestrations/${Uri.encodeComponent(runId)}');

  Future<Map<String, dynamic>> getOrchestrationTimeline(String runId) =>
      _getJson(
        '/v1/agents/orchestrations/${Uri.encodeComponent(runId)}/timeline',
      );

  Future<Map<String, dynamic>> createOrchestration({
    required String objective,
    required List<Map<String, Object?>> steps,
  }) =>
      _postJson('/v1/agents/orchestrations', <String, Object?>{
        'objective': objective,
        'steps': steps,
      });

  Future<Map<String, dynamic>> executeOrchestration(
    String runId, {
    bool confirmed = false,
  }) =>
      _postJson(
        '/v1/agents/orchestrations/${Uri.encodeComponent(runId)}/execute',
        <String, Object?>{'confirmed': confirmed},
      );

  Future<Map<String, dynamic>> confirmOrchestration(String runId) =>
      _postJson(
        '/v1/agents/orchestrations/${Uri.encodeComponent(runId)}/confirm',
        const <String, Object?>{},
      );

  Future<Map<String, dynamic>> retryOrchestration(
    String runId, {
    String? stepId,
  }) =>
      _postJson(
        '/v1/agents/orchestrations/${Uri.encodeComponent(runId)}/retry',
        <String, Object?>{
          if (stepId != null && stepId.trim().isNotEmpty)
            'step_id': stepId.trim(),
        },
      );

  Future<Map<String, dynamic>> cancelOrchestration(String runId) =>
      _postJson(
        '/v1/agents/orchestrations/${Uri.encodeComponent(runId)}/cancel',
        const <String, Object?>{},
      );

  Future<Map<String, dynamic>> getGitHubAccounts() =>
      _getJson('/v1/github/accounts');

  Future<Map<String, dynamic>> getGitHubRepositories({
    required String accountId,
    int page = 1,
  }) async {
    final uri = _uri('/v1/github/repositories').replace(
      queryParameters: <String, String>{'account_id': accountId, 'page': '$page'},
    );
    return _decode(await _client.get(uri));
  }

  Future<Map<String, dynamic>> getGitHubDashboard({
    String? repository,
    String? accountId,
  }) async {
    final query = repository?.trim();
    final params = <String, String>{
      if (query != null && query.isNotEmpty) 'repository': query,
      if (accountId != null && accountId.trim().isNotEmpty) 'account_id': accountId.trim(),
    };
    final uri = _uri('/v1/github/dashboard').replace(queryParameters: params.isEmpty ? null : params);
    return _decode(await _client.get(uri));
  }


  Future<Map<String, dynamic>> getPublicGitHubRepositories(String owner) async {
    final login = owner.trim();
    if (!RegExp(r'^[A-Za-z0-9-]{1,39}
    final uri = _uri('/v1/memory/search').replace(
      queryParameters: <String, String>{'q': query, 'limit': '5'},
    );
    final response = await _client.get(uri);
    return _decode(response);
  }

  Map<String, Object?> _aiPayload(String field, String value) {
    final provider = preferredProvider?.trim();
    return <String, Object?>{
      field: value,
      if (provider != null && provider.isNotEmpty) 'provider': provider,
    };
  }

  Future<Map<String, dynamic>> generateText(String prompt) {
    return _postJson('/v1/ai/generate', _aiPayload('prompt', prompt));
  }

  Future<Map<String, dynamic>> answerWithMemory(String question) {
    return _postJson(
      '/v1/ai/answer-with-memory',
      _aiPayload('question', question),
    );
  }

  Future<Map<String, dynamic>> commitMemory(
    String syncKey, {
    required String title,
    required List<Map<String, Object?>> conversation,
  }) async {
    final response = await _client.post(
      _uri('/v1/memory/commit'),
      headers: <String, String>{
        'Content-Type': 'application/json',
        'X-Research-OS-Sync-Key': syncKey,
      },
      body: jsonEncode(<String, Object?>{
        'title': title,
        'conversation': conversation,
        'status': 'hypothesis',
        'tags': <String>['research-os', 'chat-session'],
        'min_quality': 20,
        'confirm': true,
      }),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> getCloudConversations(String syncKey) async {
    final response = await _client.get(
      _uri('/v1/conversations/cloud'),
      headers: <String, String>{'X-Research-OS-Sync-Key': syncKey},
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> syncCloudConversation(
    String syncKey,
    Map<String, Object?> session,
  ) async {
    final response = await _client.post(
      _uri('/v1/conversations/cloud/sync'),
      headers: <String, String>{
        'Content-Type': 'application/json',
        'X-Research-OS-Sync-Key': syncKey,
      },
      body: jsonEncode(<String, Object?>{'session': session}),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> deleteCloudConversation(
    String syncKey,
    String sessionId,
  ) async {
    final response = await _client.post(
      _uri('/v1/conversations/cloud/delete'),
      headers: <String, String>{
        'Content-Type': 'application/json',
        'X-Research-OS-Sync-Key': syncKey,
      },
      body: jsonEncode(<String, Object?>{'session_id': sessionId}),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> getCopilotContext({
    String? query,
    List<String> paths = const <String>[],
    int memoryLimit = 5,
  }) async {
    final queryParts = <String>[
      if (query != null && query.trim().isNotEmpty)
        'query=${Uri.encodeQueryComponent(query.trim())}',
      for (final path in paths) 'path=${Uri.encodeQueryComponent(path)}',
      'memory_limit=${Uri.encodeQueryComponent('$memoryLimit')}',
    ];
    final uri = _uri('/v1/copilot/context?${queryParts.join('&')}');
    final response = await _client.get(uri);
    return _decode(response);
  }

  Future<Map<String, dynamic>> chatWithCopilot({
    required String message,
    List<String> paths = const <String>[],
    String? contextQuery,
    int memoryLimit = 5,
  }) {
    return _postJson('/v1/copilot/chat', <String, Object?>{
      'message': message,
      if (paths.isNotEmpty) 'paths': paths,
      if (contextQuery != null && contextQuery.trim().isNotEmpty)
        'context_query': contextQuery.trim(),
      'memory_limit': memoryLimit,
    });
  }

  Future<Map<String, dynamic>> _getJson(String path) async {
    final response = await _client.get(
      _uri(path),
      headers: _sessionHeaders(),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> _postJson(
    String path,
    Map<String, Object?> payload,
  ) async {
    final response = await _client.post(
      _uri(path),
      headers: <String, String>{
        'Content-Type': 'application/json',
        ..._sessionHeaders(),
      },
      body: jsonEncode(payload),
    );
    return _decode(response);
  }


  Future<Map<String, dynamic>> _getPublicGitHubObject(String path) async {
    final value = await _getPublicGitHubJson(path, const <String, String>{});
    if (value is! Map) {
      throw const ResearchOSApiException('GitHub returned an unexpected object response.');
    }
    return Map<String, dynamic>.from(value);
  }

  Future<Object?> _getPublicGitHubJson(String path, Map<String, String> queryParameters) async {
    final uri = Uri.https('api.github.com', path, queryParameters);
    final response = await _client.get(uri, headers: const <String, String>{
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'ResearchOS-Recon-Back-Box',
    });
    Object? decoded;
    try {
      decoded = jsonDecode(response.body);
    } on FormatException {
      throw ResearchOSApiException('GitHub returned invalid JSON (HTTP ${response.statusCode}).', statusCode: response.statusCode);
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = decoded is Map ? decoded['message'] ?? decoded['error'] ?? 'Unknown GitHub API error' : 'Unknown GitHub API error';
      throw ResearchOSApiException('GitHub public API error ${response.statusCode}: $detail', statusCode: response.statusCode);
    }
    return decoded;
  }

  Map<String, dynamic> _decode(http.Response response) {
    final Object? decoded;
    try {
      decoded = jsonDecode(response.body);
    } on FormatException {
      throw ResearchOSApiException(
        'Research OS API returned invalid JSON (${response.statusCode}).',
      );
    }
    if (decoded is! Map<String, dynamic>) {
      throw const ResearchOSApiException(
        'Research OS API returned an unexpected response shape.',
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final rawError = decoded['error'];
      final detail = rawError is Map
          ? rawError['message'] ?? rawError['code'] ?? 'Unknown error'
          : decoded['detail'] ?? rawError ?? 'Unknown error';
      throw ResearchOSApiException(
        'Research OS API error ${response.statusCode}: $detail',
        statusCode: response.statusCode,
      );
    }
    return decoded;
  }

  Map<String, String> _sessionHeaders() => <String, String>{
        if (_sessionToken != null && _sessionToken!.isNotEmpty)
          'X-Research-OS-Session': _sessionToken!,
      };

  void close() => _client.close();
}
).hasMatch(login)) {
      throw const ResearchOSApiException('GitHub owner name is invalid.');
    }
    Map<String, dynamic> identity;
    try {
      identity = await _getPublicGitHubObject('/users/$login');
    } on ResearchOSApiException catch (error) {
      if (error.statusCode != 404) rethrow;
      identity = await _getPublicGitHubObject('/orgs/$login');
    }
    final isOrganization = identity['type'] == 'Organization';
    final path = isOrganization ? '/orgs/$login/repos' : '/users/$login/repos';
    final repositories = <Map<String, dynamic>>[];
    for (var page = 1; page <= 10; page++) {
      final payload = await _getPublicGitHubJson(path, <String, String>{
        'type': isOrganization ? 'public' : 'owner',
        'sort': 'updated', 'per_page': '100', 'page': '$page',
      });
      if (payload is! List) {
        throw const ResearchOSApiException('GitHub returned an unexpected repository list.');
      }
      final pageItems = payload.whereType<Map>().map((item) => <String, dynamic>{
        'full_name': item['full_name'], 'name': item['name'],
        'default_branch': item['default_branch'], 'html_url': item['html_url'],
        'updated_at': item['updated_at'], 'stargazers_count': item['stargazers_count'],
        'forks_count': item['forks_count'], 'private': item['private'],
      }).where((item) => item['full_name'] is String).toList();
      repositories.addAll(pageItems);
      if (pageItems.length < 100) break;
    }
    repositories.sort((a, b) => (a['full_name'] as String).compareTo(b['full_name'] as String));
    return <String, dynamic>{
      'owner': login, 'owner_type': isOrganization ? 'organization' : 'user',
      'repositories': repositories, 'visibility_filter': 'public_only',
      'read_only': true, 'source': 'github_public_rest_api',
    };
  }

  Future<Map<String, dynamic>> getPublicGitHubDashboard({
    required String repository,
  }) async {
    final parts = repository.trim().split('/');
    if (parts.length != 2 ||
        !RegExp(r'^[A-Za-z0-9-]{1,39}
    final uri = _uri('/v1/memory/search').replace(
      queryParameters: <String, String>{'q': query, 'limit': '5'},
    );
    final response = await _client.get(uri);
    return _decode(response);
  }

  Map<String, Object?> _aiPayload(String field, String value) {
    final provider = preferredProvider?.trim();
    return <String, Object?>{
      field: value,
      if (provider != null && provider.isNotEmpty) 'provider': provider,
    };
  }

  Future<Map<String, dynamic>> generateText(String prompt) {
    return _postJson('/v1/ai/generate', _aiPayload('prompt', prompt));
  }

  Future<Map<String, dynamic>> answerWithMemory(String question) {
    return _postJson(
      '/v1/ai/answer-with-memory',
      _aiPayload('question', question),
    );
  }

  Future<Map<String, dynamic>> commitMemory(
    String syncKey, {
    required String title,
    required List<Map<String, Object?>> conversation,
  }) async {
    final response = await _client.post(
      _uri('/v1/memory/commit'),
      headers: <String, String>{
        'Content-Type': 'application/json',
        'X-Research-OS-Sync-Key': syncKey,
      },
      body: jsonEncode(<String, Object?>{
        'title': title,
        'conversation': conversation,
        'status': 'hypothesis',
        'tags': <String>['research-os', 'chat-session'],
        'min_quality': 20,
        'confirm': true,
      }),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> getCloudConversations(String syncKey) async {
    final response = await _client.get(
      _uri('/v1/conversations/cloud'),
      headers: <String, String>{'X-Research-OS-Sync-Key': syncKey},
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> syncCloudConversation(
    String syncKey,
    Map<String, Object?> session,
  ) async {
    final response = await _client.post(
      _uri('/v1/conversations/cloud/sync'),
      headers: <String, String>{
        'Content-Type': 'application/json',
        'X-Research-OS-Sync-Key': syncKey,
      },
      body: jsonEncode(<String, Object?>{'session': session}),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> deleteCloudConversation(
    String syncKey,
    String sessionId,
  ) async {
    final response = await _client.post(
      _uri('/v1/conversations/cloud/delete'),
      headers: <String, String>{
        'Content-Type': 'application/json',
        'X-Research-OS-Sync-Key': syncKey,
      },
      body: jsonEncode(<String, Object?>{'session_id': sessionId}),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> getCopilotContext({
    String? query,
    List<String> paths = const <String>[],
    int memoryLimit = 5,
  }) async {
    final queryParts = <String>[
      if (query != null && query.trim().isNotEmpty)
        'query=${Uri.encodeQueryComponent(query.trim())}',
      for (final path in paths) 'path=${Uri.encodeQueryComponent(path)}',
      'memory_limit=${Uri.encodeQueryComponent('$memoryLimit')}',
    ];
    final uri = _uri('/v1/copilot/context?${queryParts.join('&')}');
    final response = await _client.get(uri);
    return _decode(response);
  }

  Future<Map<String, dynamic>> chatWithCopilot({
    required String message,
    List<String> paths = const <String>[],
    String? contextQuery,
    int memoryLimit = 5,
  }) {
    return _postJson('/v1/copilot/chat', <String, Object?>{
      'message': message,
      if (paths.isNotEmpty) 'paths': paths,
      if (contextQuery != null && contextQuery.trim().isNotEmpty)
        'context_query': contextQuery.trim(),
      'memory_limit': memoryLimit,
    });
  }

  Future<Map<String, dynamic>> _getJson(String path) async {
    final response = await _client.get(
      _uri(path),
      headers: _sessionHeaders(),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> _postJson(
    String path,
    Map<String, Object?> payload,
  ) async {
    final response = await _client.post(
      _uri(path),
      headers: <String, String>{
        'Content-Type': 'application/json',
        ..._sessionHeaders(),
      },
      body: jsonEncode(payload),
    );
    return _decode(response);
  }

  Map<String, dynamic> _decode(http.Response response) {
    final Object? decoded;
    try {
      decoded = jsonDecode(response.body);
    } on FormatException {
      throw ResearchOSApiException(
        'Research OS API returned invalid JSON (${response.statusCode}).',
      );
    }
    if (decoded is! Map<String, dynamic>) {
      throw const ResearchOSApiException(
        'Research OS API returned an unexpected response shape.',
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final rawError = decoded['error'];
      final detail = rawError is Map
          ? rawError['message'] ?? rawError['code'] ?? 'Unknown error'
          : decoded['detail'] ?? rawError ?? 'Unknown error';
      throw ResearchOSApiException(
        'Research OS API error ${response.statusCode}: $detail',
        statusCode: response.statusCode,
      );
    }
    return decoded;
  }

  Map<String, String> _sessionHeaders() => <String, String>{
        if (_sessionToken != null && _sessionToken!.isNotEmpty)
          'X-Research-OS-Session': _sessionToken!,
      };

  void close() => _client.close();
}
).hasMatch(parts[0]) ||
        !RegExp(r'^[A-Za-z0-9_.-]+
    final uri = _uri('/v1/memory/search').replace(
      queryParameters: <String, String>{'q': query, 'limit': '5'},
    );
    final response = await _client.get(uri);
    return _decode(response);
  }

  Map<String, Object?> _aiPayload(String field, String value) {
    final provider = preferredProvider?.trim();
    return <String, Object?>{
      field: value,
      if (provider != null && provider.isNotEmpty) 'provider': provider,
    };
  }

  Future<Map<String, dynamic>> generateText(String prompt) {
    return _postJson('/v1/ai/generate', _aiPayload('prompt', prompt));
  }

  Future<Map<String, dynamic>> answerWithMemory(String question) {
    return _postJson(
      '/v1/ai/answer-with-memory',
      _aiPayload('question', question),
    );
  }

  Future<Map<String, dynamic>> commitMemory(
    String syncKey, {
    required String title,
    required List<Map<String, Object?>> conversation,
  }) async {
    final response = await _client.post(
      _uri('/v1/memory/commit'),
      headers: <String, String>{
        'Content-Type': 'application/json',
        'X-Research-OS-Sync-Key': syncKey,
      },
      body: jsonEncode(<String, Object?>{
        'title': title,
        'conversation': conversation,
        'status': 'hypothesis',
        'tags': <String>['research-os', 'chat-session'],
        'min_quality': 20,
        'confirm': true,
      }),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> getCloudConversations(String syncKey) async {
    final response = await _client.get(
      _uri('/v1/conversations/cloud'),
      headers: <String, String>{'X-Research-OS-Sync-Key': syncKey},
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> syncCloudConversation(
    String syncKey,
    Map<String, Object?> session,
  ) async {
    final response = await _client.post(
      _uri('/v1/conversations/cloud/sync'),
      headers: <String, String>{
        'Content-Type': 'application/json',
        'X-Research-OS-Sync-Key': syncKey,
      },
      body: jsonEncode(<String, Object?>{'session': session}),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> deleteCloudConversation(
    String syncKey,
    String sessionId,
  ) async {
    final response = await _client.post(
      _uri('/v1/conversations/cloud/delete'),
      headers: <String, String>{
        'Content-Type': 'application/json',
        'X-Research-OS-Sync-Key': syncKey,
      },
      body: jsonEncode(<String, Object?>{'session_id': sessionId}),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> getCopilotContext({
    String? query,
    List<String> paths = const <String>[],
    int memoryLimit = 5,
  }) async {
    final queryParts = <String>[
      if (query != null && query.trim().isNotEmpty)
        'query=${Uri.encodeQueryComponent(query.trim())}',
      for (final path in paths) 'path=${Uri.encodeQueryComponent(path)}',
      'memory_limit=${Uri.encodeQueryComponent('$memoryLimit')}',
    ];
    final uri = _uri('/v1/copilot/context?${queryParts.join('&')}');
    final response = await _client.get(uri);
    return _decode(response);
  }

  Future<Map<String, dynamic>> chatWithCopilot({
    required String message,
    List<String> paths = const <String>[],
    String? contextQuery,
    int memoryLimit = 5,
  }) {
    return _postJson('/v1/copilot/chat', <String, Object?>{
      'message': message,
      if (paths.isNotEmpty) 'paths': paths,
      if (contextQuery != null && contextQuery.trim().isNotEmpty)
        'context_query': contextQuery.trim(),
      'memory_limit': memoryLimit,
    });
  }

  Future<Map<String, dynamic>> _getJson(String path) async {
    final response = await _client.get(
      _uri(path),
      headers: _sessionHeaders(),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> _postJson(
    String path,
    Map<String, Object?> payload,
  ) async {
    final response = await _client.post(
      _uri(path),
      headers: <String, String>{
        'Content-Type': 'application/json',
        ..._sessionHeaders(),
      },
      body: jsonEncode(payload),
    );
    return _decode(response);
  }

  Map<String, dynamic> _decode(http.Response response) {
    final Object? decoded;
    try {
      decoded = jsonDecode(response.body);
    } on FormatException {
      throw ResearchOSApiException(
        'Research OS API returned invalid JSON (${response.statusCode}).',
      );
    }
    if (decoded is! Map<String, dynamic>) {
      throw const ResearchOSApiException(
        'Research OS API returned an unexpected response shape.',
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final rawError = decoded['error'];
      final detail = rawError is Map
          ? rawError['message'] ?? rawError['code'] ?? 'Unknown error'
          : decoded['detail'] ?? rawError ?? 'Unknown error';
      throw ResearchOSApiException(
        'Research OS API error ${response.statusCode}: $detail',
        statusCode: response.statusCode,
      );
    }
    return decoded;
  }

  Map<String, String> _sessionHeaders() => <String, String>{
        if (_sessionToken != null && _sessionToken!.isNotEmpty)
          'X-Research-OS-Session': _sessionToken!,
      };

  void close() => _client.close();
}
).hasMatch(parts[1])) {
      throw const ResearchOSApiException('Repository must use the owner/name format.');
    }
    final root = '/repos/${parts[0]}/${parts[1]}';
    final metadata = await _getPublicGitHubObject(root);
    if (metadata['private'] == true ||
        (metadata['visibility'] != null && metadata['visibility'] != 'public')) {
      throw const ResearchOSApiException('Recon Back Box can inspect public repositories only.');
    }
    final commitsFuture = _getPublicGitHubJson('$root/commits', const {'per_page': '10'});
    final pullsFuture = _getPublicGitHubJson('$root/pulls', const {'state': 'open', 'per_page': '20'});
    final runsFuture = _getPublicGitHubJson('$root/actions/runs', const {'per_page': '10'})
        .then<Map<String, dynamic>>(
          (value) => <String, dynamic>{'value': value},
          onError: (Object error) => <String, dynamic>{'error': error.toString()},
        );
    final results = await Future.wait<Object?>([commitsFuture, pullsFuture, runsFuture]);
    final commits = results[0];
    final pulls = results[1];
    final runsResult = results[2] as Map<String, dynamic>;
    if (commits is! List || pulls is! List) {
      throw const ResearchOSApiException('GitHub returned an unexpected repository dashboard response.');
    }
    final runPayload = runsResult['value'];
    final workflowRuns = runPayload is Map ? runPayload['workflow_runs'] : null;
    return <String, dynamic>{
      'repository': <String, dynamic>{
        'full_name': metadata['full_name'], 'html_url': metadata['html_url'],
        'default_branch': metadata['default_branch'],
        'visibility': metadata['visibility'] ?? 'public', 'updated_at': metadata['updated_at'],
      },
      'commits': commits, 'pull_requests': pulls,
      'workflow_runs': workflowRuns is List ? workflowRuns : null,
      if (runsResult['error'] is String) 'workflow_runs_error': runsResult['error'],
      'source': 'github_public_rest_api', 'read_only': true,
    };
  }

  Future<Map<String, dynamic>> searchMemory(String query) async {
    final uri = _uri('/v1/memory/search').replace(
      queryParameters: <String, String>{'q': query, 'limit': '5'},
    );
    final response = await _client.get(uri);
    return _decode(response);
  }

  Map<String, Object?> _aiPayload(String field, String value) {
    final provider = preferredProvider?.trim();
    return <String, Object?>{
      field: value,
      if (provider != null && provider.isNotEmpty) 'provider': provider,
    };
  }

  Future<Map<String, dynamic>> generateText(String prompt) {
    return _postJson('/v1/ai/generate', _aiPayload('prompt', prompt));
  }

  Future<Map<String, dynamic>> answerWithMemory(String question) {
    return _postJson(
      '/v1/ai/answer-with-memory',
      _aiPayload('question', question),
    );
  }

  Future<Map<String, dynamic>> commitMemory(
    String syncKey, {
    required String title,
    required List<Map<String, Object?>> conversation,
  }) async {
    final response = await _client.post(
      _uri('/v1/memory/commit'),
      headers: <String, String>{
        'Content-Type': 'application/json',
        'X-Research-OS-Sync-Key': syncKey,
      },
      body: jsonEncode(<String, Object?>{
        'title': title,
        'conversation': conversation,
        'status': 'hypothesis',
        'tags': <String>['research-os', 'chat-session'],
        'min_quality': 20,
        'confirm': true,
      }),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> getCloudConversations(String syncKey) async {
    final response = await _client.get(
      _uri('/v1/conversations/cloud'),
      headers: <String, String>{'X-Research-OS-Sync-Key': syncKey},
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> syncCloudConversation(
    String syncKey,
    Map<String, Object?> session,
  ) async {
    final response = await _client.post(
      _uri('/v1/conversations/cloud/sync'),
      headers: <String, String>{
        'Content-Type': 'application/json',
        'X-Research-OS-Sync-Key': syncKey,
      },
      body: jsonEncode(<String, Object?>{'session': session}),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> deleteCloudConversation(
    String syncKey,
    String sessionId,
  ) async {
    final response = await _client.post(
      _uri('/v1/conversations/cloud/delete'),
      headers: <String, String>{
        'Content-Type': 'application/json',
        'X-Research-OS-Sync-Key': syncKey,
      },
      body: jsonEncode(<String, Object?>{'session_id': sessionId}),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> getCopilotContext({
    String? query,
    List<String> paths = const <String>[],
    int memoryLimit = 5,
  }) async {
    final queryParts = <String>[
      if (query != null && query.trim().isNotEmpty)
        'query=${Uri.encodeQueryComponent(query.trim())}',
      for (final path in paths) 'path=${Uri.encodeQueryComponent(path)}',
      'memory_limit=${Uri.encodeQueryComponent('$memoryLimit')}',
    ];
    final uri = _uri('/v1/copilot/context?${queryParts.join('&')}');
    final response = await _client.get(uri);
    return _decode(response);
  }

  Future<Map<String, dynamic>> chatWithCopilot({
    required String message,
    List<String> paths = const <String>[],
    String? contextQuery,
    int memoryLimit = 5,
  }) {
    return _postJson('/v1/copilot/chat', <String, Object?>{
      'message': message,
      if (paths.isNotEmpty) 'paths': paths,
      if (contextQuery != null && contextQuery.trim().isNotEmpty)
        'context_query': contextQuery.trim(),
      'memory_limit': memoryLimit,
    });
  }

  Future<Map<String, dynamic>> _getJson(String path) async {
    final response = await _client.get(
      _uri(path),
      headers: _sessionHeaders(),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> _postJson(
    String path,
    Map<String, Object?> payload,
  ) async {
    final response = await _client.post(
      _uri(path),
      headers: <String, String>{
        'Content-Type': 'application/json',
        ..._sessionHeaders(),
      },
      body: jsonEncode(payload),
    );
    return _decode(response);
  }

  Map<String, dynamic> _decode(http.Response response) {
    final Object? decoded;
    try {
      decoded = jsonDecode(response.body);
    } on FormatException {
      throw ResearchOSApiException(
        'Research OS API returned invalid JSON (${response.statusCode}).',
      );
    }
    if (decoded is! Map<String, dynamic>) {
      throw const ResearchOSApiException(
        'Research OS API returned an unexpected response shape.',
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final rawError = decoded['error'];
      final detail = rawError is Map
          ? rawError['message'] ?? rawError['code'] ?? 'Unknown error'
          : decoded['detail'] ?? rawError ?? 'Unknown error';
      throw ResearchOSApiException(
        'Research OS API error ${response.statusCode}: $detail',
        statusCode: response.statusCode,
      );
    }
    return decoded;
  }

  Map<String, String> _sessionHeaders() => <String, String>{
        if (_sessionToken != null && _sessionToken!.isNotEmpty)
          'X-Research-OS-Session': _sessionToken!,
      };

  void close() => _client.close();
}
