import 'package:flutter_test/flutter_test.dart';
import 'package:research_os_owner_special/src/owner_api.dart';
import 'package:research_os_owner_special/src/startup_probe.dart';

class FakeApi extends OwnerFriendApi {
  @override
  Future<Map<String, dynamic>> health() async => <String, dynamic>{'status': 'ok'};
  @override
  Future<Map<String, dynamic>> authStatus() async => <String, dynamic>{'connected': true};
  @override
  Future<Map<String, dynamic>> status() async => <String, dynamic>{'version': '1.3.1-owner'};
  @override
  Future<Map<String, dynamic>> providerStatus() async => <String, dynamic>{'enabled': false};
  @override
  Future<Map<String, dynamic>> memory() async => <String, dynamic>{};
  @override
  Future<Map<String, dynamic>> configureProvider({required String baseUrl, required String model, String? apiKey}) async => <String, dynamic>{};
  @override
  Future<Map<String, dynamic>> testProvider() async => <String, dynamic>{};
  @override
  Future<Map<String, dynamic>> chat(String text, {int complexity = 4, int risk = 2, int parallelism = 2, int helperBudget = 0, List<String> requestedSkills = const <String>[], List<String> requestedTools = const <String>[]}) async => <String, dynamic>{};
}

class _UnauthenticatedApi extends FakeApi {
  int protectedCalls = 0;

  @override
  Future<Map<String, dynamic>> authStatus() async => <String, dynamic>{'connected': false};

  @override
  Future<Map<String, dynamic>> status() async {
    protectedCalls++;
    throw StateError('protected status must not be requested before sign-in');
  }

  @override
  Future<Map<String, dynamic>> providerStatus() async {
    protectedCalls++;
    throw StateError('protected provider must not be requested before sign-in');
  }
}

void main() {
  test('startup probe proves health status and provider boundary after sign-in', () async {
    final result = await OwnerStartupProbe(FakeApi()).run();
    expect((result['health'] as Map)['status'], 'ok');
    expect((result['status'] as Map)['version'], '1.3.1-owner');
    expect(result.containsKey('provider'), isTrue);
  });

  test('startup probe does not call protected endpoints before sign-in', () async {
    final api = _UnauthenticatedApi();
    final result = await OwnerStartupProbe(api).run();
    expect((result['health'] as Map)['status'], 'ok');
    expect((result['identity'] as Map)['connected'], isFalse);
    expect(result.containsKey('status'), isFalse);
    expect(result.containsKey('provider'), isFalse);
    expect(api.protectedCalls, 0);
  });
}
