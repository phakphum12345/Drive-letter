import 'owner_api.dart';

final class OwnerStartupProbe {
  OwnerStartupProbe(this.api);
  final OwnerFriendApi api;

  Future<Map<String, dynamic>> run() async {
    final health = await api.health();
    final identity = await api.authStatus();
    if (identity['connected'] != true) {
      // Health is intentionally public. Owner status and provider data are
      // requested only after the user has a verified Research OS session.
      return <String, dynamic>{'health': health, 'identity': identity};
    }
    final status = await api.status();
    final provider = await api.providerStatus();
    return <String, dynamic>{
      'health': health,
      'identity': identity,
      'status': status,
      'provider': provider,
    };
  }
}
