import React, { useState, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import AudioRecorder from '@/lib/audio-recorder';
import {
  Mic,
  MicOff,
  Video,
  VideoOff,
  AlertCircle,
  Radio,
} from 'lucide-react';

interface DebateAudioControlProps {
  isMuted?: boolean;
  isVideoOff?: boolean;
  canGrabMic?: boolean;
  showSpeakingControls?: boolean;
  micStatusText?: string;
  onToggleMic?: () => void;
  onToggleVideo?: () => void;
  onRequestStartRecording?: () => Promise<boolean>;
  onSendAudio?: (audioBlob: Blob, clientTranscript?: string) => void | Promise<void>;
  onGrabMic?: () => void;
  onEndTurn?: () => void;
}

const DebateAudioControl: React.FC<DebateAudioControlProps> = ({
  isMuted = false,
  isVideoOff = false,
  canGrabMic = false,
  showSpeakingControls = true,
  micStatusText,
  onToggleMic,
  onToggleVideo,
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

  // 开始语音录制
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

  // 停止语音录制并发送
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
      
      // 发送音频
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

  // 抢麦
  const handleGrabMic = () => {
    if (!canGrabMic) {
      return;
    }
    onGrabMic?.();
  };

  return (
    <div className="student-card flex w-full flex-col items-center gap-5 px-4 py-5 xl:h-full xl:w-[220px]">
      {/* 顶部状态图标 */}
      <div className="flex gap-4 w-full justify-center">
        <div className="relative group">
          <Button
            onClick={onToggleMic}
            size="icon"
            className={`rounded-xl w-10 h-10 shadow-lg transition-all duration-300 ${
              isMuted
                ? 'border border-red-200 bg-red-50 text-red-700 hover:bg-red-100'
                : 'border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
            }`}
          >
            {isMuted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </Button>
          <span className="pointer-events-none absolute -bottom-8 left-1/2 z-50 -translate-x-1/2 whitespace-nowrap rounded border border-[#ece4da] bg-white px-2 py-1 text-xs text-slate-700 opacity-0 shadow-sm transition-opacity group-hover:opacity-100">
            {isMuted ? '麦克风已关' : '麦克风已开'}
          </span>
        </div>

        <div className="relative group">
          <Button
            onClick={onToggleVideo}
            size="icon"
            className={`rounded-xl w-10 h-10 shadow-lg transition-all duration-300 ${
              isVideoOff
                ? 'border border-red-200 bg-red-50 text-red-700 hover:bg-red-100'
                : 'border border-[#d8e7f2] bg-[#e2eef8] text-slate-800 hover:bg-[#d6e8f6]'
            }`}
          >
            {isVideoOff ? <VideoOff className="w-5 h-5" /> : <Video className="w-5 h-5" />}
          </Button>
          <span className="pointer-events-none absolute -bottom-8 left-1/2 z-50 -translate-x-1/2 whitespace-nowrap rounded border border-[#ece4da] bg-white px-2 py-1 text-xs text-slate-700 opacity-0 shadow-sm transition-opacity group-hover:opacity-100">
            {isVideoOff ? '摄像头已关' : '摄像头已开'}
          </span>
        </div>
      </div>

      <div className="h-px w-full bg-[#ece4da]" />

      {/* 状态提示文本 */}
      {micStatusText && (
        <div className="student-card-muted w-full px-3 py-3 text-center">
          <p className="text-xs font-medium leading-relaxed text-slate-700">
            {micStatusText}
          </p>
        </div>
      )}

      {recordingError && (
        <Alert variant="destructive" className="w-full py-2 px-3">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="text-xs leading-relaxed">
            {recordingError}
          </AlertDescription>
        </Alert>
      )}

      {/* 核心操作区 */}
      <div className="mt-2 flex w-full flex-col gap-3">
        {/* 抢麦按钮 - 移到这里，更显眼 */}
        {showSpeakingControls && canGrabMic && (
          <Button
            onClick={handleGrabMic}
            className="h-12 w-full rounded-[10px] border border-[#e0d8ef] bg-[#171717] text-white shadow-[0_14px_30px_rgba(15,23,42,0.18)] transition-colors hover:bg-[#2a2a2a]"
          >
            <Radio className="w-5 h-5 text-white" />
            <span className="text-sm font-semibold text-white">抢麦发言</span>
          </Button>
        )}

        {showSpeakingControls && <Button
          onClick={async () => {
            if (isRecording) {
              await handleStopRecording();
              return;
            }
            const allowed = (await onRequestStartRecording?.()) ?? false;
            if (!allowed) return;
            await handleStartRecording();
          }}
          className={`flex h-12 w-full items-center justify-center gap-2 rounded-[10px] shadow-sm transition-colors ${
            isRecording
              ? 'border border-red-200 bg-red-600 text-white hover:bg-red-700'
              : 'border border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
          }`}
        >
          {isRecording ? (
            <>
              <Radio className="w-5 h-5 text-white" />
              <span className="font-medium text-white">停止录音</span>
            </>
          ) : (
            <>
              <Mic className="w-5 h-5" />
              <span className="font-medium">点击录音</span>
            </>
          )}
        </Button>}

        {showSpeakingControls && <Button
          onClick={handleEndTurn}
          className="flex h-12 w-full items-center justify-center gap-2 rounded-[10px] border border-[#f0d6c0] bg-[#f9ecde] text-slate-900 shadow-sm transition-colors hover:bg-[#f5e2cf]"
        >
          <div className="w-5 h-5 flex items-center justify-center border-2 border-current rounded-sm p-0.5">
            <div className="w-full h-full bg-current rounded-[1px]" />
          </div>
          <span className="font-medium text-slate-900">结束发言</span>
        </Button>}
      </div>

      {/* 底部功能区 - 移除抢麦按钮 */}
      <div className="mt-auto w-full">
      </div>
    </div>
  );
};

export default DebateAudioControl;
