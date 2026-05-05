import React, { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import StudentService, { type DebateReport } from '../services/student.service';
import DebateReportOverview from './debate-report-overview';
import { DebateReportDetail } from './debate-report-detail';
import { ChevronLeft, Download, Loader2 } from 'lucide-react';
import { useAuth } from '../store/auth.context';

interface DebateReportPageProps {
  debateId: string;
  studentName?: string;
  onBack: () => void;
  studentMode?: boolean;
}

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

  useEffect(() => {
    const fetchReport = async () => {
      try {
        setLoading(true);
        const data = await StudentService.getReport(debateId);
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
