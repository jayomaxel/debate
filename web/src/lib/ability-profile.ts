export interface AbilityProfileVisibilityArgs {
  completedDebates: number | null | undefined;
  skillValues: Array<number | null | undefined>;
  isDefaultAssessment?: boolean;
}

export const hasRecordedAbilityValues = (
  skillValues: Array<number | null | undefined>
): boolean => skillValues.some((value) => typeof value === 'number');

export const hasCompleteAbilityValues = (
  skillValues: Array<number | null | undefined>
): boolean =>
  skillValues.length > 0 &&
  skillValues.every((value) => typeof value === 'number');

export const shouldRenderAbilityPortrait = ({
  completedDebates,
  skillValues,
  isDefaultAssessment = false,
}: AbilityProfileVisibilityArgs): boolean =>
  (completedDebates ?? 0) > 0 &&
  !isDefaultAssessment &&
  hasRecordedAbilityValues(skillValues);
