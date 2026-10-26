import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/widgets.dart';

import 'src/api/v3_api.dart';
import 'src/research_os_v3_app.dart';
import 'src/startup_probe.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final baseUrl = await _resolveBaseUrl();
  final rawUser = Platform.environment['RESEARCH_OS_V3_USER_ID'] ??
      Platform.environment['USERNAME'] ??
      Platform.environment['USER'] ??
      'local-user';
  final rawProfile =
      Platform.environment['RESEARCH_OS_V3_PROFILE_ID'] ?? 'default';

  final api = HttpV3Api(
    baseUrl: baseUrl,
    userId: _safeIdentifier(rawUser, fallbackPrefix: 'user'),
    profileId: _safeIdentifier(rawProfile, fallbackPrefix: 'profile'),
  );

  runApp(ResearchOSV3App(api: api));

  // Paint first, then prove loopback connectivity and user isolation context.
  unawaited(StartupProbe(api).run());
}

Future<String> _resolveBaseUrl() async {
  const configuredBaseUrl = String.fromEnvironment('RESEARCH_OS_V3_BASE_URL', defaultValue: '');
  final runtimeBaseUrl = Platform.environment['RESEARCH_OS_V3_BASE_URL']?.trim() ?? '';
  if (runtimeBaseUrl.isNotEmpty) return runtimeBaseUrl;
  if (configuredBaseUrl.isNotEmpty) return configuredBaseUrl;

  final runtimePort = Platform.environment['RESEARCH_OS_V3_PORT']?.trim() ?? '';
  final parsedRuntimePort = int.tryParse(runtimePort);
  if (parsedRuntimePort != null && parsedRuntimePort >= 1 && parsedRuntimePort <= 65535) {
    return 'http://127.0.0.1:$parsedRuntimePort';
  }

  final programData = Platform.environment['PROGRAMDATA'] ?? r'C:\ProgramData';
  final config = File('${programData}\\ResearchOSV3\\service.json');
  try {
    final decoded = jsonDecode(await config.readAsString());
    if (decoded is Map<String, dynamic>) {
      final port = decoded['port'];
      if (port is int && port >= 1 && port <= 65535) return 'http://127.0.0.1:$port';
    }
  } on FileSystemException {
    // Development builds without an installed service use the stable default.
  } on FormatException {
    // Ignore incomplete configuration and use the stable default.
  }
  return 'http://127.0.0.1:8788';
}

String _safeIdentifier(String raw, {required String fallbackPrefix}) {
  final candidate = raw.trim();
  final valid = RegExp(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$');
  if (valid.hasMatch(candidate) && candidate != '.' && candidate != '..') {
    return candidate;
  }

  // FNV-1a is used only to create a deterministic, non-secret path-safe suffix.
  var hash = 0x811C9DC5;
  for (final unit in candidate.codeUnits) {
    hash ^= unit;
    hash = (hash * 0x01000193) & 0xFFFFFFFF;
  }
  final suffix = hash.toRadixString(16).padLeft(8, '0');
  return '$fallbackPrefix-$suffix';
}
