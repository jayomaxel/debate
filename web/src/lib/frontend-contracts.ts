export type TeachingDesignStatus = 'extracting' | 'ready' | 'needs_review' | 'failed';

export interface TeachingDesignPayload {
  course_title?: string | null;
  chapter_theme?: string | null;
  learning_objectives: string[];
  knowledge_points: string[];
  key_difficulties: string[];
  capability_targets: string[];
  grade_level?: string | null;
  time_constraints?: string | null;
  debate_focuses: string[];
  forbidden_boundaries: string[];
  source_summary?: string | null;
  confidence?: Record<string, number>;
  missing_fields?: string[];
  source_excerpt_map?: Record<string, string>;
}

export interface TeachingDesignVersionContract {
  id: string;
  class_id: string;
  version_name?: string | null;
  title?: string | null;
  source_type: string;
  source_filename?: string | null;
  source_file_type?: string | null;
  extracted_payload: TeachingDesignPayload;
  extraction_status: 'completed' | 'partial' | 'insufficient' | 'failed';
  correction_notes?: string | null;
  is_active: boolean;
  created_at?: string | null;
}

export interface TeachingDesignViewModel {
  id: string;
  classId: string;
  name: string;
  fileName: string;
  status: TeachingDesignStatus;
  payload: TeachingDesignPayload;
  lowConfidenceFields: string[];
  missingFields: string[];
  createdAt?: string | null;
}

export interface TopicCandidateContract {
  candidate_id: string;
  topic_text: string;
  mapped_course_objectives: string[];
  mapped_knowledge_points: string[];
  recommended_classroom_scene?: string | null;
  debatability_reason?: string | null;
  difficulty_level?: string | null;
  recommendation_reason?: string | null;
  evidence_basis: string[];
}

export interface TopicRecommendationRunContract {
  run_id: string;
  status: 'ready' | 'partial' | 'unavailable';
  teaching_design_version_id?: string | null;
  warnings: string[];
  candidates: TopicCandidateContract[];
}

export type DebateRole = 'debater_1' | 'debater_2' | 'debater_3' | 'debater_4';

export interface DebateConfigMeta {
  mode?: 'competition' | 'teaching';
  role_assignment_mode?: 'strength_first' | 'growth_first';
  assignment_policy?: 'ai_auto_assign' | 'ai_recommend_then_confirm';
  role_rotation_policy?: 'balanced_rotation' | 'strength_priority' | 'growth_priority';
  rounds?: number;
  knowledge_points?: string[];
  objective?: string[];
  evaluation_focus?: string[];
  forbidden_moves?: string[];
  support_document_ids?: string[];
  teaching_design_version_id?: string;
  topic_recommendation_run_id?: string;
  selected_topic_candidate_id?: string;
  topic_source?: 'manual' | 'ai_recommended' | 'ai_recommended_edited';
  activity_focus?: {
    chapter_focus?: string;
    training_focus?: string;
    classroom_scene?: string;
  };
}

export interface RoleAssignmentInput {
  user_id: string;
  role: DebateRole;
  override_reason?: string;
}

export interface RoleAssignmentResultContract {
  user_id: string;
  assigned_role: DebateRole;
  assignment_reason?: string | null;
  final_score?: number | null;
  confidence?: number | null;
  rotation_reason?: string | null;
}

export interface RoleAssignmentPreviewContract {
  assignment_run_id?: string | null;
  assignment_mode: string;
  assignment_source: string;
  results: RoleAssignmentResultContract[];
}

export interface AssignmentViewModel {
  runId?: string | null;
  items: Array<{
    userId: string;
    role: DebateRole;
    reason: string;
    score?: number | null;
    confidence?: number | null;
  }>;
}

export interface SupportDocumentSummarySchema {
  label: 'background' | 'evidence' | 'case' | 'optional';
  summary: string;
  key_points: string[];
  evidence_candidates: string[];
  case_candidates: string[];
  usable_phases: Array<'opening' | 'questioning' | 'free_debate' | 'closing'>;
  summary_quality: 'validated' | 'fallback';
}

export interface KnowledgeSnippetSchema {
  snippet_id: string;
  document_id: string;
  source_type: 'background' | 'evidence' | 'case' | 'optional';
  content: string;
  usage_goal: string;
  source_location: string;
}

export interface UploadGuardErrorContract {
  code?: string;
  message?: string;
  detail?: string | { code?: string; message?: string };
}
