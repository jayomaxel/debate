import React from 'react';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft,
  Volume2,
  VolumeX,
  Settings,
  Maximize,
  Minimize,
} from 'lucide-react';

interface DebateHeaderProps {
  topic: string;
  currentPhase: string;
  segmentTitle?: string;
  onBack?: () => void;
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
  currentPhase,
  segmentTitle,
  onBack,
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
  return (
    <div className="sticky top-0 z-50 px-4 py-4 sm:px-6">
      <div className="student-container">
        <div className="student-header-frame rounded-none px-4 py-3 sm:px-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          {/* 左侧：辩题和当前环节 */}
          <div className="flex min-w-0 items-start gap-5">
            {onBack ? (
              <Button
                variant="outline"
                size="sm"
                onClick={onBack}
                className="student-light-button h-10 shrink-0 rounded-[12px] px-3"
              >
                <ArrowLeft className="mr-1 h-4 w-4" />
                返回
              </Button>
            ) : null}
            {/* 辩题 */}
            <div className="flex min-w-0 items-start gap-3">
              <div className="min-w-0">
                <h1 className="max-w-[34rem] truncate text-lg font-semibold text-slate-900">
                  {currentPhase}
                </h1>
                {segmentTitle && (
                  <div className="mt-2 max-w-[34rem] truncate text-xs text-slate-500">
                    {segmentTitle}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* 中间：倒计时 */}
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
              className="h-11 w-11 rounded-[12px] text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            >
              <Settings className="h-5 w-5" />
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={onFullscreen}
              className="h-11 w-11 rounded-[12px] text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              title={isFullscreen ? '退出全屏' : '进入全屏'}
            >
              {isFullscreen ? <Minimize className="h-5 w-5" /> : <Maximize className="h-5 w-5" />}
            </Button>

            <div className="mx-1 h-6 w-px bg-slate-200" />

            <Button
              variant="ghost"
              size="sm"
              onClick={onToggleAutoPlay}
              className="h-11 w-11 rounded-[12px] text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              title={autoPlayEnabled ? '关闭自动播放' : '开启自动播放'}
            >
              {autoPlayEnabled ? <Volume2 className="h-5 w-5" /> : <VolumeX className="h-5 w-5" />}
            </Button>
          </div>
        </div>

        {/* 辩论阶段指示器 */}
        <div className="mt-4 flex justify-center overflow-x-auto">
          <div className="inline-flex items-center justify-center gap-3 rounded-[16px] border border-slate-200 bg-white px-6 py-3 shadow-[0_12px_28px_rgba(15,23,42,0.06)]">
            {['立论陈词', '攻辩环节', '自由辩论', '总结陈词'].map((phase, index) => (
              <div
                key={index}
                className="flex shrink-0 items-center gap-3"
              >
                <div
                  className={`h-2.5 w-2.5 rounded-full ${
                    currentPhase === phase
                      ? 'bg-slate-900'
                      : index < ['立论陈词', '攻辩环节', '自由辩论', '总结陈词'].indexOf(currentPhase)
                      ? 'bg-emerald-500'
                      : 'bg-slate-300'
                  }`}
                />
                <span
                  className={`text-sm ${
                    currentPhase === phase
                      ? 'font-semibold text-slate-900'
                      : index < ['立论陈词', '攻辩环节', '自由辩论', '总结陈词'].indexOf(currentPhase)
                      ? 'font-medium text-slate-600'
                      : 'font-medium text-slate-400'
                  }`}
                >
                  {phase}
                </span>
                {index < 3 && (
                  <div className="h-px w-12 bg-slate-200" />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
      </div>
    </div>
  );
};

export default DebateHeader;
