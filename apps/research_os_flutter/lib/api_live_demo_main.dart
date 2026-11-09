import 'package:flutter/material.dart';

import 'src/api/api_endpoint_store.dart';
import 'src/api/research_os_api_client.dart';
import 'src/features/api_live/api_live_demo_page.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  const configuredUrl = String.fromEnvironment('RESEARCH_OS_API_URL');
  final baseUrl = configuredUrl.trim().isNotEmpty
      ? ApiEndpointStore.normalize(configuredUrl)
      : await ApiEndpointStore.load();

  runApp(MaterialApp(
    debugShowCheckedModeBanner: false,
    title: 'Flutter API Platform Live Demo',
    theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.blue),
    home: ApiLiveDemoPage(
      apiClient: ResearchOSApiClient(baseUrl: baseUrl),
    ),
  ));
}
