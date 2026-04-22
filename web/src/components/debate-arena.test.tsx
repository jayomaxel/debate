import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DebateArena from './debate-arena';
import { useWebSocket } from '@/hooks/use-websocket';
import { useAuth } from '@/store/auth.context';
import { useToast } from '@/hooks/use-toast';
import StudentService from '@/services/student.service';

const websocketOnMock = vi.fn();
const websocketOffMock = vi.fn();
const websocketSendMock = vi.fn();
const toastMock = vi.fn();
const debateControlsPropsSpy = vi.fn();
const debateAudioControlPropsSpy = vi.fn();
const pcmPlayerInstances: MockPcmStreamPlayer[] = [];
type MockPcmPlayerOptions = {
  onPlaybackStateChange?: (isPlaying: boolean) => void;
  onStreamPlaybackStart?: (speechId: string) => void;
  onStreamPlaybackComplete?: (speechId: string) => void;
};

vi.mock('./debate-header', () => ({
  default: () => <div data-testid="debate-header" />,
}));

vi.mock('./participant-video', () => ({
  default: () => <div data-testid="participant-video" />,
}));

vi.mock('./ai-avatar', () => ({
  default: () => <div data-testid="ai-avatar" />,
}));

vi.mock('./debate-controls', () => ({
  default: (props: any) => {
    debateControlsPropsSpy(props);
    return (
      <button
        data-testid="debate-controls"
        onClick={() => props.onAutoPlayEnabledChange?.(!props.autoPlayEnabled)}
      >
        {String(props.autoPlayEnabled)}
      </button>
    );
  },
}));

vi.mock('./debate-audio-control', () => ({
  default: (props: any) => {
    debateAudioControlPropsSpy(props);
    return <div data-testid="debate-audio-control" />;
  },
}));

vi.mock('@/hooks/use-websocket', () => ({
  useWebSocket: vi.fn(),
}));

vi.mock('@/store/auth.context', () => ({
  useAuth: vi.fn(),
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: vi.fn(),
}));

vi.mock('@/services/student.service', () => ({
  default: {
    getDebateParticipants: vi.fn(),
  },
}));

vi.mock('@/lib/pcm-stream-player', () => ({
  default: class MockPcmStreamPlayer {
    startStream = vi.fn();
    appendChunk = vi.fn();
    endStream = vi.fn();
    stop = vi.fn();
    dispose = vi.fn();
    onPlaybackStateChange?: (isPlaying: boolean) => void;
    onStreamPlaybackStart?: (speechId: string) => void;
    onStreamPlaybackComplete?: (speechId: string) => void;

    constructor(options: MockPcmPlayerOptions = {}) {
      this.onPlaybackStateChange = options.onPlaybackStateChange;
      this.onStreamPlaybackStart = options.onStreamPlaybackStart;
      this.onStreamPlaybackComplete = options.onStreamPlaybackComplete;
      pcmPlayerInstances.push(this);
    }
  },
}));

class MockPcmStreamPlayer {
  startStream = vi.fn();
  appendChunk = vi.fn();
  endStream = vi.fn();
  stop = vi.fn();
  dispose = vi.fn();
  onPlaybackStateChange?: (isPlaying: boolean) => void;
  onStreamPlaybackStart?: (speechId: string) => void;
  onStreamPlaybackComplete?: (speechId: string) => void;

  constructor(options: MockPcmPlayerOptions = {}) {
    this.onPlaybackStateChange = options.onPlaybackStateChange;
    this.onStreamPlaybackStart = options.onStreamPlaybackStart;
    this.onStreamPlaybackComplete = options.onStreamPlaybackComplete;
  }
}

describe('DebateArena', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pcmPlayerInstances.length = 0;

    (useWebSocket as any).mockReturnValue({
      isConnected: true,
      send: websocketSendMock,
      on: websocketOnMock,
      off: websocketOffMock,
    });

    (useAuth as any).mockReturnValue({
      user: {
        id: 'user-001',
        name: '测试学生',
      },
    });

    (useToast as any).mockReturnValue({
      toast: toastMock,
    });

    (StudentService.getDebateParticipants as any).mockResolvedValue([]);
  });

  it('should keep websocket speech listeners registered only once after internal rerenders', async () => {
    const { rerender } = render(<DebateArena roomId="room-001" onEndDebate={vi.fn()} />);

    await waitFor(() => {
      expect(StudentService.getDebateParticipants).toHaveBeenCalledWith('room-001');
    });

    const getRegisteredHandlers = (type: string) =>
      websocketOnMock.mock.calls.filter(([eventType]: [string, unknown]) => eventType === type);

    expect(getRegisteredHandlers('speech')).toHaveLength(1);
    expect(getRegisteredHandlers('tts_stream_start')).toHaveLength(1);
    expect(getRegisteredHandlers('tts_stream_chunk')).toHaveLength(1);
    expect(getRegisteredHandlers('tts_stream_end')).toHaveLength(1);

    const stateUpdateHandler = getRegisteredHandlers('state_update')[0]?.[1] as ((data: any) => void) | undefined;
    expect(stateUpdateHandler).toBeTypeOf('function');

    act(() => {
      stateUpdateHandler?.({
        current_speaker: 'ai_1',
        speaker_mode: 'free',
        participants: [
          {
            user_id: 'user-001',
            role: 'debater_1',
            name: '测试学生',
          },
        ],
      });
    });

    rerender(<DebateArena roomId="room-001" onEndDebate={vi.fn()} />);

    expect(getRegisteredHandlers('speech')).toHaveLength(1);
    expect(getRegisteredHandlers('tts_stream_start')).toHaveLength(1);
    expect(getRegisteredHandlers('tts_stream_chunk')).toHaveLength(1);
    expect(getRegisteredHandlers('tts_stream_end')).toHaveLength(1);
  });

  it('should stop live tts autoplay after the autoplay switch is turned off', async () => {
    const { getByTestId } = render(<DebateArena roomId="room-001" onEndDebate={vi.fn()} />);

    await waitFor(() => {
      expect(StudentService.getDebateParticipants).toHaveBeenCalledWith('room-001');
    });

    const getRegisteredHandler = (type: string) =>
      websocketOnMock.mock.calls.find(([eventType]: [string, unknown]) => eventType === type)?.[1] as
        | ((data: any) => void)
        | undefined;

    const startHandler = getRegisteredHandler('tts_stream_start');
    const chunkHandler = getRegisteredHandler('tts_stream_chunk');
    const endHandler = getRegisteredHandler('tts_stream_end');

    expect(startHandler).toBeTypeOf('function');
    expect(chunkHandler).toBeTypeOf('function');
    expect(endHandler).toBeTypeOf('function');
    expect(pcmPlayerInstances).toHaveLength(1);

    act(() => {
      fireEvent.click(getByTestId('debate-controls'));
    });

    await waitFor(() => {
      expect(debateControlsPropsSpy).toHaveBeenLastCalledWith(
        expect.objectContaining({
          autoPlayEnabled: false,
        })
      );
    });

    const pcmPlayer = pcmPlayerInstances[0];
    expect(pcmPlayer.stop).toHaveBeenCalledTimes(1);

    act(() => {
      startHandler?.({ speech_id: 'speech-live-001' });
      chunkHandler?.({
        speech_id: 'speech-live-001',
        audio_base64: 'AQID',
        sample_rate: 24000,
        channels: 1,
        sample_width: 2,
      });
      endHandler?.({ speech_id: 'speech-live-001' });
    });

    expect(pcmPlayer.startStream).not.toHaveBeenCalled();
    expect(pcmPlayer.appendChunk).not.toHaveBeenCalled();
    expect(pcmPlayer.endStream).not.toHaveBeenCalled();
  });

  it('should show ai turn status and block grab mic while ai is thinking in free debate', async () => {
    render(<DebateArena roomId="room-001" onEndDebate={vi.fn()} />);

    await waitFor(() => {
      expect(StudentService.getDebateParticipants).toHaveBeenCalledWith('room-001');
    });

    const stateUpdateHandler = websocketOnMock.mock.calls.find(
      ([eventType]: [string, unknown]) => eventType === 'state_update'
    )?.[1] as ((data: any) => void) | undefined;

    expect(stateUpdateHandler).toBeTypeOf('function');

    act(() => {
      stateUpdateHandler?.({
        current_phase: 'free_debate',
        speaker_mode: 'free',
        free_debate_next_side: 'ai',
        ai_turn_status: 'thinking',
        ai_turn_segment_title: '自由辩论',
        ai_turn_speaker_role: 'ai_2',
        participants: [
          {
            user_id: 'user-001',
            role: 'debater_1',
            name: '测试学生',
          },
        ],
        ai_debaters: [
          {
            id: 'ai_2',
            name: 'AI二辩',
          },
        ],
      });
    });

    expect(screen.getAllByText('AI思考中')).toHaveLength(2);
    expect(screen.getByText('AI二辩 正在基于最新发言准备回应')).toBeTruthy();

    await waitFor(() => {
      expect(debateAudioControlPropsSpy).toHaveBeenLastCalledWith(
        expect.objectContaining({
          canGrabMic: false,
          micStatusText: 'AI二辩 正在基于最新发言准备回应',
        })
      );
    });
  });

  it('should send speech playback finished event when debate controls reports ai audio completion', async () => {
    render(<DebateArena roomId="room-001" onEndDebate={vi.fn()} />);

    await waitFor(() => {
      expect(StudentService.getDebateParticipants).toHaveBeenCalledWith('room-001');
    });

    const debateControlsProps = debateControlsPropsSpy.mock.lastCall?.[0];
    expect(debateControlsProps).toBeTruthy();

    act(() => {
      debateControlsProps.onSpeechPlaybackEvent?.({
        status: 'finished',
        speechId: 'speech-ai-001',
        segmentId: 'opening_negative_1',
        speakerRole: 'ai_1',
        source: 'audio_element',
      });
    });

    expect(websocketSendMock).toHaveBeenCalledWith(
      'speech_playback_finished',
      expect.objectContaining({
        speech_id: 'speech-ai-001',
        segment_id: 'opening_negative_1',
        speaker_role: 'ai_1',
        playback_source: 'audio_element',
      })
    );
  });

  it('should send stream playback events when pcm player reports ai speech playback lifecycle', async () => {
    render(<DebateArena roomId="room-001" onEndDebate={vi.fn()} />);

    await waitFor(() => {
      expect(StudentService.getDebateParticipants).toHaveBeenCalledWith('room-001');
    });

    const speechHandler = websocketOnMock.mock.calls.find(
      ([eventType]: [string, unknown]) => eventType === 'speech'
    )?.[1] as ((data: any) => void) | undefined;

    expect(speechHandler).toBeTypeOf('function');
    expect(pcmPlayerInstances).toHaveLength(1);

    act(() => {
      speechHandler?.({
        speech_id: 'speech-ai-stream-001',
        role: 'ai_2',
        name: 'AI二辩',
        content: '这是流式 AI 发言',
        phase: 'opening',
        segment_id: 'opening_negative_1',
        segment_title: '立论阶段：反方一辩',
      });
    });

    const pcmPlayer = pcmPlayerInstances[0];
    act(() => {
      pcmPlayer.onStreamPlaybackStart?.('speech-ai-stream-001');
      pcmPlayer.onStreamPlaybackComplete?.('speech-ai-stream-001');
    });

    expect(websocketSendMock).toHaveBeenCalledWith(
      'speech_playback_started',
      expect.objectContaining({
        speech_id: 'speech-ai-stream-001',
        segment_id: 'opening_negative_1',
        speaker_role: 'ai_2',
        playback_source: 'stream',
      })
    );
    expect(websocketSendMock).toHaveBeenCalledWith(
      'speech_playback_finished',
      expect.objectContaining({
        speech_id: 'speech-ai-stream-001',
        segment_id: 'opening_negative_1',
        speaker_role: 'ai_2',
        playback_source: 'stream',
      })
    );
  });
});
