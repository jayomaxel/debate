import { describe, expect, it } from 'vitest';
import {
  hasCompleteAbilityValues,
  hasRecordedAbilityValues,
  shouldRenderAbilityPortrait,
} from './ability-profile';

describe('ability-profile', () => {
  it('treats null skill values as empty data', () => {
    expect(hasRecordedAbilityValues([null, null, null, null, null])).toBe(false);
    expect(hasCompleteAbilityValues([null, null, null, null, null])).toBe(false);
  });

  it('hides the portrait when completed debates is zero', () => {
    expect(
      shouldRenderAbilityPortrait({
        completedDebates: 0,
        skillValues: [65, 50, 75, 60, 70],
      })
    ).toBe(false);
  });

  it('hides the portrait when assessment is marked as default', () => {
    expect(
      shouldRenderAbilityPortrait({
        completedDebates: 3,
        skillValues: [65, 50, 75, 60, 70],
        isDefaultAssessment: true,
      })
    ).toBe(false);
  });

  it('shows the portrait only when debates and real values both exist', () => {
    expect(
      shouldRenderAbilityPortrait({
        completedDebates: 2,
        skillValues: [80, 72, 68, 75, 83],
      })
    ).toBe(true);
  });
});
