import { useCallback, useEffect, useState } from 'react';
import StudentService, {
  type AssessmentResult,
  type StudentAnalytics,
} from '@/services/student.service';

export interface StudentAssessmentState {
  assessment: AssessmentResult | null;
  analytics: StudentAnalytics | null;
  needsAssessment: boolean;
  isAssessmentLocked: boolean;
  loading: boolean;
}

const getNeedsAssessment = (assessment: AssessmentResult | null) =>
  !assessment || !!assessment.is_default;

const getAssessmentLocked = (analytics: StudentAnalytics | null) =>
  (analytics?.completed_debates || 0) > 0;

export function useStudentAssessment(enabled = true) {
  const [state, setState] = useState<StudentAssessmentState>({
    assessment: null,
    analytics: null,
    needsAssessment: true,
    isAssessmentLocked: false,
    loading: true,
  });

  const refresh = useCallback(async () => {
    if (!enabled) {
      setState({
        assessment: null,
        analytics: null,
        needsAssessment: true,
        isAssessmentLocked: false,
        loading: false,
      });
      return;
    }

    setState((prev) => ({ ...prev, loading: true }));

    try {
      const [assessment, analytics] = await Promise.all([
        StudentService.getAssessment(),
        StudentService.getAnalytics().catch(() => null),
      ]);

      setState({
        assessment,
        analytics,
        needsAssessment: getNeedsAssessment(assessment),
        isAssessmentLocked: getAssessmentLocked(analytics),
        loading: false,
      });
    } catch (error) {
      console.error('[useStudentAssessment] Failed to load assessment state:', error);
      setState({
        assessment: null,
        analytics: null,
        needsAssessment: true,
        isAssessmentLocked: false,
        loading: false,
      });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    ...state,
    refresh,
  };
}
