/**
 * 语音录制服务
 * 使用Web Audio API实现录音功能
 */

interface AudioRecorderOptions {
  mimeType?: string;
  audioBitsPerSecond?: number;
  sampleRate?: number;
}

class AudioRecorder {
  private audioContext: AudioContext | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private processorNode: ScriptProcessorNode | null = null;
  private silentGainNode: GainNode | null = null;
  private pcmChunks: Float32Array[] = [];
  private stream: MediaStream | null = null;
  private isRecording: boolean = false;
  private isPaused: boolean = false;
  private options: AudioRecorderOptions;
  private recordedSampleRate: number = 0;

  constructor(options: AudioRecorderOptions = {}) {
    this.options = {
      mimeType: options.mimeType || 'audio/wav',
      audioBitsPerSecond: options.audioBitsPerSecond || 128000,
      sampleRate: options.sampleRate || 16000,
    };
  }

  private getTargetSampleRate(): number {
    return Math.max(8000, Math.min(48000, Number(this.options.sampleRate || 16000)));
  }

  /**
   * 开始录音
   */
  async startRecording(): Promise<void> {
    try {
      // 请求麦克风权限
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: this.getTargetSampleRate(),
          channelCount: 1,
        },
      });

      const AudioContextCtor =
        (window as any).AudioContext || (window as any).webkitAudioContext;
      if (!AudioContextCtor) {
        throw new Error('AudioContext is not supported');
      }

      this.audioContext = new AudioContextCtor();
      this.recordedSampleRate = this.audioContext.sampleRate;

      this.sourceNode = this.audioContext.createMediaStreamSource(this.stream);
      this.processorNode = this.audioContext.createScriptProcessor(4096, 1, 1);
      this.silentGainNode = this.audioContext.createGain();
      this.silentGainNode.gain.value = 0;

      this.pcmChunks = [];
      this.isPaused = false;

      this.processorNode.onaudioprocess = (event) => {
        if (!this.isRecording || this.isPaused) return;
        const input = event.inputBuffer.getChannelData(0);
        this.pcmChunks.push(new Float32Array(input));
      };

      this.sourceNode.connect(this.processorNode);
      this.processorNode.connect(this.silentGainNode);
      this.silentGainNode.connect(this.audioContext.destination);

      this.isRecording = true;

      console.log('Recording started');
    } catch (error) {
      console.error('Failed to start recording:', error);
      throw new Error('无法访问麦克风，请检查权限设置');
    }
  }


  /**
   * 停止录音
   */
  stopRecording(): Promise<Blob> {
    return new Promise((resolve, reject) => {
      if (!this.isRecording) {
        reject(new Error('录音未开始'));
        return;
      }

      const finalize = async () => {
        try {
          const targetSampleRate = this.getTargetSampleRate();
          const merged = AudioRecorder.mergeFloat32(this.pcmChunks);
          const resampled =
            this.recordedSampleRate && this.recordedSampleRate !== targetSampleRate
              ? AudioRecorder.resampleLinear(merged, this.recordedSampleRate, targetSampleRate)
              : merged;
          const wav = AudioRecorder.encodeWavPcm16(resampled, targetSampleRate, 1);
          const audioBlob = new Blob([wav], { type: 'audio/wav' });

          if (this.processorNode) {
            this.processorNode.disconnect();
            this.processorNode.onaudioprocess = null;
            this.processorNode = null;
          }
          if (this.silentGainNode) {
            this.silentGainNode.disconnect();
            this.silentGainNode = null;
          }
          if (this.sourceNode) {
            this.sourceNode.disconnect();
            this.sourceNode = null;
          }
          if (this.audioContext) {
            await this.audioContext.close();
            this.audioContext = null;
          }

          if (this.stream) {
            this.stream.getTracks().forEach((track) => track.stop());
            this.stream = null;
          }

          this.isRecording = false;
          this.isPaused = false;
          console.log('Recording stopped');
          resolve(audioBlob);
        } catch (e) {
          reject(e);
        }
      };

      void finalize();
    });
  }

  /**
   * 暂停录音
   */
  pauseRecording(): void {
    if (!this.isRecording) return;
    this.isPaused = true;
    console.log('Recording paused');
  }

  /**
   * 恢复录音
   */
  resumeRecording(): void {
    if (!this.isRecording) return;
    this.isPaused = false;
    console.log('Recording resumed');
  }

  /**
   * 获取录音Blob
   */
  async getAudioBlob(): Promise<Blob> {
    if (this.isRecording) {
      return this.stopRecording();
    }

    if (this.pcmChunks.length === 0) {
      throw new Error('没有录音数据');
    }

    const targetSampleRate = this.getTargetSampleRate();
    const merged = AudioRecorder.mergeFloat32(this.pcmChunks);
    const resampled =
      this.recordedSampleRate && this.recordedSampleRate !== targetSampleRate
        ? AudioRecorder.resampleLinear(merged, this.recordedSampleRate, targetSampleRate)
        : merged;
    const wav = AudioRecorder.encodeWavPcm16(resampled, targetSampleRate, 1);
    return new Blob([wav], { type: 'audio/wav' });
  }

  /**
   * 获取录音Base64编码
   */
  async getAudioBase64(): Promise<string> {
    const blob = await this.getAudioBlob();
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64 = reader.result as string;
        const base64Data = base64.split(',')[1];
        resolve(base64Data);
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  /**
   * 获取录音时长（秒）
   */
  getRecordingDuration(): number {
    const targetSampleRate = this.getTargetSampleRate();
    if (this.pcmChunks.length === 0) return 0;
    const totalSamples = this.pcmChunks.reduce((sum, chunk) => sum + chunk.length, 0);
    const sampleRateForDuration = this.recordedSampleRate || targetSampleRate;
    return totalSamples / sampleRateForDuration;
  }

  /**
   * 检查是否正在录音
   */
  isRecordingActive(): boolean {
    return this.isRecording;
  }

  /**
   * 检查浏览器是否支持录音
   */
  static isSupported(): boolean {
    return !!(
      navigator.mediaDevices &&
      typeof navigator.mediaDevices.getUserMedia === 'function' &&
      (typeof (window as any).AudioContext !== 'undefined' ||
        typeof (window as any).webkitAudioContext !== 'undefined')
    );
  }

  /**
   * 请求麦克风权限
   */
  static async requestPermission(): Promise<boolean> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      return true;
    } catch (error) {
      console.error('Microphone permission denied:', error);
      return false;
    }
  }

  /**
   * 获取可用的音频输入设备
   */
  static async getAudioDevices(): Promise<MediaDeviceInfo[]> {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      return devices.filter((device) => device.kind === 'audioinput');
    } catch (error) {
      console.error('Failed to get audio devices:', error);
      return [];
    }
  }

  private static mergeFloat32(chunks: Float32Array[]): Float32Array {
    const totalLength = chunks.reduce((sum, c) => sum + c.length, 0);
    const merged = new Float32Array(totalLength);
    let offset = 0;
    for (const c of chunks) {
      merged.set(c, offset);
      offset += c.length;
    }
    return merged;
  }

  private static resampleLinear(
    input: Float32Array,
    inputSampleRate: number,
    outputSampleRate: number
  ): Float32Array {
    if (inputSampleRate === outputSampleRate) return input;
    if (input.length === 0) return new Float32Array(0);
    const ratio = inputSampleRate / outputSampleRate;
    const outputLength = Math.max(1, Math.floor(input.length / ratio));
    const output = new Float32Array(outputLength);
    for (let i = 0; i < outputLength; i++) {
      const pos = i * ratio;
      const idx = Math.floor(pos);
      const frac = pos - idx;
      const v0 = input[idx] || 0;
      const v1 = input[Math.min(idx + 1, input.length - 1)] || 0;
      output[i] = v0 + (v1 - v0) * frac;
    }
    return output;
  }

  private static floatToPcm16(input: Float32Array): Int16Array {
    const output = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, input[i] || 0));
      output[i] = s < 0 ? Math.round(s * 0x8000) : Math.round(s * 0x7fff);
    }
    return output;
  }

  private static encodeWavPcm16(
    floatSamples: Float32Array,
    sampleRate: number,
    channels: number
  ): ArrayBuffer {
    const pcm = AudioRecorder.floatToPcm16(floatSamples);
    const bytesPerSample = 2;
    const blockAlign = channels * bytesPerSample;
    const byteRate = sampleRate * blockAlign;
    const dataSize = pcm.length * bytesPerSample;
    const buffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(buffer);

    const writeString = (offset: number, str: string) => {
      for (let i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
      }
    };

    writeString(0, 'RIFF');
    view.setUint32(4, 36 + dataSize, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, channels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, 16, true);
    writeString(36, 'data');
    view.setUint32(40, dataSize, true);

    let offset = 44;
    for (let i = 0; i < pcm.length; i++, offset += 2) {
      view.setInt16(offset, pcm[i], true);
    }

    return buffer;
  }
}

export default AudioRecorder;
export type { AudioRecorderOptions };
