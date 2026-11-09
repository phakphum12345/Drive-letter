import 'dart:convert';
import 'dart:io';

Future<String?> discoverLocalEndpoint() async {
  if (!Platform.isWindows) return null;
  final candidates = <String>[];
  final configuredData = Platform.environment['RESEARCH_OS_DATA_DIR']?.trim();
  if (configuredData != null && configuredData.isNotEmpty) {
    candidates.add('$configuredData\\runtime\\api.json');
  }
  final programData = Platform.environment['PROGRAMDATA'] ?? r'C:\ProgramData';
  candidates.add('$programData\\ResearchOS\\runtime\\api.json');
  final userProfile = Platform.environment['USERPROFILE'];
  if (userProfile != null && userProfile.isNotEmpty) {
    candidates.add('$userProfile\\ResearchOSData\\runtime\\api.json');
  }

  for (final candidate in candidates.toSet()) {
    try {
      final file = File(candidate);
      if (!await file.exists()) continue;
      final decoded = jsonDecode(await file.readAsString());
      if (decoded is! Map<String, dynamic> ||
          decoded['schema_version'] != 1 ||
          decoded['service'] != 'api' ||
          decoded['host'] != '127.0.0.1') {
        continue;
      }
      final port = decoded['port'];
      if (port is! int || port < 1 || port > 65535) continue;
      final expected = 'http://127.0.0.1:$port';
      if (decoded['url'] == expected) return expected;
    } on FileSystemException {
      // A service may be replacing the registry atomically during startup.
      continue;
    } on FormatException {
      continue;
    }
  }
  return null;
}
