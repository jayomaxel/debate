import React, { useMemo, useState } from 'react';
import { useAuth } from '../store/auth.context';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import AbilityRadarChart from './ability-radar-chart';
import SpeakingTimeChart from './speaking-time-chart';
import DebateResultDisplay from './debate-result-display';
import AIMentorFeedback from './ai-mentor-feedback';
import type { DebateReport } from '../services/student.service';
import { formatDebateRole, formatDebateStance } from '@/lib/student-display';
import {
  Award,
  BarChart3,
  Brain,
  Clock,
  FileText,
  Heart,
  PieChart,
  Star,
  Target,
  Users,
  Zap,
} from 'lucide-react';

interface DebateReportOverviewProps {
  report: DebateReport;
  studentName?: string;
  onDownloadReport?: (format: 'pdf' | 'excel') => void | Promise<void>;
  onViewDetails?: () => void;
  studentMode?: boolean;
  selectedParticipantId?: string;
  onSelectedParticipantIdChange?: (id: string) => void;
}

const DebateReportOverview: React.FC<DebateReportOverviewProps> = ({
  report,
  studentName,
  onDownloadReport,
  onViewDetails,
  studentMode = false,
  selectedParticipantId,
  onSelectedParticipantIdChange,
}) => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('summary');
  const isTeacherView = !studentMode && user?.user_type !== 'student';
  const effectiveSelectedParticipantId =
    selectedParticipantId ||
    (studentMode
      ? report.participants.find((p) => p.user_id === user?.id)?.user_id || 'all'
      : 'all');

  const selectedParticipant = useMemo(() => {
    if (effectiveSelectedParticipantId === 'all') return null;
    return report.participants.find((p) => p.user_id === effectiveSelectedParticipantId) || null;
  }, [effectiveSelectedParticipantId, report.participants]);

  const totalSpeechCount = report.participants.reduce(
    (sum, participant) => sum + Number(participant.final_score?.speech_count || 0),
    0,
  );
  const scoredParticipants = report.participants.filter(
    (participant) => Number(participant.final_score?.speech_count || 0) > 0,
  );
  const averageScore = (key: keyof DebateReport['participants'][number]['final_score']) =>
    scoredParticipants.length > 0
      ? scoredParticipants.reduce(
          (sum, participant) => sum + Number(participant.final_score?.[key] || 0),
          0,
        ) / scoredParticipants.length
      : 0;
  const classAverageScore = averageScore('overall_score');
  const aggregateParticipant = {
    user_id: 'all',
    name: '全场/班级视角',
    role: 'all',
    stance: 'positive',
    is_ai: false,
    has_speech: totalSpeechCount > 0,
    score_status: totalSpeechCount > 0 ? 'ready' : 'no_speech',
    speech_count: totalSpeechCount,
    final_score: {
      logic_score: averageScore('logic_score'),
      argument_score: averageScore('argument_score'),
      response_score: averageScore('response_score'),
      persuasion_score: averageScore('persuasion_score'),
      teamwork_score: averageScore('teamwork_score'),
      overall_score: classAverageScore,
      speech_count: totalSpeechCount,
      total_duration: report.participants.reduce(
        (sum, participant) => sum + Number(participant.final_score?.total_duration || 0),
        0,
      ),
    },
  };

  const displayParticipant =
    selectedParticipant ||
    (!studentMode && aggregateParticipant) ||
    report.participants.find((p) => p.user_id === user?.id) ||
    report.participants.find((p) => !p.is_ai) ||
    report.participants[0];

  const participantLabel = selectedParticipant
    ? `${selectedParticipant.name} · ${formatDebateRole(selectedParticipant.role)}`
    : '全场/班级视角';

  const debateResult = useMemo(() => {
    const stats = report.statistics as any;
    const participant = displayParticipant;

    const humanStats = stats?.human || null;
    const aiStats = stats?.ai || null;
    const isPositive = participant?.stance === 'positive';
    const humanStatsCompat = isPositive ? stats?.positive : stats?.negative;
    const aiStatsCompat = isPositive ? stats?.negative : stats?.positive;
    const resolvedHumanStats = humanStats || humanStatsCompat || {};
    const resolvedAiStats = aiStats || aiStatsCompat || {};

    let winner: 'human' | 'ai' | 'draw' = 'draw';
    if (stats?.human_ai_winner === 'human') winner = 'human';
    else if (stats?.human_ai_winner === 'ai') winner = 'ai';
    else if (stats?.human_ai_winner === 'tie') winner = 'draw';
    else if (stats?.winner === 'tie') winner = 'draw';
    else if (stats?.winner === 'positive') winner = isPositive ? 'human' : 'ai';
    else if (stats?.winner === 'negative') winner = isPositive ? 'ai' : 'human';

    return {
      winner,
      humanScore: Math.round(resolvedHumanStats?.avg_score || 0),
      aiScore: Math.round(resolvedAiStats?.avg_score || 0),
      debateTopic: report.topic,
      userStance: (participant?.stance || 'positive') as 'positive' | 'negative',
      viewLabel: selectedParticipant ? '查看对象' : '当前视角',
      viewValue: selectedParticipant
        ? `${selectedParticipant.name}（${formatDebateStance(selectedParticipant.stance)}）`
        : '全场/班级视角',
      duration: `${report.duration || 0} 分钟`,
      completedAt: report.end_time,
      keyMetrics: {
        logicScore: participant?.final_score?.logic_score || 0,
        argumentScore: participant?.final_score?.argument_score || 0,
        responseScore: participant?.final_score?.response_score || 0,
        persuasionScore: participant?.final_score?.persuasion_score || 0,
        teamworkScore: participant?.final_score?.teamwork_score || 0,
      },
      aiMetrics: {
        logicScore: resolvedAiStats?.avg_logic_score || 0,
        argumentScore: resolvedAiStats?.avg_argument_score || 0,
        responseScore: resolvedAiStats?.avg_response_score || 0,
        persuasionScore: resolvedAiStats?.avg_persuasion_score || 0,
        teamworkScore: resolvedAiStats?.avg_teamwork_score || 0,
      },
    };
  }, [displayParticipant, report, selectedParticipant]);

  const abilityScores = useMemo(() => {
    const scores = displayParticipant?.final_score;
    if (!scores) return [];

    return [
      {
        dimension: '逻辑建构能力',
        score: scores.logic_score || 0,
        icon: <Brain className="h-4 w-4" />,
        description: '观点结构、推理链条与论证严密度。',
        color: '#8b5cf6',
      },
      {
        dimension: 'AI 核心知识运用',
        score: scores.argument_score || 0,
        icon: <FileText className="h-4 w-4" />,
        description: 'AI 概念、案例与课程知识点的调用能力。',
        color: '#3b82f6',
      },
      {
        dimension: '批判性思维',
        score: scores.response_score || 0,
        icon: <Zap className="h-4 w-4" />,
        description: '识别漏洞、提出质疑并展开反驳的能力。',
        color: '#f59e0b',
      },
      {
        dimension: '语言表达能力',
        score: scores.persuasion_score || 0,
        icon: <Heart className="h-4 w-4" />,
        description: '表达清晰度、感染力与说服效果。',
        color: '#ec4899',
      },
      {
        dimension: 'AI 伦理与科技素养',
        score: scores.teamwork_score || 0,
        icon: <Users className="h-4 w-4" />,
        description: '对技术边界、伦理风险与社会影响的综合判断。',
        color: '#10b981',
      },
    ];
  }, [displayParticipant]);

  const speakingData = useMemo(() => {
    const humanColors = ['#171717', '#3a3a3a', '#5a5a5a', '#7c7c7c'];
    const aiColors = ['#b59676', '#ccb49a', '#dfd0bf', '#b6bda7'];

    const items = report.participants
      .map((p, idx) => {
        const duration = Number((p.final_score as any)?.total_duration || 0);
        const isAI = Boolean(p.is_ai);
        const color = isAI
          ? aiColors[idx % aiColors.length]
          : humanColors[idx % humanColors.length];
        return {
          participantId: p.user_id,
          name: p.name,
          role: p.role,
          time: duration,
          percentage: 0,
          isAI,
          color,
        };
      })
      .filter((item) => item.time > 0);

    const total = items.reduce((sum, item) => sum + item.time, 0);
    if (total <= 0) return [];

    return items.map((item) => ({
      ...item,
      percentage: Math.round((item.time / total) * 100),
    }));
  }, [report]);

  const resolvedStudentName = studentName || user?.name || '同学';

  const mentorFeedbacks = useMemo(() => {
    const stats = report.statistics as any;
    const timestamp = report.end_time ? new Date(report.end_time) : null;
    const suggestionsRaw = stats?.suggestions;
    const actionItems = Array.isArray(suggestionsRaw)
      ? suggestionsRaw.map((s: any) => String(s))
      : [];
    const feedbacks: any[] = [];
    const overall =
      typeof stats?.overall_comment === 'string' ? stats.overall_comment.trim() : '';
    if (overall) {
      feedbacks.push({
        id: 'overall_comment',
        type: 'improvement',
        title: '总体评语',
        content: overall,
        specificExamples: [],
        actionItems,
        priority: 'medium',
        timestamp,
      });
    }
    const winningReason =
      typeof stats?.winning_reason === 'string' ? stats.winning_reason.trim() : '';
    if (winningReason) {
      feedbacks.push({
        id: 'winning_reason',
        type: 'highlight',
        title: '胜负关键点',
        content: winningReason,
        specificExamples: [],
        actionItems: [],
        priority: 'low',
        timestamp,
      });
    }
    return feedbacks;
  }, [report]);

  const userParticipant = report.participants.find((p) => p.user_id === user?.id);
  const summaryParticipant = selectedParticipant || (studentMode ? userParticipant : null);
  const userSpeechCount = summaryParticipant?.final_score?.speech_count || totalSpeechCount;
  const userScore = summaryParticipant?.final_score?.overall_score || classAverageScore;
  const grade =
    userScore >= 90 ? 'S' : userScore >= 85 ? 'A+' : userScore >= 80 ? 'A' : userScore >= 75 ? 'B+' : 'B';

  const tabListClassName = studentMode
    ? 'grid h-auto w-full grid-cols-4 rounded-[12px] border border-[#d7ccbf] bg-white/76 p-1.5'
    : 'grid w-full grid-cols-4';

  const tabTriggerClassName = studentMode
    ? 'rounded-[10px] data-[state=active]:bg-[#171717] data-[state=active]:text-white'
    : '';

  return (
    <div className="space-y-5">
      {isTeacherView ? (
        <Card className="border-slate-200 bg-white shadow-sm">
          <CardContent className="flex flex-wrap items-center justify-between gap-4 p-4">
            <div>
              <div className="text-sm font-semibold text-slate-900">报告查看视角</div>
              <div className="mt-1 text-sm text-slate-500">{participantLabel}</div>
            </div>
            <Select
              value={effectiveSelectedParticipantId}
              onValueChange={(value) => onSelectedParticipantIdChange?.(value)}
            >
              <SelectTrigger className="w-full sm:w-[260px]">
                <SelectValue placeholder="选择查看对象" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全场/班级视角</SelectItem>
                {report.participants.map((participant) => (
                  <SelectItem key={participant.user_id} value={participant.user_id}>
                    {participant.name} · {formatDebateRole(participant.role)}
                    {participant.is_ai ? ' · AI' : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>
      ) : null}

      <DebateResultDisplay
        result={debateResult}
        studentMode={studentMode}
        onViewDetails={() => (onViewDetails ? onViewDetails() : setActiveTab('summary'))}
        onDownloadReport={() => onDownloadReport?.('pdf')}
      />

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className={tabListClassName}>
          <TabsTrigger value="summary" className={`flex items-center gap-2 ${tabTriggerClassName}`}>
            <BarChart3 className="h-4 w-4" />
            总结
          </TabsTrigger>
          <TabsTrigger value="ability" className={`flex items-center gap-2 ${tabTriggerClassName}`}>
            <Target className="h-4 w-4" />
            能力
          </TabsTrigger>
          <TabsTrigger value="speaking" className={`flex items-center gap-2 ${tabTriggerClassName}`}>
            <PieChart className="h-4 w-4" />
            发言
          </TabsTrigger>
          <TabsTrigger value="feedback" className={`flex items-center gap-2 ${tabTriggerClassName}`}>
            <Brain className="h-4 w-4" />
            反馈
          </TabsTrigger>
        </TabsList>

        <TabsContent value="summary" className="space-y-5">
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
            <SummaryStat
              icon={<Award className="h-6 w-6 text-slate-700" />}
              value={userScore.toFixed(1)}
              label={summaryParticipant ? '综合得分' : '全场均分'}
              badge={
                debateResult.winner === 'human'
                  ? '胜利'
                  : debateResult.winner === 'ai'
                  ? '惜败'
                  : '平局'
              }
              tone="student-card-soft-blue"
            />
            <SummaryStat
              icon={<Clock className="h-6 w-6 text-slate-700" />}
              value={debateResult.duration}
              label="辩论时长"
              tone="student-card-soft-peach"
            />
            <SummaryStat
              icon={<Users className="h-6 w-6 text-slate-700" />}
              value={String(userSpeechCount)}
              label={summaryParticipant ? '发言次数' : '全场发言次数'}
              tone="student-card-soft-lavender"
            />
            <SummaryStat
              icon={<Star className="h-6 w-6 text-slate-700" />}
              value={grade}
              label={summaryParticipant ? '表现等级' : '整体等级'}
              tone="student-card-muted"
            />
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <AbilityRadarChart
              scores={abilityScores}
              title="核心能力评估"
              showComparison
              studentMode={studentMode}
            />
            <SpeakingTimeChart
              data={speakingData}
              title="发言时间分布"
              studentMode={studentMode}
            />
          </div>
        </TabsContent>

        <TabsContent value="ability" className="space-y-5">
          <AbilityRadarChart
            scores={abilityScores}
            title="五维能力详细分析"
            showComparison
            studentMode={studentMode}
          />
        </TabsContent>

        <TabsContent value="speaking" className="space-y-5">
          <SpeakingTimeChart
            data={selectedParticipant ? speakingData.filter((item) => item.participantId === selectedParticipant.user_id) : speakingData}
            title="详细发言时间分析"
            studentMode={studentMode}
          />
        </TabsContent>

        <TabsContent value="feedback" className="space-y-5">
          <AIMentorFeedback
            feedbacks={mentorFeedbacks}
            userName={selectedParticipant?.name || resolvedStudentName}
            studentMode={studentMode}
          />
        </TabsContent>
      </Tabs>

      {isTeacherView && !selectedParticipant ? (
        <Card className="border-slate-200 bg-white shadow-sm">
          <CardContent className="p-4">
            <div className="mb-3 text-sm font-semibold text-slate-900">参与者表现列表</div>
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
              {report.participants.map((participant) => (
                <button
                  key={participant.user_id}
                  type="button"
                  onClick={() => onSelectedParticipantIdChange?.(participant.user_id)}
                  className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-left transition hover:border-slate-400 hover:bg-white"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-semibold text-slate-900">{participant.name}</div>
                    <Badge className="student-pill">
                      {participant.is_ai ? 'AI' : formatDebateStance(participant.stance)}
                    </Badge>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    {formatDebateRole(participant.role)} · 发言 {participant.final_score?.speech_count || 0} 次
                  </div>
                  <div className="mt-3 text-2xl font-bold text-slate-900">
                    {Number(participant.final_score?.overall_score || 0).toFixed(1)}
                  </div>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
};

function SummaryStat({
  icon,
  value,
  label,
  tone,
  badge,
}: {
  icon: React.ReactNode;
  value: string;
  label: string;
  tone: string;
  badge?: string;
}) {
  return (
    <Card className={`${tone} border-0 shadow-none`}>
      <CardContent className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>{icon}</div>
          {badge ? <Badge className="student-pill">{badge}</Badge> : null}
        </div>
        <div className="text-[1.45rem] font-bold text-slate-900">{value}</div>
        <div className="mt-1 text-sm text-slate-600">{label}</div>
      </CardContent>
    </Card>
  );
}

export default DebateReportOverview;
