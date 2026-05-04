import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  Bot,
  Loader2,
  Sparkles,
  Trophy,
  User,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useToast } from '@/hooks/use-toast';
import { useStudentAssessment } from '@/hooks/use-student-assessment';
import { usePageActivityRefresh } from '@/hooks/use-page-activity-refresh';
import StudentService from '@/services/student.service';
import { useAuth } from '@/store/auth.context';
import { useAppRouter } from '@/lib/router';
import {
  consumeAssessmentOnboardingPrompt,
  shouldShowAssessmentOnboardingPrompt,
} from '@/lib/student-assessment-onboarding';
import { formatDebateRole, formatStudentDate } from '@/lib/student-display';
import type { DebateHistoryItem } from '@/services/student.service';

type StudentAnalyticsTab = 'history' | 'growth' | 'comparison' | 'achievements';

interface StudentCommandCenterProps {
  studentName?: string;
  onViewReport?: (matchId: string) => void;
  onViewReplay?: (debateId: string) => void;
  onNavigateToAnalytics?: (tab?: StudentAnalyticsTab) => void;
  onNavigateToPreparation?: () => void;
  onNavigateToSettings?: (tab?: 'info' | 'password' | 'ability') => void;
}

const getHistoryOutcomeLabel = (item?: DebateHistoryItem | null) => {
  if (!item) {
    return '暂无结果';
  }

  switch (item.outcome) {
    case 'win':
      return '胜利';
    case 'lose':
      return '失利';
    case 'draw':
      return '平局';
    default:
      return '已完成';
  }
};

const StudentCommandCenter: React.FC<StudentCommandCenterProps> = ({
  studentName: propStudentName,
  onViewReport,
  onViewReplay,
  onNavigateToAnalytics,
  onNavigateToPreparation,
  onNavigateToSettings,
}) => {
  const { toast } = useToast();
  const { navigate } = useAppRouter();
  const { user } = useAuth();
  const studentName = propStudentName?.trim() || '同学';
  const welcomeName = studentName === '同学' ? studentName : `${studentName}同学`;
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [history, setHistory] = useState<DebateHistoryItem[]>([]);
  const [showAssessmentPrompt, setShowAssessmentPrompt] = useState(false);
  const {
    assessment,
    analytics,
    needsAssessment,
    loading: assessmentLoading,
  } = useStudentAssessment(true);
  const completedDebates = analytics?.completed_debates || 0;
  const averageScore = analytics?.average_score || 0;
  const totalDebates = analytics?.total_debates || 0;

  const loadCommandCenter = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent === true;

      try {
        if (silent) {
          setRefreshing(true);
        } else {
          setLoading(true);
        }

        const historyData = await StudentService.getHistory(8, 0);
        setHistory(historyData?.list || []);
      } catch (error: any) {
        console.error('[StudentCommandCenter] Failed to load data:', error);
        toast({
          variant: 'destructive',
          title: '加载失败',
          description: error?.message || '学生首页数据加载失败',
        });
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [toast]
  );

  useEffect(() => {
    void loadCommandCenter();
  }, [loadCommandCenter]);

  usePageActivityRefresh(() => loadCommandCenter({ silent: true }), {
    enabled: !loading,
    intervalMs: 15000,
  });

  useEffect(() => {
    if (assessmentLoading || !needsAssessment) {
      return;
    }

    const shouldShowPrompt = shouldShowAssessmentOnboardingPrompt(user, {
      needsAssessment,
      completedDebates,
    });

    if (!shouldShowPrompt) {
      return;
    }

    const promptKey = `assessment_prompt_dismissed:student-home:${user?.id || 'anonymous'}`;
    const dismissed = sessionStorage.getItem(promptKey) === '1';

    if (!dismissed) {
      setShowAssessmentPrompt(true);
    }
  }, [assessmentLoading, completedDebates, needsAssessment, user]);

  const dismissPrompt = () => {
    consumeAssessmentOnboardingPrompt(user);
    const promptKey = `assessment_prompt_dismissed:student-home:${user?.id || 'anonymous'}`;
    sessionStorage.setItem(promptKey, '1');
    setShowAssessmentPrompt(false);
  };

  const latestHistory = history[0] || null;

  const statusSummary = useMemo(() => {
    if (needsAssessment) {
      return { label: '待完成能力评估' };
    }

    return { label: '进入比赛区' };
  }, [needsAssessment]);

  const summaryTiles = [
    {
      label: '能力评估',
      value: needsAssessment ? '待完成' : '已完成',
      tone: 'student-card-soft-peach',
    },
    {
      label: '已完成正式辩论',
      value: `${completedDebates} 场`,
      tone: 'student-card-soft-blue',
    },
    {
      label: '累计参与',
      value: `${totalDebates} 场`,
      tone: 'student-card-soft-lavender',
    },
    {
      label: '平均得分',
      value: averageScore.toFixed(1),
      tone: 'student-card-muted',
    },
  ];

  if (assessment?.recommended_role) {
    summaryTiles.push({
      label: '推荐角色',
      value: formatDebateRole(assessment.recommended_role),
      tone: 'student-card-muted',
    });
  }

  if (loading || assessmentLoading) {
    return (
      <div className="student-container flex min-h-[70vh] items-center justify-center py-10">
        <div className="student-card min-w-[280px] px-8 py-10 text-center">
          <Loader2 className="mx-auto mb-4 h-10 w-10 animate-spin text-slate-700" />
          <p className="text-slate-600">正在加载学生首页...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="student-container py-6 pb-14">
      <Dialog
        open={showAssessmentPrompt}
        onOpenChange={(open) => {
          if (!open) {
            dismissPrompt();
            return;
          }

          setShowAssessmentPrompt(true);
        }}
      >
          <DialogContent className="rounded-[16px] border-[#d8cdbf] bg-[#fbf5ee]">
          <DialogHeader>
            <DialogTitle>先完成能力评估，再进入正式比赛流程</DialogTitle>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={dismissPrompt}
              className="student-light-button h-auto"
            >
              稍后评估
            </Button>
            <Button
              className="student-dark-button h-auto"
              onClick={() => {
                dismissPrompt();
                onNavigateToSettings?.('ability');
              }}
            >
              立即评估
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="student-page-split grid gap-5">
        <div className="space-y-5">
          <section className="student-card relative overflow-hidden px-5 py-6 md:px-6">
            <div className="grid gap-5 lg:grid-cols-[1.05fr,0.95fr] xl:grid-cols-[minmax(0,1.05fr),minmax(280px,0.95fr)]">
              <div className="space-y-4">
                <div>
                  <h1 className="student-section-title">
                    欢迎回来，{welcomeName}
                  </h1>
                </div>
                <div className="flex flex-wrap gap-3">
                  {needsAssessment ? (
                    <Button
                      className="student-dark-button h-auto"
                      onClick={() => onNavigateToSettings?.('ability')}
                    >
                      现在去评估
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                  ) : (
                    <Button
                      className="student-dark-button h-auto"
                      onClick={() => navigate('/student/competition')}
                    >
                      前往比赛区
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    className="student-light-button h-auto"
                    onClick={() => onNavigateToPreparation?.()}
                  >
                    打开备赛区
                  </Button>
                </div>
              </div>

              <div className="student-card-soft-blue p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="mt-2.5 text-[1.65rem] font-semibold tracking-[-0.04em] text-slate-900">
                      {statusSummary.label}
                    </div>
                  </div>
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="student-card-muted p-4">
                    <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
                      已完成正式辩论
                    </div>
                    <div className="mt-1.5 text-[1.85rem] font-semibold tracking-[-0.04em] text-slate-900">
                      {completedDebates}
                    </div>
                  </div>
                  <div className="student-card-muted p-4">
                    <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
                      平均得分
                    </div>
                    <div className="mt-1.5 text-[1.85rem] font-semibold tracking-[-0.04em] text-slate-900">
                      {averageScore.toFixed(1)}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="student-card px-5 py-6 md:px-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="mt-3 text-[1.6rem] font-semibold tracking-[-0.04em] text-slate-900">
                  最近一场辩论
                </h2>
              </div>
              <Button
                variant="outline"
                className="student-light-button h-auto"
                onClick={() => onNavigateToAnalytics?.('history')}
              >
                打开成长区
              </Button>
            </div>

            <div className="mt-5">
              {latestHistory ? (
                <div className="student-card-soft-peach p-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="max-w-2xl">
                      <div className="text-sm uppercase tracking-[0.18em] text-slate-500">
                        最近一场
                      </div>
                      <div className="mt-2.5 text-[1.6rem] font-semibold tracking-[-0.04em] text-slate-900">
                        {latestHistory.topic}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Badge className="student-pill">
                          {getHistoryOutcomeLabel(latestHistory)}
                        </Badge>
                        <Badge className="student-pill">
                          {formatDebateRole(latestHistory.role)}
                        </Badge>
                        <Badge className="student-pill">
                          {formatStudentDate(latestHistory.created_at) || '-'}
                        </Badge>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-3">
                      <Button
                        variant="outline"
                        className="student-light-button h-auto"
                        onClick={() => onViewReport?.(latestHistory.debate_id)}
                      >
                        查看报告
                      </Button>
                      <Button
                        variant="outline"
                        className="student-light-button h-auto"
                        onClick={() => onViewReplay?.(latestHistory.debate_id)}
                      >
                        查看回放
                      </Button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="student-dashed-card px-5 py-10 text-center text-slate-500">
                  还没有历史辩论结果。
                </div>
              )}
            </div>
          </section>
        </div>

        <div className="student-page-aside space-y-5">
          <section className="student-card px-5 py-6">
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {summaryTiles.map((item) => (
                <StatusItem key={item.label} label={item.label} value={item.value} tone={item.tone} />
              ))}
            </div>
          </section>

          <section className="student-card px-5 py-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="mt-3 text-[1.6rem] font-semibold tracking-[-0.04em] text-slate-900">
                  去你现在需要的地方
                </h2>
              </div>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <QuickLink
                icon={<Bot className="h-4 w-4" />}
                title="备赛区"
                tone="student-card-soft-blue"
                onClick={() => onNavigateToPreparation?.()}
              />
              <QuickLink
                icon={<Trophy className="h-4 w-4" />}
                title="成长区"
                tone="student-card-soft-lavender"
                onClick={() => onNavigateToAnalytics?.('history')}
              />
              <Button
                variant="outline"
                onClick={() => void loadCommandCenter({ silent: true })}
                disabled={refreshing}
                className="student-light-button h-auto w-full justify-start sm:col-span-2"
              >
                {refreshing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="mr-2 h-4 w-4" />
                )}
                刷新首页摘要
              </Button>
            </div>
          </section>

        </div>
      </div>
    </div>
  );
};

function StatusItem({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: string;
}) {
  return (
    <div className={`${tone} p-4`}>
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-2 text-[1.45rem] font-semibold tracking-[-0.04em] text-slate-900">
        {value}
      </div>
    </div>
  );
}

function QuickLink({
  icon,
  title,
  onClick,
  tone,
}: {
  icon: React.ReactNode;
  title: string;
  onClick: () => void;
  tone: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`${tone} w-full p-4 text-left transition-colors duration-150 hover:border-[#b8a891] hover:bg-white/82`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 text-slate-900">
          <div className="student-icon-bubble h-10 w-10">{icon}</div>
          <span className="font-medium">{title}</span>
        </div>
        <ArrowRight className="h-4 w-4 text-slate-500" />
      </div>
    </button>
  );
}

export default StudentCommandCenter;
