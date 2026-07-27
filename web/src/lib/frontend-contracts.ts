export type TeachingDesignStatus =
  | 'extracting'
  | 'ready'
  | 'needs_review'
  | 'failed';

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
  candidate_order?: number;
  topic_text: string;
  mapped_course_objectives: string[];
  mapped_knowledge_points: string[];
  recommended_classroom_scene?: string | null;
  debatability_reason?: string | null;
  difficulty_level?: string | null;
  recommendation_reason?: string | null;
  evidence_basis: string[];
  quality_score?: number | null;
  quality_flags?: string[];
  adoption_stats?: TopicRecommendationAdoptionSummary & {
    is_adopted?: boolean;
  };
}

export interface TopicRecommendationRunContract {
  run_id: string;
  recommendation_run_id?: string;
  parent_run_id?: string | null;
  status: 'ready' | 'partial' | 'unavailable';
  legacy_status?: string;
  teaching_design_status?: string;
  teaching_design_version_id?: string | null;
  mode?: 'competition' | 'teaching';
  activity_focus?: DebateConfigMeta['activity_focus'];
  generation_source?: string;
  provider?: string;
  generation_quality?: string;
  retry_count?: number;
  preferred_count?: number;
  difficulty_preference?: string | null;
  warnings: string[];
  generated_at?: string | null;
  candidate_count?: number;
  candidate_topics?: string[];
  adoption_summary?: TopicRecommendationAdoptionSummary;
  candidates: TopicCandidateContract[];
}

export interface TopicRecommendationAdoptionSummary {
  total_adoptions: number;
  direct_adoptions: number;
  edited_adoptions: number;
  debate_adoptions: number;
  reservation_adoptions: number;
  distinct_candidates_adopted?: number;
  last_adopted_at?: string | null;
}

export type TopicRecommendationRunSummary = Omit<
  TopicRecommendationRunContract,
  'candidates'
> & {
  candidates?: TopicCandidateContract[];
};

export interface TopicRecommendationVersionBreakdown {
  teaching_design_version_id: string;
  version_name?: string | null;
  title?: string | null;
  is_active?: boolean;
  total_runs: number;
  total_candidates: number;
  adopted_run_count: number;
  adopted_candidate_count: number;
  total_adoptions: number;
  direct_adoptions: number;
  edited_adoptions: number;
  run_adoption_rate: number;
  candidate_adoption_rate: number;
  last_generated_at?: string | null;
  last_adopted_at?: string | null;
}

export interface TopicRecommendationVersionComparisonSummary {
  current_version?: TopicRecommendationVersionBreakdown | null;
  previous_version?: TopicRecommendationVersionBreakdown | null;
  delta?: Record<string, number>;
}

export interface TopicRecommendationAnalyticsContract {
  class_id: string;
  date_from?: string | null;
  date_to?: string | null;
  total_runs: number;
  total_candidates: number;
  adopted_run_count: number;
  adopted_candidate_count: number;
  total_adoptions: number;
  direct_adoptions: number;
  edited_adoptions: number;
  debate_adoptions: number;
  reservation_adoptions: number;
  run_adoption_rate: number;
  candidate_adoption_rate: number;
  average_candidates_per_run: number;
  quality_counts: Record<string, number>;
  provider_counts: Record<string, number>;
  status_counts: Record<string, number>;
  quality_rates: Record<string, number>;
  version_breakdown: TopicRecommendationVersionBreakdown[];
  version_comparison_summary?: TopicRecommendationVersionComparisonSummary;
  last_generated_at?: string | null;
  last_adopted_at?: string | null;
  latest_run_id?: string | null;
}

export interface TopicRecommendationRankedCandidate {
  run_id: string;
  candidate_id: string;
  candidate_order?: number;
  topic_text: string;
  difficulty_level?: string | null;
  recommendation_reason?: string | null;
  quality_score?: number | null;
  quality_flags?: string[];
  total_adoptions: number;
  direct_adoptions: number;
  edited_adoptions: number;
  debate_adoptions?: number;
  reservation_adoptions?: number;
  last_adopted_at?: string | null;
}

export interface TopicRecommendationDashboardContract {
  class_id: string;
  date_from?: string | null;
  date_to?: string | null;
  summary: Pick<
    TopicRecommendationAnalyticsContract,
    | 'total_runs'
    | 'total_candidates'
    | 'adopted_run_count'
    | 'adopted_candidate_count'
    | 'total_adoptions'
    | 'run_adoption_rate'
    | 'candidate_adoption_rate'
    | 'average_candidates_per_run'
    | 'direct_adoptions'
    | 'edited_adoptions'
    | 'debate_adoptions'
    | 'reservation_adoptions'
  >;
  quality: Pick<
    TopicRecommendationAnalyticsContract,
    | 'quality_counts'
    | 'quality_rates'
    | 'provider_counts'
    | 'status_counts'
    | 'version_breakdown'
    | 'version_comparison_summary'
  >;
  timeline: {
    latest_run_id?: string | null;
    last_generated_at?: string | null;
    last_adopted_at?: string | null;
    latest_run?: TopicRecommendationRunSummary | null;
    latest_adopted_run?: TopicRecommendationRunSummary | null;
  };
  leaderboards: {
    top_adopted_candidates: TopicRecommendationRankedCandidate[];
    top_edited_candidates: TopicRecommendationRankedCandidate[];
  };
  observations: {
    high_quality_low_adoption_candidates: TopicRecommendationRankedCandidate[];
    high_quality_edited_only_candidates: TopicRecommendationRankedCandidate[];
  };
  recent_runs: TopicRecommendationRunSummary[];
}

export type DebateRole = 'debater_1' | 'debater_2' | 'debater_3' | 'debater_4';

export interface DebateConfigMeta {
  mode?: 'competition' | 'teaching';
  role_assignment_mode?: 'strength_first' | 'growth_first';
  assignment_policy?: 'ai_auto_assign' | 'ai_recommend_then_confirm';
  role_rotation_policy?:
    | 'balanced_rotation'
    | 'strength_priority'
    | 'growth_priority';
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

export interface ReportScoreContract {
  logic_score?: number | null;
  argument_score?: number | null;
  response_score?: number | null;
  persuasion_score?: number | null;
  teamwork_score?: number | null;
  overall_score?: number | null;
  speech_count?: number | null;
  total_duration?: number | null;
  feedback?: string | null;
}

export interface ReportParticipantContract {
  user_id: string;
  name?: string | null;
  role?: string | null;
  stance?: string | null;
  is_ai?: boolean;
  has_speech?: boolean;
  score_status?: string | null;
  speech_count?: number | null;
  final_score?: ReportScoreContract | null;
}

export interface ReportSpeechContract {
  id: string;
  debate_id?: string | null;
  user_id?: string | null;
  speaker_user_id?: string | null;
  speaker_type?: string | null;
  speaker_role?: string | null;
  speaker_name?: string | null;
  stance?: string | null;
  role?: string | null;
  phase?: string | null;
  content?: string | null;
  duration?: number | null;
  timestamp?: string | null;
  created_at?: string | null;
  score?: ReportScoreContract | null;
}

export interface HumanAbilityStatistics {
  ability_scope: 'human_only';
  evaluated_student_count: number;
  valid_human_speech_count: number;
  excluded_ai_speech_count: number;
  excluded_demo_record_count: number;
  has_human_ability_data: boolean;
  ability_scores: {
    logical_construction: number;
    ai_knowledge_application: number;
    critical_thinking: number;
    language_expression: number;
    ai_ethics_literacy: number;
  } | null;
  overall_score: number | null;
}

export interface ReportMetaContract {
  report_status?: 'ready' | 'processing' | 'empty' | 'failed' | string;
  report_job_status?: string | null;
  score_missing_count?: number;
  report_quality?: string;
  [key: string]: unknown;
}

export interface ReportContract {
  debate_id: string;
  student_id?: string | null;
  topic?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  duration?: number | null;
  participants?: ReportParticipantContract[] | null;
  speeches?: ReportSpeechContract[] | null;
  statistics?: Record<string, unknown> | null;
  winner?: string | null;
  summary?: string | null;
  role?: string | null;
  stance?: string | null;
  final_score?: number | null;
  ability_scores?: {
    logic?: number | null;
    expression?: number | null;
    rebuttal?: number | null;
    teamwork?: number | null;
    knowledge?: number | null;
  } | null;
  feedback?: string | null;
  generated_at?: string | null;
  report_meta?: ReportMetaContract | null;
}

export interface FrontendReportViewModel {
  debate_id: string;
  topic: string;
  start_time: string | null;
  end_time: string | null;
  duration: number;
  participants: Array<{
    user_id: string;
    name: string;
    role: string;
    stance: string;
    is_ai?: boolean;
    has_speech?: boolean;
    score_status?: string;
    speech_count?: number;
    final_score: {
      logic_score: number;
      argument_score: number;
      response_score: number;
      persuasion_score: number;
      teamwork_score: number;
      overall_score: number;
      speech_count: number;
      total_duration?: number;
    };
  }>;
  speeches: Array<{
    id: string;
    speaker_user_id?: string | null;
    speaker_type?: string;
    speaker_role?: string;
    speaker_name?: string;
    stance?: string | null;
    role?: string | null;
    phase: string;
    content: string;
    duration: number;
    timestamp: string;
    score: {
      logic_score: number;
      argument_score: number;
      response_score: number;
      persuasion_score: number;
      teamwork_score: number;
      overall_score: number;
      feedback: string;
    } | null;
  }>;
  statistics: Record<string, unknown> & {
    human_ability?: HumanAbilityStatistics;
  };
  winner: string;
  summary?: string;
  student_id?: string;
  role?: string;
  stance?: string;
  final_score?: number;
  ability_scores?: {
    logic: number;
    expression: number;
    rebuttal: number;
    teamwork: number;
    knowledge: number;
  };
  feedback?: string;
  generated_at?: string;
  report_meta?: ReportMetaContract;
}

export type FrontendAuthStatus =
  | 'initializing'
  | 'authenticated'
  | 'anonymous'
  | 'expired'
  | 'error';

export interface FrontendAuthStateShape<TUser = unknown> {
  status: FrontendAuthStatus;
  isAuthenticated: boolean;
  user: TUser | null;
  loading: boolean;
  error: string | null;
}

export interface AuthStateSource<TUser = unknown> {
  status?: FrontendAuthStatus;
  isAuthenticated?: boolean;
  user?: TUser | null;
  loading?: boolean;
  error?: string | null;
  expired?: boolean;
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
