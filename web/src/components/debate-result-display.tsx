import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { formatStudentDateTime } from '@/lib/student-display';
import {
  Trophy,
  Users,
  Bot,
  TrendingUp,
  Award,
  Star,
} from 'lucide-react';

interface DebateResult {
  winner: 'human' | 'ai' | 'draw';
  humanScore: number;
  aiScore: number;
  debateTopic: string;
  userStance: 'positive' | 'negative';
  duration: string;
  completedAt?: string | null;
  keyMetrics: {
    logicScore: number;
    argumentScore: number;
    responseScore: number;
    persuasionScore: number;
    teamworkScore: number;
  };
  aiMetrics?: {
    logicScore: number;
    argumentScore: number;
    responseScore: number;
    persuasionScore: number;
    teamworkScore: number;
  };
}

interface DebateResultDisplayProps {
  result: DebateResult;
  onViewDetails?: () => void;
  onDownloadReport?: () => void;
  studentMode?: boolean;
}

const DebateResultDisplay: React.FC<DebateResultDisplayProps> = ({
  result,
  onViewDetails,
  onDownloadReport,
  studentMode = false,
}) => {
  const getResultConfig = () => {
    switch (result.winner) {
      case 'human':
        return {
          title: '胜利',
          subtitle: '人类团队获胜',
          cardTone: 'student-card-soft-blue',
          textTone: 'text-slate-900',
          icon: <Trophy className="h-12 w-12 text-slate-900" />,
          message: '恭喜，你和你的团队在这次辩论中表现出色，成功战胜了 AI 团队。',
        };
      case 'ai':
        return {
          title: '惜败',
          subtitle: 'AI 团队获胜',
          cardTone: 'student-card-soft-lavender',
          textTone: 'text-slate-900',
          icon: <Bot className="h-12 w-12 text-slate-900" />,
          message: '虽然这次没有获胜，但你的表现依然有亮点，这份报告会帮助你更快找到改进方向。',
        };
      case 'draw':
      default:
        return {
          title: '平局',
          subtitle: '双方势均力敌',
          cardTone: 'student-card-soft-peach',
          textTone: 'text-slate-900',
          icon: <Award className="h-12 w-12 text-slate-900" />,
          message: '这是一场精彩的辩论，双方展现了相当的实力，最终以平局收场。',
        };
    }
  };

  const config = getResultConfig();
  const scoreDifference = Math.abs(result.humanScore - result.aiScore);
  const completedAt = formatStudentDateTime(result.completedAt);
  const infoItems = [
    { label: '辩题', value: result.debateTopic },
    {
      label: '你的立场',
      value: result.userStance === 'positive' ? '正方（支持）' : '反方（反对）',
    },
    { label: '辩论时长', value: result.duration },
    completedAt ? { label: '完成时间', value: completedAt } : null,
  ].filter(Boolean) as Array<{ label: string; value: string }>;

  return (
    <Card
      className={
        studentMode
          ? 'overflow-hidden rounded-[16px] border border-[#d7ccbf] bg-white/88 shadow-[0_14px_34px_rgba(58,42,28,0.07)]'
          : 'overflow-hidden border-2 shadow-xl'
      }
    >
      <CardContent className="p-5">
        <div className={`${studentMode ? config.cardTone : ''} rounded-[14px] p-5`}>
          <div className="mb-6 text-center">
            <div className="mb-4 flex justify-center">{config.icon}</div>

            <h1 className={`mb-2 text-[2rem] font-bold tracking-[-0.05em] ${config.textTone}`}>
              {config.title}
            </h1>
            <h2 className="mb-3 text-[1.4rem] font-semibold text-slate-800">
              {config.subtitle}
            </h2>
            <p className="mx-auto max-w-2xl text-slate-600">{config.message}</p>
          </div>

          <div className="mb-6">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="student-card-muted p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Users className="h-6 w-6 text-slate-700" />
                    <h3 className="text-lg font-bold text-slate-900">人类团队</h3>
                  </div>
                  {result.winner === 'human' ? (
                    <Badge className="student-pill">获胜</Badge>
                  ) : null}
                </div>

                <div className="mb-3 text-center">
                  <div className="text-[1.9rem] font-bold text-slate-900">{result.humanScore}</div>
                  <div className="text-sm text-slate-600">综合得分</div>
                </div>

                <div className="space-y-2 text-sm">
                  <MetricRow label="逻辑建构能力" value={result.keyMetrics.logicScore} />
                  <MetricRow label="AI 核心知识运用" value={result.keyMetrics.argumentScore} />
                  <MetricRow label="批判性思维" value={result.keyMetrics.responseScore} />
                </div>
              </div>

              <div className="student-card-muted p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Bot className="h-6 w-6 text-slate-700" />
                    <h3 className="text-lg font-bold text-slate-900">AI 团队</h3>
                  </div>
                  {result.winner === 'ai' ? <Badge className="student-pill">获胜</Badge> : null}
                </div>

                <div className="mb-3 text-center">
                  <div className="text-[1.9rem] font-bold text-slate-900">{result.aiScore}</div>
                  <div className="text-sm text-slate-600">综合得分</div>
                </div>

                <div className="space-y-2 text-sm">
                  <MetricRow label="逻辑建构能力" value={result.aiMetrics?.logicScore || 0} />
                  <MetricRow
                    label="AI 核心知识运用"
                    value={result.aiMetrics?.argumentScore || 0}
                  />
                  <MetricRow label="批判性思维" value={result.aiMetrics?.responseScore || 0} />
                </div>
              </div>
            </div>

            <div className="mt-3 text-center">
              <div className="student-pill inline-flex gap-2">
                <span className="text-slate-600">得分差异：</span>
                <span className="font-bold text-slate-900">{scoreDifference} 分</span>
              </div>
            </div>
          </div>

          <div className="mb-5 student-card-muted p-4">
            <h4 className="mb-3 font-medium text-slate-900">辩论信息</h4>
            <div className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
              {infoItems.map((item) => (
                <div key={item.label}>
                  <span className="text-slate-600">{item.label}：</span>
                  <span className="mt-1 block font-medium text-slate-900">
                    {item.value}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-center gap-4">
            <Button
              onClick={onViewDetails}
              variant="outline"
              className={studentMode ? 'student-light-button h-auto' : ''}
            >
              <TrendingUp className="mr-2 h-4 w-4" />
              查看详细分析
            </Button>
            <Button
              onClick={onDownloadReport}
              className={studentMode ? 'student-dark-button h-auto' : ''}
            >
              <Star className="mr-2 h-4 w-4" />
              下载完整报告
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

function MetricRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-600">{label}</span>
      <span className="font-medium text-slate-900">{value}</span>
    </div>
  );
}

export default DebateResultDisplay;
