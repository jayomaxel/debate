import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Clock3,
  Loader2,
  ShieldCheck,
  Sparkles,
  User,
  Users,
} from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import DebateTopicCard from './debate-topic-card';
import StudentService from '@/services/student.service';
import type { Debate, DebateParticipant } from '@/services/student.service';
import { useAuth } from '@/store/auth.context';
import { usePageActivityRefresh } from '@/hooks/use-page-activity-refresh';
import { useWebSocket } from '@/hooks/use-websocket';
import {
  getCurrentUserChecklist,
  getRealtimeParticipantCount,
  hasDebateStarted,
  parseWaitingRoomState,
  type WaitingRoomState,
} from '@/lib/waiting-room';

interface StudentOnboardingProps {
  initialDebate?: Debate | null;
  onDebateStart?: (debateId?: string) => void;
  onBackToLogin?: () => void;
  onNavigateToAnalytics?: (tab: 'history' | 'growth') => void;
}

type DebateRole = NonNullable<Debate['role']>;

const roleLabel: Record<DebateRole, string> = {
  debater_1: '一辩',
  debater_2: '二辩',
  debater_3: '三辩',
  debater_4: '四辩',
};

const roleDescription: Record<DebateRole, string> = {
  debater_1: '负责立论陈词，先建立本方框架与核心主张。',
  debater_2: '负责推进攻辩，用问题与追问拆解对方论证。',
  debater_3: '负责质询与回应，在交锋中补强团队论证。',
  debater_4: '负责总结陈词，提炼全场重点并完成收束。',
};

const statusPriority: Record<Debate['status'], number> = {
  in_progress: 0,
  published: 1,
  draft: 2,
  completed: 3,
};

const readinessChecklist = [
  '确认你的辩位与本场辩题已经同步。',
  '快速阅读背景资料，并整理 2 到 3 个核心观点。',
  '准备一组支撑论据，并至少想好一条对对方的预判回应。',
  '检查麦克风、耳机和网络连接，比赛开始后尽量不要离场。',
];

const sortJoinedDebates = (debates: Debate[]) =>
  debates
    .filter((debate) => debate.is_joined)
    .slice()
    .sort((a, b) => {
      const statusDelta =
        (statusPriority[a.status] ?? 99) - (statusPriority[b.status] ?? 99);
      if (statusDelta !== 0) {
        return statusDelta;
      }

      const roleDelta = Number(!!b.role) - Number(!!a.role);
      if (roleDelta !== 0) {
        return roleDelta;
      }

      return Date.parse(b.created_at) - Date.parse(a.created_at);
    });

const isDebateRole = (role: unknown): role is DebateRole =>
  typeof role === 'string' && role in roleLabel;

const getParticipantCount = (debate: Debate | null) => {
  if (!Array.isArray(debate?.participants)) {
    return typeof debate?.participant_count === 'number'
      ? debate.participant_count
      : 0;
  }

  return debate.participants.length;
};

const getHumanParticipants = (participants?: DebateParticipant[] | null) => {
  if (!Array.isArray(participants)) {
    return [];
  }

  return participants.filter((participant) => !!participant.role);
};

const StudentOnboarding: React.FC<StudentOnboardingProps> = ({
  initialDebate,
  onDebateStart,
  onBackToLogin,
  onNavigateToAnalytics,
}) => {
  void onNavigateToAnalytics;
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [joinedDebate, setJoinedDebate] = useState<Debate | null>(
    initialDebate || null
  );
  const [waitingState, setWaitingState] = useState<WaitingRoomState | null>(null);
  const navigateTriggeredRef = useRef(false);

  const loadWaitingContext = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent === true;

      try {
        if (silent) {
          setRefreshing(true);
        } else {
          setLoading(true);
        }

        setError(null);

        let debate = initialDebate || null;

        if (!debate) {
          const debates = await StudentService.getAvailableDebates({
            force: silent,
          });
          debate = sortJoinedDebates(debates)[0] ?? null;
        }

        if (debate?.id) {
          const needsParticipants =
            !Array.isArray(debate.participants) || debate.participants.length === 0;

          if (needsParticipants) {
            try {
              const participants = await StudentService.getDebateParticipants(
                debate.id
              );
              debate = {
                ...debate,
                participants,
              };
            } catch (participantError) {
              console.error(
                '[StudentOnboarding] Failed to load debate participants:',
                participantError
              );
            }
          }
        }

        setJoinedDebate(debate);
      } catch (loadError: any) {
        console.error('[StudentOnboarding] Failed to load waiting context:', loadError);
        setError(loadError?.message || '等待页加载失败，请稍后重试。');
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [initialDebate]
  );

  useEffect(() => {
    void loadWaitingContext();
  }, [loadWaitingContext]);

  usePageActivityRefresh(() => loadWaitingContext({ silent: true }), {
    enabled: !loading,
    intervalMs: 12000,
  });

  const roomId = joinedDebate?.id ?? null;
  const { isConnected, send, on, off } = useWebSocket(roomId, {
    onError: () => {
      setError((current) => current ?? '实时房间同步失败，请稍后刷新重试。');
    },
  });

  useEffect(() => {
    const handleStateUpdate = (data: Record<string, unknown>) => {
      const nextState = parseWaitingRoomState(data);
      if (nextState) {
        setWaitingState(nextState);
      }
    };

    on('state_update', handleStateUpdate);
    return () => {
      off('state_update', handleStateUpdate);
    };
  }, [off, on]);

  const assignedRole = joinedDebate?.role;
  const displayRole = isDebateRole(assignedRole) ? assignedRole : null;
  const participants = getHumanParticipants(joinedDebate?.participants);
  const fallbackParticipantCount = getParticipantCount(joinedDebate);
  const participantCount = getRealtimeParticipantCount(
    waitingState,
    fallbackParticipantCount
  );
  const myChecklist = getCurrentUserChecklist(waitingState, user?.id);
  const debateStarted =
    joinedDebate?.status === 'in_progress' || hasDebateStarted(waitingState);
  const readyCount = waitingState?.waiting_status?.ready_count ?? 0;
  const requiredCount = waitingState?.waiting_status?.required_count ?? 4;

  const handleChecklistToggle = useCallback(
    (index: number, checked: boolean) => {
      if (!displayRole || !user?.id) {
        return;
      }

      const nextItems = [...myChecklist];
      nextItems[index] = checked;

      setWaitingState((current) => {
        if (!current) {
          return current;
        }

        return {
          ...current,
          waiting_checklists: {
            ...(current.waiting_checklists || {}),
            [user.id]: {
              ...(current.waiting_checklists?.[user.id] || {
                completed_count: 0,
                ready: false,
              }),
              items: nextItems,
              completed_count: nextItems.filter(Boolean).length,
              ready: nextItems.every(Boolean),
              role: displayRole,
              name: user.name,
              online: true,
            },
          },
        };
      });

      send('waiting_checklist_update', { items: nextItems });
    },
    [displayRole, myChecklist, send, user?.id, user?.name]
  );

  useEffect(() => {
    if (!joinedDebate?.id || !debateStarted || navigateTriggeredRef.current) {
      return;
    }

    navigateTriggeredRef.current = true;
    onDebateStart?.(joinedDebate.id);
  }, [debateStarted, joinedDebate?.id, onDebateStart]);

  const rosterCards = useMemo(() => {
    const rosterByRole = new Map<string, DebateParticipant>();
    for (const participant of participants) {
      if (participant.role) {
        rosterByRole.set(participant.role, participant);
      }
    }

    return (Object.keys(roleLabel) as DebateRole[]).map((role) => {
      const participant = rosterByRole.get(role);
      const isMe = participant?.user_id === user?.id || joinedDebate?.role === role;

      return {
        role,
        participant,
        isMe,
      };
    });
  }, [joinedDebate?.role, participants, user?.id]);

  if (loading) {
    return (
      <div className="student-container flex min-h-[70vh] items-center justify-center py-10">
        <div className="student-card min-w-[280px] px-8 py-10 text-center">
          <Loader2 className="mx-auto mb-4 h-10 w-10 animate-spin text-slate-700" />
          <p className="text-slate-600">正在加载等待与准备页面...</p>
        </div>
      </div>
    );
  }

  if (!joinedDebate) {
    return (
      <div className="student-container py-8">
        <div className="mx-auto max-w-3xl">
          <div className="student-card px-8 py-10">
            <h1 className="text-[2rem] font-semibold tracking-[-0.04em] text-slate-900">
              还没有加入本场辩论
            </h1>
            <Button onClick={onBackToLogin} className="student-dark-button mt-6 h-auto">
              返回学生首页
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="student-container py-6 pb-14">
      {error ? (
        <div className="mb-6 max-w-md">
          <Alert variant="destructive" className="rounded-[18px]">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </div>
      ) : null}

      <section className="student-card px-5 py-6 md:px-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            {onBackToLogin ? (
              <Button
                variant="outline"
                size="sm"
                onClick={onBackToLogin}
                className="student-light-button h-auto px-4 py-2"
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                返回上一页
              </Button>
            ) : null}
            <h1 className="mt-4 max-w-2xl text-[1.95rem] font-semibold leading-[1.08] tracking-[-0.05em] text-slate-900 md:text-[2.3rem]">
              先确认你的辩位和参赛名单，四位辩手全部完成准备后会自动进入正式辩论。
            </h1>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge className="student-pill">邀请码 {joinedDebate.invitation_code}</Badge>
            <Badge className="student-pill">
              {debateStarted ? '比赛已启动' : '等待全员准备'}
            </Badge>
          </div>
        </div>
      </section>

      <main className="student-page-split mt-5 grid gap-5">
        <div className="space-y-5">
          <section className="student-card px-5 py-6 md:px-6">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <StatusCard
                title="我的辩位"
                value={displayRole ? roleLabel[displayRole] : '等待分配'}
                description={displayRole ? roleDescription[displayRole] : ''}
                icon={<ShieldCheck className="h-5 w-5 text-slate-700" />}
                tone="student-card-soft-blue"
              />
              <StatusCard
                title="在线人数"
                value={`${participantCount}/4`}
                description={isConnected ? '实时同步当前在线候场人数' : '正在连接房间实时状态'}
                icon={<Users className="h-5 w-5 text-slate-700" />}
                tone="student-card-soft-peach"
              />
              <StatusCard
                title="准备状态"
                value={debateStarted ? '已可进入比赛' : '等待全员准备'}
                description={
                  debateStarted
                    ? '四位辩手均已完成准备'
                    : '四位辩手全部准备完成后自动开赛'
                }
                icon={<Sparkles className="h-5 w-5 text-slate-700" />}
                tone="student-card-soft-lavender"
              />
            </div>
          </section>

          <DebateTopicCard debate={joinedDebate} />

          <section className="student-card px-5 py-6 md:px-6">
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {rosterCards.map(({ role, participant, isMe }, index) => (
                <div
                  key={role}
                  className={`${
                    isMe
                      ? 'student-card-soft-blue'
                      : index % 2 === 0
                        ? 'student-card-muted'
                        : 'student-card-soft-peach'
                  } p-4`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
                        辩位
                      </div>
                      <div className="mt-1.5 text-lg font-semibold tracking-[-0.03em] text-slate-900">
                        {roleLabel[role]}
                      </div>
                    </div>
                    {isMe ? <Badge className="student-pill">我的位置</Badge> : null}
                  </div>
                  <div className="mt-3 text-sm font-medium text-slate-900">
                    {participant?.name || '等待该辩位同学进入候场'}
                  </div>
                  <div className="mt-1.5 text-sm leading-7 text-slate-600">
                    {participant?.role_reason || roleDescription[role]}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>

        <div className="student-page-aside space-y-5">
          <section className="student-card px-5 py-6">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold tracking-[-0.03em] text-slate-900">
                  准备清单
                </h3>
                <p className="mt-1 text-sm text-slate-500">
                  四位辩手都完成全部勾选后，会自动进入比赛界面。
                </p>
              </div>
              <Badge className="student-pill">
                {myChecklist.filter(Boolean).length}/{readinessChecklist.length}
              </Badge>
            </div>
            <div className="mt-4 space-y-3">
              {readinessChecklist.map((item, index) => (
                <label
                  key={item}
                  className={`flex items-start gap-3 rounded-2xl border px-4 py-3 transition ${
                    displayRole
                      ? 'cursor-pointer border-slate-200 hover:border-slate-300'
                      : 'cursor-not-allowed border-slate-100 opacity-70'
                  }`}
                >
                  <Checkbox
                    checked={myChecklist[index]}
                    disabled={!displayRole}
                    onCheckedChange={(checked) =>
                      handleChecklistToggle(index, checked === true)
                    }
                    className="mt-1"
                  />
                  <span className="text-sm leading-7 text-slate-600">{item}</span>
                </label>
              ))}
            </div>
            <div className="mt-4 text-sm text-slate-500">
              当前已有 {readyCount}/{requiredCount} 位辩手完成全部准备。
            </div>
          </section>

          <section className="student-card-soft-lavender px-5 py-6">
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <Button
                className="student-dark-button h-auto w-full justify-center"
                disabled={!debateStarted}
                onClick={() => onDebateStart?.(joinedDebate.id)}
              >
                {debateStarted ? '进入正式辩论' : '等待四人全部准备完成'}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                className="student-light-button h-auto w-full justify-start"
                onClick={() => void loadWaitingContext({ silent: true })}
                disabled={refreshing}
              >
                {refreshing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Clock3 className="mr-2 h-4 w-4" />
                )}
                刷新当前状态
              </Button>
            </div>

            <div className="student-glass-divider mt-5 pt-5">
              <div className="flex items-center gap-3">
                <div className="student-icon-bubble h-11 w-11 bg-white">
                  <User className="h-5 w-5 text-slate-700" />
                </div>
                <div>
                  <div className="text-sm font-medium text-slate-900">
                    {user?.name || '学生'}
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
};

function StatusCard({
  title,
  value,
  description,
  icon,
  tone,
}: {
  title: string;
  value: string;
  description?: string;
  icon: React.ReactNode;
  tone: string;
}) {
  return (
    <div className={`${tone} p-5`}>
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-slate-500">
        {icon}
        <span>{title}</span>
      </div>
      <div className="mt-3 text-2xl font-semibold tracking-[-0.05em] text-slate-900">
        {value}
      </div>
      {description ? (
        <div className="mt-3 text-sm leading-7 text-slate-600">{description}</div>
      ) : null}
    </div>
  );
}

export default StudentOnboarding;
