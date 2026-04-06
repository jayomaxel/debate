import { audioPlaybackDebug } from './utils';

interface StreamChunkPayload {
  audioBase64: string;
  sampleRate?: number;
  channels?: number;
  sampleWidth?: number;
}

interface PcmStreamPlayerOptions {
  onPlaybackStateChange?: (isPlaying: boolean) => void;
}

interface PendingStreamState {
  streamId: string;
  chunks: StreamChunkPayload[];
  hasStarted: boolean;
  hasEnded: boolean;
  chunkCount: number;
}

/**
 * 轻量PCM流播放器。
 * 后端通过 websocket 持续推送 pcm_s16le 分块，前端收到后按时间轴串行调度播放。
 * 如果新的语音流在上一条尚未播完时到达，会先进等待队列，避免后来的语音直接截断前一条。
 */
export class PcmStreamPlayer {
  private audioContext: AudioContext | null = null;
  private nextPlaybackTime = 0;
  private activeStreamId: string | null = null;
  private scheduledNodes = new Set<AudioBufferSourceNode>();
  private releaseTimer: number | null = null;
  private readonly onPlaybackStateChange?: (isPlaying: boolean) => void;
  private streamChunkCount = 0;
  private pendingStreams = new Map<string, PendingStreamState>();
  private pendingStreamQueue: string[] = [];

  constructor(options: PcmStreamPlayerOptions = {}) {
    this.onPlaybackStateChange = options.onPlaybackStateChange;
  }

  private async ensureAudioContext(): Promise<AudioContext> {
    if (!this.audioContext) {
      this.audioContext = new AudioContext();
    }

    if (this.audioContext.state === 'suspended') {
      try {
        await this.audioContext.resume();
      } catch {
        // 浏览器若阻止自动播放，这里保持静默，等用户交互后再恢复。
      }
    }

    return this.audioContext;
  }

  private getOrCreatePendingStream(streamId: string): PendingStreamState {
    const existingState = this.pendingStreams.get(streamId);
    if (existingState) {
      return existingState;
    }

    const newState: PendingStreamState = {
      streamId,
      chunks: [],
      hasStarted: false,
      hasEnded: false,
      chunkCount: 0,
    };
    this.pendingStreams.set(streamId, newState);
    return newState;
  }

  private enqueuePendingStream(streamId: string): void {
    if (this.pendingStreamQueue.includes(streamId)) {
      return;
    }
    this.pendingStreamQueue.push(streamId);
  }

  private async activateNextQueuedStream(): Promise<void> {
    if (this.activeStreamId) {
      return;
    }

    const nextStreamId = this.pendingStreamQueue.shift();
    if (!nextStreamId) {
      this.onPlaybackStateChange?.(false);
      return;
    }

    const nextStream = this.pendingStreams.get(nextStreamId);
    if (!nextStream || !nextStream.hasStarted) {
      // 队列里若混入了未正式开始的流，直接跳过并尝试下一条，避免卡死。
      this.pendingStreams.delete(nextStreamId);
      await this.activateNextQueuedStream();
      return;
    }

    const context = await this.ensureAudioContext();
    this.activeStreamId = nextStreamId;
    this.streamChunkCount = nextStream.chunkCount;
    this.nextPlaybackTime = context.currentTime + 0.05;
    this.clearReleaseTimer();
    audioPlaybackDebug('PcmStreamPlayer', '开始播放新的流式 TTS', {
      streamId: nextStreamId,
      currentTime: Number(context.currentTime.toFixed(3)),
      nextPlaybackTime: Number(this.nextPlaybackTime.toFixed(3)),
      bufferedChunkCount: nextStream.chunks.length,
      queuedStreamCount: this.pendingStreamQueue.length,
    });
    this.onPlaybackStateChange?.(true);

    // 队列里的 chunk 需要按原顺序补排到时间轴里，保证晚到的下一条语音不会插播。
    for (const chunk of nextStream.chunks) {
      await this.scheduleChunk(nextStream, chunk, context);
    }
    nextStream.chunks = [];

    if (nextStream.hasEnded) {
      this.scheduleActiveStreamCompletion(nextStreamId, context);
    }
  }

  private async scheduleChunk(
    streamState: PendingStreamState,
    payload: StreamChunkPayload,
    existingContext?: AudioContext
  ): Promise<void> {
    const context = existingContext || await this.ensureAudioContext();
    const channels = Math.max(1, payload.channels || 1);
    const sampleRate = payload.sampleRate || 24000;
    const pcm = this.decodeBase64ToBytes(payload.audioBase64);
    const floatChannelData = this.decodePcm16ToFloat32Channels(pcm, channels);
    const frameCount = floatChannelData[0]?.length || 0;
    if (frameCount === 0) return;

    streamState.chunkCount += 1;
    this.streamChunkCount = streamState.chunkCount;

    const audioBuffer = context.createBuffer(channels, frameCount, sampleRate);
    for (let index = 0; index < channels; index += 1) {
      audioBuffer.getChannelData(index).set(floatChannelData[index]);
    }

    const source = context.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(context.destination);

    const startAt = Math.max(context.currentTime + 0.02, this.nextPlaybackTime);
    source.onended = () => {
      this.scheduledNodes.delete(source);
    };
    source.start(startAt);
    this.scheduledNodes.add(source);
    this.nextPlaybackTime = startAt + audioBuffer.duration;
    this.clearReleaseTimer();
    audioPlaybackDebug('PcmStreamPlayer', '追加 PCM chunk 到播放时间轴', {
      streamId: streamState.streamId,
      chunkIndex: streamState.chunkCount,
      frameCount,
      duration: Number(audioBuffer.duration.toFixed(3)),
      startAt: Number(startAt.toFixed(3)),
      nextPlaybackTime: Number(this.nextPlaybackTime.toFixed(3)),
      scheduledNodeCount: this.scheduledNodes.size,
    });
  }

  private scheduleActiveStreamCompletion(streamId: string, existingContext?: AudioContext): void {
    if (!streamId || this.activeStreamId !== streamId) {
      return;
    }

    const context = existingContext || this.audioContext;
    if (!context) {
      return;
    }

    const tailMs = Math.max(0, Math.ceil((this.nextPlaybackTime - context.currentTime) * 1000));
    this.clearReleaseTimer();
    audioPlaybackDebug('PcmStreamPlayer', '收到流结束事件，等待尾音播放完成', {
      streamId,
      chunkCount: this.streamChunkCount,
      tailMs,
      currentTime: Number(context.currentTime.toFixed(3)),
      nextPlaybackTime: Number(this.nextPlaybackTime.toFixed(3)),
      queuedStreamCount: this.pendingStreamQueue.length,
    });
    this.releaseTimer = window.setTimeout(() => {
      if (this.activeStreamId !== streamId) {
        return;
      }

      this.pendingStreams.delete(streamId);
      this.activeStreamId = null;
      this.nextPlaybackTime = 0;
      this.streamChunkCount = 0;
      audioPlaybackDebug('PcmStreamPlayer', '流式 TTS 已完全播放结束', {
        streamId,
        queuedStreamCount: this.pendingStreamQueue.length,
      });

      if (this.pendingStreamQueue.length > 0) {
        void this.activateNextQueuedStream();
        return;
      }

      this.onPlaybackStateChange?.(false);
    }, tailMs + 60);
  }

  async startStream(streamId: string): Promise<void> {
    if (!streamId) return;

    const streamState = this.getOrCreatePendingStream(streamId);

    // 同一条流重复收到 start 事件时直接忽略，避免重复入队。
    if (streamState.hasStarted) {
      audioPlaybackDebug('PcmStreamPlayer', '重复收到同一条流的 start 事件', {
        streamId,
        isActiveStream: this.activeStreamId === streamId,
        queuedStreamCount: this.pendingStreamQueue.length,
        scheduledNodeCount: this.scheduledNodes.size,
      });
      if (this.activeStreamId === streamId) {
        this.clearReleaseTimer();
        this.onPlaybackStateChange?.(true);
      }
      return;
    }

    streamState.hasStarted = true;
    if (this.activeStreamId && this.activeStreamId !== streamId) {
      // 上一条还没播完时，后一条只排队不打断，确保 AI 团队语音严格按顺序播放。
      this.enqueuePendingStream(streamId);
      audioPlaybackDebug('PcmStreamPlayer', '新流进入等待队列，等待上一条播放完成', {
        activeStreamId: this.activeStreamId,
        streamId,
        queuedStreamCount: this.pendingStreamQueue.length,
      });
      return;
    }

    this.enqueuePendingStream(streamId);
    await this.activateNextQueuedStream();
  }

  async appendChunk(streamId: string, payload: StreamChunkPayload): Promise<void> {
    if (!streamId || !payload.audioBase64) return;
    const streamState = this.getOrCreatePendingStream(streamId);
    if (this.activeStreamId !== streamId) {
      // 非当前活动流的 chunk 先缓存，等轮到该流播放时再统一调度。
      streamState.chunks.push(payload);
      audioPlaybackDebug('PcmStreamPlayer', '缓存尚未轮到播放的 PCM chunk', {
        streamId,
        activeStreamId: this.activeStreamId,
        bufferedChunkCount: streamState.chunks.length,
      });
      return;
    }

    await this.scheduleChunk(streamState, payload);
  }

  async endStream(streamId: string): Promise<void> {
    if (!streamId) return;

    const streamState = this.getOrCreatePendingStream(streamId);
    streamState.hasEnded = true;

    if (this.activeStreamId !== streamId) {
      audioPlaybackDebug('PcmStreamPlayer', '收到排队中流的结束事件，等待后续轮到播放', {
        streamId,
        activeStreamId: this.activeStreamId,
        bufferedChunkCount: streamState.chunks.length,
      });
      return;
    }

    const context = await this.ensureAudioContext();
    this.scheduleActiveStreamCompletion(streamId, context);
  }

  stop(): void {
    audioPlaybackDebug('PcmStreamPlayer', '停止当前流式 TTS', {
      activeStreamId: this.activeStreamId,
      scheduledNodeCount: this.scheduledNodes.size,
      chunkCount: this.streamChunkCount,
      queuedStreamCount: this.pendingStreamQueue.length,
    });
    this.clearReleaseTimer();
    this.scheduledNodes.forEach((node) => {
      try {
        node.stop();
      } catch {
        // 节点可能已经结束，忽略 stop 异常。
      }
    });
    this.scheduledNodes.clear();
    this.activeStreamId = null;
    this.nextPlaybackTime = 0;
    this.streamChunkCount = 0;
    this.pendingStreams.clear();
    this.pendingStreamQueue = [];
    this.onPlaybackStateChange?.(false);
  }

  dispose(): void {
    audioPlaybackDebug('PcmStreamPlayer', '销毁流式 TTS 播放器');
    this.stop();
    if (this.audioContext) {
      const currentContext = this.audioContext;
      this.audioContext = null;
      void currentContext.close().catch(() => {});
    }
  }

  private clearReleaseTimer(): void {
    if (this.releaseTimer !== null) {
      window.clearTimeout(this.releaseTimer);
      this.releaseTimer = null;
    }
  }

  private decodeBase64ToBytes(audioBase64: string): Uint8Array {
    const binary = window.atob(audioBase64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
  }

  private decodePcm16ToFloat32Channels(bytes: Uint8Array, channels: number): Float32Array[] {
    const frameCount = Math.floor(bytes.length / 2 / channels);
    const channelData = Array.from({ length: channels }, () => new Float32Array(frameCount));
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);

    for (let frame = 0; frame < frameCount; frame += 1) {
      for (let channel = 0; channel < channels; channel += 1) {
        const offset = (frame * channels + channel) * 2;
        const sample = view.getInt16(offset, true);
        channelData[channel][frame] = sample / 0x8000;
      }
    }

    return channelData;
  }
}

export default PcmStreamPlayer;
