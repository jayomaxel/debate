import { afterEach, describe, expect, it } from 'vitest';
import {
  consumeAssessmentOnboardingPrompt,
  markAssessmentOnboardingPendingForAccount,
  shouldShowAssessmentOnboardingPrompt,
} from './student-assessment-onboarding';

describe('student-assessment-onboarding', () => {
  afterEach(() => {
    localStorage.clear();
  });

  it('shows the prompt once after a newly logged-in student with pending onboarding reaches home', () => {
    markAssessmentOnboardingPendingForAccount('student-001');

    const user = {
      id: 'user-001',
      account: 'student-001',
      user_type: 'student',
    } as const;

    expect(
      shouldShowAssessmentOnboardingPrompt(user, {
        needsAssessment: true,
        completedDebates: 0,
      })
    ).toBe(true);

    consumeAssessmentOnboardingPrompt(user);

    expect(
      shouldShowAssessmentOnboardingPrompt(user, {
        needsAssessment: true,
        completedDebates: 0,
      })
    ).toBe(false);
  });

  it('does not show the prompt when assessment is already completed or the first debate is finished', () => {
    markAssessmentOnboardingPendingForAccount('student-001');

    const user = {
      id: 'user-001',
      account: 'student-001',
      user_type: 'student',
    } as const;

    expect(
      shouldShowAssessmentOnboardingPrompt(user, {
        needsAssessment: false,
        completedDebates: 0,
      })
    ).toBe(false);

    expect(
      shouldShowAssessmentOnboardingPrompt(user, {
        needsAssessment: true,
        completedDebates: 1,
      })
    ).toBe(false);
  });
});
