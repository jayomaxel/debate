import React, { useState, useEffect } from 'react';
import {
  ArrowLeft,
  Download,
  TrendingUp,
  Award,
  Clock,
  Users,
  Trophy,
} from 'lucide-react';
import StudentService, { type DebateReport } from '../services/student.service';
import { useAuth } from '../store/auth.context';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  formatDebateRole,
  formatDebateStance,
  formatStudentDateTime,
  formatStudentTime,
} from '@/lib/student-display';

interface ReportDetailProps {
  debateId: string;
  onBack: () => void;
  studentMode?: boolean;
  initialReport?: DebateReport | null;
  selectedParticipantId?: string;
  onSelectedParticipantIdChange?: (id: string) => void;
}

export const DebateReportDetail: React.FC<ReportDetailProps> = ({
  debateId,
  onBack,
  studentMode = false,
  initialReport = null,
  selectedParticipantId,
  onSelectedParticipantIdChange,
}) => {
  const [report, setReport] = useState<DebateReport | null>(initialReport);
  const [loading, setLoading] = useState(!initialReport);
  const [exporting, setExporting] = useState<'pdf' | 'excel' | null>(null);
  const { user } = useAuth();

  useEffect(() => {
    if (initialReport) {
      setReport(initialReport);
      setLoading(false);
      return;
    }
    loadReport();
  }, [debateId, initialReport]);

  const loadReport = async () => {
    try {
      setLoading(true);
      const data = await StudentService.getReport(debateId);
      setReport(data);
    } catch (error) {
      console.error('加载报告失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (format: 'pdf' | 'excel') => {
    try {
      setExporting(format);
      if (format === 'pdf') {
        await StudentService.exportReportPDF(debateId);
      } else {
        await StudentService.exportReportExcel(debateId);
      }
    } catch (error) {
      console.error('导出失败:', error);
    } finally {
      setExporting(null);
    }
  };

  const getPhaseLabel = (phase: string) => {
    const labels: Record<string, string> = {
      opening: '立论阶段',
      questioning: '盘问阶段',
      free_debate: '自由辩论',
      closing: '总结陈词',
    };
    return labels[phase] || phase;
  };

  if (loading) {
    return (
      <div
        className={`${
          studentMode ? 'student-container py-10' : 'min-h-screen bg-slate-50'
        } flex min-h-[70vh] items-center justify-center`}
      >
        <div className={`${studentMode ? 'student-card px-8 py-10' : 'text-center'}`}>
          <div
            className={`mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2 ${
              studentMode ? 'border-[#171717]' : 'border-purple-600'
            }`}
          />
          <p className={studentMode ? 'text-slate-600' : 'text-gray-600'}>
            加载报告中...
          </p>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div
        className={`${
          studentMode ? 'student-container py-10' : 'min-h-screen bg-slate-50'
        } flex min-h-[70vh] items-center justify-center`}
      >
        <div className={`${studentMode ? 'student-card px-8 py-10' : 'text-center'}`}>
          <p className={`${studentMode ? 'text-slate-600' : 'text-gray-600'} mb-4`}>
            报告加载失败
          </p>
          <Button
            onClick={onBack}
            className={studentMode ? 'student-dark-button h-auto' : 'bg-purple-600 hover:bg-purple-700'}
          >
            返回
          </Button>
        </div>
      </div>
    );
  }

  const effectiveSelectedParticipantId =
    selectedParticipantId ||
    (studentMode
      ? report.participants.find((p) => p.user_id === user?.id)?.user_id || 'all'
      : 'all');
  const selectedParticipant =
    effectiveSelectedParticipantId === 'all'
      ? null
      : report.participants.find((p) => p.user_id === effectiveSelectedParticipantId) || null;
  const participant =
    selectedParticipant ||
    (studentMode ? report.participants.find((p) => p.user_id === user?.id) : null) ||
    null;
  const isTeacherView = !studentMode && user?.user_type !== 'student';
  const visibleSpeeches = selectedParticipant
    ? report.speeches.filter((speech) => {
        if (selectedParticipant.is_ai) {
          return `ai:${speech.speaker_role}` === selectedParticipant.user_id;
        }
        return (
          speech.speaker_user_id === selectedParticipant.user_id ||
          (speech.speaker_type === 'human' && speech.speaker_name === selectedParticipant.name)
        );
      })
    : report.speeches;

  const statistics = report.statistics as unknown as {
    positive: { avg_score: number; speech_count: number; total_duration: number };
    negative: { avg_score: number; speech_count: number; total_duration: number };
    winner: 'positive' | 'negative' | 'tie';
  };
  const startTime = formatStudentDateTime(report.start_time);
  const detailShellClassName = studentMode
    ? 'student-container py-6 pb-14 space-y-5'
    : 'min-h-screen bg-gray-50 p-6';
  const contentWidthClassName = studentMode ? '' : 'max-w-6xl mx-auto';
  const cardClassName = studentMode ? 'student-card p-5 md:p-6' : 'bg-white rounded-lg shadow-sm p-6';
  return (
    <div className={detailShellClassName}>
      <div className={contentWidthClassName}>
        <div className={cardClassName}>
          <div className="mb-4 flex items-center justify-between gap-4">
            <Button
              onClick={onBack}
              variant="outline"
              className={studentMode ? 'student-light-button h-auto px-4 py-2' : ''}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              返回
            </Button>
            <Button
              onClick={() => handleExport('pdf')}
              disabled={exporting !== null}
              className={studentMode ? 'student-dark-button h-auto px-4 py-2' : 'bg-purple-600 hover:bg-purple-700'}
            >
              <Download className="mr-2 h-4 w-4" />
              {exporting === 'pdf' ? '导出中...' : '导出 PDF'}
            </Button>
          </div>

          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              {studentMode ? <div className="student-kicker">详细分析</div> : null}
              <h1 className="mt-3 text-2xl font-semibold text-slate-900 md:text-[2rem]">
                {report.topic}
              </h1>
              <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-slate-600">
                {startTime ? (
                  <span className="flex items-center gap-1">
                    <Clock className="h-4 w-4" />
                    {startTime}
                  </span>
                ) : null}
                <span>时长：{report.duration} 分钟</span>
                <span className="flex items-center gap-1">
                  <Users className="h-4 w-4" />
                  {report.participants.length} 位参与者
                </span>
                {report.end_time ? (
                  <span>完成：{formatStudentDateTime(report.end_time)}</span>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>

      {statistics && (
        <div className={contentWidthClassName}>
          <div className={cardClassName}>
            <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-slate-900">
              <Trophy className="h-5 w-5 text-slate-700" />
              辩论结果总览
            </h2>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div
                className={`${
                  statistics.winner === 'positive'
                    ? 'student-card-soft-blue'
                    : 'student-card-muted'
                } p-4`}
              >
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-bold text-slate-900">正方</h3>
                  {statistics.winner === 'positive' ? (
                    <span className="student-pill">获胜</span>
                  ) : null}
                </div>
                <div className="mb-2 text-3xl font-bold text-slate-900">
                  {statistics.positive?.avg_score || 0}
                </div>
                <div className="text-sm text-slate-600">
                  <div>平均得分</div>
                  <div className="mt-2 text-xs">
                    发言：{statistics.positive?.speech_count || 0} 次 | 时长：
                    {Math.round((statistics.positive?.total_duration || 0) / 60)} 分钟
                  </div>
                </div>
              </div>

              <div className="student-card-muted flex flex-col items-center justify-center p-4 text-center">
                <div className="mb-2 text-lg font-bold text-slate-900">
                  {statistics.winner === 'positive'
                    ? '正方获胜'
                    : statistics.winner === 'negative'
                    ? '反方获胜'
                    : '平局'}
                </div>
                <div className="text-sm text-slate-500">
                  双方经过激烈辩论
                  <br />
                  {statistics.winner !== 'tie' ? '最终决出胜负' : '最终势均力敌'}
                </div>
              </div>

              <div
                className={`${
                  statistics.winner === 'negative'
                    ? 'student-card-soft-lavender'
                    : 'student-card-muted'
                } p-4`}
              >
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-bold text-slate-900">反方</h3>
                  {statistics.winner === 'negative' ? (
                    <span className="student-pill">获胜</span>
                  ) : null}
                </div>
                <div className="mb-2 text-3xl font-bold text-slate-900">
                  {statistics.negative?.avg_score || 0}
                </div>
                <div className="text-sm text-slate-600">
                  <div>平均得分</div>
                  <div className="mt-2 text-xs">
                    发言：{statistics.negative?.speech_count || 0} 次 | 时长：
                    {Math.round((statistics.negative?.total_duration || 0) / 60)} 分钟
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className={contentWidthClassName}>
        <div className={cardClassName}>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-xl font-semibold text-slate-900">
              <Award className="h-5 w-5 text-slate-700" />
              个人表现总览
            </h2>
            {isTeacherView ? (
              <Select
                value={effectiveSelectedParticipantId}
                onValueChange={(value) => onSelectedParticipantIdChange?.(value)}
              >
                <SelectTrigger className="w-full sm:w-[260px]">
                  <SelectValue placeholder="选择查看对象" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全场/班级视角</SelectItem>
                  {report.participants.map((item) => (
                    <SelectItem key={item.user_id} value={item.user_id}>
                      {item.name} · {formatDebateRole(item.role)}
                      {item.is_ai ? ' · AI' : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : null}
          </div>

          {participant ? (
            <>
              <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
                <div className="student-card-soft-blue p-4 text-center">
                  <div className="text-3xl font-bold text-slate-900">
                    {participant.final_score.overall_score.toFixed(1)}
                  </div>
                  <div className="mt-1 text-sm text-slate-600">总分</div>
                </div>
                <div className="student-card-muted p-4 text-center">
                  <div className="text-3xl font-bold text-slate-900">
                    {participant.final_score.speech_count}
                  </div>
                  <div className="mt-1 text-sm text-slate-600">发言次数</div>
                </div>
                <div className="student-card-soft-lavender p-4 text-center">
                  <div className="text-2xl font-bold text-slate-900">
                    {formatDebateStance(participant.stance)}
                  </div>
                  <div className="mt-1 text-sm text-slate-600">立场</div>
                </div>
                <div className="student-card-soft-peach p-4 text-center">
                  <div className="text-2xl font-bold text-slate-900">
                    {formatDebateRole(participant.role)}
                  </div>
                  <div className="mt-1 text-sm text-slate-600">角色</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                <div className="student-card-muted p-3 text-center">
                  <div className="text-2xl font-bold text-slate-900">
                    {participant.final_score.logic_score.toFixed(1)}
                  </div>
                  <div className="text-sm text-slate-600">逻辑建构力</div>
                </div>
                <div className="student-card-muted p-3 text-center">
                  <div className="text-2xl font-bold text-slate-900">
                    {participant.final_score.argument_score.toFixed(1)}
                  </div>
                  <div className="text-sm text-slate-600">AI 核心知识运用</div>
                </div>
                <div className="student-card-muted p-3 text-center">
                  <div className="text-2xl font-bold text-slate-900">
                    {participant.final_score.response_score.toFixed(1)}
                  </div>
                  <div className="text-sm text-slate-600">批判性思维</div>
                </div>
                <div className="student-card-muted p-3 text-center">
                  <div className="text-2xl font-bold text-slate-900">
                    {participant.final_score.persuasion_score.toFixed(1)}
                  </div>
                  <div className="text-sm text-slate-600">语言表达力</div>
                </div>
                <div className="student-card-muted p-3 text-center">
                  <div className="text-2xl font-bold text-slate-900">
                    {participant.final_score.teamwork_score.toFixed(1)}
                  </div>
                  <div className="text-sm text-slate-600">AI 伦理与科技素养</div>
                </div>
              </div>
            </>
          ) : (
            <div className="student-card-muted p-4 text-center text-slate-500">
              {isTeacherView ? '当前为全场视角，请选择具体参与者查看个人表现。' : '您未参与该辩论，无法查看个人表现数据'}
            </div>
          )}
        </div>
      </div>

      <div className={contentWidthClassName}>
        <div className={cardClassName}>
          <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-slate-900">
            <TrendingUp className="h-5 w-5 text-slate-700" />
            发言详情与评分
          </h2>
          <div className="space-y-4">
            {visibleSpeeches.map((speech) => (
              <div key={speech.id} className="student-card-muted p-4">
                <div className="mb-2 flex items-start justify-between gap-4">
                  <div>
                    <div className="mb-1 text-sm font-semibold text-slate-900">
                      {(speech.speaker_name ||
                        formatDebateRole(speech.role || speech.speaker_role) ||
                        '未知发言者') +
                        (speech.stance
                          ? `（${formatDebateStance(String(speech.stance))}）`
                          : '')}
                    </div>
                    <span className="student-pill mr-2 inline-flex">
                      {getPhaseLabel(speech.phase)}
                    </span>
                    {formatStudentTime(speech.timestamp) ? (
                      <span className="text-sm text-slate-500">
                        {formatStudentTime(speech.timestamp)}
                      </span>
                    ) : null}
                  </div>
                  {speech.score && (
                    <div className="text-right">
                      <div className="text-2xl font-bold text-slate-900">
                        {speech.score.overall_score.toFixed(1)}
                      </div>
                      <div className="text-xs text-slate-500">本次得分</div>
                    </div>
                  )}
                </div>
                <p className="mb-3 text-slate-700">{speech.content}</p>
                {speech.score && (
                  <div className="rounded-[12px] border border-black/5 bg-white/65 p-3">
                    <div className="mb-2 grid grid-cols-2 gap-2 text-xs md:grid-cols-5">
                      <div>
                        <span className="text-slate-600">逻辑:</span>
                        <span className="ml-1 font-semibold">{speech.score.logic_score.toFixed(1)}</span>
                      </div>
                      <div>
                        <span className="text-slate-600">知识:</span>
                        <span className="ml-1 font-semibold">{speech.score.argument_score.toFixed(1)}</span>
                      </div>
                      <div>
                        <span className="text-slate-600">思维:</span>
                        <span className="ml-1 font-semibold">{speech.score.response_score.toFixed(1)}</span>
                      </div>
                      <div>
                        <span className="text-slate-600">表达:</span>
                        <span className="ml-1 font-semibold">{speech.score.persuasion_score.toFixed(1)}</span>
                      </div>
                      <div>
                        <span className="text-slate-600">伦理:</span>
                        <span className="ml-1 font-semibold">{speech.score.teamwork_score.toFixed(1)}</span>
                      </div>
                    </div>
                    {speech.score.feedback && (
                      <div className="mt-2 border-t border-black/5 pt-2 text-sm text-slate-600">
                        <span className="font-semibold">评语:</span> {speech.score.feedback}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
            {visibleSpeeches.length === 0 ? (
              <div className="student-card-muted p-4 text-center text-sm text-slate-500">
                当前查看对象暂无有效发言记录
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
};
