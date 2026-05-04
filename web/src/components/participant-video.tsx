import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import {
  Mic,
  MicOff,
  Video,
  VideoOff,
  User,
  Crown,
  Signal,
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
  const getSignalColor = (strength?: number) => {
    if (!strength) return 'text-slate-500';
    if (strength >= 80) return 'text-emerald-500';
    if (strength >= 50) return 'text-amber-500';
    return 'text-red-500';
  };

  const getActiveStyles = () => {
    if (!isActive) return '';

    return 'translate-y-[-2px] ring-2 ring-[#1f2937]/15 ring-offset-4 ring-offset-[#f8f5f1]';
  };

  const getSpeakingStyles = () => {
    if (!participant.isSpeaking) return '';

    return participant.isAI
      ? 'border-[#cfc3e8] bg-[#f3effa]'
      : 'border-[#c4dced] bg-[#eef6fb]';
  };

  const isOffline = typeof participant.signalStrength !== 'number';

  return (
    <Card className={`
      group relative overflow-hidden rounded-[26px] transition-all duration-300
      bg-[linear-gradient(145deg,rgba(255,255,255,0.96)_0%,rgba(242,248,252,0.92)_54%,rgba(255,250,245,0.9)_100%)]
      ${getActiveStyles()} ${getSpeakingStyles()}
      border ${participant.isSpeaking ? 'border-[#b9d6ea]' : 'border-white/80'}
      shadow-[0_22px_54px_rgba(82,72,61,0.10)]
    `}>
      <CardContent className="relative h-[218px] p-5">
        <div className="pointer-events-none absolute inset-0 opacity-70">
          <div className="absolute -right-12 -top-14 h-32 w-32 rounded-full bg-[#d8e7f2]" />
          <div className="absolute -bottom-16 left-8 h-28 w-28 rounded-full bg-[#f9ecde]" />
        </div>

        <div className="relative flex h-full flex-col">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Badge className="rounded-full border-[#d8e7f2] bg-white/80 text-xs text-slate-700">
                  正方席位
                </Badge>
                {isCurrentUser && (
                  <Badge className="rounded-full border-slate-900 bg-slate-900 text-xs text-white">
                    我
                  </Badge>
                )}
              </div>
              <h3 className="mt-3 truncate text-lg font-semibold tracking-[-0.02em] text-slate-950">
                {participant.name}
              </h3>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Badge variant="secondary" className="student-pill text-xs">
                  {participant.position}
                </Badge>
                {participant.role === 'captain' && (
                  <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-700">
                    <Crown className="h-3 w-3" />
                    队长
                  </span>
                )}
              </div>
            </div>

            <div className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${
              isOffline
                ? 'border-slate-200 bg-white/70 text-slate-500'
                : 'border-emerald-200 bg-emerald-50 text-emerald-700'
            }`}>
              <Signal className={`h-3 w-3 ${getSignalColor(participant.signalStrength)}`} />
              {isOffline ? '未入场' : '在线'}
            </div>
          </div>

          <div className="mt-auto flex items-end justify-between gap-4">
            <div className="flex items-center gap-3">
              <Avatar className={`h-16 w-16 border-4 border-white shadow-[0_16px_34px_rgba(82,72,61,0.14)] ${
                participant.isSpeaking ? 'ring-4 ring-emerald-100' : ''
              }`}>
                <AvatarImage src={participant.avatar} alt={participant.name} />
                <AvatarFallback className="bg-[#e2eef8] text-slate-800">
                  <User className="h-8 w-8" />
                </AvatarFallback>
              </Avatar>
              <div>
                <p className="text-xs text-slate-500">当前状态</p>
                <p className={`mt-1 text-sm font-semibold ${
                  participant.isSpeaking ? 'text-emerald-700' : isOffline ? 'text-slate-500' : 'text-slate-900'
                }`}>
                  {participant.isSpeaking ? '正在发言' : isOffline ? '等待入场' : '准备中'}
                </p>
              </div>
            </div>

            {participant.isSpeaking && (
              <div className="rounded-full border border-emerald-200 bg-white/88 px-3 py-1 text-xs font-semibold text-emerald-700 shadow-sm">
                Live
              </div>
            )}
          </div>

          {/* AI 标识 */}
          {participant.isAI && (
            <div className="absolute top-2 left-2">
              <Badge className="border-[#e0d8ef] bg-[#eae6f6] text-xs text-slate-800">
                AI
              </Badge>
            </div>
          )}

          {/* 控制按钮 */}
          {isCurrentUser && (
            <div className="absolute bottom-5 right-5 flex justify-center gap-2 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100">
              <Button
                size="sm"
                variant="secondary"
                onClick={onToggleMic}
                className={`h-8 w-8 rounded-full ${
                  participant.isMuted ? 'bg-red-600 text-white hover:bg-red-700' : 'bg-white/90 text-slate-800 hover:bg-white'
                }`}
              >
                {participant.isMuted ? (
                  <MicOff className="w-4 h-4 text-white" />
                ) : (
                  <Mic className="w-4 h-4 text-slate-800" />
                )}
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={onToggleVideo}
                className={`h-8 w-8 rounded-full ${
                  participant.isVideoOff ? 'bg-red-600 text-white hover:bg-red-700' : 'bg-white/90 text-slate-800 hover:bg-white'
                }`}
              >
                {participant.isVideoOff ? (
                  <VideoOff className="w-4 h-4 text-white" />
                ) : (
                  <Video className="w-4 h-4 text-slate-800" />
                )}
              </Button>
            </div>
          )}

          {/* 静音状态指示 */}
          {participant.isMuted && !isCurrentUser && (
            <div className="absolute bottom-5 right-5">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-red-600/90 shadow-sm">
                <MicOff className="h-4 w-4 text-white" />
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default ParticipantVideo;
