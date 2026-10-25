import 'package:flutter_test/flutter_test.dart';
import 'package:research_os_flutter/src/ui/enterprise_navigation.dart';
import 'package:research_os_flutter/src/ui/research_os_feature_color_system.dart';

void main() {
  group('ResearchOSFeatureColorSystem', () {
    test('maps every canonical navigation destination to a known feature track', () {
      final destinations = researchNavigationItems
          .map((item) => item.destinationId)
          .toList(growable: false);

      expect(destinations.toSet(), hasLength(destinations.length));
      for (final destinationId in destinations) {
        expect(
          ResearchOSFeatureColorSystem.hasDestination(destinationId),
          isTrue,
          reason: 'Missing feature color mapping for $destinationId',
        );
        expect(
          ResearchOSFeatureColorSystem.forDestination(destinationId).id,
          isNot('unclassified'),
          reason: '$destinationId must have an explicit feature track',
        );
      }
    });

    test('feature track IDs are unique and status is not encoded as a track', () {
      final ids = ResearchOSFeatureColorSystem.tracks
          .map((track) => track.id)
          .toList(growable: false);

      expect(ids.toSet(), hasLength(ids.length));
      expect(ids, containsAll(<String>[
        'architecture',
        'execution_automation',
        'research_knowledge',
        'assurance_evidence',
        'owner_experience',
        'workspace',
      ]));
      expect(ids, isNot(contains('pass')));
      expect(ids, isNot(contains('fail')));
      expect(ids, isNot(contains('blocked')));
    });

    test('unknown destinations remain neutral instead of being guessed', () {
      expect(
        ResearchOSFeatureColorSystem.hasDestination('future_unknown_route'),
        isFalse,
      );
      expect(
        ResearchOSFeatureColorSystem
            .forDestination('future_unknown_route')
            .id,
        'unclassified',
      );
    });
  });
}
