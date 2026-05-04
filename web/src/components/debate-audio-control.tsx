import React, { useRef, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import AudioRecorder from '@/lib/audio-recorder';
import { AlertCircle, Mic, MicOff, Radio } from 'lucide-react';

interface DebateAudioControlProps {
  isMuted?: boolean;
  canGrabMic?: boolean;
  showSpeakingControls?: boolean;
  micStatusText?: string;
  onToggleMic?: () => void;
  onRequestStartRecording?: () => Promise<boolean>;
  onSendAudio?: (audioBlob: Blob, clientTranscript?: string) => void | Promise<void>;
  onGrabMic?: () => void;
  onEndTurn?: () => void;
}

const DebateAudioControl: React.FC<DebateAudioControlProps> = ({
  isMuted = false,
  canGrabMic = false,
  showSpeakingControls = true,
  micStatusText,
  onToggleMic,
  onRequestStartRecording,
  onSendAudio,
  onGrabMic,
  onEndTurn,
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingError, setRecordingError] = useState<string | null>(null);
  const audioRecorderRef = useRef<AudioRecorder | null>(null);
  const speechRecognitionRef = useRef<any>(null);
  const clientTranscriptRef = useRef('');

  const startClientSpeechRecognition = () => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      clientTranscriptRef.current = '';
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = 'zh-CN';
      recognition.continuous = true;
      recognition.interimResults = true;
      clientTranscriptRef.current = '';
      recognition.onresult = (event: any) => {
        let text = '';
        for (let i = 0; i < event.results.length; i += 1) {
          text += event.results[i]?.[0]?.transcript || '';
        }
        clientTranscriptRef.current = text.trim();
      };
      recognition.onerror = () => {
        // 浏览器语音识别只是服务端ASR的兜底，不阻断正常录音。
      };
      recognition.start();
      speechRecognitionRef.current = recognition;
    } catch {
      speechRecognitionRef.current = null;
    }
  };

  const stopClientSpeechRecognition = () => {
    try {
      speechRecognitionRef.current?.stop?.();
    } catch {
      // ignore
    } finally {
      speechRecognitionRef.current = null;
    }

    return clientTranscriptRef.current.trim();
  };

  const handleStartRecording = async () => {
    try {
      setRecordingError(null);
      if (!AudioRecorder.isSupported()) {
        setRecordingError('当前浏览器不支持麦克风录音，请使用 Chrome、Edge 或 Safari 的较新版本。');
        return;
      }

      if (!audioRecorderRef.current) {
        audioRecorderRef.current = new AudioRecorder({ sampleRate: 16000 });
      }

      await audioRecorderRef.current.startRecording();
      startClientSpeechRecognition();
      setIsRecording(true);
    } catch (err: any) {
      console.error('Failed to start recording:', err);
      setRecordingError(err.message || '无法开始录音');
    }
  };

  const handleStopRecording = async () => {
    try {
      if (!audioRecorderRef.current) {
        return;
      }

      const clientTranscript = stopClientSpeechRecognition();
      const audioBlob = await audioRecorderRef.current.stopRecording();
      setIsRecording(false);

      if (!audioBlob || audioBlob.size < 1024) {
        setRecordingError('录音内容太短或没有检测到声音，请重新录制后再发送。');
        return;
      }

      await onSendAudio?.(audioBlob, clientTranscript);
    } catch (err: any) {
      stopClientSpeechRecognition();
      console.error('Failed to stop recording:', err);
      setRecordingError(err.message || '录音失败');
      setIsRecording(false);
    }
  };

  const handleEndTurn = async () => {
    if (isRecording) {
      await handleStopRecording();
    }
    onEndTurn?.();
  };

  const handleGrabMic = () => {
    if (!canGrabMic) {
      return;
    }
    onGrabMic?.();
  };

  return (
    <div className="student-card flex w-full flex-col gap-5 px-5 py-5">
      <div>
        <h3 className="mt-1 text-lg font-semibold text-slate-900">发言操作台</h3>
      </div>

      {/* 顶部状态图标 */}
      <div className="grid grid-cols-1 gap-3">
        <div className="relative group">
          <Button
            onClick={onToggleMic}
            size="icon"
            className={`h-12 w-full rounded-[14px] shadow-sm transition-all duration-300 ${
              isMuted
                ? 'border border-red-200 bg-red-50 text-red-700 hover:bg-red-100'
                : 'border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
            }`}
          >
            {isMuted ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
            <span className="ml-2 text-sm font-semibold">{isMuted ? '麦克风关' : '麦克风开'}</span>
          </Button>
        </div>
      </div>

      <div className="h-px w-full bg-[#ece4da]" />

      {micStatusText && (
        <div className="rounded-[16px] border border-[#ece4da] bg-[#fbf7f1] px-4 py-4">
          <p className="mt-2 text-sm font-medium leading-relaxed text-slate-800">
            {micStatusText}
          </p>
        </div>
      )}

      {recordingError && (
        <Alert variant="destructive" className="w-full px-3 py-2">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="text-xs leading-relaxed">
            {recordingError}
          </AlertDescription>
        </Alert>
      )}

      <div className="flex w-full flex-col gap-3">
        {showSpeakingControls && canGrabMic && (
          <Button
            onClick={handleGrabMic}
            className="h-14 w-full rounded-[14px] border border-[#e0d8ef] bg-[#171717] text-white shadow-[0_18px_38px_rgba(15,23,42,0.2)] transition-colors hover:bg-[#2a2a2a]"
          >
            <Radio className="h-5 w-5 text-white" />
            <span className="text-sm font-semibold text-white">抢麦发言</span>
          </Button>
        )}

        {showSpeakingControls && (
          <Button
            onClick={async () => {
              if (isRecording) {
                await handleStopRecording();
                return;
              }

              const allowed = (await onRequestStartRecording?.()) ?? false;
              if (!allowed) return;
              await handleStartRecording();
            }}
            className={`flex h-14 w-full items-center justify-center gap-2 rounded-[14px] shadow-sm transition-colors ${
              isRecording
                ? 'border border-red-200 bg-red-600 text-white hover:bg-red-700'
                : 'border border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
            }`}
          >
            {isRecording ? (
              <>
                <Radio className="h-5 w-5 text-white" />
                <span className="font-medium text-white">停止录音</span>
              </>
            ) : (
              <>
                <Mic className="h-5 w-5" />
                <span className="font-medium">点击录音</span>
              </>
            )}
          </Button>
        )}

        {showSpeakingControls && (
          <Button
            onClick={handleEndTurn}
            className="flex h-12 w-full items-center justify-center gap-2 rounded-[14px] border border-[#f0d6c0] bg-[#f9ecde] text-slate-900 shadow-sm transition-colors hover:bg-[#f5e2cf]"
          >
            <div className="flex h-5 w-5 items-center justify-center rounded-sm border-2 border-current p-0.5">
              <div className="h-full w-full rounded-[1px] bg-current" />
            </div>
            <span className="font-medium text-slate-900">结束发言</span>
          </Button>
        )}
      </div>

      <div className="mt-auto w-full" />
    </div>
  );
};

export default DebateAudioControl;
