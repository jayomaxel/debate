import { describe, expect, it } from 'vitest';
import {
  normalizeTranscriptEntry,
  upsertTranscriptEntry,
  TRANSCRIPT_PENDING_TEXT,
} from './debate-transcript';

describe('debate-transcript', () => {
  it('should merge audio-first and text-later events into one transcript entry', () => {
    const firstEntry = normalizeTranscriptEntry({
      speech_id: 'speech-001',
      role: 'debater_1',
      name: '学生A',
      audio_url: '/uploads/audio-001.mp3',
      timestamp: '2026-03-21T10:00:00+08:00',
    });
    const mergedOnce = upsertTranscriptEntry([], firstEntry);

    expect(mergedOnce).toHaveLength(1);
    expect(mergedOnce[0].message).toBe(TRANSCRIPT_PENDING_TEXT);

    const secondEntry = normalizeTranscriptEntry({
      speech_id: 'speech-001',
      role: 'debater_1',
      name: '学生A',
      content: '这是补回来的ASR文本',
      audio_url: '/uploads/audio-001.mp3',
      timestamp: '2026-03-21T10:00:01+08:00',
    });
    const mergedTwice = upsertTranscriptEntry(mergedOnce, secondEntry);

    expect(mergedTwice).toHaveLength(1);
    expect(mergedTwice[0].message).toBe('这是补回来的ASR文本');
    expect(mergedTwice[0].audioUrl).toBe('/uploads/audio-001.mp3');
    expect(mergedTwice[0].isPendingText).toBe(false);
  });

  it('should merge text-first and audio-later events into one transcript entry', () => {
    const firstEntry = normalizeTranscriptEntry({
      speech_id: 'speech-002',
      role: 'ai_1',
      speaker_type: 'ai',
      name: 'AI一辩',
      content: '这是AI先到的文本',
      timestamp: '2026-03-21T10:05:00+08:00',
    });
    const mergedOnce = upsertTranscriptEntry([], firstEntry);

    const secondEntry = normalizeTranscriptEntry({
      speech_id: 'speech-002',
      role: 'ai_1',
      speaker_type: 'ai',
      name: 'AI一辩',
      content: '这是AI先到的文本',
      audio_url: '/uploads/ai-002.mp3',
      audio_format: 'mp3',
      timestamp: '2026-03-21T10:05:02+08:00',
    });
    const mergedTwice = upsertTranscriptEntry(mergedOnce, secondEntry);

    expect(mergedTwice).toHaveLength(1);
    expect(mergedTwice[0].message).toBe('这是AI先到的文本');
    expect(mergedTwice[0].audioUrl).toBe('/uploads/ai-002.mp3');
    expect(mergedTwice[0].isAI).toBe(true);
  });
});
