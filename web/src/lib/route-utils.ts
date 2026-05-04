import type { UserInfo } from './token-manager';

export type StudentAnalyticsTab =
  | 'history'
  | 'growth'
  | 'comparison'
  | 'achievements';

export type SettingsTab = 'info' | 'password' | 'ability';

export type PublicSection = 'home' | 'competition' | 'preparation' | 'growth';

const publicSections: PublicSection[] = [
  'home',
  'competition',
  'preparation',
  'growth',
];

const studentAnalyticsTabs: StudentAnalyticsTab[] = [
  'history',
  'growth',
  'comparison',
  'achievements',
];

const settingsTabs: SettingsTab[] = ['info', 'password', 'ability'];

export const normalizePublicSection = (value?: string | null): PublicSection =>
  publicSections.includes(value as PublicSection)
    ? (value as PublicSection)
    : 'home';

export const normalizeStudentAnalyticsTab = (
  value?: string | null
): StudentAnalyticsTab =>
  studentAnalyticsTabs.includes(value as StudentAnalyticsTab)
    ? (value as StudentAnalyticsTab)
    : 'history';

export const normalizeSettingsTab = (value?: string | null): SettingsTab =>
  settingsTabs.includes(value as SettingsTab)
    ? (value as SettingsTab)
    : 'info';

export const getDefaultHomePath = (
  userType?: UserInfo['user_type'] | null
) => {
  if (userType === 'teacher') {
    return '/teacher';
  }

  if (userType === 'administrator') {
    return '/admin';
  }

  if (userType === 'student') {
    return '/student';
  }

  return '/';
};

export const getPublicSectionPath = (section: PublicSection) =>
  section === 'home' ? '/' : `/explore/${section}`;

export const getStudentAnalyticsPath = (tab: StudentAnalyticsTab = 'history') =>
  `/student/analytics/${tab}`;

export const getStudentSettingsPath = (tab: SettingsTab = 'info') =>
  `/student/settings?tab=${tab}`;
