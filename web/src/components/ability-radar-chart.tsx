import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Brain,
  Zap,
  Heart,
  Users,
  TrendingUp,
  Award,
  Target
} from 'lucide-react';

interface AbilityScore {
  dimension: string;
  score: number;
  icon: React.ReactNode;
  description: string;
  color: string;
  improvement?: number;
}

interface AbilityRadarChartProps {
  scores: AbilityScore[];
  title?: string;
  showComparison?: boolean;
  comparisonScores?: number[];
}

const AbilityRadarChart: React.FC<AbilityRadarChartProps> = ({
  scores,
  title = "五维能力评估",
  showComparison = false,
  comparisonScores = []
}) => {
  const format2 = (value: number) => {
    const n = Number.isFinite(value) ? value : 0;
    return n.toFixed(2);
  };

  const getScoreLevel = (score: number) => {
    if (score >= 90) return { label: '卓越', color: 'text-emerald-600 bg-emerald-50' };
    if (score >= 80) return { label: '优秀', color: 'text-blue-600 bg-blue-50' };
    if (score >= 70) return { label: '良好', color: 'text-amber-600 bg-amber-50' };
    if (score >= 60) return { label: '及格', color: 'text-orange-600 bg-orange-50' };
    return { label: '待提升', color: 'text-red-600 bg-red-50' };
  };

  const getOverallScore = () => {
    if (scores.length === 0) return 0;
    const total = scores.reduce((sum, score) => sum + score.score, 0);
    return Math.round(total / scores.length);
  };

  const renderRadarVisualization = () => {
    const centerX = 150;
    const centerY = 150;
    const maxRadius = 120;
    const levels = 5;
    const canShowComparison = showComparison && comparisonScores.length === scores.length;

    return (
      <svg width="300" height="300" className="mx-auto">
        {/* 背景网格 */}
        {Array.from({ length: levels }, (_, i) => {
          const radius = (maxRadius / levels) * (i + 1);
          const points = scores.map((_, index) => {
            const angle = (index * 2 * Math.PI) / scores.length - Math.PI / 2;
            const x = centerX + radius * Math.cos(angle);
            const y = centerY + radius * Math.sin(angle);
            return `${x},${y}`;
          }).join(' ');

          return (
            <polygon
              key={i}
              points={points}
              fill="none"
              stroke="#e2e8f0"
              strokeWidth="1"
            />
          );
        })}

        {/* 轴线 */}
        {scores.map((_, index) => {
          const angle = (index * 2 * Math.PI) / scores.length - Math.PI / 2;
          const x = centerX + maxRadius * Math.cos(angle);
          const y = centerY + maxRadius * Math.sin(angle);

          return (
            <line
              key={index}
              x1={centerX}
              y1={centerY}
              x2={x}
              y2={y}
              stroke="#cbd5e1"
              strokeWidth="1"
            />
          );
        })}

        {/* 数据区域 */}
        <polygon
          points={scores.map((score, index) => {
            const angle = (index * 2 * Math.PI) / scores.length - Math.PI / 2;
            const radius = (maxRadius * score.score) / 100;
            const x = centerX + radius * Math.cos(angle);
            const y = centerY + radius * Math.sin(angle);
            return `${x},${y}`;
          }).join(' ')}
          fill="#3b82f6"
          fillOpacity="0.3"
          stroke="#3b82f6"
          strokeWidth="2"
        />

        {canShowComparison && (
          <polygon
            points={comparisonScores.map((score, index) => {
              const clamped = Math.max(0, Math.min(100, score || 0));
              const angle = (index * 2 * Math.PI) / scores.length - Math.PI / 2;
              const radius = (maxRadius * clamped) / 100;
              const x = centerX + radius * Math.cos(angle);
              const y = centerY + radius * Math.sin(angle);
              return `${x},${y}`;
            }).join(' ')}
            fill="#8b5cf6"
            fillOpacity="0.16"
            stroke="#8b5cf6"
            strokeWidth="2"
            strokeDasharray="6 4"
          />
        )}

        {/* 数据点 */}
        {scores.map((score, index) => {
          const angle = (index * 2 * Math.PI) / scores.length - Math.PI / 2;
          const radius = (maxRadius * score.score) / 100;
          const x = centerX + radius * Math.cos(angle);
          const y = centerY + radius * Math.sin(angle);

          return (
            <circle
              key={index}
              cx={x}
              cy={y}
              r="4"
              fill="#3b82f6"
              stroke="white"
              strokeWidth="2"
            />
          );
        })}

        {canShowComparison && comparisonScores.map((score, index) => {
          const clamped = Math.max(0, Math.min(100, score || 0));
          const angle = (index * 2 * Math.PI) / scores.length - Math.PI / 2;
          const radius = (maxRadius * clamped) / 100;
          const x = centerX + radius * Math.cos(angle);
          const y = centerY + radius * Math.sin(angle);

          return (
            <circle
              key={`comparison-${index}`}
              cx={x}
              cy={y}
              r="3"
              fill="#8b5cf6"
              stroke="white"
              strokeWidth="2"
            />
          );
        })}

        {/* 标签 */}
        {scores.map((score, index) => {
          const angle = (index * 2 * Math.PI) / scores.length - Math.PI / 2;
          const labelRadius = maxRadius + 20;
          const x = centerX + labelRadius * Math.cos(angle);
          const y = centerY + labelRadius * Math.sin(angle);

          return (
            <text
              key={index}
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="middle"
              className="text-xs font-medium fill-slate-700"
            >
              {score.dimension}
            </text>
          );
        })}
      </svg>
    );
  };

  const overallScore = getOverallScore();
  const overallLevel = getScoreLevel(overallScore);

  if (scores.length === 0) {
    return (
      <Card className="bg-white border-slate-200 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Award className="w-5 h-5 text-blue-600" />
              {title}
            </div>
            <Badge className="bg-slate-100 text-slate-700 border-slate-300">暂无数据</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center text-sm text-slate-500 py-10">暂无能力评估数据</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-white border-slate-200 shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Target className="w-5 h-5 text-blue-600" />
            {title}
          </div>
          <div className="flex items-center gap-3">
            <Badge className={overallLevel.color} variant="outline">
              <Award className="w-3 h-3 mr-1" />
              {overallLevel.label}
            </Badge>
            <div className="text-right">
              <div className="text-2xl font-bold text-slate-900">{overallScore}</div>
              <div className="text-xs text-slate-500">综合评分</div>
            </div>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* 雷达图 */}
        <div className="flex justify-center">
          {renderRadarVisualization()}
        </div>

        {showComparison && comparisonScores.length === scores.length && (
          <div className="flex items-center justify-center gap-3 text-xs text-slate-600">
            <div className="flex items-center gap-2">
              <span className="inline-block w-2.5 h-2.5 rounded-full bg-blue-500" />
              <span>我的能力</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block w-2.5 h-2.5 rounded-full bg-purple-500" />
              <span>对比参考</span>
            </div>
          </div>
        )}

        {/* 详细分数 */}
        <div className="space-y-4">
          <h4 className="font-medium text-slate-900 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            能力维度详情
          </h4>

          <div className="space-y-3">
            {scores.map((score, index) => {
              const level = getScoreLevel(score.score);
              const showImprovement = score.improvement && score.improvement > 0;

              return (
                <div key={index} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center">
                        {score.icon}
                      </div>
                      <div>
                        <div className="font-medium text-slate-900">{score.dimension}</div>
                        <div className="text-xs text-slate-500">{score.description}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-lg font-bold text-slate-900">{format2(score.score)}</span>
                      <Badge className={level.color} variant="outline">
                        {level.label}
                      </Badge>
                      {showImprovement && (
                        <Badge className="bg-emerald-100 text-emerald-700 border-emerald-300">
                          +{score.improvement}
                        </Badge>
                      )}
                    </div>
                  </div>

                  <Progress
                    value={score.score}
                    className="h-2"
                  />
                </div>
              );
            })}
          </div>
        </div>

        {/* 对比展示（如果有对比数据） */}
        {showComparison && comparisonScores.length > 0 && (
          <div className="border-t border-slate-200 pt-4">
            <h4 className="font-medium text-slate-900 mb-3">与平均水平对比</h4>
            <div className="grid grid-cols-5 gap-2">
              {scores.map((score, index) => {
                const base = comparisonScores[index] ?? 0;
                const diff = score.score - base;
                return (
                <div key={index} className="text-center">
                  <div className="text-xs text-slate-600 mb-1">{score.dimension}</div>
                  <div className="flex flex-col items-center">
                    <div className="text-sm font-medium text-slate-900">{format2(score.score)}</div>
                    <div className="text-xs text-slate-500">vs {format2(base)}</div>
                    <div className={`text-xs font-medium ${
                      diff > 0
                        ? 'text-emerald-600'
                        : diff < 0
                        ? 'text-red-600'
                        : 'text-slate-600'
                    }`}>
                      {diff > 0 && '+'}
                      {format2(diff)}
                    </div>
                  </div>
                </div>
              )})}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default AbilityRadarChart;
