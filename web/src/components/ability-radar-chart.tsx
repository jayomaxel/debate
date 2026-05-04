import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Award, Target, TrendingUp } from 'lucide-react';

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
  studentMode?: boolean;
}

const themeCard = (studentMode: boolean) =>
  studentMode
    ? 'rounded-[16px] border border-[#d7ccbf] bg-white/88 shadow-[0_14px_34px_rgba(58,42,28,0.07)]'
    : 'bg-white border-slate-200 shadow-sm';

const AbilityRadarChart: React.FC<AbilityRadarChartProps> = ({
  scores,
  title = '五维能力评估',
  showComparison = false,
  comparisonScores = [],
  studentMode = false,
}) => {
  const format2 = (value: number) => {
    const n = Number.isFinite(value) ? value : 0;
    return n.toFixed(2);
  };

  const getScoreLevel = (score: number) => {
    if (score >= 90) return { label: '卓越', color: 'text-emerald-700 bg-emerald-50' };
    if (score >= 80) return { label: '优秀', color: 'text-[#7c5e40] bg-[#f2e7da]' };
    if (score >= 70) return { label: '良好', color: 'text-amber-700 bg-amber-50' };
    if (score >= 60) return { label: '及格', color: 'text-orange-700 bg-orange-50' };
    return { label: '待提升', color: 'text-slate-700 bg-slate-100' };
  };

  const getOverallScore = () => {
    if (scores.length === 0) return 0;
    const total = scores.reduce((sum, score) => sum + score.score, 0);
    return Math.round(total / scores.length);
  };

  const renderRadarVisualization = () => {
    const svgWidth = 340;
    const svgHeight = 320;
    const centerX = svgWidth / 2;
    const centerY = svgHeight / 2;
    const maxRadius = 110;
    const levels = 5;
    const canShowComparison =
      showComparison && comparisonScores.length === scores.length;
    const labelRadius = maxRadius + 18;

    const getLabelAnchor = (angle: number) => {
      const horizontal = Math.cos(angle);
      if (horizontal > 0.35) return 'end';
      if (horizontal < -0.35) return 'start';
      return 'middle';
    };

    const getLabelPosition = (angle: number) => {
      const horizontal = Math.cos(angle);
      const vertical = Math.sin(angle);

      return {
        x:
          centerX +
          labelRadius * horizontal +
          (Math.abs(horizontal) > 0.2 ? Math.sign(horizontal) * 12 : 0),
        y:
          centerY +
          labelRadius * vertical +
          (Math.abs(vertical) > 0.2 ? Math.sign(vertical) * 6 : 0),
      };
    };

    return (
      <svg width={svgWidth} height={svgHeight} className="mx-auto">
        {Array.from({ length: levels }, (_, i) => {
          const radius = (maxRadius / levels) * (i + 1);
          const points = scores
            .map((_, index) => {
              const angle = (index * 2 * Math.PI) / scores.length - Math.PI / 2;
              const x = centerX + radius * Math.cos(angle);
              const y = centerY + radius * Math.sin(angle);
              return `${x},${y}`;
            })
            .join(' ');

          return (
            <polygon
              key={i}
              points={points}
              fill="none"
              stroke="#ddd3c7"
              strokeWidth="1"
            />
          );
        })}

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
              stroke="#d0c4b7"
              strokeWidth="1"
            />
          );
        })}

        <polygon
          points={scores
            .map((score, index) => {
              const angle = (index * 2 * Math.PI) / scores.length - Math.PI / 2;
              const radius = (maxRadius * score.score) / 100;
              const x = centerX + radius * Math.cos(angle);
              const y = centerY + radius * Math.sin(angle);
              return `${x},${y}`;
            })
            .join(' ')}
          fill="#171717"
          fillOpacity="0.22"
          stroke="#171717"
          strokeWidth="2"
        />

        {canShowComparison ? (
          <polygon
            points={comparisonScores
              .map((score, index) => {
                const clamped = Math.max(0, Math.min(100, score || 0));
                const angle = (index * 2 * Math.PI) / scores.length - Math.PI / 2;
                const radius = (maxRadius * clamped) / 100;
                const x = centerX + radius * Math.cos(angle);
                const y = centerY + radius * Math.sin(angle);
                return `${x},${y}`;
              })
              .join(' ')}
            fill="#d8c8b8"
            fillOpacity="0.28"
            stroke="#b59676"
            strokeWidth="2"
            strokeDasharray="6 4"
          />
        ) : null}

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
              fill="#171717"
              stroke="white"
              strokeWidth="2"
            />
          );
        })}

        {canShowComparison
          ? comparisonScores.map((score, index) => {
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
                  fill="#b59676"
                  stroke="white"
                  strokeWidth="2"
                />
              );
            })
          : null}

        {scores.map((score, index) => {
          const angle = (index * 2 * Math.PI) / scores.length - Math.PI / 2;
          const { x, y } = getLabelPosition(angle);

          return (
            <text
              key={index}
              x={x}
              y={y}
              textAnchor={getLabelAnchor(angle)}
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
      <Card className={themeCard(studentMode)}>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Award className="h-5 w-5 text-slate-700" />
              {title}
            </div>
            <Badge className="student-pill">暂无数据</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="py-10 text-center text-sm text-slate-500">
            暂无能力评估数据
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={themeCard(studentMode)}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Target className="h-5 w-5 text-slate-700" />
            {title}
          </div>
          <div className="flex items-center gap-3">
            <Badge className={overallLevel.color} variant="outline">
              <Award className="mr-1 h-3 w-3" />
              {overallLevel.label}
            </Badge>
            <div className="text-right">
              <div className="text-2xl font-bold text-slate-900">{overallScore}</div>
              <div className="text-xs text-slate-500">综合评分</div>
            </div>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex justify-center">{renderRadarVisualization()}</div>

        {showComparison && comparisonScores.length === scores.length ? (
          <div className="flex items-center justify-center gap-4 text-xs text-slate-600">
            <div className="flex items-center gap-2">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-[#171717]" />
              <span>我的能力</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-[#b59676]" />
              <span>对比参考</span>
            </div>
          </div>
        ) : null}

        <div className="space-y-4">
          <h4 className="flex items-center gap-2 font-medium text-slate-900">
            <TrendingUp className="h-4 w-4" />
            能力维度详情
          </h4>

          <div className="space-y-3">
            {scores.map((score, index) => {
              const level = getScoreLevel(score.score);
              const showImprovement = score.improvement && score.improvement > 0;

              return (
                <div key={index} className="space-y-2">
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div className="student-icon-bubble h-9 w-9 bg-white text-slate-900">
                        {score.icon}
                      </div>
                      <div>
                        <div className="font-medium text-slate-900">{score.dimension}</div>
                        <div className="text-xs text-slate-500">{score.description}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-lg font-bold text-slate-900">
                        {format2(score.score)}
                      </span>
                      <Badge className={level.color} variant="outline">
                        {level.label}
                      </Badge>
                      {showImprovement ? (
                        <Badge className="bg-emerald-100 text-emerald-700 border-emerald-300">
                          +{score.improvement}
                        </Badge>
                      ) : null}
                    </div>
                  </div>

                  <Progress
                    value={score.score}
                    className="h-2 bg-[#ece3d8] [&>div]:bg-[#171717]"
                  />
                </div>
              );
            })}
          </div>
        </div>

        {showComparison && comparisonScores.length > 0 ? (
          <div className="border-t border-black/5 pt-4">
            <h4 className="mb-3 font-medium text-slate-900">与平均水平对比</h4>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
              {scores.map((score, index) => {
                const base = comparisonScores[index] ?? 0;
                const diff = score.score - base;
                return (
                  <div key={index} className="student-card-muted p-3 text-center">
                    <div className="text-xs text-slate-600">{score.dimension}</div>
                    <div className="mt-2 text-sm font-medium text-slate-900">
                      {format2(score.score)}
                    </div>
                    <div className="text-xs text-slate-500">vs {format2(base)}</div>
                    <div
                      className={`mt-1 text-xs font-medium ${
                        diff > 0
                          ? 'text-emerald-600'
                          : diff < 0
                          ? 'text-red-600'
                          : 'text-slate-600'
                      }`}
                    >
                      {diff > 0 && '+'}
                      {format2(diff)}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
};

export default AbilityRadarChart;
