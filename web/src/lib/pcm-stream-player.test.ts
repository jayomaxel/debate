import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PcmStreamPlayer } from './pcm-stream-player';

class MockAudioBuffer {
  public readonly duration: number;
  private readonly channels: Float32Array[];

  constructor(
    channelCount: number,
    frameCount: number,
    sampleRate: number,
  ) {
    this.duration = frameCount / sampleRate;
    this.channels = Array.from({ length: channelCount }, () => new Float32Array(frameCount));
  }

  getChannelData(index: number): Float32Array {
    return this.channels[index];
  }
}

class MockAudioBufferSourceNode {
  public buffer: MockAudioBuffer | null = null;
  public onended: (() => void) | null = null;
  public readonly start = vi.fn();
  public readonly stop = vi.fn(() => {
    this.onended?.();
  });

  connect(): void {
    // 测试里不需要真实音频输出，只保留空实现即可。
  }
}

class MockAudioContext {
  public state: AudioContextState = 'running';
  public destination = {};
  public currentTime = 0;
  public readonly createdSources: MockAudioBufferSourceNode[] = [];

  async resume(): Promise<void> {
    this.state = 'running';
  }

  createBuffer(channelCount: number, frameCount: number, sampleRate: number): MockAudioBuffer {
    return new MockAudioBuffer(channelCount, frameCount, sampleRate);
  }

  createBufferSource(): MockAudioBufferSourceNode {
    const source = new MockAudioBufferSourceNode();
    this.createdSources.push(source);
    return source;
  }

  async close(): Promise<void> {}
}

describe('PcmStreamPlayer', () => {
  const originalAudioContext = globalThis.AudioContext;
  let mockContext: MockAudioContext;

  beforeEach(() => {
    vi.useFakeTimers();
    mockContext = new MockAudioContext();
    const MockAudioContextConstructor = function MockAudioContextConstructor() {
      return mockContext;
    };
    (globalThis as typeof globalThis & { AudioContext: typeof AudioContext }).AudioContext =
      MockAudioContextConstructor as unknown as typeof AudioContext;
  });

  afterEach(() => {
    vi.useRealTimers();
    (globalThis as typeof globalThis & { AudioContext: typeof AudioContext }).AudioContext = originalAudioContext;
  });

  it('should queue later streams instead of interrupting the current one', async () => {
    const playbackStateChanges: boolean[] = [];
    const player = new PcmStreamPlayer({
      onPlaybackStateChange: (isPlaying) => playbackStateChanges.push(isPlaying),
    });

    const chunkPayload = {
      audioBase64: buildPcmBase64([0, 1000, -1000, 500, -500, 0, 300, -300]),
      sampleRate: 24000,
      channels: 1,
      sampleWidth: 2,
    };

    await player.startStream('speech-001');
    await player.appendChunk('speech-001', chunkPayload);

    expect(mockContext.createdSources).toHaveLength(1);
    const firstSource = mockContext.createdSources[0];

    await player.startStream('speech-002');
    await player.appendChunk('speech-002', chunkPayload);

    // 第二条流只应缓存等待，不应直接创建新的播放节点，也不应中断第一条。
    expect(mockContext.createdSources).toHaveLength(1);
    expect(firstSource.stop).not.toHaveBeenCalled();

    await player.endStream('speech-001');
    await player.endStream('speech-002');

    await vi.advanceTimersByTimeAsync(200);

    // 第一条播完之后，第二条才真正开始创建播放节点。
    expect(mockContext.createdSources).toHaveLength(2);
    expect(playbackStateChanges.filter((value) => value === false)).toHaveLength(0);

    await vi.advanceTimersByTimeAsync(200);

    expect(playbackStateChanges.at(-1)).toBe(false);
  });
});

function buildPcmBase64(samples: number[]): string {
  const bytes = new Uint8Array(samples.length * 2);
  const view = new DataView(bytes.buffer);

  // 测试里直接拼一段最小 PCM 数据，便于验证播放器的排队调度逻辑。
  samples.forEach((sample, index) => {
    view.setInt16(index * 2, sample, true);
  });

  let binary = '';
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return window.btoa(binary);
}
