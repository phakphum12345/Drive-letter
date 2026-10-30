import 'dart:io';

import 'package:flutter/material.dart';

import 'src/friend_app.dart';
import 'src/owner_api.dart';

Future<void> main() async {
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

  // Render immediately; the UI probes the API after its first frame.
  runApp(OwnerFriendApp(api: api));
}
