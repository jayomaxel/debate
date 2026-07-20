import { describe, expect, it } from 'vitest';
import { toAuthStateShape, toReportViewModel } from './frontend-adapters';

describe('frontend adapters', () => {
  it('normalizes an incomplete report into a stable page model', () => {
    const source = {
      debate_id: 'debate-1',
      topic: null,
      participants: [
        {
          user_id: 'user-1',
          name: '学生甲',
          final_score: { overall_score: Number.NaN, speech_count: 2 },
        },
      ],
      speeches: [
        {
          id: 'speech-1',
          content: '论点内容',
          score: { logic_score: 82, feedback: '结构清晰' },
        },
      ],
    };

    const result = toReportViewModel(source);

    expect(result).not.toBe(source);
    expect(result.topic).toBe('未命名辩题');
    expect(result.participants[0].role).toBe('unknown');
    expect(result.participants[0].final_score.overall_score).toBe(0);
    expect(result.participants[0].final_score.speech_count).toBe(2);
    expect(result.speeches[0].phase).toBe('unknown');
    expect(result.speeches[0].score?.logic_score).toBe(82);
    expect(result.speeches[0].score?.feedback).toBe('结构清晰');
  });

  it('maps auth inputs to the five explicit frontend states', () => {
    const user = { id: 'user-1' };

    expect(toAuthStateShape({ status: 'initializing' })).toMatchObject({
      status: 'initializing',
      loading: true,
      isAuthenticated: false,
    });
    expect(toAuthStateShape({ isAuthenticated: true, user })).toMatchObject({
      status: 'authenticated',
      loading: false,
      isAuthenticated: true,
      user,
    });
    expect(toAuthStateShape({ status: 'anonymous', user })).toMatchObject({
      status: 'anonymous',
      user: null,
    });
    expect(toAuthStateShape({ status: 'authenticated' })).toMatchObject({
      status: 'anonymous',
      isAuthenticated: false,
      user: null,
    });
    expect(toAuthStateShape({ expired: true, user })).toMatchObject({
      status: 'expired',
      user: null,
    });
    expect(toAuthStateShape({ error: '网络错误' })).toMatchObject({
      status: 'error',
      error: '网络错误',
    });
  });
});
