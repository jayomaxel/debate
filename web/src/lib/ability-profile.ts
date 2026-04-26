type AbilityValue = number | null | undefined;

export interface AbilityPortraitOptions {
  completedDebates?: number | null;
  skillValues?: AbilityValue[];
  isDefaultAssessment?: boolean | null;
}

const isRecordedAbilityValue = (value: AbilityValue): value is number =>
  typeof value === 'number' && Number.isFinite(value);

export const hasRecordedAbilityValues = (values: AbilityValue[]): boolean =>
  values.some(isRecordedAbilityValue);

export const hasCompleteAbilityValues = (values: AbilityValue[]): boolean =>
  values.length > 0 && values.every(isRecordedAbilityValue);

export const shouldRenderAbilityPortrait = ({
  completedDebates = 0,
  skillValues = [],
  isDefaultAssessment = false,
}: AbilityPortraitOptions): boolean => {
  const normalizedCompletedDebates = completedDebates ?? 0;

  return (
    normalizedCompletedDebates > 0 &&
    !isDefaultAssessment &&
    hasRecordedAbilityValues(skillValues)
  );
};
