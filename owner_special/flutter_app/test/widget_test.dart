import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:research_os_owner_special/src/friend_app.dart';
import 'package:research_os_owner_special/src/owner_api.dart';

class FakeOwnerFriendApi extends OwnerFriendApi {
  String? lastPrompt;
  int? lastComplexity;
  int? lastHelperBudget;

  @override
  Future<Map<String, dynamic>> health() async => <String, dynamic>{'status': 'ok'};

  @override
  Future<Map<String, dynamic>> status() async => <String, dynamic>{
        'brain_profiles': <String, int>{'1^3': 1, '3^3': 27},
        'helper_scheduler': <String, int>{'max_logical_helpers': 1000000, 'max_active_workers': 128},
        'capabilities': <String>['brain', 'skills', 'persistent-memory'],
      };

  @override
  Future<Map<String, dynamic>> memory() async => <String, dynamic>{'count': 0, 'items': <Object>[]};

  @override
  Future<Map<String, dynamic>> providerStatus() async => <String, dynamic>{
        'enabled': false,
        'credential_present': false,
        'secret_backend': 'test',
        'base_url': '',
        'model': '',
      };

  @override
  Future<Map<String, dynamic>> configureProvider({required String baseUrl, required String model, String? apiKey}) async =>
      <String, dynamic>{'enabled': true, 'credential_present': true, 'secret_backend': 'test'};

  @override
  Future<Map<String, dynamic>> testProvider() async => <String, dynamic>{'connected': true};

  @override
  Future<Map<String, dynamic>> chat(
    String text, {
    int complexity = 4,
    int risk = 2,
    int parallelism = 2,
    int helperBudget = 0,
    List<String> requestedSkills = const <String>[],
    List<String> requestedTools = const <String>[],
  }) async {
    lastPrompt = text;
    lastComplexity = complexity;
    lastHelperBudget = helperBudget;
    return <String, dynamic>{
      'text': 'Research OS ตอบกลับ: $text',
      'decision': <String, dynamic>{'scale': helperBudget >= 1000000 ? 'fast-1m' : '6^6', 'capacity': helperBudget >= 1000000 ? 1000000 : 46656},
      'helpers': <String, dynamic>{'active_workers': 128, 'batches': 7813},
    };
  }
}

void main() {
  testWidgets('Research OS AI chat renders controls and sends through the existing API', (tester) async {
    tester.view.physicalSize = const Size(1440, 900);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    final api = FakeOwnerFriendApi();
    await tester.pumpWidget(OwnerFriendApp(api: api));
    await tester.pump();

    await tester.tap(find.text('Friend Runtime').first);
    await tester.pumpAndSettle();

    expect(find.text('AI Chat'), findsOneWidget);
    expect(find.byKey(const Key('ai-chat-input')), findsOneWidget);
    expect(find.byKey(const Key('ai-chat-send')), findsOneWidget);
    expect(find.byKey(const Key('ai-chat-mode')), findsOneWidget);
    expect(find.byKey(const Key('ai-chat-turbo')), findsOneWidget);
    expect(find.text('ค้นคว้าข้อมูล'), findsOneWidget);
    expect(find.text('วิเคราะห์ปัญหา'), findsOneWidget);

    await tester.enterText(find.byKey(const Key('ai-chat-input')), 'ตรวจสอบระบบ Research OS');
    await tester.tap(find.byKey(const Key('ai-chat-send')));
    await tester.pump();
    await tester.pumpAndSettle();

    expect(api.lastPrompt, 'ตรวจสอบระบบ Research OS');
    expect(api.lastHelperBudget, 1000000);
    expect(find.text('Research OS ตอบกลับ: ตรวจสอบระบบ Research OS'), findsOneWidget);
    expect(find.textContaining('Brain: fast-1m'), findsOneWidget);
  });

  testWidgets('Research OS AI chat can attach context to a prompt', (tester) async {
    tester.view.physicalSize = const Size(1440, 900);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    final api = FakeOwnerFriendApi();
    await tester.pumpWidget(OwnerFriendApp(api: api));
    await tester.pump();
    await tester.tap(find.text('Friend Runtime').first);
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('เพิ่มบริบท/ข้อความอ้างอิง'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).last, 'ข้อกำหนดระบบ: ต้องรักษาข้อมูลเดิม');
    await tester.tap(find.text('ใช้บริบทนี้'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('ai-chat-input')), 'ช่วยวางแผนแก้ไข');
    await tester.tap(find.byKey(const Key('ai-chat-send')));
    await tester.pump();
    await tester.pumpAndSettle();

    expect(api.lastPrompt, contains('ข้อกำหนดระบบ: ต้องรักษาข้อมูลเดิม'));
    expect(api.lastPrompt, contains('ช่วยวางแผนแก้ไข'));
  });
}
