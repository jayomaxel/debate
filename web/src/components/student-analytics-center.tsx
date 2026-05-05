import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  BarChart3,
  Brain,
  CheckCircle,
  Clock,
  Heart,
  History,
  Loader2,
  Lock,
  RefreshCw,
  Star,
  Target,
  TrendingUp,
  Trophy,
  Users,
  Zap,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useAuth } from '@/store/auth.context';
import { useToast } from '@/hooks/use-toast';
import { usePageActivityRefresh } from '@/hooks/use-page-activity-refresh';
import StudentService from '@/services/student.service';
import type {
  Achievement,
  ClassComparison,
  DebateHistoryItem,
  StudentAnalytics,
} from '@/services/student.service';
import DebateHistoryRecords from '@/components/debate-history-records';
import AbilityRadarChart from '@/components/ability-radar-chart';
import {
  formatDebateRole,
  formatDebateStatus,
  formatDebateStance,
  formatStudentDate,
  formatStudentDateTime,
  formatStudentMonthDay,
} from '@/lib/student-display';

interface StudentAnalyticsCenterProps {
  onBack?: () => void;
  onViewReport?: (debateId: string) => void;
  onViewReplay?: (debateId: string) => void;
  defaultTab?: MenuTab;
}

type MenuTab = 'history' | 'growth' | 'comparison' | 'achievements';

const comparisonMetricOptions = [
  { value: 'overall', label: '综合得分' },
  { value: 'logic', label: '逻辑建构能力' },
  { value: 'argument', label: 'AI 核心知识运用' },
  { value: 'response', label: '批判性思维' },
  { value: 'persuasion', label: '语言表达能力' },
  { value: 'teamwork', label: 'AI 伦理与科技素养' },
];

const StudentAnalyticsCenter: React.FC<StudentAnalyticsCenterProps> = ({
  onBack,
  onViewReport,
  onViewReplay,
  defaultTab = 'history',
}) => {
  const { user } = useAuth();
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<MenuTab>(defaultTab);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [analytics, setAnalytics] = useState<StudentAnalytics | null>(null);
  const [history, setHistory] = useState<DebateHistoryItem[]>([]);
  const [growthTrend, setGrowthTrend] = useState<any[]>([]);
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [comparison, setComparison] = useState<ClassComparison | null>(null);
  const [comparisonMetric, setComparisonMetric] = useState<string>('overall');
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [comparisonNotice, setComparisonNotice] = useState('');
  const [checkingAchievements, setCheckingAchievements] = useState(false);
  const [recentlyUnlockedAchievementIds, setRecentlyUnlockedAchievementIds] =
    useState<string[]>([]);
  const achievementsAutoCheckedRef = useRef(false);

  const isMissingClassError = (error: any) => {
    const message = String(error?.message || error?.detail || '');
    return message.includes('未加入班级');
  };

  const loadBaseData = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent === true;

      try {
        if (silent) {
          setRefreshing(true);
        } else {
          setLoading(true);
        }

        const [
          analyticsResult,
          historyResult,
          growthResult,
          achievementsResult,
        ] = await Promise.allSettled([
          StudentService.getAnalytics(),
          StudentService.getHistory(20, 0),
          StudentService.getGrowthTrend(10),
          StudentService.getAchievements(),
        ]);

        if (analyticsResult.status === 'fulfilled') {
          setAnalytics(analyticsResult.value);
        } else if (!silent) {
          toast({
            variant: 'destructive',
            title: '加载失败',
            description:
              (analyticsResult.reason as any)?.message || '加载统计数据失败',
          });
        }

        if (historyResult.status === 'fulfilled') {
          setHistory(historyResult.value?.list || []);
        } else if (!silent) {
          toast({
            variant: 'destructive',
            title: '加载失败',
            description:
              (historyResult.reason as any)?.message || '加载历史记录失败',
          });
        }

        if (growthResult.status === 'fulfilled') {
          setGrowthTrend(growthResult.value?.debates || []);
        }

        if (achievementsResult.status === 'fulfilled') {
          setAchievements(achievementsResult.value || []);
        }
      } catch (error: any) {
        console.error('[StudentAnalyticsCenter] Failed to load base data:', error);
        if (!silent) {
          toast({
            variant: 'destructive',
            title: '加载失败',
            description: error?.message || '加载成长区数据失败',
          });
        }
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [toast]
  );

  const loadComparison = useCallback(
    async (metric: string, options?: { silent?: boolean }) => {
      const silent = options?.silent === true;

      try {
        setComparisonLoading(true);
        setComparisonNotice('');
        const data = await StudentService.getClassComparison({ metric, top: 10 });
        setComparison(data);
      } catch (error: any) {
        setComparison(null);
        if (isMissingClassError(error)) {
          setComparisonNotice('你还没有加入班级');
          return;
        }
        if (!silent) {
          toast({
            variant: 'destructive',
            title: '加载失败',
            description: error?.message || '加载对比分析失败',
          });
        }
      } finally {
        setComparisonLoading(false);
      }
    },
    [toast]
  );

  useEffect(() => {
    void loadBaseData();
  }, [loadBaseData]);

  useEffect(() => {
    void loadComparison(comparisonMetric);
  }, [comparisonMetric, loadComparison]);

  useEffect(() => {
    setActiveTab(defaultTab);
  }, [defaultTab]);

  usePageActivityRefresh(
    async () => {
      await loadBaseData({ silent: true });
      if (activeTab === 'comparison') {
        await loadComparison(comparisonMetric, { silent: true });
      }
    },
    {
      enabled: !loading,
      intervalMs: 15000,
    }
  );

  const handleCheckAchievements = async () => {
    try {
      setCheckingAchievements(true);
      const result = await StudentService.checkAchievements();

      if (result.count > 0) {
        setRecentlyUnlockedAchievementIds(
          result.newly_unlocked.map((achievement) => achievement.id)
        );
        toast({
          title: '成就已更新',
          description: `新解锁 ${result.count} 个成就。`,
        });
      } else {
        toast({
          title: '暂无新成就',
          description: '继续参与辩论，新的成就会在这里出现。',
        });
      }

      const updatedAchievements = await StudentService.getAchievements();
      setAchievements(updatedAchievements || []);

      if (result.count > 0) {
        window.setTimeout(() => {
          setRecentlyUnlockedAchievementIds([]);
        }, 1600);
      }
    } catch (error: any) {
      toast({
        variant: 'destructive',
        title: '检查失败',
        description: error?.message || '检查成就失败',
      });
    } finally {
      setCheckingAchievements(false);
    }
  };

  useEffect(() => {
    if (activeTab !== 'achievements' || achievementsAutoCheckedRef.current) {
      return;
    }

    achievementsAutoCheckedRef.current = true;

    (async () => {
      try {
        setCheckingAchievements(true);
        const result = await StudentService.checkAchievements();
        if (result.count > 0) {
          const updatedAchievements = await StudentService.getAchievements();
          setAchievements(updatedAchievements || []);
        }
      } catch (error) {
        console.error(
          '[StudentAnalyticsCenter] Auto check achievements failed:',
          error
        );
      } finally {
        setCheckingAchievements(false);
      }
    })();
  }, [activeTab]);

  const menuItems = [
    {
      id: 'history' as MenuTab,
      icon: <History className="h-5 w-5" />,
      label: '历史记录',
      desc: '查看历次辩论',
      tone: 'student-card-soft-blue',
    },
    {
      id: 'growth' as MenuTab,
      icon: <TrendingUp className="h-5 w-5" />,
      label: '成长趋势',
      desc: '关注能力变化',
      tone: 'student-card-soft-peach',
    },
    {
      id: 'comparison' as MenuTab,
      icon: <Users className="h-5 w-5" />,
      label: '同班对比',
      desc: '查看班级参照',
      tone: 'student-card-soft-lavender',
    },
    {
      id: 'achievements' as MenuTab,
      icon: <Trophy className="h-5 w-5" />,
      label: '成就',
      desc: '查看里程碑与徽章',
      tone: 'student-card-soft-peach',
    },
  ];

  const renderHistory = () => (
    <DebateHistoryRecords
      history={history}
      onSelect={(debateId) => onViewReport?.(debateId)}
      onReplay={(debateId) => onViewReplay?.(debateId)}
    />
  );

  const renderGrowth = () => (
    <div className="space-y-6">
      <section className="student-card px-5 py-6">
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <SummaryCard
            icon={<BarChart3 className="h-6 w-6 text-slate-700" />}
            value={analytics?.average_score?.toFixed(1) || '0'}
            label="平均得分"
            tone="student-card-soft-blue"
          />
          <SummaryCard
            icon={<TrendingUp className="h-6 w-6 text-slate-700" />}
            value={String(analytics?.completed_debates || 0)}
            label="完成场次"
            tone="student-card-soft-peach"
          />
          <SummaryCard
            icon={<Clock className="h-6 w-6 text-slate-700" />}
            value={String(analytics?.total_debates || 0)}
            label="累计参与"
            tone="student-card-soft-lavender"
          />
        </div>
      </section>

      <section className="student-card px-5 py-6">
        <h3 className="mt-3 text-[1.6rem] font-semibold tracking-[-0.04em] text-slate-900">
          得分趋势
        </h3>
        <p className="mt-1.5 text-sm leading-7 text-slate-600">
          观察你最近几场辩论的能力变化和得分波动。
        </p>

        <div className="mt-5">
          {growthTrend.length > 0 ? (
            <div className="space-y-4">
              {growthTrend.map((item, index) => (
                <div key={`${item.date}-${index}`} className="space-y-2">
                  <div className="flex items-center justify-between gap-4 text-sm text-slate-600">
                    <span>
                      {formatStudentMonthDay(item.date) || '-'}
                    </span>
                    <span className="font-medium text-slate-900">{item.score}</span>
                  </div>
                  <div className="h-10 overflow-hidden rounded-full bg-[#f5efe8]">
                    <div
                      className="flex h-full items-center justify-end rounded-full bg-[#1b2436] pr-4 text-sm font-medium text-white transition-all"
                      style={{ width: `${Math.max(8, item.score)}%` }}
                    >
                      {item.score}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<TrendingUp className="h-16 w-16 text-slate-300" />}
              title="暂无成长数据"
              description=""
            />
          )}
        </div>
      </section>
    </div>
  );

  const renderComparison = () => (
    <div className="space-y-6">
      <section className="student-card px-5 py-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="mt-3 text-[1.6rem] font-semibold tracking-[-0.04em] text-slate-900">
              班级排名与平均差距
            </h3>
          </div>
          <div className="flex items-center gap-3">
            <Select value={comparisonMetric} onValueChange={setComparisonMetric}>
              <SelectTrigger className="h-10 w-[190px] rounded-[10px] border-black/10 bg-white/80">
                <SelectValue placeholder="选择指标" />
              </SelectTrigger>
              <SelectContent>
                {comparisonMetricOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              className="student-light-button h-auto"
              onClick={() => void loadComparison(comparisonMetric)}
              disabled={comparisonLoading}
            >
              {comparisonLoading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              刷新
            </Button>
          </div>
        </div>
      </section>

      {comparisonLoading ? (
        <section className="student-card px-6 py-16 text-center">
          <Loader2 className="mx-auto mb-4 h-10 w-10 animate-spin text-slate-700" />
          <p className="text-slate-600">正在加载同班对比...</p>
        </section>
      ) : comparisonNotice ? (
        <EmptyState
          icon={<Users className="h-16 w-16 text-amber-400" />}
          title={comparisonNotice}
          description=""
        />
      ) : !comparison || comparison.sample_size === 0 ? (
        <EmptyState
          icon={<Users className="h-16 w-16 text-[#d1a37b]" />}
          title="暂无可对比数据"
          description=""
        />
      ) : (
        <div className="space-y-6">
          <section className="grid gap-4 md:grid-cols-4">
            <SummaryCard
              icon={<Trophy className="h-6 w-6 text-slate-700" />}
              value={comparison.my?.rank ? `#${comparison.my.rank}` : '-'}
              label="班级排名"
              tone="student-card-soft-blue"
            />
            <SummaryCard
              icon={<Star className="h-6 w-6 text-slate-700" />}
              value={
                comparison.my?.percentile === null ||
                comparison.my?.percentile === undefined
                  ? '-'
                  : `${comparison.my.percentile}%`
              }
              label="领先百分位"
              tone="student-card-soft-peach"
            />
            <SummaryCard
              icon={<BarChart3 className="h-6 w-6 text-slate-700" />}
              value={comparison.my?.score?.toFixed(1) || '0'}
              label="我的当前指标"
              tone="student-card-soft-lavender"
            />
            <SummaryCard
              icon={<Users className="h-6 w-6 text-slate-700" />}
              value={comparison.class_avg?.score?.toFixed(1) || '0'}
              label={`班级平均（${comparison.sample_size} 人）`}
              tone="student-card-muted"
            />
          </section>

          <AbilityRadarChart
            title="五维能力对比（我 vs 班级平均）"
            showComparison
            studentMode
            comparisonScores={[
              comparison.class_avg?.ability_scores.logic || 0,
              comparison.class_avg?.ability_scores.argument || 0,
              comparison.class_avg?.ability_scores.response || 0,
              comparison.class_avg?.ability_scores.persuasion || 0,
              comparison.class_avg?.ability_scores.teamwork || 0,
            ]}
            scores={[
              {
                dimension: '逻辑建构能力',
                score: comparison.my?.ability_scores.logic || 0,
                icon: <Brain className="h-4 w-4" />,
                description: '观点结构、推理链条与论证严密度。',
                color: 'text-[#8a5a36]',
              },
              {
                dimension: 'AI 核心知识运用',
                score: comparison.my?.ability_scores.argument || 0,
                icon: <Target className="h-4 w-4" />,
                description: '知识点、案例与课程概念的调用能力。',
                color: 'text-emerald-600',
              },
              {
                dimension: '批判性思维',
                score: comparison.my?.ability_scores.response || 0,
                icon: <Zap className="h-4 w-4" />,
                description: '识别漏洞、质疑论证并展开反驳的能力。',
                color: 'text-amber-600',
              },
              {
                dimension: '语言表达能力',
                score: comparison.my?.ability_scores.persuasion || 0,
                icon: <Heart className="h-4 w-4" />,
                description: '表达清晰度、感染力和说服效果。',
                color: 'text-rose-600',
              },
              {
                dimension: 'AI 伦理与科技素养',
                score: comparison.my?.ability_scores.teamwork || 0,
                icon: <Users className="h-4 w-4" />,
                description: '对技术边界、伦理风险与社会影响的综合判断。',
                color: 'text-[#8b82b4]',
              },
            ]}
          />

          <section className="student-card px-5 py-6">
            <div className="flex items-center justify-between gap-3">
              <Badge className="student-pill">Top {comparison.leaderboard.length}</Badge>
            </div>

            <div className="mt-4 space-y-3">
              {comparison.leaderboard.map((item, index) => {
                const isMe = item.student_id === user?.id;
                const tone =
                  index === 0
                    ? 'student-card-soft-peach'
                    : index === 1
                    ? 'student-card-soft-blue'
                    : index === 2
                    ? 'student-card-soft-lavender'
                    : 'student-card-muted';

                return (
                  <div
                    key={item.student_id}
                    className={`${isMe ? 'student-card-soft-blue' : tone} flex items-center justify-between gap-4 p-4`}
                  >
                    <div className="flex items-center gap-4">
                      <div className="student-icon-bubble h-10 w-10 bg-white text-sm font-semibold text-slate-900">
                        {item.rank}
                      </div>
                      <div>
                        <div className="flex items-center gap-2 font-semibold text-slate-900">
                          <span>{item.student_name}</span>
                          {isMe ? <Badge className="student-pill">我</Badge> : null}
                        </div>
                        <div className="text-xs text-slate-500">
                          综合均分 {item.overall_score.toFixed(1)}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-semibold tracking-[-0.03em] text-slate-900">
                        {item.score.toFixed(1)}
                      </div>
                      <div className="text-xs text-slate-500">当前指标</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        </div>
      )}
    </div>
  );

  const renderAchievements = () => {
    const unlockedAchievements = achievements.filter((item) => item.unlocked);
    const lockedAchievements = achievements.filter((item) => !item.unlocked);

    return (
      <div className="space-y-6">
        <section className="student-card px-5 py-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="mt-3 text-[1.6rem] font-semibold tracking-[-0.04em] text-slate-900">
                成就与进度
              </h3>
            </div>
            <div className="flex items-center gap-3">
              <Badge className="student-pill">
                {unlockedAchievements.length} / {achievements.length} 已解锁
              </Badge>
              <Button
                variant="outline"
                className="student-light-button h-auto"
                onClick={handleCheckAchievements}
                disabled={checkingAchievements}
              >
                {checkingAchievements ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Star className="mr-2 h-4 w-4" />
                )}
                检查新成就
              </Button>
            </div>
          </div>
        </section>

        {unlockedAchievements.length > 0 ? (
          <section className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {unlockedAchievements.map((achievement) => {
                const isNewlyUnlocked = recentlyUnlockedAchievementIds.includes(
                  achievement.id
                );

                return (
                  <Card
                    key={achievement.id}
                    className={`overflow-hidden rounded-[16px] border border-[#ece4da] bg-[#fbf7f2] shadow-[0_14px_34px_rgba(174,154,126,0.08)] ${
                      isNewlyUnlocked ? 'ring-2 ring-[#efd2bc]' : ''
                    }`}
                  >
                    <CardContent className="p-5">
                      <div className="flex items-start gap-4">
                        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#1b2436] text-white">
                          <Trophy className="h-5 w-5" />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-start justify-between gap-3">
                            <h5 className="font-semibold text-slate-900">
                              {achievement.name}
                            </h5>
                            <Badge className="student-pill">已解锁</Badge>
                          </div>
                          <p className="mt-2 text-sm leading-7 text-slate-600">
                            {achievement.description}
                          </p>
                          {achievement.unlocked_at ? (
                            <p className="mt-3 text-xs text-slate-500">
                              解锁于{' '}
                              {formatStudentDate(achievement.unlocked_at)}
                            </p>
                          ) : null}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </section>
        ) : null}

        {lockedAchievements.length > 0 ? (
          <section className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {lockedAchievements.map((achievement) => (
                <Card
                  key={achievement.id}
                  className="rounded-[16px] border border-[#ece4da] bg-white/82 opacity-90 shadow-[0_10px_24px_rgba(174,154,126,0.05)]"
                >
                  <CardContent className="p-5">
                    <div className="flex items-start gap-4">
                      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-200 text-slate-500">
                        <Lock className="h-5 w-5" />
                      </div>
                      <div className="flex-1">
                        <h5 className="font-semibold text-slate-700">
                          {achievement.name}
                        </h5>
                        <p className="mt-2 text-sm leading-7 text-slate-500">
                          {achievement.description}
                        </p>
                        {achievement.progress !== undefined &&
                        achievement.target !== undefined ? (
                          <div className="mt-4">
                            <div className="mb-1 flex items-center justify-between text-xs text-slate-600">
                              <span>进度</span>
                              <span>
                                {achievement.progress} / {achievement.target}
                              </span>
                            </div>
                            <div className="h-2 overflow-hidden rounded-full bg-slate-200">
                              <div
                                className="h-full rounded-full bg-[#1b2436]"
                                style={{
                                  width: `${Math.min(
                                    100,
                                    (achievement.progress / achievement.target) * 100
                                  )}%`,
                                }}
                              />
                            </div>
                          </div>
                        ) : null}
                        {achievement.unlock_hint ? (
                          <div className="mt-3 text-xs text-slate-600">
                            {achievement.unlock_hint}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>
        ) : null}

        {achievements.length === 0 ? (
          <EmptyState
            icon={<Trophy className="h-16 w-16 text-slate-300" />}
            title="暂无成就数据"
            description=""
          />
        ) : null}
      </div>
    );
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'history':
        return renderHistory();
      case 'growth':
        return renderGrowth();
      case 'comparison':
        return renderComparison();
      case 'achievements':
        return renderAchievements();
      default:
        return null;
    }
  };

  if (loading) {
    return (
      <div className="student-container flex min-h-[70vh] items-center justify-center py-10">
        <div className="student-card min-w-[280px] px-8 py-10 text-center">
          <Loader2 className="mx-auto mb-4 h-10 w-10 animate-spin text-slate-700" />
          <p className="text-slate-600">正在加载成长区...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="student-container py-6 pb-14">
      <div className="mt-5 grid gap-5 xl:grid-cols-[240px,minmax(0,1fr)]">
        <aside className="student-card h-fit px-3.5 py-3.5 xl:sticky xl:top-28">
          <div className="space-y-2">
            {menuItems.map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full rounded-[12px] p-3.5 text-left transition-colors duration-150 ${
                  activeTab === item.id ? 'student-sidebar-tab-active' : 'student-card-muted'
                }`}
              >
                  <div className="flex items-start gap-3">
                    <div className="student-icon-bubble h-10 w-10 bg-white text-slate-900">
                      {item.icon}
                    </div>
                    <div>
                      <div className="font-medium text-slate-900">{item.label}</div>
                    <div className="mt-1 text-xs leading-6 text-slate-500">
                      {item.desc}
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </aside>

        <section className="space-y-6">{renderContent()}</section>
      </div>
    </div>
  );
};

function SummaryCard({
  icon,
  value,
  label,
  tone,
}: {
  icon: React.ReactNode;
  value: string;
  label: string;
  tone: string;
}) {
  return (
      <div className={`${tone} p-4`}>
        <div className="mb-3 flex items-center justify-between">{icon}</div>
      <div className="text-[1.8rem] font-semibold tracking-[-0.05em] text-slate-900">
        {value}
      </div>
      <div className="mt-2 text-sm text-slate-600">{label}</div>
    </div>
  );
}

function EmptyState({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <section className="student-card px-5 py-12 text-center">
      <div className="mx-auto mb-4 flex justify-center">{icon}</div>
      <h4 className="text-[1.55rem] font-semibold tracking-[-0.03em] text-slate-900">
        {title}
      </h4>
      {description ? <p className="mt-3 text-sm leading-7 text-slate-600">{description}</p> : null}
    </section>
  );
}

export default StudentAnalyticsCenter;
