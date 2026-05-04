import React, { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Clock,
  Users,
  Volume2,
  VolumeX,
  Settings,
  Maximize,
  Minimize,
  Trophy,
  Zap,
  Target,
} from 'lucide-react';

interface DebateHeaderProps {
  topic: string;
  currentPhase: string;
  segmentTitle?: string;
  timeRemaining: number;
  canStartDebate?: boolean;
  canAdvanceSegment?: boolean;
  canEndDebate?: boolean;
  onStartDebate?: () => void;
  onAdvanceSegment?: () => void;
  onEndDebate?: () => void;
  onSettings?: () => void;
  onFullscreen?: () => void;
  isFullscreen?: boolean;
  autoPlayEnabled?: boolean;
  onToggleAutoPlay?: () => void;
}

const DebateHeader: React.FC<DebateHeaderProps> = ({
  topic,
  currentPhase,
  segmentTitle,
  timeRemaining,
  canStartDebate,
  canAdvanceSegment,
  canEndDebate,
  onStartDebate,
  onAdvanceSegment,
  onEndDebate,
  onSettings,
  onFullscreen,
  isFullscreen = false,
  autoPlayEnabled = true,
  onToggleAutoPlay
}) => {
  const [isPulsing, setIsPulsing] = useState(false);

  useEffect(() => {
    if (timeRemaining <= 60) {
      setIsPulsing(true);
    } else {
      setIsPulsing(false);
    }
  }, [timeRemaining]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const getTimeColor = () => {
    if (timeRemaining <= 30) return 'border-red-200 bg-red-50 text-red-700';
    if (timeRemaining <= 60) return 'border-amber-200 bg-amber-50 text-amber-700';
    return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  };

  const getPhaseColor = (phase: string) => {
    switch (phase) {
      case '立论陈词': return 'border-[#d8e7f2] bg-[#e2eef8] text-slate-800';
      case '攻辩环节': return 'border-[#e0d8ef] bg-[#eae6f6] text-slate-800';
      case '自由辩论': return 'border-[#f0d6c0] bg-[#f9ecde] text-slate-800';
      case '总结陈词': return 'border-emerald-200 bg-emerald-50 text-emerald-800';
      default: return 'border-[#e9e1d7] bg-white text-slate-700';
    }
  };

  return (
    <div className="sticky top-0 z-50 px-4 py-4 sm:px-6">
      <div className="student-container">
        <div className="student-header-frame rounded-none px-4 py-3 sm:px-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          {/* 左侧：辩题和当前环节 */}
          <div className="flex min-w-0 items-start gap-5">
            {/* 辩题 */}
            <div className="flex min-w-0 items-start gap-3">
              <div className="student-icon-bubble h-11 w-11 shrink-0 bg-[#151515] text-white shadow-[0_14px_30px_rgba(15,23,42,0.18)]">
                <Target className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <h1 className="max-w-[34rem] truncate text-lg font-semibold tracking-[-0.03em] text-slate-900">
                  {topic}
                </h1>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Badge className={`student-pill ${getPhaseColor(currentPhase)}`}>
                    {currentPhase}
                  </Badge>
                  <div className="student-pill gap-1">
                    <Users className="w-3 h-3" />
                    <span>4v4 对抗</span>
                  </div>
                </div>
                {segmentTitle && (
                  <div className="mt-2 max-w-[34rem] truncate text-xs text-slate-500">
                    {segmentTitle}
                  </div>
                )}
              </div>
            </div>

            {/* 对战统计 */}
            <div className="hidden items-center gap-3 text-sm xl:flex">
              <div className="student-pill gap-2">
                <Trophy className="w-4 h-4 text-amber-600" />
                <span>对抗等级: A+</span>
              </div>
              <div className="student-pill gap-2">
                <Zap className="w-4 h-4 text-slate-700" />
                <span>匹配度: 92%</span>
              </div>
            </div>
          </div>

          {/* 中间：倒计时 */}
          <div className="flex items-center lg:justify-center">
            <div className={`relative ${isPulsing ? 'animate-pulse' : ''}`}>
              <div className={`flex items-center gap-3 rounded-[14px] border px-5 py-3 shadow-[0_12px_28px_rgba(174,154,126,0.08)] ${getTimeColor()}`}>
                <Clock className="w-5 h-5" />
                <div className="text-center">
                  <p className="text-xs font-medium">剩余时间</p>
                  <p className="text-2xl font-semibold tracking-[-0.04em]">
                    {formatTime(timeRemaining)}
                  </p>
                </div>
              </div>

              {/* 时间警告效果 */}
              {timeRemaining <= 30 && (
                <div className="absolute inset-0 rounded-xl border-2 border-red-500 animate-ping opacity-75" />
              )}
            </div>
          </div>

          {/* 右侧：控制按钮 */}
          <div className="flex flex-wrap items-center gap-2 lg:justify-end">
            {canStartDebate && (
              <Button
                size="sm"
                onClick={onStartDebate}
                className="student-dark-button h-9"
              >
                开始辩论
              </Button>
            )}
            {canAdvanceSegment && (
              <Button
                size="sm"
                variant="secondary"
                onClick={onAdvanceSegment}
                className="student-light-button h-9"
              >
                强制下一阶段
              </Button>
            )}
            {canEndDebate && (
              <Button
                size="sm"
                variant="secondary"
                onClick={onEndDebate}
                className="h-9 rounded-[10px] bg-red-600 px-3 text-white hover:bg-red-700"
              >
                结束辩论
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={onSettings}
              className="h-9 w-9 rounded-[10px] text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            >
              <Settings className="w-4 h-4" />
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={onFullscreen}
              className="h-9 w-9 rounded-[10px] text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              title={isFullscreen ? '退出全屏' : '进入全屏'}
            >
              {isFullscreen ? <Minimize className="w-4 h-4" /> : <Maximize className="w-4 h-4" />}
            </Button>

            <div className="mx-1 h-6 w-px bg-slate-200" />

            <Button
              variant="ghost"
              size="sm"
              onClick={onToggleAutoPlay}
              className="h-9 w-9 rounded-[10px] text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              title={autoPlayEnabled ? '关闭自动播放' : '开启自动播放'}
            >
              {autoPlayEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            </Button>
          </div>
        </div>

        {/* 底部进度条 */}
        <div className="mt-3">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#ede4da]">
            <div
              className={`h-full rounded-full transition-all duration-1000 ease-out ${
                timeRemaining <= 30 ? 'bg-red-500' :
                timeRemaining <= 60 ? 'bg-amber-500' :
                'bg-[#171717]'
              }`}
              style={{
                width: `${Math.max(2, (timeRemaining / 1800) * 100)}%`
              }}
            />
          </div>
        </div>

        {/* 辩论阶段指示器 */}
        <div className="mt-3 flex items-center justify-center gap-2 overflow-x-auto">
          {['立论陈词', '攻辩环节', '自由辩论', '总结陈词'].map((phase, index) => (
            <div
              key={index}
              className="flex shrink-0 items-center gap-2"
            >
              <div
                className={`w-2 h-2 rounded-full ${
                  currentPhase === phase
                    ? 'bg-slate-900'
                    : index < ['立论陈词', '攻辩环节', '自由辩论', '总结陈词'].indexOf(currentPhase)
                    ? 'bg-emerald-500'
                    : 'bg-slate-300'
                }`}
              />
              <span
                className={`text-xs ${
                  currentPhase === phase
                    ? 'text-slate-900 font-medium'
                    : index < ['立论陈词', '攻辩环节', '自由辩论', '总结陈词'].indexOf(currentPhase)
                    ? 'text-slate-600'
                    : 'text-slate-400'
                }`}
              >
                {phase}
              </span>
              {index < 3 && (
                <div className="w-8 h-px bg-slate-200" />
              )}
            </div>
          ))}
        </div>
      </div>
      </div>
    </div>
  );
};

export default DebateHeader;
