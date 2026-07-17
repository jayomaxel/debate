import type {
  AssignmentViewModel,
  RoleAssignmentPreviewContract,
  TeachingDesignVersionContract,
  TeachingDesignViewModel,
} from './frontend-contracts';

export const toTeachingDesignViewModel = (
  source: TeachingDesignVersionContract
): TeachingDesignViewModel => {
  const payload = source.extracted_payload || ({} as TeachingDesignVersionContract['extracted_payload']);
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
  items: source.results.map((item) => ({
    userId: item.user_id,
    role: item.assigned_role,
    reason: item.assignment_reason || item.rotation_reason || '系统综合评估',
    score: item.final_score,
    confidence: item.confidence,
  })),
});

export const toReportViewModel = <T>(source: T): T => source;
export const toAuthStateShape = <T>(source: T): T => source;
