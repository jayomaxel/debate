import React, { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import StudentService, { type DebateReport } from '../services/student.service';
import DebateReportOverview from './debate-report-overview';
import { DebateReportDetail } from './debate-report-detail';
import { ChevronLeft, Download, Loader2, /* Mail */ } from 'lucide-react';

interface DebateReportPageProps {
  debateId: string;
  studentName?: string;
  onBack: () => void;
}

const DebateReportPage: React.FC<DebateReportPageProps> = ({ debateId, studentName, onBack }) => {
  const { toast } = useToast();
  const [report, setReport] = useState<DebateReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<'pdf' | 'excel' | null>(null);
  // const [sendingEmail, setSendingEmail] = useState(false);
  const [view, setView] = useState<'overview' | 'detail'>('overview');

  useEffect(() => {
    const fetchReport = async () => {
      try {
        setLoading(true);
        const data = await StudentService.getReport(debateId);
        setReport(data);
      } catch (error: any) {
        toast({
          title: "获取报告失败",
          description: error?.message || "无法加载辩论报告数据，请稍后重试",
          variant: "destructive"
        });
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, [debateId, toast]);

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
        title: "导出失败",
        description: error?.message || "导出报告失败，请稍后重试",
        variant: "destructive"
      });
    } finally {
      setExporting(null);
    }
  };

  // const handleSendEmail = async () => {
  //   try {
  //     setSendingEmail(true);
  //     await StudentService.sendReportEmail(debateId);
  //     toast({
  //       title: "邮件发送成功",
  //       description: "报告内容已发送到您的邮箱",
  //     });
  //   } catch (error: any) {
  //     toast({
  //       title: "邮件发送失败",
  //       description: error?.message || "邮件发送失败，请稍后重试",
  //       variant: "destructive"
  //     });
  //   } finally {
  //     setSendingEmail(false);
  //   }
  // };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-slate-600">正在加载辩论报告...</p>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-600 mb-4">报告加载失败</p>
          <Button onClick={onBack}>返回</Button>
        </div>
      </div>
    );
  }

  if (view === 'detail') {
    return <DebateReportDetail debateId={debateId} onBack={() => setView('overview')} />;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-purple-50">
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
                <h1 className="text-2xl font-bold text-slate-900">辩论报告</h1>
                <p className="text-sm text-slate-600">{report.topic}</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/*
              <Button
                variant="ghost"
                size="sm"
                disabled={exporting !== null || sendingEmail}
                onClick={handleSendEmail}
                className="text-slate-600 hover:text-slate-900"
              >
                <Mail className="w-4 h-4 mr-2" />
                {sendingEmail ? '发送中...' : '发送邮件'}
              </Button>
              */}
              <Button
                variant="ghost"
                size="sm"
                disabled={exporting !== null}
                onClick={() => handleDownload('pdf')}
                className="text-slate-600 hover:text-slate-900"
              >
                <Download className="w-4 h-4 mr-2" />
                {exporting === 'pdf' ? '导出中...' : '导出PDF'}
              </Button>
              {/*<Button
                variant="ghost"
                size="sm"
                disabled={exporting !== null}
                onClick={() => handleDownload('excel')}
                className="text-slate-600 hover:text-slate-900"
              >
                <Download className="w-4 h-4 mr-2" />
                {exporting === 'excel' ? '导出中...' : '导出Excel'}
              </Button>
               */}
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        <DebateReportOverview
          report={report}
          studentName={studentName}
          onDownloadReport={(format) => handleDownload(format)}
          onViewDetails={() => setView('detail')}
        />
      </main>
    </div>
  );
};

export default DebateReportPage;
