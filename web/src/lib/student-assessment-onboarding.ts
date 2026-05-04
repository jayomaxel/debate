import type { UserInfo } from './token-manager';

const PENDING_ACCOUNT_PREFIX = 'student_assessment_onboarding:pending_account:';
const PENDING_USER_PREFIX = 'student_assessment_onboarding:pending_user:';
const CONSUMED_USER_PREFIX = 'student_assessment_onboarding:consumed_user:';

const canUseStorage = () => typeof localStorage !== 'undefined';

const normalizeKeyPart = (value?: string | null) => String(value || '').trim();

const getPendingAccountKey = (account?: string | null) =>
  `${PENDING_ACCOUNT_PREFIX}${normalizeKeyPart(account)}`;

const getPendingUserKey = (userId?: string | null) =>
  `${PENDING_USER_PREFIX}${normalizeKeyPart(userId)}`;

const getConsumedUserKey = (userId?: string | null) =>
  `${CONSUMED_USER_PREFIX}${normalizeKeyPart(userId)}`;

export const markAssessmentOnboardingPendingForAccount = (account?: string | null) => {
  const normalizedAccount = normalizeKeyPart(account);
  if (!canUseStorage() || !normalizedAccount) {
    return;
  }

  localStorage.setItem(getPendingAccountKey(normalizedAccount), '1');
};

export const shouldShowAssessmentOnboardingPrompt = (
  user: Pick<UserInfo, 'id' | 'account' | 'user_type'> | null | undefined,
  options: {
    needsAssessment: boolean;
    completedDebates?: number | null;
  }
) => {
  if (
    !canUseStorage() ||
    !user ||
    user.user_type !== 'student' ||
    !user.id ||
    !options.needsAssessment ||
    (options.completedDebates || 0) > 0
  ) {
    return false;
  }

  const consumedKey = getConsumedUserKey(user.id);
  if (localStorage.getItem(consumedKey) === '1') {
    return false;
  }

  const pendingUserKey = getPendingUserKey(user.id);
  if (localStorage.getItem(pendingUserKey) === '1') {
    return true;
  }

  const normalizedAccount = normalizeKeyPart(user.account);
  if (!normalizedAccount) {
    return false;
  }

  const pendingAccountKey = getPendingAccountKey(normalizedAccount);
  if (localStorage.getItem(pendingAccountKey) !== '1') {
    return false;
  }

  localStorage.setItem(pendingUserKey, '1');
  localStorage.removeItem(pendingAccountKey);
  return true;
};

export const consumeAssessmentOnboardingPrompt = (
  user: Pick<UserInfo, 'id' | 'account'> | null | undefined
) => {
  if (!canUseStorage() || !user?.id) {
    return;
  }

  localStorage.setItem(getConsumedUserKey(user.id), '1');
  localStorage.removeItem(getPendingUserKey(user.id));

  const normalizedAccount = normalizeKeyPart(user.account);
  if (normalizedAccount) {
    localStorage.removeItem(getPendingAccountKey(normalizedAccount));
  }
};
