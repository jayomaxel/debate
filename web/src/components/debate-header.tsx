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
  Target
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
    if (timeRemaining <= 30) return 'text-red-600 bg-red-50 border-red-200';
    if (timeRemaining <= 60) return 'text-amber-600 bg-amber-50 border-amber-200';
    return 'text-emerald-600 bg-emerald-50 border-emerald-200';
  };

  const getPhaseColor = (phase: string) => {
    switch (phase) {
      case '立论陈词': return 'bg-blue-100 text-blue-700 border-blue-300';
      case '攻辩环节': return 'bg-purple-100 text-purple-700 border-purple-300';
      case '自由辩论': return 'bg-orange-100 text-orange-700 border-orange-300';
      case '总结陈词': return 'bg-emerald-100 text-emerald-700 border-emerald-300';
      default: return 'bg-slate-100 text-slate-700 border-slate-300';
    }
  };

  return (
    <div className="bg-slate-900/95 backdrop-blur-lg border-b border-slate-700/50 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 py-3">
        <div className="flex items-center justify-between">
          {/* 左侧：辩题和当前环节 */}
          <div className="flex items-center gap-6">
            {/* 辩题 */}
            <div className="flex items-center gap-3">
              <Target className="w-5 h-5 text-blue-400" />
              <div>
                <h1 className="text-lg font-bold text-white truncate max-w-md">
                  {topic}
                </h1>
                <div className="flex items-center gap-2 mt-1">
                  <Badge className={`text-xs ${getPhaseColor(currentPhase)}`}>
                    {currentPhase}
                  </Badge>
                  <div className="flex items-center gap-1 text-xs text-slate-400">
                    <Users className="w-3 h-3" />
                    <span>4v4 对抗</span>
                  </div>
                </div>
                {segmentTitle && (
                  <div className="text-xs text-slate-400 mt-1 truncate max-w-md">
                    {segmentTitle}
                  </div>
                )}
              </div>
            </div>

            {/* 对战统计 */}
            <div className="hidden md:flex items-center gap-4 text-sm">
              <div className="flex items-center gap-2 text-slate-300">
                <Trophy className="w-4 h-4 text-amber-400" />
                <span>对抗等级: A+</span>
              </div>
              <div className="flex items-center gap-2 text-slate-300">
                <Zap className="w-4 h-4 text-blue-400" />
                <span>匹配度: 92%</span>
              </div>
            </div>
          </div>

          {/* 中间：倒计时 */}
          <div className="flex items-center justify-center">
            <div className={`relative ${isPulsing ? 'animate-pulse' : ''}`}>
              <div className={`flex items-center gap-3 px-6 py-3 rounded-xl border-2 ${getTimeColor()} ${isPulsing ? 'shadow-lg' : ''}`}>
                <Clock className={`w-6 h-6 ${timeRemaining <= 30 ? 'animate-spin' : ''}`} />
                <div className="text-center">
                  <p className="text-xs font-medium">剩余时间</p>
                  <p className={`text-2xl font-bold ${timeRemaining <= 30 ? 'animate-pulse' : ''}`}>
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
          <div className="flex items-center gap-2">
            {canStartDebate && (
              <Button
                size="sm"
                onClick={onStartDebate}
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                开始辩论
              </Button>
            )}
            {canAdvanceSegment && (
              <Button
                size="sm"
                variant="secondary"
                onClick={onAdvanceSegment}
                className="bg-slate-700 hover:bg-slate-600 text-white"
              >
                强制下一阶段
              </Button>
            )}
            {canEndDebate && (
              <Button
                size="sm"
                variant="secondary"
                onClick={onEndDebate}
                className="bg-red-700 hover:bg-red-800 text-white"
              >
                结束辩论
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={onSettings}
              className="text-slate-400 hover:text-white hover:bg-slate-700"
            >
              <Settings className="w-4 h-4" />
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={onFullscreen}
              className="text-slate-400 hover:text-white hover:bg-slate-700"
              title={isFullscreen ? '退出全屏' : '进入全屏'}
            >
              {isFullscreen ? <Minimize className="w-4 h-4" /> : <Maximize className="w-4 h-4" />}
            </Button>

            <div className="w-px h-6 bg-slate-600 mx-2" />

            <Button
              variant="ghost"
              size="sm"
              onClick={onToggleAutoPlay}
              className="text-slate-400 hover:text-white hover:bg-slate-700"
              title={autoPlayEnabled ? '关闭自动播放' : '开启自动播放'}
            >
              {autoPlayEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            </Button>
          </div>
        </div>

        {/* 底部进度条 */}
        <div className="mt-3">
          <div className="w-full bg-slate-700 rounded-full h-1.5 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-1000 ease-out ${
                timeRemaining <= 30 ? 'bg-red-500' :
                timeRemaining <= 60 ? 'bg-amber-500' :
                'bg-gradient-to-r from-blue-500 to-emerald-500'
              }`}
              style={{
                width: `${Math.max(2, (timeRemaining / 1800) * 100)}%`
              }}
            />
          </div>
        </div>

        {/* 辩论阶段指示器 */}
        <div className="mt-3 flex items-center justify-center gap-2">
          {['立论陈词', '攻辩环节', '自由辩论', '总结陈词'].map((phase, index) => (
            <div
              key={index}
              className="flex items-center gap-2"
            >
              <div
                className={`w-2 h-2 rounded-full ${
                  currentPhase === phase
                    ? 'bg-blue-500 animate-pulse'
                    : index < ['立论陈词', '攻辩环节', '自由辩论', '总结陈词'].indexOf(currentPhase)
                    ? 'bg-emerald-500'
                    : 'bg-slate-600'
                }`}
              />
              <span
                className={`text-xs ${
                  currentPhase === phase
                    ? 'text-white font-medium'
                    : index < ['立论陈词', '攻辩环节', '自由辩论', '总结陈词'].indexOf(currentPhase)
                    ? 'text-slate-400'
                    : 'text-slate-600'
                }`}
              >
                {phase}
              </span>
              {index < 3 && (
                <div className="w-8 h-px bg-slate-600" />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default DebateHeader;
