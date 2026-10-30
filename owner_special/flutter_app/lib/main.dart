import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';

import 'src/friend_app.dart';
import 'src/owner_api.dart';
import 'src/startup_probe.dart';

Future<void> _probeStartupInBackground(OwnerFriendApi api) async {
  try {
    await OwnerStartupProbe(api).run();
  } catch (_) {
    // Startup diagnostics must never prevent the app shell from opening.
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
  unawaited(_probeStartupInBackground(api));
}
