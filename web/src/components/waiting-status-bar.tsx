import React, { useEffect, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Loader2, Wifi, CheckCircle2, Clock3, Users } from 'lucide-react';

interface WaitingStatusBarProps {
  hasAssignedRole?: boolean;
  participantCount?: number;
  isReady?: boolean;
}

type WaitingStage = 'connecting' | 'matching' | 'preparing' | 'ready';

const clampParticipantCount = (value?: number) => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return 0;
  }

  return Math.max(0, Math.min(4, value));
};

const dotsForTick = (tick: number) => '.'.repeat((tick % 3) + 1);

const getStageMeta = (stage: WaitingStage, participantCount: number) => {
  switch (stage) {
    case 'connecting':
      return {
        message: '正在连接本场辩论',
        details: '正在同步房间状态，请稍等片刻。',
      };
    case 'matching':
      return {
        message: '正在确认角色与对阵',
        details: '系统正在确认你的辩位和当前参赛名单。',
      };
    case 'preparing':
      return {
        message: '等待其余参与者并完成准备',
        details: `当前已有 ${participantCount}/4 位同学到场。你可以先查看辩题、整理观点并检查设备。`,
      };
    case 'ready':
    default:
      return {
        message: '本场辩论可以开始',
        details: '角色和名单已经确认完成，现在可以直接进入正式辩论。',
      };
  }
};

const getStageTone = (stage: WaitingStage) => {
  switch (stage) {
    case 'connecting':
      return {
        card: 'student-card-soft-blue',
        badge: 'student-pill',
      };
    case 'matching':
      return {
        card: 'student-card-soft-peach',
        badge: 'student-pill',
      };
    case 'preparing':
      return {
        card: 'student-card-soft-lavender',
        badge: 'student-pill',
      };
    case 'ready':
    default:
      return {
        card: 'student-card-soft-blue',
        badge: 'student-pill',
      };
  }
};

const getStageIcon = (stage: WaitingStage) => {
  switch (stage) {
    case 'connecting':
      return <Loader2 className="h-5 w-5 animate-spin text-slate-700" />;
    case 'matching':
      return <Users className="h-5 w-5 text-slate-700" />;
    case 'preparing':
      return <Clock3 className="h-5 w-5 text-slate-700" />;
    case 'ready':
    default:
      return <CheckCircle2 className="h-5 w-5 text-emerald-700" />;
  }
};

const WaitingStatusBar: React.FC<WaitingStatusBarProps> = ({
  hasAssignedRole = false,
  participantCount,
  isReady = false,
}) => {
  const [dotTick, setDotTick] = useState(0);
  const normalizedParticipantCount = clampParticipantCount(participantCount);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setDotTick((prev) => prev + 1);
    }, 500);

    return () => {
      window.clearInterval(timer);
    };
  }, []);

  const stage = useMemo<WaitingStage>(() => {
    if (isReady) {
      return 'ready';
    }

    if (!hasAssignedRole) {
      return 'matching';
    }

    if (normalizedParticipantCount <= 0) {
      return 'connecting';
    }

    return 'preparing';
  }, [hasAssignedRole, isReady, normalizedParticipantCount]);

  const stageMeta = getStageMeta(stage, normalizedParticipantCount);
  const tone = getStageTone(stage);
  const animatedMessage =
    stage === 'ready'
      ? stageMeta.message
      : `${stageMeta.message}${dotsForTick(dotTick)}`;

  return (
    <section className={`${tone.card} p-5`}>
      <div className="flex items-start gap-4">
        <div className="student-icon-bubble h-11 w-11 bg-white/90">{getStageIcon(stage)}</div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold tracking-[-0.03em] text-slate-900">
              {animatedMessage}
            </h3>
            <Badge className={tone.badge}>
              <Wifi className="mr-1 h-3 w-3" />
              {stage === 'ready' ? '已就绪' : '同步中'}
            </Badge>
          </div>
          <p className="mt-2 text-sm leading-7 text-slate-600">{stageMeta.details}</p>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <div className="student-card-muted p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
            角色分配
          </div>
          <div className="mt-2 font-medium text-slate-900">
            {hasAssignedRole ? '已确认' : '等待同步'}
          </div>
        </div>
        <div className="student-card-muted p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
            人类参与者
          </div>
          <div className="mt-2 font-medium text-slate-900">
            {normalizedParticipantCount}/4
          </div>
        </div>
        <div className="student-card-muted p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
            开赛状态
          </div>
          <div className="mt-2 font-medium text-slate-900">
            {isReady ? '可进入正式辩论' : '等待与准备中'}
          </div>
        </div>
      </div>
    </section>
  );
};

export default WaitingStatusBar;
