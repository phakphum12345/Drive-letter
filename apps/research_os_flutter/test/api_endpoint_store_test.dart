import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:research_os_flutter/src/api/api_endpoint_store.dart';

void main() {
  test('build default follows the compile-time API contract', () {
    const expected = String.fromEnvironment(
      'RESEARCH_OS_API_BASE_URL',
      defaultValue: ApiEndpointStore.tailscaleDefault,
    );
    expect(ApiEndpointStore.buildDefault, expected);
  });


  test('runtime endpoint registry resolves a generated loopback API URL', () {
    const record = '''
{
  "schema_version": 1,
  "service": "api",
  "host": "127.0.0.1",
  "port": 43127,
  "url": "http://127.0.0.1:43127",
  "pid": 42
}
''';
    expect(
      ApiEndpointStore.parseLocalEndpointRecord(record),
      'http://127.0.0.1:43127',
    );
  });

  test('runtime endpoint registry rejects non-loopback and malformed records', () {
    const nonLoopback = '''
{"schema_version":1,"service":"api","host":"0.0.0.0","port":43127,"url":"http://0.0.0.0:43127","pid":42}
''';
    const wrongService = '''
{"schema_version":1,"service":"friend","host":"127.0.0.1","port":43127,"url":"http://127.0.0.1:43127","pid":42}
''';
    const invalidPort = '''
{"schema_version":1,"service":"api","host":"127.0.0.1","port":0,"url":"http://127.0.0.1:0","pid":42}
''';
    expect(ApiEndpointStore.parseLocalEndpointRecord(nonLoopback), isNull);
    expect(ApiEndpointStore.parseLocalEndpointRecord(wrongService), isNull);
    expect(ApiEndpointStore.parseLocalEndpointRecord(invalidPort), isNull);
    expect(ApiEndpointStore.parseLocalEndpointRecord('{broken'), isNull);
  });

  test('generated loopback endpoint is accepted as a valid API URL', () {
    expect(
      ApiEndpointStore.normalize('http://127.0.0.1:43127'),
      'http://127.0.0.1:43127',
    );
  });

  test('stale saved loopback endpoint is discarded when no runtime registry exists', () async {
    SharedPreferences.setMockInitialValues(<String, Object>{
      'research_os_api_base_url_v1': 'http://127.0.0.1:8787',
    });

    expect(
      await ApiEndpointStore.load(),
      ApiEndpointStore.profileUrl(ApiEndpointStore.connectionResearchOs),
    );
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('research_os_api_base_url_v1'), isNull);
  });

  test('new installs default to the configured Research OS API endpoint', () async {
    SharedPreferences.setMockInitialValues(<String, Object>{});

    expect(
      await ApiEndpointStore.load(),
      ApiEndpointStore.profileUrl(ApiEndpointStore.connectionResearchOs),
    );
  });

  test('legacy hosted endpoint is migrated to Tailscale Serve', () async {
    SharedPreferences.setMockInitialValues(<String, Object>{
      'research_os_api_base_url_v1': 'https://legacy-service.onrender.com',
    });

    expect(await ApiEndpointStore.load(), ApiEndpointStore.tailscaleDefault);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('research_os_api_base_url_v1'), ApiEndpointStore.tailscaleDefault);
  });

}
