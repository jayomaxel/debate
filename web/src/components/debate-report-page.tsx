import React, { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import StudentService, { type DebateReport } from '../services/student.service';
import TeacherService, {
  type TeacherReportMeta,
  type TeacherSpeechAnchor,
  type TeachingSummaryResult,
} from '../services/teacher.service';
import DebateReportOverview from './debate-report-overview';
import { DebateReportDetail } from './debate-report-detail';
import TeachingSummaryPanel from './teaching-summary-panel';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  Download,
  Loader2,
  MapPinned,
  RefreshCw,
} from 'lucide-react';
import { useAuth } from '../store/auth.context';

interface DebateReportPageProps {
  debateId: string;
  studentName?: string;
  onBack: () => void;
  studentMode?: boolean;
}

const getQualityLabel = (quality?: string | null) => {
  if (quality === 'validated') return '报告已校验';
  if (quality === 'partial') return '报告部分可用';
  if (quality === 'fallback') return '报告降级可用';
  return '报告状态待确认';
};

const getQualityTone = (quality?: string | null) => {
  if (quality === 'validated') {
    return {
      className: 'border-emerald-200 bg-emerald-50 text-emerald-900',
      icon: CheckCircle2,
    };
  }
  if (quality === 'fallback') {
    return {
      className: 'border-amber-200 bg-amber-50 text-amber-950',
      icon: AlertTriangle,
    };
  }
  return {
    className: 'border-sky-200 bg-sky-50 text-sky-950',
    icon: AlertTriangle,
  };
};

const formatMetaStatus = (value?: string | number | boolean | null) => {
  if (value === undefined || value === null || value === '') return '-';
  if (typeof value === 'boolean') return value ? '是' : '否';
  return String(value);
};

const getScoringSourceLabel = (reportMeta?: TeacherReportMeta | null) => {
  if (!reportMeta) return '-';
  const source =
    reportMeta.scoring_source === 'judge_model'
      ? '评分模型'
      : reportMeta.scoring_source === 'fallback'
        ? '降级补全'
        : reportMeta.scoring_source || '-';
  return reportMeta.provider ? `${source} / ${reportMeta.provider}` : source;
};

const formatEvidenceSources = (sources?: TeacherReportMeta['evidence_sources']) => {
  if (!sources?.length) return '-';
  return sources
    .map((item) => `${item.label || item.source_type || 'unknown'} ×${item.count ?? 0}`)
    .join('、');
};

const DebateReportPage: React.FC<DebateReportPageProps> = ({
  debateId,
  studentName,
  onBack,
  studentMode = false,
}) => {
  const { toast } = useToast();
  const { user } = useAuth();
  const [report, setReport] = useState<DebateReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<'pdf' | 'excel' | null>(null);
  const [view, setView] = useState<'overview' | 'detail'>('overview');
  const [selectedParticipantId, setSelectedParticipantId] = useState('all');
  const [reportMeta, setReportMeta] = useState<TeacherReportMeta | null>(null);
  const [speechAnchors, setSpeechAnchors] = useState<TeacherSpeechAnchor[]>([]);
  const [teachingSummary, setTeachingSummary] = useState<TeachingSummaryResult | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [pendingAnchorId, setPendingAnchorId] = useState<string | undefined>();

  useEffect(() => {
    const fetchReport = async () => {
      try {
        setLoading(true);
        const data = studentMode
          ? await StudentService.getReport(debateId)
          : await TeacherService.getReport(debateId).then((payload) => {
              setReportMeta(payload.report_meta || null);
              setSpeechAnchors(payload.speech_anchors || []);
              return payload.report;
            });
        setReport(data);
        const currentUserParticipant = data.participants.find((p) => p.user_id === user?.id);
        setSelectedParticipantId(
          studentMode && currentUserParticipant ? currentUserParticipant.user_id : 'all',
        );
      } catch (error: any) {
        toast({
          title: '获取报告失败',
          description: error?.message || '无法加载辩论报告数据，请稍后重试',
          variant: 'destructive',
        });
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, [debateId, studentMode, toast, user?.id]);

  const reloadTeacherReport = useCallback(async () => {
    const payload = await TeacherService.getReport(debateId);
    setReportMeta(payload.report_meta || null);
    setSpeechAnchors(payload.speech_anchors || []);
    setReport(payload.report);
    return payload.report;
  }, [debateId]);

  useEffect(() => {
    if (studentMode) return;
    const fetchTeachingSummary = async () => {
      try {
        setSummaryLoading(true);
        const summary = await TeacherService.getTeachingSummary(debateId);
        setTeachingSummary(summary);
        if (summary.report_meta) {
          setReportMeta(summary.report_meta);
        }
      } catch (error: any) {
        toast({
          title: '复盘摘要加载失败',
          description: error?.message || '无法加载教师复盘摘要',
          variant: 'destructive',
        });
      } finally {
        setSummaryLoading(false);
      }
    };
    fetchTeachingSummary();
  }, [debateId, studentMode, toast]);

  const handleDownload = async (format: 'pdf' | 'excel') => {
    try {
      setExporting(format);
      if (format === 'pdf') {
        await StudentService.exportReportPDF(debateId);
        return;
      }
      await StudentService.exportReportExcel(debateId);
    } catch (error: any) {
      toast({
        title: '导出失败',
        description: error?.message || '导出报告失败，请稍后重试',
        variant: 'destructive',
      });
    } finally {
      setExporting(null);
    }
  };

  const handleRecalculate = async () => {
    if (studentMode) return;
    try {
      setRecalculating(true);
      const result = await TeacherService.recalculateReport(debateId);
      setReportMeta(result.report_meta);
      setTeachingSummary(result.teaching_summary);
      await reloadTeacherReport();
      toast({
        title: '报告已重算',
        description: '已清理报告缓存并刷新教师复盘摘要',
      });
    } catch (error: any) {
      toast({
        title: '报告重算失败',
        description: error?.message || '无法完成教师报告轻量重算',
        variant: 'destructive',
      });
    } finally {
      setRecalculating(false);
    }
  };

  const handleAnchorClick = (anchorId: string) => {
    setPendingAnchorId(anchorId);
    setView('detail');
  };

  const qualityTone = getQualityTone(reportMeta?.report_quality);
  const QualityIcon = qualityTone.icon;

  if (loading) {
    return studentMode ? (
      <div className="student-container flex min-h-[70vh] items-center justify-center py-10">
        <div className="student-card min-w-[280px] px-8 py-10 text-center">
          <Loader2 className="mx-auto mb-4 h-10 w-10 animate-spin text-slate-700" />
          <p className="text-slate-600">正在加载辩论报告...</p>
        </div>
      </div>
    ) : (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="text-center">
          <Loader2 className="mx-auto mb-4 h-8 w-8 animate-spin text-slate-700" />
          <p className="text-slate-600">正在加载辩论报告...</p>
        </div>
      </div>
    );
  }

  if (!report) {
    return studentMode ? (
      <div className="student-container flex min-h-[70vh] items-center justify-center py-10">
        <div className="student-card min-w-[280px] px-8 py-10 text-center">
          <p className="mb-4 text-slate-600">报告加载失败</p>
          <Button onClick={onBack} className="student-dark-button h-auto">
            返回
          </Button>
        </div>
      </div>
    ) : (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="text-center">
          <p className="mb-4 text-slate-600">报告加载失败</p>
          <Button onClick={onBack}>返回</Button>
        </div>
      </div>
    );
  }

  if (view === 'detail') {
    return (
      <DebateReportDetail
        debateId={debateId}
        onBack={() => setView('overview')}
        studentMode={studentMode}
        initialReport={report}
        selectedParticipantId={selectedParticipantId}
        onSelectedParticipantIdChange={setSelectedParticipantId}
        initialAnchorId={pendingAnchorId}
        loadReport={studentMode ? undefined : reloadTeacherReport}
      />
    );
  }

  if (studentMode) {
    return (
      <div className="student-container py-6 pb-14">
        <section className="student-card px-5 py-6 md:px-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <div className="student-kicker">报告总览</div>
              <h1 className="mt-4 text-[2rem] font-semibold leading-[1.06] tracking-[-0.05em] text-slate-900 md:text-[2.35rem]">
                辩论报告
              </h1>
              <p className="mt-3 text-[15px] leading-7 text-slate-600">{report.topic}</p>
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
                disabled={exporting !== null}
                onClick={() => handleDownload('pdf')}
                className="student-light-button h-auto px-4 py-2"
              >
                <Download className="mr-2 h-4 w-4" />
                {exporting === 'pdf' ? '导出中...' : '导出 PDF'}
              </Button>
            </div>
          </div>
        </section>

        <main className="mt-5">
          <DebateReportOverview
            report={report}
            studentName={studentName}
            studentMode
            selectedParticipantId={selectedParticipantId}
            onSelectedParticipantIdChange={setSelectedParticipantId}
            onDownloadReport={(format) => handleDownload(format)}
            onViewDetails={() => setView('detail')}
          />
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-white via-slate-50 to-blue-50">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white shadow-sm">
        <div className="mx-auto max-w-full px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="sm" onClick={onBack}>
                <ChevronLeft className="mr-2 h-4 w-4" />
                返回
              </Button>
              <div>
                <h1 className="text-2xl font-bold text-slate-900">辩论报告</h1>
                <p className="text-sm text-slate-600">{report.topic}</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                disabled={exporting !== null}
                onClick={() => handleDownload('pdf')}
                className="text-slate-600 hover:text-slate-900"
              >
                <Download className="mr-2 h-4 w-4" />
                {exporting === 'pdf' ? '导出中...' : '导出 PDF'}
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        <section className={`mb-5 rounded-lg border p-4 shadow-sm ${qualityTone.className}`}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex min-w-0 items-start gap-3">
              <QualityIcon className="mt-0.5 h-5 w-5 shrink-0" />
              <div>
                <div className="text-base font-semibold">
                  {getQualityLabel(reportMeta?.report_quality)}
                </div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm">
                  <span>有效发言：{formatMetaStatus(reportMeta?.score_speech_count)}</span>
                  <span>缺失评分：{formatMetaStatus(reportMeta?.score_missing_count)}</span>
                  <span>Markdown：{formatMetaStatus(reportMeta?.report_markdown_cache_status || reportMeta?.report_markdown_status)}</span>
                  <span>PDF：{formatMetaStatus(reportMeta?.report_pdf_cache_status || reportMeta?.report_pdf_status)}</span>
                </div>
                <div className="mt-2 grid gap-1 text-sm md:grid-cols-2 xl:grid-cols-3">
                  <span>评分来源：{getScoringSourceLabel(reportMeta)}</span>
                  <span>量表版本：{formatMetaStatus(reportMeta?.rubric_version)}</span>
                  <span>Prompt Pack：{formatMetaStatus(reportMeta?.prompt_pack_version)}</span>
                  <span>校准版本：{formatMetaStatus(reportMeta?.calibration_version)}</span>
                  <span>证据锚点：{formatMetaStatus(reportMeta?.evidence_anchor_count)}</span>
                  <span>证据来源：{formatEvidenceSources(reportMeta?.evidence_sources)}</span>
                </div>
                {reportMeta?.quality_flags?.length ? (
                  <div className="mt-2 flex flex-wrap gap-2 text-xs">
                    {reportMeta.quality_flags.map((flag) => (
                      <span key={flag} className="rounded-full bg-white/65 px-2 py-1">
                        {flag}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={recalculating}
              onClick={handleRecalculate}
              className="border-current bg-white/70 text-current hover:bg-white"
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${recalculating ? 'animate-spin' : ''}`} />
              {recalculating ? '重算中...' : '重算报告'}
            </Button>
          </div>
        </section>

        <section className="mb-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
          <TeachingSummaryPanel
            summary={teachingSummary}
            loading={summaryLoading}
            onAnchorClick={handleAnchorClick}
          />

          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-3 flex items-center gap-2 text-base font-semibold text-slate-900">
              <MapPinned className="h-5 w-5 text-slate-600" />
              发言锚点
            </div>
            <div className="max-h-[280px] space-y-2 overflow-y-auto pr-1">
              {speechAnchors.slice(0, 12).map((anchor) => (
                <button
                  key={anchor.anchor_id}
                  type="button"
                  onClick={() => handleAnchorClick(anchor.anchor_id)}
                  className="block w-full rounded-md border border-slate-100 px-3 py-2 text-left text-sm transition hover:border-slate-300 hover:bg-slate-50"
                >
                  <div className="flex items-center justify-between gap-2 text-slate-800">
                    <span className="truncate">
                      {anchor.sequence}. {anchor.speaker_name || anchor.speaker_role || '发言'}
                    </span>
                    <span className="shrink-0 text-xs text-slate-500">
                      {anchor.score_status === 'ready' ? '已评分' : '未评分'}
                    </span>
                  </div>
                  {anchor.summary ? (
                    <div className="mt-1 line-clamp-2 text-xs text-slate-500">{anchor.summary}</div>
                  ) : null}
                  <div className="mt-1 text-[11px] text-slate-400">
                    证据来源：{anchor.source_label || anchor.evidence_source || 'Debate speech transcript'}
                  </div>
                </button>
              ))}
              {!speechAnchors.length ? (
                <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-500">
                  暂无可跳转的发言锚点
                </div>
              ) : null}
            </div>
            {speechAnchors.length > 12 ? (
              <div className="mt-3 text-xs text-slate-500">
                已显示前 12 条，可在详情页查看完整发言记录。
              </div>
            ) : null}
          </div>
        </section>

        <DebateReportOverview
          report={report}
          studentName={studentName}
          studentMode={studentMode}
          selectedParticipantId={selectedParticipantId}
          onSelectedParticipantIdChange={setSelectedParticipantId}
          onDownloadReport={(format) => handleDownload(format)}
          onViewDetails={() => setView('detail')}
        />
      </main>
    </div>
  );
};

export default DebateReportPage;
