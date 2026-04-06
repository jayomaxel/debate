import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DebateControls from './debate-controls';
import type { TranscriptEntry } from '@/lib/debate-transcript';

describe('DebateControls', () => {
  beforeEach(() => {
    const playMock = vi.fn().mockResolvedValue(undefined);
    const pauseMock = vi.fn();
    const loadMock = vi.fn();

    Object.defineProperty(HTMLMediaElement.prototype, 'play', {
      configurable: true,
      value: playMock,
    });
    Object.defineProperty(HTMLMediaElement.prototype, 'pause', {
      configurable: true,
      value: pauseMock,
    });
    Object.defineProperty(HTMLMediaElement.prototype, 'load', {
      configurable: true,
      value: loadMock,
    });
  });

  it('should autoplay audio entries one by one', async () => {
    const transcript: TranscriptEntry[] = [
      {
        id: 'speech-001',
        speaker: '学生A',
        position: '一辩',
        message: '第一段语音',
        timestamp: new Date('2026-03-21T10:00:00+08:00'),
        audioUrl: '/uploads/audio-001.mp3',
        audioSourceUrl: '/uploads/audio-001.mp3',
        audioFormat: 'mp3',
      },
      {
        id: 'speech-002',
        speaker: 'AI一辩',
        position: '一辩',
        message: '第二段语音',
        timestamp: new Date('2026-03-21T10:00:02+08:00'),
        audioUrl: '/uploads/audio-002.mp3',
        audioSourceUrl: '/uploads/audio-002.mp3',
        audioFormat: 'mp3',
        isAI: true,
      },
    ];

    const { container } = render(
      <DebateControls canSpeak={false} transcript={transcript} showInput={false} />
    );

    const hiddenAutoPlayer = container.querySelector('audio.hidden') as HTMLAudioElement | null;
    expect(hiddenAutoPlayer).not.toBeNull();

    await waitFor(() => {
      expect(hiddenAutoPlayer?.src).toContain('/uploads/audio-001.mp3');
    });

    act(() => {
      fireEvent.ended(hiddenAutoPlayer as HTMLAudioElement);
    });

    await waitFor(() => {
      expect(hiddenAutoPlayer?.src).toContain('/uploads/audio-002.mp3');
    });
  });

  it('should pause queued autoplay while external playback lock is active', async () => {
    const transcript: TranscriptEntry[] = [
      {
        id: 'speech-locked-001',
        speaker: 'AI一辩',
        position: '一辩',
        message: '流式播报测试',
        timestamp: new Date('2026-03-21T10:00:00+08:00'),
        audioUrl: '/uploads/audio-locked-001.mp3',
        audioSourceUrl: '/uploads/audio-locked-001.mp3',
        audioFormat: 'mp3',
        isAI: true,
      },
    ];

    const pauseSpy = vi.spyOn(HTMLMediaElement.prototype, 'pause');
    const { container } = render(
      <DebateControls
        canSpeak={false}
        transcript={transcript}
        showInput={false}
        externalPlaybackLock
      />
    );

    const hiddenAutoPlayer = container.querySelector('audio.hidden') as HTMLAudioElement | null;
    expect(hiddenAutoPlayer).not.toBeNull();

    await waitFor(() => {
      expect(pauseSpy).toHaveBeenCalled();
    });

    expect(hiddenAutoPlayer?.getAttribute('src')).toBeNull();
  });

  it('should not autoplay final audio for entries already played via live stream', async () => {
    const playSpy = vi.spyOn(HTMLMediaElement.prototype, 'play');
    const transcript: TranscriptEntry[] = [
      {
        id: 'speech-streamed-001',
        speaker: 'AI一辩',
        position: '一辩',
        message: '这是一段已经流式播报过的语音',
        timestamp: new Date('2026-03-21T10:00:00+08:00'),
        audioUrl: '/uploads/audio-streamed-001.mp3',
        audioSourceUrl: '/uploads/audio-streamed-001.mp3',
        audioFormat: 'mp3',
        isAI: true,
      },
    ];

    const { container } = render(
      <DebateControls
        canSpeak={false}
        transcript={transcript}
        showInput={false}
        suppressAutoPlayEntryIds={['speech-streamed-001']}
      />
    );

    const hiddenAutoPlayer = container.querySelector('audio.hidden') as HTMLAudioElement | null;
    expect(hiddenAutoPlayer).not.toBeNull();

    await waitFor(() => {
      expect(playSpy).not.toHaveBeenCalled();
    });

    expect(hiddenAutoPlayer?.getAttribute('src')).toBeNull();
  });

  it('should pause autoplay and other visible audio when user manually plays another audio', async () => {
    const transcript: TranscriptEntry[] = [
      {
        id: 'speech-manual-001',
        speaker: '学生A',
        position: '一辩',
        message: '第一段语音',
        timestamp: new Date('2026-03-21T10:00:00+08:00'),
        audioUrl: '/uploads/manual-001.mp3',
        audioSourceUrl: '/uploads/manual-001.mp3',
        audioFormat: 'mp3',
      },
      {
        id: 'speech-manual-002',
        speaker: '学生B',
        position: '二辩',
        message: '第二段语音',
        timestamp: new Date('2026-03-21T10:00:02+08:00'),
        audioUrl: '/uploads/manual-002.mp3',
        audioSourceUrl: '/uploads/manual-002.mp3',
        audioFormat: 'mp3',
      },
    ];

    const { container } = render(
      <DebateControls canSpeak={false} transcript={transcript} showInput={false} />
    );

    const hiddenAutoPlayer = container.querySelector('audio.hidden') as HTMLAudioElement | null;
    const visibleAudios = Array.from(container.querySelectorAll('audio:not(.hidden)')) as HTMLAudioElement[];
    expect(hiddenAutoPlayer).not.toBeNull();
    expect(visibleAudios).toHaveLength(2);

    await waitFor(() => {
      expect(hiddenAutoPlayer?.src).toContain('/uploads/manual-001.mp3');
    });

    const hiddenPauseSpy = vi.fn();
    const firstVisiblePauseSpy = vi.fn();
    const secondVisiblePauseSpy = vi.fn();

    Object.defineProperty(hiddenAutoPlayer as HTMLAudioElement, 'paused', {
      configurable: true,
      value: false,
    });
    Object.defineProperty(visibleAudios[0], 'paused', {
      configurable: true,
      value: false,
    });
    Object.defineProperty(visibleAudios[1], 'paused', {
      configurable: true,
      value: false,
    });

    Object.defineProperty(hiddenAutoPlayer as HTMLAudioElement, 'pause', {
      configurable: true,
      value: hiddenPauseSpy,
    });
    Object.defineProperty(visibleAudios[0], 'pause', {
      configurable: true,
      value: firstVisiblePauseSpy,
    });
    Object.defineProperty(visibleAudios[1], 'pause', {
      configurable: true,
      value: secondVisiblePauseSpy,
    });

    act(() => {
      fireEvent.play(visibleAudios[1]);
    });

    expect(hiddenPauseSpy).toHaveBeenCalledTimes(1);
    expect(firstVisiblePauseSpy).toHaveBeenCalledTimes(1);
    expect(secondVisiblePauseSpy).not.toHaveBeenCalled();
  });

  it('should keep unplayed queued audio available after toggling autoplay off and on', async () => {
    const transcript: TranscriptEntry[] = [
      {
        id: 'speech-toggle-001',
        speaker: '学生A',
        position: '一辩',
        message: '第一段语音',
        timestamp: new Date('2026-03-21T10:00:00+08:00'),
        audioUrl: '/uploads/toggle-001.mp3',
        audioSourceUrl: '/uploads/toggle-001.mp3',
        audioFormat: 'mp3',
      },
      {
        id: 'speech-toggle-002',
        speaker: '学生B',
        position: '二辩',
        message: '第二段语音',
        timestamp: new Date('2026-03-21T10:00:02+08:00'),
        audioUrl: '/uploads/toggle-002.mp3',
        audioSourceUrl: '/uploads/toggle-002.mp3',
        audioFormat: 'mp3',
      },
    ];

    const { container, getByRole } = render(
      <DebateControls canSpeak={false} transcript={transcript} showInput={false} />
    );

    const hiddenAutoPlayer = container.querySelector('audio.hidden') as HTMLAudioElement | null;
    expect(hiddenAutoPlayer).not.toBeNull();

    await waitFor(() => {
      expect(hiddenAutoPlayer?.src).toContain('/uploads/toggle-001.mp3');
    });

    const toggleButton = getByRole('button', { name: /自动播放/i });

    act(() => {
      fireEvent.click(toggleButton);
    });

    await waitFor(() => {
      expect(hiddenAutoPlayer?.getAttribute('src')).toBeNull();
    });

    act(() => {
      fireEvent.click(toggleButton);
    });

    await waitFor(() => {
      expect(hiddenAutoPlayer?.src).toContain('/uploads/toggle-002.mp3');
    });
  });
});
