import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';

void main() {
  late Map<String, dynamic> contract;

  setUp(() {
    contract = jsonDecode('''
{
  "roles": {
    "owner": {"switch_team": true, "create_team": true, "admin": true},
    "member": {"switch_team": true, "create_team": false, "admin": false},
    "viewer": {"switch_team": false, "create_team": false, "admin": false}
  },
  "services": {
    "research_os_api": "workspace",
    "team_engineering": "team",
    "friend_internal": "friend-internal",
    "developer_api": "developer-access"
  }
}
''') as Map<String, dynamic>;
  });

  test('owner has full team controls', () {
    final owner = Map<String, dynamic>.from(contract['roles']['owner'] as Map);
    expect(owner['switch_team'], isTrue);
    expect(owner['create_team'], isTrue);
    expect(owner['admin'], isTrue);
  });

  test('member cannot create teams or administer', () {
    final member = Map<String, dynamic>.from(contract['roles']['member'] as Map);
    expect(member['switch_team'], isTrue);
    expect(member['create_team'], isFalse);
    expect(member['admin'], isFalse);
  });

  test('viewer has no team mutation access', () {
    final viewer = Map<String, dynamic>.from(contract['roles']['viewer'] as Map);
    expect(viewer['switch_team'], isFalse);
    expect(viewer['create_team'], isFalse);
    expect(viewer['admin'], isFalse);
  });

  test('service topology uses stable identities, not port numbers', () {
    final services = Map<String, dynamic>.from(contract['services'] as Map);
    expect(services.keys.toSet(), {
      'research_os_api',
      'team_engineering',
      'friend_internal',
      'developer_api',
    });
    expect(services['research_os_api'], 'workspace');
    expect(services['team_engineering'], 'team');
    expect(services['friend_internal'], 'friend-internal');
    expect(services['developer_api'], 'developer-access');
  });
}
