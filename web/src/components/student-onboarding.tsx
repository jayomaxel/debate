import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
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
import DebateTopicCard from './debate-topic-card';
import WaitingStatusBar from './waiting-status-bar';
import StudentService from '@/services/student.service';
import type { Debate, DebateParticipant } from '@/services/student.service';
import { useAuth } from '@/store/auth.context';
import { usePageActivityRefresh } from '@/hooks/use-page-activity-refresh';

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
  debater_1: '负责立论陈词，先建立本方框架与价值主张。',
  debater_2: '负责攻辩推进，用问题和追击拆解对方论证。',
  debater_3: '负责质询与回应，在交锋里补强团队论证。',
  debater_4: '负责总结陈词，提炼全场优势并完成收束。',
};

const statusPriority: Record<Debate['status'], number> = {
  in_progress: 0,
  published: 1,
  draft: 2,
  completed: 3,
};

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

const readinessChecklist = [
  '确认你的辩位与本场辩题是否已经同步。',
  '阅读辩题背景资料，先整理 2 到 3 个核心论点。',
  '准备一组支持论据和至少一条对对方的预判反驳。',
  '检查麦克风、耳机和网络连接，正式开始后尽量不要离场。',
];

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
        setError(loadError?.message || '等待与准备页加载失败，请稍后重试。');
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

  const assignedRole = joinedDebate?.role;
  const displayRole = isDebateRole(assignedRole) ? assignedRole : null;
  const participants = getHumanParticipants(joinedDebate?.participants);
  const participantCount = getParticipantCount(joinedDebate);
  const canStartDebate =
    joinedDebate?.status === 'in_progress' ||
    (joinedDebate?.status === 'published' && !!displayRole);

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
          <p className="text-slate-600">正在加载等待与准备页...</p>
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
            <h1 className="mt-4 max-w-2xl text-[1.95rem] font-semibold leading-[1.08] tracking-[-0.05em] text-slate-900 md:text-[2.3rem]">
              在正式开赛前，把角色、名单和准备状态一次看清。
            </h1>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge className="student-pill">邀请码 {joinedDebate.invitation_code}</Badge>
            <Badge className="student-pill">
              {joinedDebate.status === 'in_progress' ? '已开赛' : '等待开赛'}
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
                title="人类参与者"
                value={`${participantCount}/4`}
                description=""
                icon={<Users className="h-5 w-5 text-slate-700" />}
                tone="student-card-soft-peach"
              />
              <StatusCard
                title="下一步"
                value={canStartDebate ? '进入正式辩论' : '继续等待与准备'}
                description=""
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
                    {participant?.name || '等待该辩位同步参与者'}
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
          <WaitingStatusBar
            hasAssignedRole={!!displayRole}
            participantCount={participantCount}
            isReady={canStartDebate}
          />

          <section className="student-card px-5 py-6">
            <div className="mt-4 space-y-3">
              {readinessChecklist.map((item, index) => (
                <div key={item} className="flex items-start gap-3">
                  <CheckCircle2
                    className={`mt-1 h-4 w-4 ${
                      index === 0 && displayRole ? 'text-emerald-600' : 'text-slate-300'
                    }`}
                  />
                  <span className="text-sm leading-7 text-slate-600">{item}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="student-card-soft-lavender px-5 py-6">
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <Button
                className="student-dark-button h-auto w-full justify-center"
                disabled={!canStartDebate}
                onClick={() => onDebateStart?.(joinedDebate.id)}
              >
                进入正式辩论
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
