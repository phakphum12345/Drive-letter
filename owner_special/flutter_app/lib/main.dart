import 'dart:async';
import 'dart:io';

import 'package:material_ui/material_ui.dart';

import 'src/friend_app.dart';
import 'src/owner_api.dart';
import 'src/startup_probe.dart';

Future<void> _writeStartupProbeLog(String message) async {
  final path = Platform.environment['RESEARCH_OS_STARTUP_PROBE_LOG']?.trim();
  if (path == null || path.isEmpty) return;
  try {
    await File(path).writeAsString(
      '${DateTime.now().toUtc().toIso8601String()} $message\n',
      mode: FileMode.append,
      flush: true,
    );
  } catch (_) {
    // Diagnostic logging must never prevent the app shell from opening.
  }
}

String _safeStartupBaseUrl(String value) {
  try {
    final uri = Uri.parse(value);
    final authority = uri.hasPort ? '${uri.host}:${uri.port}' : uri.host;
    return '${uri.scheme}://$authority${uri.path}';
  } catch (_) {
    return '<invalid-api-base-url>';
  }
}

Future<void> _probeStartupInBackground(
  OwnerFriendApi api,
  String baseUrl,
) async {
  await _writeStartupProbeLog(
    'START api_base_url=${_safeStartupBaseUrl(baseUrl)}',
  );
  try {
    final result = await OwnerStartupProbe(api).run();
    final health = result['health'];
    final status = health is Map ? health['status'] : null;
    await _writeStartupProbeLog(
      'PASS public_health_status=${status ?? 'unknown'}',
    );
  } catch (error) {
    // Keep the app shell available while making the failure diagnosable.
    // Do not log exception text, request headers, or session credentials.
    await _writeStartupProbeLog(
      'FAIL error_type=${error.runtimeType}',
    );
  }
}

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  final ownerId = Platform.environment['RESEARCH_OS_OWNER_ID'] ?? 'owner';
  final profileId =
      Platform.environment['RESEARCH_OS_OWNER_PROFILE'] ?? 'default';
  final sessionId =
      Platform.environment['RESEARCH_OS_OWNER_SESSION'] ?? 'desktop';
  final baseUrl =
      (Platform.environment['RESEARCH_OS_API_BASE_URL'] ??
              'https://phakphumwir.tail4b06c9.ts.net')
          .trim();

  final api = HttpOwnerFriendApi(
    baseUrl: baseUrl,
    ownerId: ownerId,
    profileId: profileId,
    sessionId: sessionId,
  );
  registerOwnerFriendApi(api);

  // Render immediately, then collect health/status/provider evidence without
  // blocking first frame. Offline API state must not strand the user at launch.
  runApp(OwnerFriendApp(api: api));
  unawaited(_probeStartupInBackground(api, baseUrl));
}
