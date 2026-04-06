import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import {
  Mic,
  MicOff,
  Video,
  VideoOff,
  Volume2,
  User,
  Crown,
  Signal
} from 'lucide-react';

export interface Participant {
  id: string;
  name: string;
  avatar?: string;
  position: '一辩' | '二辩' | '三辩' | '四辩';
  isAI?: boolean;
  isMuted?: boolean;
  isVideoOff?: boolean;
  isSpeaking?: boolean;
  signalStrength?: number;
  role?: 'captain' | 'member';
}

interface ParticipantVideoProps {
  participant: Participant;
  isActive?: boolean;
  isCurrentUser?: boolean;
  onToggleMic?: () => void;
  onToggleVideo?: () => void;
}

const ParticipantVideo: React.FC<ParticipantVideoProps> = ({
  participant,
  isActive = false,
  isCurrentUser = false,
  onToggleMic,
  onToggleVideo
}) => {
  const [audioLevel, setAudioLevel] = useState(0);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // 模拟音频波形
  useEffect(() => {
    if (participant.isSpeaking) {
      const interval = setInterval(() => {
        setAudioLevel(Math.random() * 100);
      }, 100);
      return () => clearInterval(interval);
    } else {
      setAudioLevel(0);
    }
  }, [participant.isSpeaking]);

  // 绘制音频波形
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const drawWaveform = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      if (audioLevel > 0) {
        ctx.strokeStyle = participant.isAI ? '#8b5cf6' : '#3b82f6';
        ctx.lineWidth = 2;
        ctx.beginPath();

        const barCount = 20;
        const barWidth = canvas.width / barCount;

        for (let i = 0; i < barCount; i++) {
          const barHeight = (Math.random() * audioLevel / 100) * canvas.height * 0.8;
          const x = i * barWidth + barWidth / 2;
          const y = canvas.height / 2 - barHeight / 2;

          ctx.fillRect(x - 1, y, 2, barHeight);
        }

        ctx.stroke();
      }
    };

    drawWaveform();
  }, [audioLevel, participant.isAI]);

  const getSignalColor = (strength?: number) => {
    if (!strength) return 'text-slate-500';
    if (strength >= 80) return 'text-emerald-500';
    if (strength >= 50) return 'text-amber-500';
    return 'text-red-500';
  };

  const getActiveStyles = () => {
    if (!isActive) return '';

    return 'ring-4 ring-blue-500/50 ring-offset-2 ring-offset-slate-900 scale-105';
  };

  const getSpeakingStyles = () => {
    if (!participant.isSpeaking) return '';

    return participant.isAI
      ? 'border-purple-500 bg-purple-950/30'
      : 'border-blue-500 bg-blue-950/30';
  };

  return (
    <Card className={`
      relative overflow-hidden transition-all duration-300
      ${participant.isVideoOff ? 'bg-slate-900' : 'bg-slate-800'}
      ${getActiveStyles()} ${getSpeakingStyles()}
      border-2 ${participant.isSpeaking ? '' : 'border-slate-700'}
    `}>
      <CardContent className="p-0 h-40">
        {/* 视频区域 */}
        <div className="relative h-full">
          {participant.isVideoOff ? (
            <div className="absolute inset-0 flex items-center justify-center bg-slate-900">
              <Avatar className="w-16 h-16">
                <AvatarImage src={participant.avatar} alt={participant.name} />
                <AvatarFallback className={participant.isAI ? 'bg-purple-600' : 'bg-blue-600'}>
                  {participant.isAI ? (
                    <div className="text-white text-2xl font-bold">AI</div>
                  ) : (
                    <User className="w-8 h-8 text-white" />
                  )}
                </AvatarFallback>
              </Avatar>
            </div>
          ) : (
            <div className="absolute inset-0 bg-gradient-to-br from-slate-800 to-slate-900">
              {/* 模拟视频背景 */}
              <div className="absolute inset-0 opacity-20">
                <div className="h-full w-full bg-slate-700 animate-pulse" />
              </div>

              {/* 用户信息叠加层 */}
              <div className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-black/80 to-transparent">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-white text-sm font-medium truncate">
                      {participant.name}
                    </span>
                    {participant.role === 'captain' && (
                      <Crown className="w-4 h-4 text-amber-400" />
                    )}
                    <Badge variant="secondary" className="text-xs text-white">
                      {participant.position}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-1">
                    <Signal className={`w-3 h-3 ${getSignalColor(participant.signalStrength)}`} />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 音频波形覆盖层 */}
          {participant.isSpeaking && (
            <canvas
              ref={canvasRef}
              width={200}
              height={40}
              className="absolute top-2 left-2 right-2 h-10 pointer-events-none opacity-80"
            />
          )}

          {/* 发言指示器 */}
          {participant.isSpeaking && (
            <div className="absolute top-2 right-2">
              <div className="flex items-center gap-1 px-2 py-1 bg-red-500 rounded-full animate-pulse">
                <div className="w-2 h-2 bg-white rounded-full animate-ping" />
                <span className="text-white text-xs font-medium">发言中</span>
              </div>
            </div>
          )}

          {/* AI 标识 */}
          {participant.isAI && (
            <div className="absolute top-2 left-2">
              <Badge className="bg-purple-600 text-white text-xs">
                AI
              </Badge>
            </div>
          )}

          {/* 控制按钮 */}
          {isCurrentUser && (
            <div className="absolute bottom-14 left-0 right-0 flex justify-center gap-2 opacity-0 hover:opacity-100 transition-opacity">
              <Button
                size="sm"
                variant="secondary"
                onClick={onToggleMic}
                className={`w-8 h-8 rounded-full ${
                  participant.isMuted ? 'bg-red-600 hover:bg-red-700' : ''
                }`}
              >
                {participant.isMuted ? (
                  <MicOff className="w-4 h-4 text-white" />
                ) : (
                  <Mic className="w-4 h-4 text-white" />
                )}
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={onToggleVideo}
                className={`w-8 h-8 rounded-full ${
                  participant.isVideoOff ? 'bg-red-600 hover:bg-red-700' : ''
                }`}
              >
                {participant.isVideoOff ? (
                  <VideoOff className="w-4 h-4 text-white" />
                ) : (
                  <Video className="w-4 h-4 text-white" />
                )}
              </Button>
            </div>
          )}

          {/* 静音状态指示 */}
          {participant.isMuted && !isCurrentUser && (
            <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
              <div className="w-12 h-12 bg-red-600/80 rounded-full flex items-center justify-center">
                <MicOff className="w-6 h-6 text-white" />
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default ParticipantVideo;
