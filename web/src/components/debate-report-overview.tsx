import React, { useMemo, useState } from 'react';
import { useAuth } from '../store/auth.context';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import AbilityRadarChart from './ability-radar-chart';
import SpeakingTimeChart from './speaking-time-chart';
import DebateResultDisplay from './debate-result-display';
import AIMentorFeedback from './ai-mentor-feedback';
import type { DebateReport } from '../services/student.service';
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
}

const DebateReportOverview: React.FC<DebateReportOverviewProps> = ({
  report,
  studentName,
  onDownloadReport,
  onViewDetails,
}) => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('summary');

  const debateResult = useMemo(() => {
    const stats = report.statistics as any;
    const participant =
      report.participants.find(p => p.user_id === user?.id) ||
      report.participants.find(p => !p.is_ai) ||
      report.participants[0];

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
      duration: `${report.duration || 0}分钟`,
      keyMetrics: {
        logicScore: participant?.final_score?.logic_score || 0,
        argumentScore: participant?.final_score?.argument_score || 0,
        responseScore: participant?.final_score?.response_score || 0,
        persuasionScore: participant?.final_score?.persuasion_score || 0,
        teamworkScore: participant?.final_score?.teamwork_score || 0
      }
    };
  }, [report, user?.id]);

  const abilityScores = useMemo(() => {
    const participant =
      report.participants.find(p => p.user_id === user?.id) ||
      report.participants.find(p => !p.is_ai) ||
      report.participants[0];

    const scores = participant?.final_score;
    if (!scores) return [];

    return [
      {
        dimension: '逻辑建构力',
        score: scores.logic_score || 0,
        icon: <Brain className="w-4 h-4" />,
        description: '观点结构、推理链条与论证严密性',
        color: '#8b5cf6'
      },
      {
        dimension: 'AI核心知识运用',
        score: scores.argument_score || 0,
        icon: <FileText className="w-4 h-4" />,
        description: 'AI概念、案例与课程知识点的调用能力',
        color: '#3b82f6'
      },
      {
        dimension: '批判性思维',
        score: scores.response_score || 0,
        icon: <Zap className="w-4 h-4" />,
        description: '识别漏洞、提出质疑与展开反驳的能力',
        color: '#f59e0b'
      },
      {
        dimension: '语言表达力',
        score: scores.persuasion_score || 0,
        icon: <Heart className="w-4 h-4" />,
        description: '表达清晰度、感染力与说服效果',
        color: '#ec4899'
      },
      {
        dimension: 'AI伦理与科技素养',
        score: scores.teamwork_score || 0,
        icon: <Users className="w-4 h-4" />,
        description: '对技术边界、伦理风险与社会影响的综合判断',
        color: '#10b981'
      }
    ];
  }, [report, user?.id]);

  const speakingData = useMemo(() => {
    const humanColors = ['#3b82f6', '#06b6d4', '#0ea5e9', '#2563eb'];
    const aiColors = ['#8b5cf6', '#a855f7', '#c084fc', '#7c3aed'];

    const items = report.participants
      .map((p, idx) => {
        const duration = Number((p.final_score as any)?.total_duration || 0);
        const isAI = Boolean(p.is_ai);
        const color = isAI ? aiColors[idx % aiColors.length] : humanColors[idx % humanColors.length];
        return {
          name: p.name,
          time: duration,
          percentage: 0,
          isAI,
          color
        };
      })
      .filter(item => item.time > 0);

    const total = items.reduce((sum, item) => sum + item.time, 0);
    if (total <= 0) return [];

    return items.map(item => ({
      ...item,
      percentage: Math.round((item.time / total) * 100)
    }));
  }, [report]);

  const resolvedStudentName = studentName || user?.name || '同学';

  const mentorFeedbacks = useMemo(() => {
    const stats = report.statistics as any;
    const timestamp = report.end_time ? new Date(report.end_time) : new Date();
    const suggestionsRaw = stats?.suggestions;
    const actionItems = Array.isArray(suggestionsRaw)
      ? suggestionsRaw.map((s: any) => String(s))
      : [];
    const feedbacks: any[] = [];
    const overall = typeof stats?.overall_comment === 'string' ? stats.overall_comment.trim() : '';
    if (overall) {
      feedbacks.push({
        id: 'overall_comment',
        type: 'improvement',
        title: '总体评语',
        content: overall,
        specificExamples: [],
        actionItems,
        priority: 'medium',
        timestamp
      });
    }
    const winningReason = typeof stats?.winning_reason === 'string' ? stats.winning_reason.trim() : '';
    if (winningReason) {
      feedbacks.push({
        id: 'winning_reason',
        type: 'highlight',
        title: '胜负关键点',
        content: winningReason,
        specificExamples: [],
        actionItems: [],
        priority: 'low',
        timestamp
      });
    }
    return feedbacks;
  }, [report]);

  const userParticipant = report.participants.find(p => p.user_id === user?.id);
  const userSpeechCount = userParticipant?.final_score?.speech_count || 0;
  const userScore = userParticipant?.final_score?.overall_score || 0;
  const grade = userScore >= 90 ? 'S' : userScore >= 85 ? 'A+' : userScore >= 80 ? 'A' : userScore >= 75 ? 'B+' : 'B';

  return (
    <div className="space-y-6">
      <DebateResultDisplay
        result={debateResult}
        onViewDetails={() => (onViewDetails ? onViewDetails() : setActiveTab('summary'))}
        onDownloadReport={() => onDownloadReport?.('pdf')}
      />

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="summary" className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4" />
            总结
          </TabsTrigger>
          <TabsTrigger value="ability" className="flex items-center gap-2">
            <Target className="w-4 h-4" />
            能力
          </TabsTrigger>
          <TabsTrigger value="speaking" className="flex items-center gap-2">
            <PieChart className="w-4 h-4" />
            发言
          </TabsTrigger>
          <TabsTrigger value="feedback" className="flex items-center gap-2">
            <Brain className="w-4 h-4" />
            反馈
          </TabsTrigger>
        </TabsList>

        <TabsContent value="summary" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="bg-white border-slate-200 shadow-sm">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="w-12 h-12 bg-emerald-100 rounded-lg flex items-center justify-center">
                    <Award className="w-6 h-6 text-emerald-600" />
                  </div>
                  <Badge className={`${debateResult.winner === 'human' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-700'}`}>
                    {debateResult.winner === 'human' ? '胜利' : debateResult.winner === 'ai' ? '惜败' : '平局'}
                  </Badge>
                </div>
                <div className="text-2xl font-bold text-slate-900 mb-1">{userScore.toFixed(1)}</div>
                <div className="text-sm text-slate-600">综合得分</div>
              </CardContent>
            </Card>

            <Card className="bg-white border-slate-200 shadow-sm">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                    <Clock className="w-6 h-6 text-blue-600" />
                  </div>
                </div>
                <div className="text-2xl font-bold text-slate-900 mb-1">{debateResult.duration}</div>
                <div className="text-sm text-slate-600">辩论时长</div>
              </CardContent>
            </Card>

            <Card className="bg-white border-slate-200 shadow-sm">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                    <Users className="w-6 h-6 text-purple-600" />
                  </div>
                </div>
                <div className="text-2xl font-bold text-slate-900 mb-1">{userSpeechCount}</div>
                <div className="text-sm text-slate-600">发言次数</div>
              </CardContent>
            </Card>

            <Card className="bg-white border-slate-200 shadow-sm">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="w-12 h-12 bg-amber-100 rounded-lg flex items-center justify-center">
                    <Star className="w-6 h-6 text-amber-600" />
                  </div>
                </div>
                <div className="text-2xl font-bold text-slate-900 mb-1">{grade}</div>
                <div className="text-sm text-slate-600">表现等级</div>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <AbilityRadarChart
              scores={abilityScores}
              title="核心能力评估"
              showComparison={true}
            />
            <SpeakingTimeChart
              data={speakingData}
              title="发言时间分布"
              showComparison={true}
            />
          </div>
        </TabsContent>

        <TabsContent value="ability" className="space-y-6">
          <AbilityRadarChart
            scores={abilityScores}
            title="五维能力详细分析"
            showComparison={true}
          />
        </TabsContent>

        <TabsContent value="speaking" className="space-y-6">
          <SpeakingTimeChart
            data={speakingData}
            title="详细发言时间分析"
            showComparison={true}
          />
        </TabsContent>

        <TabsContent value="feedback" className="space-y-6">
          <AIMentorFeedback
            feedbacks={mentorFeedbacks}
            userName={resolvedStudentName}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default DebateReportOverview;
