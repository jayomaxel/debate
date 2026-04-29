interface AudioRecorderOptions {
  mimeType?: string;
  sampleRate?: number;
}

export default class AudioRecorder {
  private mediaRecorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private chunks: BlobPart[] = [];
  private readonly preferredMimeType?: string;

  constructor(options: AudioRecorderOptions = {}) {
    this.preferredMimeType = options.mimeType;
  }

  async startRecording(): Promise<void> {
    if (this.mediaRecorder?.state === 'recording') {
      return;
    }

    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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

    return candidates.find((mimeType) => MediaRecorder.isTypeSupported(mimeType));
  }

  private stopTracks(): void {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    this.mediaRecorder = null;
  }
}
