import React, { useEffect, useState } from 'react';
import { useAuth } from '../store/auth.context';
import StudentService, { type DebateReport } from '../services/student.service';
import { useToast } from '@/hooks/use-toast';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import DebateReportOverview from './debate-report-overview';
import {
  formatDebateRole,
  formatDebateStance,
  formatDebateStatus,
  formatStudentDateTime,
} from '@/lib/student-display';
import {
  Download,
  Mail,
  Share2,
  FileText,
  Calendar,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  History,
  Loader2,
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
  onBack,
}) => {
  const [activeView, setActiveView] = useState<'overview' | 'history'>('overview');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { user } = useAuth();
  const { toast } = useToast();
  const [report, setReport] = useState<DebateReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [historyItems, setHistoryItems] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedParticipantId, setSelectedParticipantId] = useState('all');
  const isStudentMode = userType === 'student';

  useEffect(() => {
    const fetchReport = async () => {
      if (!debateId) return;

      try {
        setLoading(true);
        const data = await StudentService.getReport(debateId);
        setReport(data);
        const currentUserParticipant = data.participants.find((p) => p.user_id === user?.id);
        setSelectedParticipantId(
          isStudentMode && currentUserParticipant ? currentUserParticipant.user_id : 'all',
        );
      } catch (error) {
        toast({
          title: '获取报告失败',
          description: '无法加载辩论报告数据，请稍后重试',
          variant: 'destructive',
        });
      } finally {
        setLoading(false);
      }
    };

    fetchReport();
  }, [debateId, isStudentMode, toast, user?.id]);

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

  if (loading) {
    return (
      <div
        className={`${
          isStudentMode ? 'student-container py-10' : 'min-h-screen bg-slate-50'
        } flex min-h-[70vh] items-center justify-center`}
      >
        <div className={`${isStudentMode ? 'student-card px-8 py-10' : 'text-center'}`}>
          <Loader2 className="mx-auto mb-4 h-8 w-8 animate-spin text-slate-700" />
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
        title: '邮件发送成功',
        description: '报告已发送至你的邮箱',
        variant: 'success',
      });
    } catch (error) {
      toast({
        title: '邮件发送失败',
        description: '请稍后重试',
        variant: 'destructive',
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
      report.participants.find((p) => p.user_id === user?.id) ||
      report.participants.find((p) => !p.is_ai) ||
      report.participants[0];
    const overallScore = participant?.final_score?.overall_score ?? 0;
    const summary = `辩题：${report.topic}\n最终得分：${overallScore}\n对局 ID：${report.debate_id}\n${report.summary || '我刚完成了一场人机辩论，来看看这份赛后分析。'}`;

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
      icon: <BarChart3 className="h-4 w-4" />,
      description: '当前辩论报告',
      tone: 'student-card-soft-blue',
    },
    {
      id: 'history',
      label: '历史记录',
      icon: <History className="h-4 w-4" />,
      description: '查看历史辩论',
      tone: 'student-card-soft-peach',
    },
  ];

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
    activeDays: 0,
  };

  const renderMainContent = () => {
    switch (activeView) {
      case 'overview':
        if (!report) {
          return (
            <div className="py-10 text-center text-sm text-slate-500">
              暂无可用的辩论报告数据
            </div>
          );
        }
        return (
          <DebateReportOverview
            report={report}
            studentName={resolvedStudentName}
            studentMode={isStudentMode}
            selectedParticipantId={selectedParticipantId}
            onSelectedParticipantIdChange={setSelectedParticipantId}
            onDownloadReport={(format) => handleDownloadReport(format)}
          />
        );

      case 'history':
        return (
          <div className="space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-slate-900">辩论历史记录</h2>
              <Badge className={isStudentMode ? 'student-pill' : ''}>
                {safeStudentStats.totalDebates} 场辩论
              </Badge>
            </div>

            {historyLoading ? (
              <div className="flex items-center justify-center py-10">
                <Loader2 className="h-6 w-6 animate-spin text-slate-700" />
              </div>
            ) : historyItems.length === 0 ? (
              <div
                className={`${
                  isStudentMode ? 'student-card-muted' : 'rounded-lg bg-white'
                } py-10 text-center text-sm text-slate-500`}
              >
                暂无历史记录
              </div>
            ) : (
              <div className="space-y-3">
                {historyItems.map((item: any, index) => (
                  <Card
                    key={item.debate_id}
                    className={`cursor-pointer transition-colors duration-150 hover:border-black/10 ${
                      isStudentMode
                        ? index % 3 === 0
                          ? 'student-card-soft-blue'
                          : index % 3 === 1
                          ? 'student-card-soft-peach'
                          : 'student-card-soft-lavender'
                        : 'bg-white border-slate-200 shadow-sm'
                    }`}
                    onClick={async () => {
                      try {
                        setLoading(true);
                        const data = await StudentService.getReport(item.debate_id);
                        setReport(data);
                        const currentUserParticipant = data.participants.find((p) => p.user_id === user?.id);
                        setSelectedParticipantId(
                          isStudentMode && currentUserParticipant ? currentUserParticipant.user_id : 'all',
                        );
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
                          <div className="truncate text-sm font-semibold text-slate-900">
                            {item.topic}
                          </div>
                          <div className="mt-1 text-xs text-slate-500">
                            {formatStudentDateTime(item.created_at) || '-'}
                          </div>
                          <div className="mt-2 flex items-center gap-3 text-xs text-slate-600">
                            <span>{formatDebateRole(item.role)}</span>
                            <span>{formatDebateStance(item.stance)}</span>
                            <span>{formatDebateStatus(item.status)}</span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-lg font-semibold text-slate-900">
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

  if (isStudentMode) {
    return (
      <div className="student-container py-6 pb-14">
        <section className="student-card px-5 py-6 md:px-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <div className="student-kicker">赛后分析</div>
              <h1 className="mt-4 text-[2rem] font-semibold leading-[1.06] tracking-[-0.05em] text-slate-900 md:text-[2.35rem]">
                {resolvedStudentName} 的赛后分析
              </h1>
              <p className="mt-3 text-[15px] leading-7 text-slate-600">
                {activeView === 'overview'
                  ? '查看这场辩论的表现分析、能力反馈与发言结构。'
                  : '从历史记录里切换不同场次，继续回看你的赛后报告。'}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={onBack}
                className="student-light-button h-auto px-4 py-2"
              >
                <ChevronLeft className="mr-2 h-4 w-4" />
                返回
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleShareReport}
                className="student-light-button h-auto px-4 py-2"
              >
                <Share2 className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleEmailReport}
                className="student-light-button h-auto px-4 py-2"
              >
                <Mail className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleDownloadReport('pdf')}
                className="student-light-button h-auto px-4 py-2"
              >
                <Download className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </section>

        <div className="mt-5 grid gap-5 lg:grid-cols-[240px,1fr]">
          <aside className="student-card h-fit px-3.5 py-3.5">
            <nav className="space-y-2">
              {navigationItems.map((item) => (
                <button
                  key={item.id}
                  className={`w-full rounded-[12px] p-3.5 text-left transition-colors duration-150 ${
                    activeView === item.id ? item.tone : 'student-card-muted'
                  }`}
                  onClick={() => setActiveView(item.id as any)}
                >
                  <div className="flex items-center gap-3">
                    <div className="student-icon-bubble h-10 w-10 bg-white text-slate-900">
                      {item.icon}
                    </div>
                    <div>
                      <div className="font-medium text-slate-900">{item.label}</div>
                      <div className="mt-1 text-xs text-slate-500">{item.description}</div>
                    </div>
                  </div>
                </button>
              ))}
            </nav>

            <div className="mt-4 border-t border-black/5 pt-4">
              <Button
                variant="outline"
                size="sm"
                className="student-light-button h-auto w-full"
                onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              >
                {sidebarCollapsed ? (
                  <ChevronRight className="mr-2 h-4 w-4" />
                ) : (
                  <ChevronLeft className="mr-2 h-4 w-4" />
                )}
                {sidebarCollapsed ? '展开目录' : '收起目录'}
              </Button>
            </div>
          </aside>

          <section className="space-y-5">{renderMainContent()}</section>
        </div>

        <div className="student-card-muted mt-5 flex flex-wrap items-center justify-between gap-4 p-4">
          <div className="text-sm text-slate-600">
            <Calendar className="mr-1 inline h-4 w-4" />
            {report?.end_time
              ? `完成时间：${formatStudentDateTime(report.end_time)}`
              : '完成时间暂不可用'}
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              onClick={handleEmailReport}
              className="student-light-button h-auto px-4 py-2"
            >
              <Mail className="mr-2 h-4 w-4" />
              再次发送邮件
            </Button>
            <Button
              variant="outline"
              onClick={() => handleDownloadReport('excel')}
              className="student-light-button h-auto px-4 py-2"
            >
              <Download className="mr-2 h-4 w-4" />
              下载 Excel
            </Button>
            <Button onClick={() => handleDownloadReport('pdf')} className="student-dark-button h-auto">
              <FileText className="mr-2 h-4 w-4" />
              下载 PDF 报告
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="student-container py-6 pb-14">
      <section className="student-card px-5 py-6 md:px-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <div className="student-kicker">教师赛后分析</div>
            <h1 className="mt-4 text-[2rem] font-semibold leading-[1.06] tracking-[-0.05em] text-slate-900 md:text-[2.35rem]">
              教师赛后分析
            </h1>
            <p className="mt-3 text-[15px] leading-7 text-slate-600">
              {activeView === 'overview'
                ? '详细的辩论表现分析与改进建议'
                : '查看历史辩论记录和详细数据'}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={onBack} className="student-light-button h-auto px-4 py-2">
              <ChevronLeft className="mr-2 h-4 w-4" />
              返回
            </Button>
            <Button variant="outline" size="sm" onClick={handleShareReport} className="student-light-button h-auto px-4 py-2">
              <Share2 className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={handleEmailReport} className="student-light-button h-auto px-4 py-2">
              <Mail className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={() => handleDownloadReport('pdf')} className="student-light-button h-auto px-4 py-2">
              <Download className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </section>

      <div className="mt-5 grid gap-5 lg:grid-cols-[240px,1fr]">
        <aside className="student-card h-fit px-3.5 py-3.5">
          <nav className="space-y-2">
            {navigationItems.map((item) => (
              <button
                key={item.id}
                className={`w-full rounded-[12px] p-3.5 text-left transition-colors duration-150 ${
                  activeView === item.id ? item.tone : 'student-card-muted'
                }`}
                onClick={() => setActiveView(item.id as any)}
              >
                <div className="flex items-center gap-3">
                  <div className="student-icon-bubble h-10 w-10 bg-white text-slate-900">
                    {item.icon}
                  </div>
                  <div>
                    <div className="font-medium text-slate-900">{item.label}</div>
                    <div className="mt-1 text-xs text-slate-500">{item.description}</div>
                  </div>
                </div>
              </button>
            ))}
          </nav>
        </aside>

        <section className="space-y-5">{renderMainContent()}</section>
      </div>

      <div className="student-card-muted mt-5 flex flex-wrap items-center justify-between gap-4 p-4">
        <div className="text-sm text-slate-600">
          <Calendar className="mr-1 inline h-4 w-4" />
          报告生成时间：{new Date().toLocaleString('zh-CN')}
        </div>
        <div className="flex items-center gap-3">
          <Button onClick={() => handleDownloadReport('pdf')} className="student-dark-button h-auto">
            <FileText className="mr-2 h-4 w-4" />
            下载 PDF 报告
          </Button>
        </div>
      </div>
    </div>
  );
};

export default EnhancedDebateAnalytics;
