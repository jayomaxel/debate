import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Trophy,
  Users,
  Bot,
  TrendingUp,
  Award,
  Target,
  Star,
  Zap,
  Shield
} from 'lucide-react';

interface DebateResult {
  winner: 'human' | 'ai' | 'draw';
  humanScore: number;
  aiScore: number;
  debateTopic: string;
  userStance: 'positive' | 'negative';
  duration: string;
  keyMetrics: {
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
}

const DebateResultDisplay: React.FC<DebateResultDisplayProps> = ({
  result,
  onViewDetails,
  onDownloadReport
}) => {
  const getResultConfig = () => {
    switch (result.winner) {
      case 'human':
        return {
          title: '胜利！',
          subtitle: '人类团队获胜',
          color: 'from-emerald-500 to-blue-600',
          bgColor: 'bg-gradient-to-br from-emerald-50 to-blue-50',
          borderColor: 'border-emerald-300',
          textColor: 'text-emerald-700',
          icon: <Trophy className="w-12 h-12 text-emerald-600" />,
          message: '恭喜！您和您的团队在这次辩论中表现出色，成功击败了AI团队。'
        };
      case 'ai':
        return {
          title: '惜败',
          subtitle: 'AI团队获胜',
          color: 'from-purple-500 to-pink-600',
          bgColor: 'bg-gradient-to-br from-purple-50 to-pink-50',
          borderColor: 'border-purple-300',
          textColor: 'text-purple-700',
          icon: <Bot className="w-12 h-12 text-purple-600" />,
          message: '虽然这次没有获胜，但您的表现依然出色，AI团队展现了强大的辩论能力。'
        };
      case 'draw':
        return {
          title: '平局',
          subtitle: '势均力敌',
          color: 'from-amber-500 to-orange-600',
          bgColor: 'bg-gradient-to-br from-amber-50 to-orange-50',
          borderColor: 'border-amber-300',
          textColor: 'text-amber-700',
          icon: <Award className="w-12 h-12 text-amber-600" />,
          message: '这是一场精彩的辩论，双方展现了相当的实力，最终以平局收场。'
        };
      default:
        return {
          title: '结果',
          subtitle: '辩论结束',
          color: 'from-slate-500 to-slate-600',
          bgColor: 'bg-gradient-to-br from-slate-50 to-slate-100',
          borderColor: 'border-slate-300',
          textColor: 'text-slate-700',
          icon: <Target className="w-12 h-12 text-slate-600" />,
          message: '辩论已结束，感谢您的参与。'
        };
    }
  };

  const getScoreColor = (score: number, isHuman: boolean) => {
    if (score >= 80) return isHuman ? 'text-emerald-600' : 'text-purple-600';
    if (score >= 70) return isHuman ? 'text-blue-600' : 'text-pink-600';
    if (score >= 60) return isHuman ? 'text-amber-600' : 'text-orange-600';
    return isHuman ? 'text-red-600' : 'text-red-600';
  };

  const config = getResultConfig();
  const scoreDifference = Math.abs(result.humanScore - result.aiScore);

  return (
    <Card className={`${config.bgColor} ${config.borderColor} border-2 shadow-xl overflow-hidden`}>
      <CardContent className="p-8">
        {/* 主要结果展示 */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            {config.icon}
          </div>

          <h1 className={`text-4xl font-bold bg-gradient-to-r ${config.color} bg-clip-text text-transparent mb-2`}>
            {config.title}
          </h1>
          <h2 className="text-2xl font-semibold text-slate-800 mb-4">
            {config.subtitle}
          </h2>
          <p className="text-slate-600 max-w-2xl mx-auto">
            {config.message}
          </p>
        </div>

        {/* 评分对比 */}
        <div className="mb-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* 人类团队 */}
            <div className={`p-6 rounded-xl border-2 ${
              result.winner === 'human'
                ? 'border-emerald-400 bg-emerald-50'
                : 'border-slate-300 bg-white'
            }`}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Users className="w-6 h-6 text-blue-600" />
                  <h3 className="text-lg font-bold text-slate-900">人类团队</h3>
                </div>
                {result.winner === 'human' && (
                  <Badge className="bg-emerald-100 text-emerald-700 border-emerald-300">
                    <Trophy className="w-3 h-3 mr-1" />
                    获胜
                  </Badge>
                )}
              </div>

              <div className="text-center mb-4">
                <div className={`text-4xl font-bold ${getScoreColor(result.humanScore, true)}`}>
                  {result.humanScore}
                </div>
                <div className="text-sm text-slate-600">综合得分</div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">逻辑建构力</span>
                  <span className={`font-medium ${getScoreColor(result.keyMetrics.logicScore, true)}`}>
                    {result.keyMetrics.logicScore}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">AI核心知识运用</span>
                  <span className={`font-medium ${getScoreColor(result.keyMetrics.argumentScore, true)}`}>
                    {result.keyMetrics.argumentScore}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">批判性思维</span>
                  <span className={`font-medium ${getScoreColor(result.keyMetrics.responseScore, true)}`}>
                    {result.keyMetrics.responseScore}
                  </span>
                </div>
              </div>
            </div>

            {/* AI团队 */}
            <div className={`p-6 rounded-xl border-2 ${
              result.winner === 'ai'
                ? 'border-purple-400 bg-purple-50'
                : 'border-slate-300 bg-white'
            }`}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Bot className="w-6 h-6 text-purple-600" />
                  <h3 className="text-lg font-bold text-slate-900">AI团队</h3>
                </div>
                {result.winner === 'ai' && (
                  <Badge className="bg-purple-100 text-purple-700 border-purple-300">
                    <Trophy className="w-3 h-3 mr-1" />
                    获胜
                  </Badge>
                )}
              </div>

              <div className="text-center mb-4">
                <div className={`text-4xl font-bold ${getScoreColor(result.aiScore, false)}`}>
                  {result.aiScore}
                </div>
                <div className="text-sm text-slate-600">综合得分</div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">逻辑建构力</span>
                  <span className={`font-medium ${getScoreColor(result.keyMetrics.logicScore, false)}`}>
                    {result.keyMetrics.logicScore + 5}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">AI核心知识运用</span>
                  <span className={`font-medium ${getScoreColor(result.keyMetrics.argumentScore, false)}`}>
                    {result.keyMetrics.argumentScore + 8}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">批判性思维</span>
                  <span className={`font-medium ${getScoreColor(result.keyMetrics.responseScore, false)}`}>
                    {result.keyMetrics.responseScore + 3}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* 得分差异显示 */}
          <div className="text-center mt-4">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-slate-100 rounded-full">
              <span className="text-sm text-slate-600">得分差异：</span>
              <span className="font-bold text-slate-900">{scoreDifference} 分</span>
            </div>
          </div>
        </div>

        {/* 辩论信息 */}
        <div className="mb-6">
          <div className="bg-white/60 rounded-lg border border-slate-200 p-4">
            <h4 className="font-medium text-slate-900 mb-3">辩论信息</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-slate-600">辩题：</span>
                <span className="text-slate-900 font-medium block">{result.debateTopic}</span>
              </div>
              <div>
                <span className="text-slate-600">您的立场：</span>
                <span className="text-slate-900 font-medium block">
                  {result.userStance === 'positive' ? '正方（支持）' : '反方（反对）'}
                </span>
              </div>
              <div>
                <span className="text-slate-600">辩论时长：</span>
                <span className="text-slate-900 font-medium block">{result.duration}</span>
              </div>
              <div>
                <span className="text-slate-600">完成时间：</span>
                <span className="text-slate-900 font-medium block">
                  {new Date().toLocaleString('zh-CN')}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* 操作按钮 */}
        <div className="flex items-center justify-center gap-4">
          <Button
            onClick={onViewDetails}
            variant="outline"
            className="border-slate-300 text-slate-700 hover:bg-slate-50"
          >
            <TrendingUp className="w-4 h-4 mr-2" />
            查看详细分析
          </Button>
          <Button
            onClick={onDownloadReport}
            className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white"
          >
            <Star className="w-4 h-4 mr-2" />
            下载完整报告
          </Button>
        </div>

        {/* 装饰性元素 */}
        <div className="absolute top-4 left-4 w-16 h-16 opacity-10">
          <Zap className="w-full h-full text-slate-600" />
        </div>
        <div className="absolute bottom-4 right-4 w-16 h-16 opacity-10">
          <Shield className="w-full h-full text-slate-600" />
        </div>
      </CardContent>
    </Card>
  );
};

export default DebateResultDisplay;
