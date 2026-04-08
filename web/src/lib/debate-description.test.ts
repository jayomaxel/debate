import { describe, expect, it } from 'vitest';
import {
  buildDebateDescription,
  parseDebateDescription,
} from './debate-description';

describe('debate-description', () => {
  it('builds and parses labeled metadata', () => {
    const description = buildDebateDescription(
      '3',
      '情感计算、自然语言处理, AI伦理'
    );
    const parsed = parseDebateDescription(description);

    expect(description).toContain('发言轮次：3轮');
    expect(description).toContain('支撑知识点：情感计算、自然语言处理、AI伦理');
    expect(parsed.rounds).toBe('3');
    expect(parsed.roundsInfo).toBe('发言轮次：3轮');
    expect(parsed.knowledgePoints).toEqual([
      '情感计算',
      '自然语言处理',
      'AI伦理',
    ]);
    expect(parsed.knowledgePointsText).toBe('情感计算、自然语言处理、AI伦理');
    expect(parsed.hasStructuredMeta).toBe(true);
  });

  it('keeps plain text descriptions as raw text', () => {
    const parsed = parseDebateDescription('请围绕该辩题准备论据与反驳点。');

    expect(parsed.raw).toBe('请围绕该辩题准备论据与反驳点。');
    expect(parsed.rounds).toBe('');
    expect(parsed.knowledgePoints).toEqual([]);
    expect(parsed.hasStructuredMeta).toBe(false);
  });

  it('parses json metadata when present', () => {
    const parsed = parseDebateDescription(
      JSON.stringify({
        rounds: 4,
        knowledgePoints: ['区块链', '监管政策'],
        summary: '课堂辩论准备说明',
      })
    );

    expect(parsed.raw).toBe('课堂辩论准备说明');
    expect(parsed.rounds).toBe('4');
    expect(parsed.knowledgePoints).toEqual(['区块链', '监管政策']);
    expect(parsed.hasStructuredMeta).toBe(true);
  });
});
