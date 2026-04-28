import React, { useState, useEffect } from 'react';
import { useAuth } from '../store/auth.context';
import StudentService, { type DebateReport } from '../services/student.service';
import { useToast } from '@/hooks/use-toast';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import AbilityRadarChart from './ability-radar-chart';
import SpeakingTimeChart from './speaking-time-chart';
import DebateResultDisplay from './debate-result-display';
import AIMentorFeedback from './ai-mentor-feedback';
import DebateReportOverview from './debate-report-overview';
import {
  Download,
  Mail,
  Share2,
  FileText,
  Users,
  Calendar,
  BarChart3,
  Brain,
  Zap,
  Heart,
  ChevronLeft,
  ChevronRight,
  History,
  Loader2
} from 'lucide-react';

interface EnhancedDebateAnalyticsProps {
  userType?: 'student' | 'teacher';
  studentName?: string;
  debateId?: string;
  studentStats?: {
    totalDebates: number;
    wins: number;
    losses: number;
    draws: number;
    averageScore: number;
    currentStreak: number;
    bestStreak: number;
    totalImprovement: number;
    lastDebateDate?: Date;
    activeDays: number;
  };
  onBack?: () => void;
}

const EnhancedDebateAnalytics: React.FC<EnhancedDebateAnalyticsProps> = ({
  userType = 'student',
  studentName,
  debateId,
  studentStats,
  onBack
}) => {
  const [activeView, setActiveView] = useState<'overview' | 'history'>('overview');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState('summary');
  const { user } = useAuth();
  const { toast } = useToast();
  const [report, setReport] = useState<DebateReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [historyItems, setHistoryItems] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    const fetchReport = async () => {
      if (!debateId) return;
      
      try {
        setLoading(true);
        const data = await StudentService.getReport(debateId);
        setReport(data);
      } catch (error) {
        toast({
          title: "获取报告失败",
          description: "无法加载辩论报告数据，请稍后重试",
          variant: "destructive"
        });
      } finally {
        setLoading(false);
      }
    };

    fetchReport();
  }, [debateId, toast]);

  useEffect(() => {
    const fetchHistory = async () => {
      if (activeView !== 'history') return;
      try {
        setHistoryLoading(true);
        const data = await StudentService.getHistory(50, 0);
        setHistoryItems((data as any)?.list || []);
      } catch (error) {
        toast({
          title: '获取历史记录失败',
          description: '无法加载历史辩论数据，请稍后重试',
          variant: 'destructive',
        });
      } finally {
        setHistoryLoading(false);
      }
    };
    fetchHistory();
  }, [activeView, toast]);

  // Transform report data for visualization
  const getDebateResult = () => {
    if (!report) return null;

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
  };

  const getAbilityScores = () => {
    if (!report) return [];
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
  };

  const getSpeakingData = () => {
    if (!report) return [];

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
  };

  const debateResult = getDebateResult();
  const abilityScores = getAbilityScores();
  const speakingData = getSpeakingData();
  const resolvedStudentName = studentName || user?.name || '同学';
  const safeStudentStats = studentStats || {
    totalDebates: 0,
    wins: 0,
    losses: 0,
    draws: 0,
    averageScore: 0,
    currentStreak: 0,
    bestStreak: 0,
    totalImprovement: 0,
    lastDebateDate: undefined,
    activeDays: 0
  };
  const mentorFeedbacks = (() => {
    if (!report) return [];
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
  })();

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-slate-600">正在生成辩论分析报告...</p>
        </div>
      </div>
    );
  }

  const handleDownloadReport = async (format: 'pdf' | 'excel') => {
    if (!report) return;
    if (format === 'pdf') {
      await StudentService.exportReportPDF(report.debate_id);
      return;
    }
    await StudentService.exportReportExcel(report.debate_id);
  };

  const handleEmailReport = async () => {
    if (!report) return;
    try {
      await StudentService.sendReportEmail(report.debate_id);
      toast({
        title: "邮件发送成功",
        description: "报告已发送至您的邮箱",
        variant: "success"
      });
    } catch (error) {
      toast({
        title: "邮件发送失败",
        description: "请稍后重试",
        variant: "destructive"
      });
    }
  };

  const handleShareReport = async () => {
    if (!report) {
      toast({
        title: '暂无可分享报告',
        description: '报告加载完成后再试一次。',
        variant: 'destructive',
      });
      return;
    }

    const participant =
      report.participants.find(p => p.user_id === user?.id) ||
      report.participants.find(p => !p.is_ai) ||
      report.participants[0];
    const overallScore = participant?.final_score?.overall_score ?? 0;
    const summary = `辩题：${report.topic}\n最终得分：${overallScore}\n对局ID：${report.debate_id}\n${report.summary || '我刚完成了一场人机辩论，来看看这份赛后分析。'}`;

    try {
      if (navigator.share) {
        await navigator.share({
          title: '辩论赛后分析报告',
          text: summary,
        });
        return;
      }

      await navigator.clipboard.writeText(summary);
      toast({
        title: '分享内容已复制',
        description: '当前浏览器不支持系统分享，已复制摘要文本。',
        variant: 'success',
      });
    } catch (error) {
      toast({
        title: '分享失败',
        description: '请稍后重试。',
        variant: 'destructive',
      });
    }
  };

  const navigationItems = [
    {
      id: 'overview',
      label: '总览',
      icon: <BarChart3 className="w-4 h-4" />,
      description: '当前辩论报告'
    },
    {
      id: 'history',
      label: '历史记录',
      icon: <History className="w-4 h-4" />,
      description: '查看历史辩论'
    }
  ];

  const renderMainContent = () => {
    const userParticipant = report?.participants.find(p => p.user_id === user?.id);
    const userSpeechCount = userParticipant?.final_score?.speech_count || 0;
    const userScore = userParticipant?.final_score?.overall_score || 0;
    const grade = userScore >= 90 ? 'S' : userScore >= 85 ? 'A+' : userScore >= 80 ? 'A' : userScore >= 75 ? 'B+' : 'B';

    switch (activeView) {
      case 'overview':
        if (!report || !debateResult) {
          return (
            <div className="text-center text-sm text-slate-500 py-10">
              暂无可用的辩论报告数据
            </div>
          );
        }
        return (
          <DebateReportOverview
            report={report}
            studentName={resolvedStudentName}
            onDownloadReport={(format) => handleDownloadReport(format)}
          />
        );

      case 'history':
        return (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-slate-900">辩论历史记录</h2>
              <Badge className="bg-blue-100 text-blue-700 border-blue-300">
                {safeStudentStats.totalDebates} 场辩论
              </Badge>
            </div>

            {historyLoading ? (
              <div className="flex items-center justify-center py-10">
                <Loader2 className="w-6 h-6 text-blue-600 animate-spin" />
              </div>
            ) : historyItems.length === 0 ? (
              <div className="text-center text-sm text-slate-500 py-10">暂无历史记录</div>
            ) : (
              <div className="space-y-3">
                {historyItems.map((item: any) => (
                  <Card
                    key={item.debate_id}
                    className="bg-white border-slate-200 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
                    onClick={async () => {
                      try {
                        setLoading(true);
                        const data = await StudentService.getReport(item.debate_id);
                        setReport(data);
                        setActiveView('overview');
                      } catch (error) {
                        toast({
                          title: '加载报告失败',
                          description: '无法打开该场辩论报告，请稍后重试',
                          variant: 'destructive',
                        });
                      } finally {
                        setLoading(false);
                      }
                    }}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <div className="text-sm font-semibold text-slate-900 truncate">
                            {item.topic}
                          </div>
                          <div className="text-xs text-slate-500 mt-1">
                            {item.created_at ? new Date(item.created_at).toLocaleString('zh-CN') : '-'}
                          </div>
                          <div className="text-xs text-slate-600 mt-2 flex items-center gap-3">
                            <span>{item.role}</span>
                            <span>{item.stance}</span>
                            <span>{item.status}</span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-lg font-bold text-slate-900">
                            {typeof item.score === 'number' ? item.score.toFixed(1) : '-'}
                          </div>
                          <div className="text-xs text-slate-500">综合得分</div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-purple-50">
      {/* 顶部导航 */}
      <header className="bg-white border-b border-slate-200 shadow-sm sticky top-0 z-40">
        <div className="max-w-full mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={onBack}
                className="text-slate-600 hover:text-slate-900"
              >
                <ChevronLeft className="w-4 h-4 mr-2" />
                返回
              </Button>
              <div>
                <h1 className="text-2xl font-bold text-slate-900">
                  {userType === 'student' ? `${resolvedStudentName} 的` : '教师'}分析中心
                </h1>
                <p className="text-sm text-slate-600">
                  {activeView === 'overview' && '详细的辩论表现分析和个性化改进建议'}
                  {activeView === 'history' && '查看历史辩论记录和详细数据'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* 操作按钮 */}
              <Button
                variant="ghost"
                size="sm"
                onClick={handleShareReport}
                className="text-slate-600 hover:text-slate-900"
              >
                <Share2 className="w-4 h-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleEmailReport}
                className="text-slate-600 hover:text-slate-900"
              >
                <Mail className="w-4 h-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleDownloadReport('pdf')}
                className="text-slate-600 hover:text-slate-900"
              >
                <Download className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* 主要内容区域 */}
      <div className="flex">
        {/* 侧边导航 */}
        <div className={`bg-white border-r border-slate-200 transition-all duration-300 ${
          sidebarCollapsed ? 'w-16' : 'w-64'
        }`}>
          <nav className="p-4 space-y-2">
            {navigationItems.map((item) => (
              <Button
                key={item.id}
                variant={activeView === item.id ? 'default' : 'ghost'}
                className={`w-full justify-start h-auto p-3 ${
                  sidebarCollapsed ? 'px-2' : ''
                }`}
                onClick={() => setActiveView(item.id as any)}
              >
                <div className="flex items-center gap-3">
                  {item.icon}
                  {!sidebarCollapsed && (
                    <div className="text-left">
                      <div className="font-medium">{item.label}</div>
                      <div className="text-xs text-slate-500">{item.description}</div>
                    </div>
                  )}
                </div>
              </Button>
            ))}
          </nav>

          {/* 收起/展开按钮 */}
          <div className="p-4 border-t border-slate-200">
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            >
              {sidebarCollapsed ? (
                <ChevronRight className="w-4 h-4" />
              ) : (
                <ChevronLeft className="w-4 h-4 mr-2" />
              )}
              {!sidebarCollapsed && '收起菜单'}
            </Button>
          </div>
        </div>

        {/* 主要内容 */}
        <div className="flex-1 p-6">
          <div className="max-w-7xl mx-auto">
            {renderMainContent()}
          </div>
        </div>
      </div>

      {/* 底部操作栏 */}
      <div className="bg-white border-t border-slate-200 shadow-lg">
        <div className="max-w-full mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="text-sm text-slate-600">
                <Calendar className="w-4 h-4 inline mr-1" />
                报告生成时间：{new Date().toLocaleString('zh-CN')}
              </div>
              {userType === 'student' && (
                <div className="text-sm text-slate-600">
                  报告已自动发送至您的邮箱
                </div>
              )}
            </div>

            <div className="flex items-center gap-3">
              {userType === 'student' && (
                <>
                  <Button
                    variant="outline"
                    onClick={handleEmailReport}
                    className="border-blue-300 text-blue-700 hover:bg-blue-50"
                  >
                    <Mail className="w-4 h-4 mr-2" />
                    再次发送邮件
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => handleDownloadReport('excel')}
                    className="border-green-300 text-green-700 hover:bg-green-50"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    下载Excel
                  </Button>
                </>
              )}
              <Button
                onClick={() => handleDownloadReport('pdf')}
                className="bg-blue-600 hover:bg-blue-700 text-white"
              >
                <FileText className="w-4 h-4 mr-2" />
                下载PDF报告
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EnhancedDebateAnalytics;
