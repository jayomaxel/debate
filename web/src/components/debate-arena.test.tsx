import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react';
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
const pcmPlayerInstances: MockPcmStreamPlayer[] = [];

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
  default: () => <div data-testid="debate-audio-control" />,
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

    constructor() {
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
});
