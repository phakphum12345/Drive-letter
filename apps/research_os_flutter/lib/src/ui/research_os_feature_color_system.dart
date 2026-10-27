import 'package:flutter/material.dart';

/// Canonical feature-track presentation metadata for Research OS navigation.
///
/// This is presentation-only metadata. It must never be used for authorization,
/// execution routing, release status, or PASS/FAIL/BLOCKED state.
class ResearchOSFeatureStyle {
  const ResearchOSFeatureStyle({
    required this.id,
    required this.label,
    required this.color,
    required this.icon,
  });

  final String id;
  final String label;
  final Color color;
  final IconData icon;
}

class ResearchOSFeatureColorSystem {
  ResearchOSFeatureColorSystem._();

  // Feature colors are intentionally separate from operational status colors.
  // PASS, FAIL, BLOCKED, warnings, and authorization outcomes have their own
  // status system and must not be inferred from these values.
  static const architecture = ResearchOSFeatureStyle(
    id: 'architecture',
    label: 'Platform Architecture',
    color: Color(0xFF2563EB),
    icon: Icons.account_tree_outlined,
  );
  static const execution = ResearchOSFeatureStyle(
    id: 'execution_automation',
    label: 'Execution & Automation',
    color: Color(0xFF0D9488),
    icon: Icons.play_circle_outline,
  );
  static const research = ResearchOSFeatureStyle(
    id: 'research_knowledge',
    label: 'M.2 Platform & Research',
    color: Color(0xFF7C3AED),
    icon: Icons.psychology_alt_outlined,
  );
  static const assurance = ResearchOSFeatureStyle(
    id: 'assurance_evidence',
    label: 'Assurance & Evidence',
    color: Color(0xFFEA580C),
    icon: Icons.fact_check_outlined,
  );
  static const ownerExperience = ResearchOSFeatureStyle(
    id: 'owner_experience',
    label: 'Owner Experience & UI',
    color: Color(0xFFDB2777),
    icon: Icons.person_outline,
  );
  static const workspace = ResearchOSFeatureStyle(
    id: 'workspace',
    label: 'Workspace',
    color: Color(0xFF64748B),
    icon: Icons.dashboard_outlined,
  );
  static const unclassified = ResearchOSFeatureStyle(
    id: 'unclassified',
    label: 'Unclassified feature',
    color: Color(0xFF64748B),
    icon: Icons.help_outline,
  );

  /// The destination ID is taken from the one canonical navigation registry.
  /// Unknown destinations stay neutral rather than being guessed into a track.
  static const Map<String, ResearchOSFeatureStyle> byDestination = {
    'home': workspace,
    'ai_chat': workspace,
    'agent_center': execution,
    'brain_skills': research,
    'library': research,
    'knowledge_graph': research,
    'github': architecture,
    'google_workspace': research,
    'friend_connect': execution,
    'local_api_service': architecture,
    'system_monitor': assurance,
    'settings': assurance,
    'developer_access': assurance,
    'google_sign_in': ownerExperience,
    'projects': workspace,
    'workflows': execution,
    'control_center': assurance,
    'owner': ownerExperience,
    'localization_center': workspace,
  };

  static ResearchOSFeatureStyle forDestination(String destinationId) =>
      byDestination[destinationId] ?? unclassified;

  static bool hasDestination(String destinationId) =>
      byDestination.containsKey(destinationId);

  static List<ResearchOSFeatureStyle> get tracks => const [
        architecture,
        execution,
        research,
        assurance,
        ownerExperience,
        workspace,
      ];
}
