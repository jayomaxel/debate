import React, { useMemo } from 'react';
import {
  ArrowRight,
  BarChart3,
  Bot,
  Brain,
  DoorOpen,
  History,
  Lock as LockIcon,
  Search,
  Sparkles,
  Target,
  TrendingUp,
  Trophy,
  Users,
  Zap,
} from 'lucide-react';
import debateStartJourney from '@/assets/debate-start-journey.png';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Textarea } from '@/components/ui/textarea';
import AbilityRadarChart from '@/components/ability-radar-chart';
import { useAppRouter } from '@/lib/router';

type GuestStudentSection = 'home' | 'competition' | 'preparation' | 'growth';
type AnalyticsTab = 'history' | 'growth' | 'comparison' | 'achievements';

interface GuestStudentPreviewProps {
  section: GuestStudentSection;
  analyticsTab?: AnalyticsTab;
}

const loginPlaceholder = '登录后显示';
const numberPlaceholder = '-';
const statusPlaceholder = '待登录';

const analyticsMenuItems = [
  {
    id: 'history' as AnalyticsTab,
    icon: <History className="h-5 w-5" />,
    label: '历史记录',
    desc: '查看历次辩论',
    tone: 'student-card-soft-blue',
  },
  {
    id: 'growth' as AnalyticsTab,
    icon: <TrendingUp className="h-5 w-5" />,
    label: '成长趋势',
    desc: '关注能力变化',
    tone: 'student-card-soft-peach',
  },
  {
    id: 'comparison' as AnalyticsTab,
    icon: <Users className="h-5 w-5" />,
    label: '同班对比',
    desc: '查看班级参照',
    tone: 'student-card-soft-lavender',
  },
  {
    id: 'achievements' as AnalyticsTab,
    icon: <Trophy className="h-5 w-5" />,
    label: '成就',
    desc: '查看里程碑与徽章',
    tone: 'student-card-soft-peach',
  },
];

const previewScores = [
  {
    dimension: '逻辑建构能力',
    score: 0,
    icon: <Brain className="h-4 w-4" />,
    description: loginPlaceholder,
    color: 'text-[#8a5a36]',
  },
  {
    dimension: 'AI 核心知识运用',
    score: 0,
    icon: <Target className="h-4 w-4" />,
    description: loginPlaceholder,
    color: 'text-emerald-600',
  },
  {
    dimension: '批判性思维',
    score: 0,
    icon: <Zap className="h-4 w-4" />,
    description: loginPlaceholder,
    color: 'text-amber-600',
  },
  {
    dimension: '语言表达能力',
    score: 0,
    icon: <Sparkles className="h-4 w-4" />,
    description: loginPlaceholder,
    color: 'text-rose-600',
  },
  {
    dimension: 'AI 伦理与科技素养',
    score: 0,
    icon: <Users className="h-4 w-4" />,
    description: loginPlaceholder,
    color: 'text-[#8b82b4]',
  },
];

export default function GuestStudentPreview({
  section,
  analyticsTab = 'history',
}: GuestStudentPreviewProps) {
  const { navigate } = useAppRouter();
  const goLogin = () => navigate('/login');

  const content = useMemo(() => {
    switch (section) {
      case 'competition':
        return <GuestCompetition onLogin={goLogin} />;
      case 'preparation':
        return <GuestPreparation onLogin={goLogin} />;
      case 'growth':
        return <GuestGrowth activeTab={analyticsTab} onLogin={goLogin} />;
      case 'home':
      default:
        return <GuestHome onLogin={goLogin} />;
    }
  }, [analyticsTab, section]);

  return content;
}

function GuestHome({ onLogin }: { onLogin: () => void }) {
  const summaryTiles = [
    { label: '能力评估', value: statusPlaceholder, tone: 'student-card-soft-peach' },
    { label: '正式辩论', value: numberPlaceholder, tone: 'student-card-soft-blue' },
    { label: '累计参与', value: numberPlaceholder, tone: 'student-card-muted' },
    { label: '平均得分', value: numberPlaceholder, tone: 'student-card-muted' },
  ];

  const trustItems = ['AI 备赛助手', '能力成长记录', '同伴匹配辩论', '报告复盘'];

  return (
    <div className="student-container py-8 pb-14 lg:py-10">
      <section
        className="student-home-hero"
        style={{ backgroundImage: `url(${debateStartJourney})` }}
      >
        <div className="student-home-copy">
          <Badge className="student-pill w-fit">Human + AI Debate Studio</Badge>
          <h1 className="student-hero-title">碳硅之辩</h1>
          <p className="student-hero-copy">
            用 AI 备赛、实时辩论和成长报告，把每一次观点交锋都沉淀成可追踪的能力进步。
          </p>
          <div className="flex flex-wrap gap-3">
            <Button className="student-dark-button h-auto" onClick={onLogin}>
              开始辩论
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              className="student-light-button h-auto"
              onClick={onLogin}
            >
              打开备赛区
            </Button>
          </div>
        </div>
      </section>

      <section className="student-trust-row">
        {trustItems.map((item) => (
          <div key={item} className="student-trust-item">
            {item}
          </div>
        ))}
      </section>

      <div className="mt-8 space-y-5">
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {summaryTiles.map((item) => (
            <PreviewTile
              key={item.label}
              label={item.label}
              value={item.value}
              tone={item.tone}
            />
          ))}
        </section>

        <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="student-card px-5 py-6 md:px-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-[1.45rem] font-semibold tracking-[-0.03em] text-slate-950">
                  去你现在需要的地方
                </h2>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  登录后继续进入备赛、匹配和成长复盘。
                </p>
              </div>
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <PreviewLink
                icon={<Bot className="h-4 w-4" />}
                title="备赛区"
                tone="student-card-soft-blue"
                onClick={onLogin}
              />
              <PreviewLink
                icon={<Trophy className="h-4 w-4" />}
                title="成长区"
                tone="student-card-soft-lavender"
                onClick={onLogin}
              />
              <PreviewLink
                icon={<Users className="h-4 w-4" />}
                title="匹配大厅"
                tone="student-card-muted"
                onClick={onLogin}
              />
            </div>
          </div>

          <div className="student-card px-5 py-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-[1.45rem] font-semibold tracking-[-0.03em] text-slate-950">
                  最近一场辩论
                </h2>
                <div className="mt-2 text-sm text-slate-500">登录后查看</div>
              </div>
              <Badge className="student-pill">{statusPlaceholder}</Badge>
            </div>
            <div className="mt-5 flex flex-wrap gap-3">
              <Button
                variant="outline"
                className="student-light-button h-auto"
                onClick={onLogin}
              >
                查看报告
              </Button>
              <Button
                variant="outline"
                className="student-light-button h-auto"
                onClick={onLogin}
              >
                查看回放
              </Button>
            </div>
          </div>
        </section>

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.8fr)]">
          <Card className="student-card border-0 shadow-none">
            <div className="border-b border-black/5 px-6 py-5">
              <div className="flex items-center gap-2 text-slate-950">
                <Users className="h-5 w-5 text-sky-700" />
                预约辩论赛
                <Badge variant="outline">{statusPlaceholder}</Badge>
              </div>
            </div>
            <CardContent className="p-6">
              <div className="student-dashed-card py-10 text-center text-slate-500">
                登录后查看预约记录
              </div>
            </CardContent>
          </Card>

          <Card className="student-card border-0 shadow-none">
            <div className="border-b border-black/5 px-6 py-5">
              <div className="flex items-center gap-2 text-slate-950">
                <DoorOpen className="h-5 w-5 text-sky-700" />
                待加入房间
              </div>
            </div>
            <CardContent className="p-6">
              <div className="student-dashed-card py-10 text-center text-slate-500">
                登录后查看可加入的房间
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function GuestCompetition({ onLogin }: { onLogin: () => void }) {
  return (
    <div className="student-container py-6 pb-14">
      <div className="student-page-split grid gap-5">
        <section className="student-card px-5 py-6 md:px-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-2xl">
              <h1 className="mt-4 text-[2rem] font-semibold leading-[1.06] tracking-[-0.05em] text-slate-900 md:text-[2.35rem]">
                加入本场辩论
              </h1>
            </div>
          </div>

          <div className="mt-6">
            <div className="student-card-soft-lavender p-5">
              <div className="max-w-lg">
                <div className="mt-2.5 text-lg font-semibold tracking-[-0.03em] text-slate-900">
                  用 6 位邀请码加入本场辩论
                </div>
              </div>

              <div className="mt-5 space-y-3">
                <Input
                  readOnly
                  value=""
                  onClick={onLogin}
                  placeholder="登录后显示"
                  className="h-14 rounded-[16px] border-black/10 bg-white/85 text-center font-mono text-lg tracking-[0.25em] text-slate-900"
                />
                <Button
                  onClick={onLogin}
                  className="student-dark-button h-auto w-full justify-center"
                >
                  加入本场辩论
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </section>

        <div className="student-page-aside space-y-5">
          <section className="student-card px-5 py-6">
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <PreviewStatus
                icon={<Sparkles className="h-4 w-4 text-slate-700" />}
                label="能力评估"
                value={statusPlaceholder}
                tone="student-card-soft-peach"
              />
              <PreviewStatus
                icon={<Users className="h-4 w-4 text-slate-700" />}
                label="比赛状态"
                value={statusPlaceholder}
                tone="student-card-muted"
              />
              <Button
                variant="outline"
                onClick={onLogin}
                className="student-light-button h-auto justify-start"
              >
                <Sparkles className="mr-2 h-4 w-4" />
                刷新比赛状态
              </Button>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function GuestPreparation({ onLogin }: { onLogin: () => void }) {
  return (
    <div className="student-container py-6 pb-12">
      <div className="grid gap-5 xl:grid-cols-[320px,1fr]">
        <aside className="student-card flex min-h-[calc(100vh-11rem)] flex-col overflow-hidden">
          <div className="border-b border-black/5 p-4">
            <div className="student-card-soft-lavender p-3.5">
              <div>
                <div>
                  <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
                    AI 备赛助手
                  </div>
                  <div className="mt-1.5 text-lg font-semibold tracking-[-0.03em] text-slate-900">
                    开启新对话
                  </div>
                </div>
              </div>

              <div className="mt-4 space-y-3">
                <Button onClick={onLogin} className="student-dark-button h-auto w-full justify-center">
                  开始提问
                </Button>
                <Button
                  variant="outline"
                  className="student-light-button h-auto w-full justify-center"
                  onClick={onLogin}
                >
                  刷新会话
                </Button>
              </div>
            </div>
          </div>

          <div className="border-b border-black/5 px-4 py-4">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold text-slate-900">资料库</div>
                <div className="text-xs text-slate-500">登录后查看资料</div>
              </div>
            </div>

            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                readOnly
                onClick={onLogin}
                placeholder="登录后显示"
                className="w-full rounded-[14px] border border-black/10 bg-white/75 py-3 pl-10 pr-3 text-sm outline-none"
              />
            </div>

            <div className="mt-3 space-y-2">
              <div className="student-card-muted px-3 py-6 text-center text-sm text-slate-500">
                登录后查看资料列表
              </div>
            </div>
          </div>

          <ScrollArea className="flex-1">
            <div className="space-y-2 p-3.5">
              <div className="py-8 text-center text-sm text-slate-400">
                登录后查看会话
              </div>
            </div>
          </ScrollArea>
        </aside>

        <section className="student-card flex min-h-[calc(100vh-11rem)] flex-col overflow-hidden">
          <header className="border-b border-black/5 px-5 py-4">
            <div className="flex items-start gap-4">
              <div className="student-icon-bubble h-14 w-14 bg-[#151515] text-white">
                <Bot className="h-6 w-6" />
              </div>
              <div>
                <div className="student-kicker">备赛助手</div>
                <h1 className="mt-3 text-[1.95rem] font-semibold tracking-[-0.05em] text-slate-900">
                  备赛区 AI 助手
                </h1>
              </div>
            </div>
          </header>

          <ScrollArea className="flex-1 px-5 py-5">
            <div className="mx-auto max-w-5xl space-y-5 pb-4">
              <div className="py-10">
                <div className="mx-auto max-w-3xl p-6 text-center">
                  <div className="student-icon-bubble mx-auto h-16 w-16 bg-white text-slate-900">
                    <Bot className="h-9 w-9" />
                  </div>
                  <h2 className="mt-5 text-[1.55rem] font-semibold tracking-[-0.04em] text-slate-900">
                    还没有备赛会话
                  </h2>
                  <p className="mx-auto mt-3 max-w-xl text-sm leading-7 text-slate-600">
                    登录后开始使用
                  </p>
                </div>
              </div>
            </div>
          </ScrollArea>

          <div className="border-t border-black/5 bg-white/45 p-5">
            <div className="relative mx-auto max-w-5xl">
              <Textarea
                readOnly
                onClick={onLogin}
                placeholder="登录后显示"
                className="min-h-[112px] resize-none rounded-[14px] border-black/10 bg-white/85 p-4 pr-24 text-[15px] leading-7"
              />
              <div className="absolute bottom-4 right-4">
                <Button onClick={onLogin} className="student-dark-button h-auto px-5 py-3">
                  发送
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function GuestGrowth({
  activeTab,
  onLogin,
}: {
  activeTab: AnalyticsTab;
  onLogin: () => void;
}) {
  return (
    <div className="student-container py-6 pb-14">
      <section className="student-card px-5 py-6 md:px-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <h1 className="mt-4 text-[2rem] font-semibold leading-[1.06] tracking-[-0.05em] text-slate-900 md:text-[2.35rem]">
              成长区
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              onClick={onLogin}
              className="student-light-button h-auto"
            >
              刷新成长区
            </Button>
          </div>
        </div>
      </section>

      <div className="mt-5 grid gap-5 xl:grid-cols-[240px,minmax(0,1fr)]">
        <aside className="student-card h-fit px-3.5 py-3.5 xl:sticky xl:top-28">
          <div className="space-y-2">
            {analyticsMenuItems.map((item) => (
              <button
                key={item.id}
                onClick={onLogin}
                className={`w-full rounded-[12px] p-3.5 text-left transition-colors duration-150 ${
                  activeTab === item.id ? item.tone : 'student-card-muted'
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

        <section className="space-y-6">
          {activeTab === 'comparison' ? (
            <>
              <section className="student-card px-5 py-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="mt-3 text-[1.6rem] font-semibold tracking-[-0.04em] text-slate-900">
                      班级排名与平均差距
                    </h3>
                  </div>
                  <div className="flex items-center gap-3">
                    <Button
                      variant="outline"
                      className="student-light-button h-auto"
                      onClick={onLogin}
                    >
                      选择指标
                    </Button>
                    <Button
                      variant="outline"
                      className="student-light-button h-auto"
                      onClick={onLogin}
                    >
                      刷新
                    </Button>
                  </div>
                </div>
              </section>

              <section className="grid gap-4 md:grid-cols-4">
                <PreviewSummaryCard
                icon={<Trophy className="h-6 w-6 text-slate-700" />}
                  value={numberPlaceholder}
                  label="班级排名"
                  tone="student-card-soft-blue"
                />
                <PreviewSummaryCard
                  icon={<Sparkles className="h-6 w-6 text-slate-700" />}
                  value={numberPlaceholder}
                  label="领先百分位"
                  tone="student-card-soft-peach"
                />
                <PreviewSummaryCard
                  icon={<BarChart3 className="h-6 w-6 text-slate-700" />}
                  value={numberPlaceholder}
                  label="我的当前指标"
                  tone="student-card-soft-lavender"
                />
                <PreviewSummaryCard
                  icon={<Users className="h-6 w-6 text-slate-700" />}
                  value={numberPlaceholder}
                  label="班级平均"
                  tone="student-card-muted"
                />
              </section>

              <AbilityRadarChart
                title="五维能力对比（我 vs 班级平均）"
                showComparison
                studentMode
                comparisonScores={[0, 0, 0, 0, 0]}
                scores={previewScores}
              />

              <section className="student-card px-5 py-6">
                <div className="flex items-center justify-between gap-3">
                  <Badge className="student-pill">Top 10</Badge>
                </div>
                <div className="mt-4 space-y-3">
                  {Array.from({ length: 3 }, (_, index) => (
                    <div
                      key={index}
                      className="student-card-muted flex items-center justify-between gap-4 p-4"
                    >
                      <div className="flex items-center gap-4">
                        <div className="student-icon-bubble h-10 w-10 bg-white text-sm font-semibold text-slate-900">
                          {index + 1}
                        </div>
                        <div>
                          <div className="font-semibold text-slate-900">{statusPlaceholder}</div>
                          <div className="text-xs text-slate-500">登录后显示姓名</div>
                        </div>
                      </div>
                        <div className="text-right">
                        <div className="text-lg font-semibold tracking-[-0.03em] text-slate-900">
                          {numberPlaceholder}
                        </div>
                        <div className="text-xs text-slate-500">当前指标</div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </>
          ) : activeTab === 'achievements' ? (
            <>
              <section className="student-card px-5 py-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="mt-3 text-[1.6rem] font-semibold tracking-[-0.04em] text-slate-900">
                      成就与进度
                    </h3>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge className="student-pill">{statusPlaceholder}</Badge>
                    <Button
                      variant="outline"
                      className="student-light-button h-auto"
                      onClick={onLogin}
                    >
                      检查新成就
                    </Button>
                  </div>
                </div>
              </section>

              <EmptyPreview title="登录后显示" />
            </>
          ) : activeTab === 'growth' ? (
            <>
              <section className="student-card px-5 py-6">
                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  <PreviewSummaryCard
                    icon={<BarChart3 className="h-6 w-6 text-slate-700" />}
                    value={numberPlaceholder}
                    label="平均得分"
                    tone="student-card-soft-blue"
                  />
                  <PreviewSummaryCard
                    icon={<TrendingUp className="h-6 w-6 text-slate-700" />}
                    value={numberPlaceholder}
                    label="完成场次"
                    tone="student-card-soft-peach"
                  />
                  <PreviewSummaryCard
                    icon={<Sparkles className="h-6 w-6 text-slate-700" />}
                    value={numberPlaceholder}
                    label="累计参与"
                    tone="student-card-soft-lavender"
                  />
                </div>
              </section>

              <section className="student-card px-5 py-6">
                <h3 className="mt-3 text-[1.6rem] font-semibold tracking-[-0.04em] text-slate-900">
                  得分趋势
                </h3>
                <EmptyPreview title="登录后显示" />
              </section>
            </>
          ) : (
            <EmptyPreview title="登录后显示" />
          )}
        </section>
      </div>
    </div>
  );
}

function PreviewTile({
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
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
        {label}
      </div>
      <div className="mt-2 text-[1.45rem] font-semibold tracking-[-0.04em] text-slate-900">
        {value}
      </div>
    </div>
  );
}

function PreviewLink({
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

function PreviewStatus({
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

function PreviewSummaryCard({
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

function EmptyPreview({ title }: { title: string }) {
  return (
    <section className="student-card px-5 py-12 text-center">
      <div className="mx-auto mb-4 flex justify-center">
        <LockIcon className="h-16 w-16 text-slate-300" />
      </div>
      <h4 className="text-[1.55rem] font-semibold tracking-[-0.03em] text-slate-900">
        {title}
      </h4>
    </section>
  );
}
