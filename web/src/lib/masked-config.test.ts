import { describe, expect, it } from 'vitest';
import {
  getMaskedSecretDisplay,
  hasConfiguredSecret,
  normalizeSecretUpdate,
} from './masked-config';

describe('masked configuration helpers', () => {
  it('shows only masked/configured state', () => {
    expect(getMaskedSecretDisplay(true, 'sk-****1234')).toBe('sk-****1234');
    expect(getMaskedSecretDisplay(true, null)).toBe('已配置');
    expect(getMaskedSecretDisplay(false, null)).toBe('未配置');
    expect(hasConfiguredSecret(false, 'pat_****')).toBe(true);
  });

  it('omits blank secret updates so an existing secret is preserved', () => {
    expect(normalizeSecretUpdate('')).toBeUndefined();
    expect(normalizeSecretUpdate('   ')).toBeUndefined();
    expect(normalizeSecretUpdate('  new-secret  ')).toBe('new-secret');
  });
});
