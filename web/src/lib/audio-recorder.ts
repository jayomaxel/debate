interface AudioRecorderOptions {
  mimeType?: string;
  sampleRate?: number;
}

export default class AudioRecorder {
  private mediaRecorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private chunks: BlobPart[] = [];
  private readonly preferredMimeType?: string;
  private readonly sampleRate?: number;

  constructor(options: AudioRecorderOptions = {}) {
    this.preferredMimeType = options.mimeType;
    this.sampleRate = options.sampleRate;
  }

  static isSupported(): boolean {
    return (
      typeof navigator !== 'undefined' &&
      !!navigator.mediaDevices?.getUserMedia &&
      typeof MediaRecorder !== 'undefined'
    );
  }

  async startRecording(): Promise<void> {
    if (this.mediaRecorder?.state === 'recording') {
      return;
    }

    if (!AudioRecorder.isSupported()) {
      throw new Error('当前浏览器不支持麦克风录音，请使用新版 Chrome、Edge 或 Safari。');
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: { ideal: 1 },
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: this.sampleRate ? { ideal: this.sampleRate } : undefined,
        },
      });
    } catch (error) {
      throw new Error(AudioRecorder.getPermissionErrorMessage(error));
    }

    this.chunks = [];

    const mimeType = this.resolveMimeType();
    this.mediaRecorder = new MediaRecorder(
      this.stream,
      mimeType ? { mimeType } : undefined
    );

    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        this.chunks.push(event.data);
      }
    };

    this.mediaRecorder.start();
  }

  static getPermissionErrorMessage(error: unknown): string {
    const name = error instanceof DOMException ? error.name : '';

    if (name === 'NotAllowedError' || name === 'SecurityError') {
      return '麦克风权限被拒绝，请在浏览器地址栏允许麦克风权限后重试。';
    }

    if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
      return '没有检测到可用麦克风，请连接麦克风后重试。';
    }

    if (name === 'NotReadableError' || name === 'TrackStartError') {
      return '麦克风正被其他应用占用，请关闭占用程序后重试。';
    }

    if (name === 'OverconstrainedError') {
      return '当前麦克风不支持所需录音参数，请换一个输入设备后重试。';
    }

    return error instanceof Error ? error.message : '无法开始录音，请检查麦克风权限。';
  }

  async stopRecording(): Promise<Blob> {
    if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
      throw new Error('Recording has not started');
    }

    const recorder = this.mediaRecorder;
    const mimeType = recorder.mimeType || this.resolveMimeType() || 'audio/webm';

    return new Promise<Blob>((resolve, reject) => {
      recorder.onstop = () => {
        this.stopTracks();
        resolve(new Blob(this.chunks, { type: mimeType }));
      };
      recorder.onerror = () => {
        this.stopTracks();
        reject(new Error('Recording failed'));
      };
      recorder.stop();
    });
  }

  private resolveMimeType(): string | undefined {
    const candidates = [
      this.preferredMimeType,
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
    ].filter(Boolean) as string[];

    return candidates.find((mimeType) => MediaRecorder.isTypeSupported?.(mimeType));
  }

  private stopTracks(): void {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    this.mediaRecorder = null;
  }
}
