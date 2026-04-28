import React, { useState, useEffect } from 'react';
import { ArrowLeft, Download, TrendingUp, Award, Clock, Users, Trophy, /* Mail */ } from 'lucide-react';
import StudentService, { type DebateReport } from '../services/student.service';
import { useAuth } from '../store/auth.context';
import { useToast } from '@/hooks/use-toast';

interface ReportDetailProps {
  debateId: string;
  onBack: () => void;
}

export const DebateReportDetail: React.FC<ReportDetailProps> = ({ debateId, onBack }) => {
  const { toast } = useToast();
  const [report, setReport] = useState<DebateReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<'pdf' | 'excel' | null>(null);
  // const [sendingEmail, setSendingEmail] = useState(false);
  const { user } = useAuth();

  useEffect(() => {
    loadReport();
  }, [debateId]);

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

  const getPhaseLabel = (phase: string) => {
    const labels: Record<string, string> = {
      opening: '立论阶段',
      questioning: '盘问阶段',
      free_debate: '自由辩论',
      closing: '总结陈词'
    };
    return labels[phase] || phase;
  };

  const getStanceLabel = (stance: string) => {
    return stance === 'positive' ? '正方' : '反方';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto mb-4"></div>
          <p className="text-gray-600">加载报告中...</p>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <p className="text-gray-600 mb-4">报告加载失败</p>
          <button
            onClick={onBack}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
          >
            返回
          </button>
        </div>
      </div>
    );
  }

  // 优先查找当前用户的参与记录，如果未找到（如管理员查看）则默认显示第一个参与者
  const participant = report.participants.find(p => p.user_id === user?.id) || report.participants[0];

  const statistics = report.statistics as unknown as {
    positive: { avg_score: number; speech_count: number; total_duration: number };
    negative: { avg_score: number; speech_count: number; total_duration: number };
    winner: 'positive' | 'negative' | 'tie';
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      {/* 头部 */}
      <div className="max-w-6xl mx-auto mb-6">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeft className="w-5 h-5" />
          返回
        </button>

        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 mb-2">{report.topic}</h1>
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <span className="flex items-center gap-1">
                  <Clock className="w-4 h-4" />
                  {new Date(report.start_time || '').toLocaleString('zh-CN')}
                </span>
                <span>时长: {report.duration}分钟</span>
                <span className="flex items-center gap-1">
                  <Users className="w-4 h-4" />
                  {report.participants.length}位参与者
                </span>
              </div>
            </div>
            <div className="flex gap-2">
              {/*
              <button
                onClick={handleSendEmail}
                disabled={exporting !== null || sendingEmail}
                className="flex items-center gap-2 px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
              >
                <Mail className="w-4 h-4" />
                {sendingEmail ? '发送中...' : '发送邮件'}
              </button>
              */}
              <button
                onClick={() => handleExport('pdf')}
                disabled={exporting !== null}
                className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
              >
                <Download className="w-4 h-4" />
                {exporting === 'pdf' ? '导出中...' : '导出PDF'}
              </button>
              {/*<button
                onClick={() => handleExport('excel')}
                disabled={exporting !== null}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
              >
                <Download className="w-4 h-4" />
                {exporting === 'excel' ? '导出中...' : '导出Excel'}
              </button>
              */}
            </div>
          </div>
        </div>
      </div>

      {/* 辩论室结果总览 */}
      {statistics && (
        <div className="max-w-6xl mx-auto mb-6">
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
              <Trophy className="w-5 h-5 text-yellow-500" />
              辩论结果总览
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* 正方数据 */}
              <div className={`p-4 rounded-lg border-2 ${statistics.winner === 'positive' ? 'border-emerald-400 bg-emerald-50' : 'border-gray-200'}`}>
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-bold text-gray-900">正方</h3>
                  {statistics.winner === 'positive' && <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-1 rounded-full">获胜</span>}
                </div>
                <div className="text-3xl font-bold text-emerald-600 mb-2">{statistics.positive?.avg_score || 0}</div>
                <div className="text-sm text-gray-600">
                  <div>平均得分</div>
                  <div className="mt-2 text-xs">
                    发言: {statistics.positive?.speech_count || 0} 次 | 时长: {Math.round((statistics.positive?.total_duration || 0) / 60)} 分钟
                  </div>
                </div>
              </div>

              {/* 结果展示 */}
              <div className="flex flex-col items-center justify-center">
                <div className="text-lg font-bold text-gray-900 mb-2">
                  {statistics.winner === 'positive' ? '正方获胜' : statistics.winner === 'negative' ? '反方获胜' : '平局'}
                </div>
                <div className="text-sm text-gray-500 text-center">
                  双方经过激烈辩论<br/>
                  {statistics.winner !== 'tie' ? '最终决出胜负' : '最终势均力敌'}
                </div>
              </div>

              {/* 反方数据 */}
              <div className={`p-4 rounded-lg border-2 ${statistics.winner === 'negative' ? 'border-purple-400 bg-purple-50' : 'border-gray-200'}`}>
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-bold text-gray-900">反方</h3>
                  {statistics.winner === 'negative' && <span className="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded-full">获胜</span>}
                </div>
                <div className="text-3xl font-bold text-purple-600 mb-2">{statistics.negative?.avg_score || 0}</div>
                <div className="text-sm text-gray-600">
                  <div>平均得分</div>
                  <div className="mt-2 text-xs">
                    发言: {statistics.negative?.speech_count || 0} 次 | 时长: {Math.round((statistics.negative?.total_duration || 0) / 60)} 分钟
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 个人表现总览 */}
      {participant ? (
        <div className="max-w-6xl mx-auto mb-6">
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
              <Award className="w-5 h-5 text-purple-600" />
              个人表现总览
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="text-center p-4 bg-purple-50 rounded-lg">
                <div className="text-3xl font-bold text-purple-600">{participant.final_score.overall_score.toFixed(1)}</div>
                <div className="text-sm text-gray-600 mt-1">总分</div>
              </div>
              <div className="text-center p-4 bg-blue-50 rounded-lg">
                <div className="text-3xl font-bold text-blue-600">{participant.final_score.speech_count}</div>
                <div className="text-sm text-gray-600 mt-1">发言次数</div>
              </div>
              <div className="text-center p-4 bg-green-50 rounded-lg">
                <div className="text-2xl font-bold text-green-600">{getStanceLabel(participant.stance)}</div>
                <div className="text-sm text-gray-600 mt-1">立场</div>
              </div>
              <div className="text-center p-4 bg-amber-50 rounded-lg">
                <div className="text-2xl font-bold text-amber-600">{participant.role}</div>
                <div className="text-sm text-gray-600 mt-1">角色</div>
              </div>
            </div>

            {/* 五维能力雷达图数据 */}
            <div className="grid grid-cols-5 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">{participant.final_score.logic_score.toFixed(1)}</div>
                <div className="text-sm text-gray-600">逻辑建构力</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">{participant.final_score.argument_score.toFixed(1)}</div>
                <div className="text-sm text-gray-600">AI核心知识运用</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">{participant.final_score.response_score.toFixed(1)}</div>
                <div className="text-sm text-gray-600">批判性思维</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">{participant.final_score.persuasion_score.toFixed(1)}</div>
                <div className="text-sm text-gray-600">语言表达力</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">{participant.final_score.teamwork_score.toFixed(1)}</div>
                <div className="text-sm text-gray-600">AI伦理与科技素养</div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="max-w-6xl mx-auto mb-6">
           <div className="bg-white rounded-lg shadow-sm p-6 text-center text-gray-500">
              您未参与该辩论，无法查看个人表现数据
           </div>
        </div>
      )}

      {/* 发言详情 */}
      <div className="max-w-6xl mx-auto">
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-purple-600" />
            发言详情与评分
          </h2>
          <div className="space-y-4">
            {report.speeches.map((speech, index) => (
              <div key={speech.id} className="border border-gray-200 rounded-lg p-4">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <div className="text-sm font-semibold text-gray-900 mb-1">
                      {(speech.speaker_name || speech.speaker_role || '未知发言者') +
                        (speech.stance ? `（${getStanceLabel(String(speech.stance))}）` : '')}
                    </div>
                    <span className="inline-block px-2 py-1 bg-purple-100 text-purple-700 text-xs rounded mr-2">
                      {getPhaseLabel(speech.phase)}
                    </span>
                    <span className="text-sm text-gray-500">
                      {new Date(speech.timestamp).toLocaleTimeString('zh-CN')}
                    </span>
                  </div>
                  {speech.score && (
                    <div className="text-right">
                      <div className="text-2xl font-bold text-purple-600">{speech.score.overall_score.toFixed(1)}</div>
                      <div className="text-xs text-gray-500">本次得分</div>
                    </div>
                  )}
                </div>
                <p className="text-gray-700 mb-3">{speech.content}</p>
                {speech.score && (
                  <div className="bg-gray-50 rounded p-3">
                    <div className="grid grid-cols-5 gap-2 mb-2 text-xs">
                      <div>
                        <span className="text-gray-600">逻辑:</span>
                        <span className="ml-1 font-semibold">{speech.score.logic_score.toFixed(1)}</span>
                      </div>
                      <div>
                        <span className="text-gray-600">知识:</span>
                        <span className="ml-1 font-semibold">{speech.score.argument_score.toFixed(1)}</span>
                      </div>
                      <div>
                        <span className="text-gray-600">思维:</span>
                        <span className="ml-1 font-semibold">{speech.score.response_score.toFixed(1)}</span>
                      </div>
                      <div>
                        <span className="text-gray-600">表达:</span>
                        <span className="ml-1 font-semibold">{speech.score.persuasion_score.toFixed(1)}</span>
                      </div>
                      <div>
                        <span className="text-gray-600">伦理:</span>
                        <span className="ml-1 font-semibold">{speech.score.teamwork_score.toFixed(1)}</span>
                      </div>
                    </div>
                    {speech.score.feedback && (
                      <div className="text-sm text-gray-600 border-t border-gray-200 pt-2 mt-2">
                        <span className="font-semibold">评语:</span> {speech.score.feedback}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
