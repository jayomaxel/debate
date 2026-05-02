import React, { useState, useRef } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import AudioRecorder from '@/lib/audio-recorder';
import {
  Mic,
  MicOff,
  Video,
  VideoOff,
  Settings,
  AlertCircle,
  Radio,
  Volume2
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
    <div className="h-full bg-slate-800/60 backdrop-blur-md border-r border-slate-700/50 flex flex-col items-center py-6 px-4 gap-6 w-[200px]">
      {/* 顶部状态图标 */}
      <div className="flex gap-4 w-full justify-center">
        <div className="relative group">
          <Button
            onClick={onToggleMic}
            size="icon"
            className={`rounded-xl w-10 h-10 shadow-lg transition-all duration-300 ${
              isMuted
                ? 'bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30'
                : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30'
            }`}
          >
            {isMuted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </Button>
          <span className="absolute left-1/2 -translate-x-1/2 -bottom-8 bg-slate-900 text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none border border-slate-700 z-50">
            {isMuted ? '麦克风已关' : '麦克风已开'}
          </span>
        </div>

        <div className="relative group">
          <Button
            onClick={onToggleVideo}
            size="icon"
            className={`rounded-xl w-10 h-10 shadow-lg transition-all duration-300 ${
              isVideoOff
                ? 'bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30'
                : 'bg-blue-500/20 text-blue-400 border border-blue-500/30 hover:bg-blue-500/30'
            }`}
          >
            {isVideoOff ? <VideoOff className="w-5 h-5" /> : <Video className="w-5 h-5" />}
          </Button>
          <span className="absolute left-1/2 -translate-x-1/2 -bottom-8 bg-slate-900 text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none border border-slate-700 z-50">
            {isVideoOff ? '摄像头已关' : '摄像头已开'}
          </span>
        </div>
      </div>

      <div className="w-full h-px bg-slate-700/50" />

      {/* 状态提示文本 */}
      {micStatusText && (
        <div className="w-full px-2 py-2 bg-slate-700/30 rounded-lg border border-slate-600/30 text-center">
          <p className="text-xs text-slate-300 font-medium leading-relaxed">
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
      <div className="flex flex-col gap-4 w-full mt-4">
        {/* 抢麦按钮 - 移到这里，更显眼 */}
        {showSpeakingControls && canGrabMic && (
          <Button
            onClick={handleGrabMic}
            className="w-full h-14 rounded-xl shadow-lg transition-all duration-300 flex items-center justify-center gap-2 bg-gradient-to-br from-purple-500 to-purple-700 hover:from-purple-400 hover:to-purple-600 border border-purple-400/30 animate-pulse"
          >
            <Radio className="w-5 h-5 text-white" />
            <span className="font-bold text-white text-base">抢麦发言</span>
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
          className={`w-full h-12 rounded-xl shadow-md transition-all duration-300 flex items-center justify-center gap-2 ${
            isRecording
              ? 'bg-red-500 hover:bg-red-600 animate-pulse ring-2 ring-red-500/20'
              : 'bg-gradient-to-br from-emerald-500 to-emerald-700 hover:from-emerald-400 hover:to-emerald-600 border border-emerald-400/30'
          }`}
        >
          {isRecording ? (
            <>
              <Radio className="w-5 h-5 text-white" />
              <span className="font-medium text-white">停止录音</span>
            </>
          ) : (
            <>
              <Mic className="w-5 h-5 text-white" />
              <span className="font-medium text-white">点击录音</span>
            </>
          )}
        </Button>}

        {showSpeakingControls && <Button
          onClick={handleEndTurn}
          className={`w-full h-12 rounded-xl shadow-md transition-all duration-300 flex items-center justify-center gap-2 ${
            'bg-gradient-to-br from-amber-500 to-amber-700 hover:from-amber-400 hover:to-amber-600 border border-amber-400/30'
          }`}
        >
          <div className="w-5 h-5 flex items-center justify-center border-2 border-current rounded-sm p-0.5">
            <div className="w-full h-full bg-current rounded-[1px]" />
          </div>
          <span className="font-medium text-white">结束发言</span>
        </Button>}
      </div>

      {/* 底部功能区 - 移除抢麦按钮 */}
      <div className="mt-auto w-full">
      </div>
    </div>
  );
};

export default DebateAudioControl;
