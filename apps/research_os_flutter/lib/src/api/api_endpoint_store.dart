import 'dart:convert';
import 'dart:io';

import 'package:shared_preferences/shared_preferences.dart';

class ApiEndpointStore {
  ApiEndpointStore._();

  static const _storageKey = 'research_os_api_base_url_v1';
  // Legacy explicit value retained for migration of saved preferences only.
  // Windows Local Mode resolves the current endpoint from runtime/api.json.
  static const localDefault = 'http://127.0.0.1:8787';
  static const developerDefault = 'http://127.0.0.1:8790';
  static const tailscaleDefault = 'https://phakphumwir.tail4b06c9.ts.net';

  // Connection names remain internal; PORT labels are user-facing.
  static const connectionResearchOs = 'research_os';
  static const connectionOwnerSpecial = 'owner_special';
  static const connectionDeveloperRuntime = 'developer_runtime';

  static const port1Label = 'PORT 1';
  static const port2Label = 'PORT 2';

  static const loginWindows = 'windows';
  static const loginGitHub = 'github';
  static const loginGoogle = 'google';
  static const loginNone = 'none';
  static const loginCustom = 'custom';

  static const userLevelOwner = 'owner';
  static const userLevelDeveloper = 'developer';
  static const userLevelGeneral = 'general';

  static const developerBuildDefault = String.fromEnvironment(
    'RESEARCH_OS_DEVELOPER_BASE_URL',
    defaultValue: developerDefault,
  );

  static const buildDefault = String.fromEnvironment(
    'RESEARCH_OS_API_BASE_URL',
    defaultValue: tailscaleDefault,
  );

  static const port1BuildDefault = String.fromEnvironment(
    'RESEARCH_OS_PORT_1_BASE_URL',
    defaultValue: buildDefault,
  );

  static const port2BuildDefault = String.fromEnvironment(
    'RESEARCH_OS_PORT_2_BASE_URL',
    defaultValue: developerDefault,
  );

  static String profileUrl(String profile) {
    switch (profile) {
      case connectionOwnerSpecial:
        return normalize(port2BuildDefault);
      case connectionDeveloperRuntime:
        return normalize(developerBuildDefault);
      case connectionResearchOs:
      default:
        return normalize(port1BuildDefault);
    }
  }

  static String portLabel(String profile) {
    switch (profile) {
      case connectionOwnerSpecial:
        return port2Label;
      case connectionResearchOs:
      default:
        return port1Label;
    }
  }

  static String profileForPortLabel(String label) {
    switch (label) {
      case port2Label:
        return connectionOwnerSpecial;
      case port1Label:
      default:
        return connectionResearchOs;
    }
  }

  static String profileLabel(String profile) {
    switch (profile) {
      case connectionOwnerSpecial:
        return port2Label;
      case connectionDeveloperRuntime:
        return 'Developer Runtime';
      case connectionResearchOs:
      default:
        return port1Label;
    }
  }

  static String profileForUrl(String url) {
    final normalized = normalize(url);

    if (normalized == profileUrl(connectionOwnerSpecial)) {
      return connectionOwnerSpecial;
    }

    if (normalized == profileUrl(connectionDeveloperRuntime)) {
      return connectionDeveloperRuntime;
    }

    if (normalized == profileUrl(connectionResearchOs)) {
      return connectionResearchOs;
    }

    return 'custom';
  }

  static String? parseLocalEndpointRecord(String source) {
    try {
      final decoded = jsonDecode(source);
      if (decoded is! Map<String, dynamic> ||
          decoded['schema_version'] != 1 ||
          decoded['service'] != 'api' ||
          decoded['host'] != '127.0.0.1') {
        return null;
      }
      final port = decoded['port'];
      if (port is! int || port < 1 || port > 65535) return null;
      final expected = 'http://127.0.0.1:$port';
      if (decoded['url'] != expected) return null;
      return expected;
    } on FormatException {
      return null;
    }
  }

  static Future<String?> discoverLocalEndpoint() async {
    if (!Platform.isWindows) return null;
    final candidates = <String>[];
    final configuredData = Platform.environment['RESEARCH_OS_DATA_DIR']?.trim();
    if (configuredData != null && configuredData.isNotEmpty) {
      candidates.add('$configuredData\\runtime\\api.json');
    }
    final programData = Platform.environment['PROGRAMDATA'] ?? r'C:\\ProgramData';
    candidates.add('$programData\\ResearchOS\\runtime\\api.json');
    final userProfile = Platform.environment['USERPROFILE'];
    if (userProfile != null && userProfile.isNotEmpty) {
      candidates.add('$userProfile\\ResearchOSData\\runtime\\api.json');
    }

    for (final candidate in candidates.toSet()) {
      try {
        final file = File(candidate);
        if (!await file.exists()) continue;
        final endpoint = parseLocalEndpointRecord(await file.readAsString());
        if (endpoint != null) return endpoint;
      } on FileSystemException {
        // A service may be updating its atomic registry file during startup.
        continue;
      }
    }
    return null;
  }

  static Future<String> load() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_storageKey)?.trim();
    final discovered = await discoverLocalEndpoint();

    if (discovered != null &&
        (saved == null || saved.isEmpty || normalize(saved) == localDefault)) {
      await prefs.setString(_storageKey, discovered);
      return discovered;
    }

    if (saved == null || saved.isEmpty) {
      return normalize(profileUrl(connectionResearchOs));
    }

    final normalized = normalize(saved);

    // Preserve custom and Local choices, but migrate a previously saved
    // hosted Render default to the supported Tailscale Serve endpoint.
    final savedUri = Uri.tryParse(normalized);
    if (savedUri != null && savedUri.host.toLowerCase().endsWith('.onrender.com')) {
      final migrated = normalize(tailscaleDefault);
      await prefs.setString(_storageKey, migrated);
      return migrated;
    }
    return normalized;
  }

  static Future<void> save(String value) async {
    final normalized = normalize(value);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_storageKey, normalized);
  }

  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_storageKey);
  }

  static String normalize(String value) {
    var normalized = value.trim();
    while (normalized.endsWith('/')) {
      normalized = normalized.substring(0, normalized.length - 1);
    }
    final uri = Uri.tryParse(normalized);
    if (uri == null ||
        !uri.hasScheme ||
        (uri.scheme != 'http' && uri.scheme != 'https') ||
        uri.host.isEmpty) {
      throw const FormatException(
        'API Base URL ???????? http:// ???? https:// ??????????',
      );
    }
    return normalized;
  }
}
