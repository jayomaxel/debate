export const hasConfiguredSecret = (
  configured?: boolean,
  maskedValue?: string | null
): boolean => Boolean(configured || maskedValue);

export const getMaskedSecretDisplay = (
  configured?: boolean,
  maskedValue?: string | null
): string => {
  if (!hasConfiguredSecret(configured, maskedValue)) return '未配置';
  return maskedValue || '已配置';
};

export const normalizeSecretUpdate = (value?: string): string | undefined => {
  const normalized = value?.trim();
  return normalized || undefined;
};
