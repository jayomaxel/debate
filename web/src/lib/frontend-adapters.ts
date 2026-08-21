import type {
  AssignmentViewModel,
  AuthStateSource,
  FrontendAuthStateShape,
  FrontendAuthStatus,
  FrontendReportViewModel,
  ReportContract,
  ReportParticipantContract,
  ReportScoreContract,
  RoleAssignmentPreviewContract,
  TeachingDesignVersionContract,
  TeachingDesignViewModel,
} from './frontend-contracts';

const finiteNumber = (value: number | null | undefined): number =>
  typeof value === 'number' && Number.isFinite(value) ? value : 0;

const normalizeScore = (score?: ReportScoreContract | null) => ({
  logic_score: finiteNumber(score?.logic_score),
  argument_score: finiteNumber(score?.argument_score),
  response_score: finiteNumber(score?.response_score),
  persuasion_score: finiteNumber(score?.persuasion_score),
  teamwork_score: finiteNumber(score?.teamwork_score),
  overall_score: finiteNumber(score?.overall_score),
});

const toHundredPointScale = (value: number | null | undefined): number => {
  const normalized = finiteNumber(value);
  return normalized > 0 && normalized <= 10 ? normalized * 10 : normalized;
};

export const toTeachingDesignViewModel = (
  source: TeachingDesignVersionContract
): TeachingDesignViewModel => {
  const payload =
    source.extracted_payload ||
    ({} as TeachingDesignVersionContract['extracted_payload']);
  const confidence = payload.confidence || {};
  return {
    id: source.id,
    classId: source.class_id,
    name: source.version_name || source.title || '当前教学设计',
    fileName: source.source_filename || '在线录入',
    status:
      source.extraction_status === 'completed'
        ? 'ready'
        : source.extraction_status === 'failed'
          ? 'failed'
          : 'needs_review',
    payload,
    lowConfidenceFields: Object.entries(confidence)
      .filter(([, value]) => value < 0.6)
      .map(([key]) => key),
    missingFields: payload.missing_fields || [],
    createdAt: source.created_at,
  };
};

export const toAssignmentViewModel = (
  source: RoleAssignmentPreviewContract
): AssignmentViewModel => ({
  runId: source.assignment_run_id,
  items: source.results.map(item => ({
    userId: item.user_id,
    role: item.assigned_role,
    reason: item.assignment_reason || item.rotation_reason || '系统综合评估',
    score: item.final_score,
    confidence: item.confidence,
  })),
});

export const toReportViewModel = (
  source: ReportContract
): FrontendReportViewModel => {
  const legacyAbilityScores = source.ability_scores;
  const legacyParticipant: ReportParticipantContract[] =
    !source.participants && source.student_id
      ? [
          {
            user_id: source.student_id,
            name: '当前学生',
            role: source.role,
            stance: source.stance,
            speech_count: source.speeches?.length || 0,
            final_score: {
              logic_score: toHundredPointScale(legacyAbilityScores?.logic),
              argument_score: toHundredPointScale(
                legacyAbilityScores?.knowledge
              ),
              response_score: toHundredPointScale(
                legacyAbilityScores?.rebuttal
              ),
              persuasion_score: toHundredPointScale(
                legacyAbilityScores?.expression
              ),
              teamwork_score: toHundredPointScale(
                legacyAbilityScores?.teamwork
              ),
              overall_score: finiteNumber(source.final_score),
              speech_count: source.speeches?.length || 0,
            },
          },
        ]
      : [];
  const participants = source.participants || legacyParticipant;

  return {
    debate_id: source.debate_id,
    topic: source.topic || '未命名辩题',
    start_time: source.start_time || null,
    end_time: source.end_time || null,
    duration: finiteNumber(source.duration),
    participants: participants.map(participant => ({
      user_id: participant.user_id,
      name: participant.name || '未命名参与者',
      role: participant.role || 'unknown',
      stance: participant.stance || 'unknown',
      is_ai: participant.is_ai,
      has_speech: participant.has_speech,
      score_status: participant.score_status || undefined,
      speech_count:
        participant.speech_count == null
          ? undefined
          : finiteNumber(participant.speech_count),
      final_score: {
        ...normalizeScore(participant.final_score),
        speech_count: finiteNumber(participant.final_score?.speech_count),
        total_duration:
          participant.final_score?.total_duration == null
            ? undefined
            : finiteNumber(participant.final_score.total_duration),
      },
    })),
    speeches: (source.speeches || []).map(speech => ({
      id: speech.id,
      speaker_user_id: speech.speaker_user_id || speech.user_id,
      speaker_type: speech.speaker_type || undefined,
      speaker_role: speech.speaker_role || undefined,
      speaker_name: speech.speaker_name || undefined,
      stance: speech.stance,
      role: speech.role,
      phase: speech.phase || 'unknown',
      content: speech.content || '',
      duration: finiteNumber(speech.duration),
      timestamp: speech.timestamp || speech.created_at || '',
      score: speech.score
        ? {
            ...normalizeScore(speech.score),
            feedback: speech.score.feedback || '',
          }
        : null,
    })),
    statistics: source.statistics ? { ...source.statistics } : {},
    report_meta: source.report_meta ? { ...source.report_meta } : undefined,
    winner: source.winner || '',
    summary: source.summary || source.feedback || undefined,
    student_id: source.student_id || undefined,
    role: source.role || undefined,
    stance: source.stance || undefined,
    final_score:
      source.final_score == null ? undefined : finiteNumber(source.final_score),
    ability_scores: legacyAbilityScores
      ? {
          logic: finiteNumber(legacyAbilityScores.logic),
          expression: finiteNumber(legacyAbilityScores.expression),
          rebuttal: finiteNumber(legacyAbilityScores.rebuttal),
          teamwork: finiteNumber(legacyAbilityScores.teamwork),
          knowledge: finiteNumber(legacyAbilityScores.knowledge),
        }
      : undefined,
    feedback: source.feedback || undefined,
    generated_at: source.generated_at || undefined,
  };
};

const resolveAuthStatus = <TUser>(
  source: AuthStateSource<TUser>
): FrontendAuthStatus => {
  if (source.status) return source.status;
  if (source.loading) return 'initializing';
  if (source.expired) return 'expired';
  if (source.error) return 'error';
  return source.isAuthenticated && source.user ? 'authenticated' : 'anonymous';
};

export const toAuthStateShape = <TUser>(
  source: AuthStateSource<TUser>
): FrontendAuthStateShape<TUser> => {
  const resolvedStatus = resolveAuthStatus(source);
  const status =
    resolvedStatus === 'authenticated' && !source.user ? 'anonymous' : resolvedStatus;
  const authenticated = status === 'authenticated' && Boolean(source.user);

  return {
    status,
    isAuthenticated: authenticated,
    user: authenticated ? source.user || null : null,
    loading: status === 'initializing',
    error: status === 'error' ? source.error || '认证状态检查失败' : null,
  };
};
