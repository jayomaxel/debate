import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  Loader2,
  ShieldCheck,
  Sparkles,
  Swords,
  Users,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { useStudentAssessment } from '@/hooks/use-student-assessment';
import { usePageActivityRefresh } from '@/hooks/use-page-activity-refresh';
import StudentService from '@/services/student.service';
import type { Debate } from '@/services/student.service';

interface StudentCompetitionHubProps {
  onNavigateToWaiting?: () => void;
  onNavigateToSettings?: (tab?: 'info' | 'password' | 'ability') => void;
  onNavigateToPostMatch?: (debateId: string) => void;
}

const roleLabelMap = {
  debater_1: '一辩',
  debater_2: '二辩',
  debater_3: '三辩',
  debater_4: '四辩',
} as const;

const sortJoinedDebates = (debates: Debate[]) =>
  debates
    .filter((debate) => debate.is_joined)
    .slice()
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));

const getStatusLabel = (status?: Debate['status']) => {
  switch (status) {
    case 'published':
      return '等待开赛';
    case 'in_progress':
      return '进行中';
    case 'completed':
      return '已结束';
    case 'draft':
      return '草稿中';
    default:
      return '未加入';
  }
};

export default function StudentCompetitionHub({
  onNavigateToWaiting,
  onNavigateToSettings,
  onNavigateToPostMatch,
}: StudentCompetitionHubProps) {
  const { toast } = useToast();
  const { needsAssessment, loading: assessmentLoading } =
    useStudentAssessment(true);
  const [invitationCode, setInvitationCode] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [joining, setJoining] = useState(false);
  const [joinedDebate, setJoinedDebate] = useState<Debate | null>(null);

  const loadCompetitionContext = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent === true;

      try {
        if (silent) {
          setRefreshing(true);
        } else {
          setLoading(true);
        }

        const debates = await StudentService.getAvailableDebates({
          force: silent,
        }).catch(() => []);

        setJoinedDebate(sortJoinedDebates(debates)[0] || null);
      } catch (error: any) {
        console.error('[StudentCompetitionHub] Failed to load data:', error);
        if (!silent) {
          toast({
            variant: 'destructive',
            title: '加载失败',
            description: error?.message || '比赛区数据加载失败',
          });
        }
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [toast]
  );

  useEffect(() => {
    void loadCompetitionContext();
  }, [loadCompetitionContext]);

  usePageActivityRefresh(() => loadCompetitionContext({ silent: true }), {
    enabled: !loading,
    intervalMs: 12000,
  });

  const canJoin = !needsAssessment;
  const actionTitle = useMemo(() => {
    if (needsAssessment) {
      return '先完成能力评估';
    }

    if (joinedDebate?.status === 'completed') {
      return '查看赛后分析';
    }

    if (joinedDebate) {
      return '继续比赛流程';
    }

    return '加入本场辩论';
  }, [joinedDebate, needsAssessment]);

  const actionDescription = useMemo(() => {
    if (needsAssessment) {
      return '';
    }

    if (joinedDebate?.status === 'completed') {
      return '';
    }

    if (joinedDebate) {
      return '';
    }

    return '';
  }, [joinedDebate, needsAssessment]);

  const handleJoinDebate = async () => {
    if (!canJoin) {
      toast({
        variant: 'destructive',
        title: '请先完成能力评估',
        description: '完成评估后，比赛区入口才会解锁。',
      });
      onNavigateToSettings?.('ability');
      return;
    }

    if (invitationCode.trim().length !== 6) {
      toast({
        variant: 'destructive',
        title: '邀请码格式不正确',
        description: '请输入 6 位邀请码。',
      });
      return;
    }

    try {
      setJoining(true);
      const debate = await StudentService.joinDebate({
        invitation_code: invitationCode.trim(),
      });
      setJoinedDebate(debate);
      setInvitationCode('');
      onNavigateToWaiting?.();
    } catch (error: any) {
      toast({
        variant: 'destructive',
        title: '加入失败',
        description: error?.message || '加入本场辩论失败',
      });
    } finally {
      setJoining(false);
    }
  };

  if (loading || assessmentLoading) {
    return (
      <div className="student-container flex min-h-[70vh] items-center justify-center py-10">
        <div className="student-card min-w-[280px] px-8 py-10 text-center">
          <Loader2 className="mx-auto mb-4 h-10 w-10 animate-spin text-slate-700" />
          <p className="text-slate-600">正在加载比赛区...</p>
        </div>
      </div>
    );
  }

  return (
      <div className="student-container py-6 pb-14">
      <div className="student-page-split grid gap-5">
        <section className="student-card px-5 py-6 md:px-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-2xl">
              <div className="student-kicker">
                <Swords className="h-4 w-4" />
                比赛区
              </div>
              <h1 className="mt-4 text-[2rem] font-semibold leading-[1.06] tracking-[-0.05em] text-slate-900 md:text-[2.35rem]">
                {actionTitle}
              </h1>
            </div>
          </div>

          <div className="mt-6">
            {!canJoin ? (
              <div className="student-card-soft-peach p-5">
                <div className="flex items-start gap-4">
                  <div className="student-icon-bubble h-12 w-12 bg-white text-slate-900">
                    <ShieldCheck className="h-5 w-5 text-amber-700" />
                  </div>
                  <div className="space-y-3">
                    <div className="text-lg font-semibold tracking-[-0.03em] text-slate-900">
                      能力评估尚未完成
                    </div>
                    <Button
                      onClick={() => onNavigateToSettings?.('ability')}
                      className="student-dark-button h-auto"
                    >
                      现在去评估
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ) : joinedDebate ? (
              <div className="student-card-soft-blue p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="mt-2.5 text-[1.6rem] font-semibold tracking-[-0.04em] text-slate-900">
                      {joinedDebate.topic}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Badge className="student-pill">
                        邀请码 {joinedDebate.invitation_code}
                      </Badge>
                      <Badge className="student-pill">
                        {getStatusLabel(joinedDebate.status)}
                      </Badge>
                      {joinedDebate.role ? (
                        <Badge className="student-pill">
                          {roleLabelMap[joinedDebate.role]}
                        </Badge>
                      ) : null}
                    </div>
                  </div>
                </div>

                <div className="mt-5">
                  {joinedDebate.status === 'completed' ? (
                    <Button
                      onClick={() => onNavigateToPostMatch?.(joinedDebate.id)}
                      className="student-dark-button h-auto"
                    >
                      进入赛后分析页
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                  ) : (
                    <Button
                      onClick={onNavigateToWaiting}
                      className="student-dark-button h-auto"
                    >
                      进入等待与准备页
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            ) : (
              <div className="student-card-soft-lavender p-5">
                <div className="max-w-lg">
                  <div className="mt-2.5 text-lg font-semibold tracking-[-0.03em] text-slate-900">
                    用 6 位邀请码加入本场辩论
                  </div>
                </div>

                <div className="mt-5 space-y-3">
                  <Input
                    value={invitationCode}
                    onChange={(event) =>
                      setInvitationCode(event.target.value.trim().toUpperCase())
                    }
                    placeholder="例如 ABC123"
                    maxLength={6}
                    className="h-14 rounded-[16px] border-black/10 bg-white/85 text-center font-mono text-lg tracking-[0.25em] text-slate-900"
                  />
                  <Button
                    onClick={handleJoinDebate}
                    disabled={joining}
                    className="student-dark-button h-auto w-full justify-center"
                  >
                    {joining ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        正在加入...
                      </>
                    ) : (
                      <>
                        加入本场辩论
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </>
                    )}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </section>

        <div className="student-page-aside space-y-5">
          <section className="student-card px-5 py-6">
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <StatusItem
                icon={<Sparkles className="h-4 w-4 text-slate-700" />}
                label="能力评估"
                value={canJoin ? '已完成' : '待完成'}
                tone={canJoin ? 'student-card-soft-blue' : 'student-card-soft-peach'}
              />
              <StatusItem
                icon={<Users className="h-4 w-4 text-slate-700" />}
                label="比赛状态"
                value={joinedDebate ? getStatusLabel(joinedDebate.status) : '未加入'}
                tone="student-card-muted"
              />
              <Button
                variant="outline"
                onClick={() => void loadCompetitionContext({ silent: true })}
                disabled={refreshing}
                className="student-light-button h-auto justify-start"
              >
                {refreshing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="mr-2 h-4 w-4" />
                )}
                刷新比赛状态
              </Button>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function StatusItem({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone: string;
}) {
  return (
    <div className={`${tone} p-5`}>
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-slate-500">
        {icon}
        <span>{label}</span>
      </div>
      <div className="mt-3 text-2xl font-semibold tracking-[-0.05em] text-slate-900">
        {value}
      </div>
    </div>
  );
}
