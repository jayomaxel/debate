import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  TrendingUp,
  TrendingDown,
  Target,
  Brain,
  Zap,
  Heart,
  Users,
  Calendar,
  Award,
  BarChart3,
  LineChart,
  Activity,
  Star
} from 'lucide-react';

export interface DataPoint {
  date: Date;
  debateTopic: string;
  stance: 'positive' | 'negative';
  result: 'win' | 'lose' | 'draw';
  abilityScores: {
    logicScore: number;
    argumentScore: number;
    responseScore: number;
    persuasionScore: number;
    teamworkScore: number;
  };
  overallScore: number;
}

interface GrowthTrendChartProps {
  data: DataPoint[];
  timeframe?: 'month' | 'semester' | 'year' | 'all';
  studentName?: string;
}

const GrowthTrendChart: React.FC<GrowthTrendChartProps> = ({
  data,
  timeframe = 'all',
  studentName = '学生'
}) => {
  const [selectedAbility, setSelectedAbility] = useState<string>('all');
  const [timeframeFilter, setTimeframeFilter] = useState(timeframe);
  const timeframeOptions: Array<{ value: 'month' | 'semester' | 'year' | 'all'; label: string }> = [
    { value: 'month', label: '1个月' },
    { value: 'semester', label: '1学期' },
    { value: 'year', label: '1年' },
    { value: 'all', label: '全部' },
  ];

  const filterDataByTimeframe = (data: DataPoint[], timeframe: string) => {
    const now = new Date();
    const filtered = data.filter(point => {
      const pointDate = new Date(point.date);
      const daysDiff = (now.getTime() - pointDate.getTime()) / (1000 * 60 * 60 * 24);

      switch (timeframe) {
        case 'month':
          return daysDiff <= 30;
        case 'semester':
          return daysDiff <= 120;
        case 'year':
          return daysDiff <= 365;
        default:
          return true;
      }
    });

    return filtered.sort((a, b) => a.date.getTime() - b.date.getTime());
  };

  const filteredData = filterDataByTimeframe(data, timeframeFilter);

  const abilities = [
    { key: 'logicScore', name: '逻辑思维', icon: <Brain className="w-4 h-4" />, color: 'blue' },
    { key: 'argumentScore', name: '论据质量', icon: <Target className="w-4 h-4" />, color: 'purple' },
    { key: 'responseScore', name: '反应速度', icon: <Zap className="w-4 h-4" />, color: 'amber' },
    { key: 'persuasionScore', name: '情绪感染力', icon: <Heart className="w-4 h-4" />, color: 'red' },
    { key: 'teamworkScore', name: '团队配合', icon: <Users className="w-4 h-4" />, color: 'green' }
  ];

  const getColorForAbility = (color: string) => {
    const colors = {
      blue: '#3b82f6',
      purple: '#8b5cf6',
      amber: '#f59e0b',
      red: '#ef4444',
      green: '#10b981'
    };
    return colors[color as keyof typeof colors] || '#6b7280';
  };

  const calculateGrowth = (scores: number[]) => {
    if (scores.length < 2) return 0;
    const first = scores[0];
    const last = scores[scores.length - 1];
    return ((last - first) / first) * 100;
  };

  const getGrowthConfig = (growth: number) => {
    if (growth > 0) {
      return {
        icon: <TrendingUp className="w-4 h-4" />,
        color: 'text-emerald-600',
        bgColor: 'bg-emerald-50',
        sign: '+'
      };
    } else if (growth < 0) {
      return {
        icon: <TrendingDown className="w-4 h-4" />,
        color: 'text-red-600',
        bgColor: 'bg-red-50',
        sign: ''
      };
    }
    return {
      icon: <Activity className="w-4 h-4" />,
      color: 'text-slate-600',
      bgColor: 'bg-slate-50',
      sign: ''
    };
  };

  const renderLineChart = (width: number = 600, height: number = 300) => {
    const padding = { top: 20, right: 40, bottom: 60, left: 50 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    if (filteredData.length < 2) {
      return (
        <div className="flex items-center justify-center h-full bg-slate-50 rounded-lg">
          <div className="text-center">
            <BarChart3 className="w-12 h-12 mx-auto text-slate-300 mb-2" />
            <p className="text-slate-500">数据不足，需要至少2场辩论记录</p>
          </div>
        </div>
      );
    }

    // 计算数据范围
    const allScores = filteredData.flatMap(point => [
      point.overallScore,
      ...abilities.map(ability => point.abilityScores[ability.key as keyof typeof point.abilityScores])
    ]);
    const minScore = Math.min(...allScores) - 5;
    const maxScore = Math.max(...allScores) + 5;

    // 生成X轴刻度
    const xStep = chartWidth / Math.max(filteredData.length - 1, 1);
    const yScale = chartHeight / (maxScore - minScore);

    return (
      <svg width={width} height={height} className="w-full h-full">
        {/* 背景网格 */}
        {Array.from({ length: 5 }, (_, i) => {
          const y = padding.top + (chartHeight / 4) * i;
          return (
            <line
              key={`grid-${i}`}
              x1={padding.left}
              y1={y}
              x2={width - padding.right}
              y2={y}
              stroke="#e5e7eb"
              strokeWidth="1"
              strokeDasharray="2,2"
            />
          );
        })}

        {/* Y轴刻度和标签 */}
        {Array.from({ length: 5 }, (_, i) => {
          const value = maxScore - ((maxScore - minScore) / 4) * i;
          const y = padding.top + (chartHeight / 4) * i;
          return (
            <g key={`y-${i}`}>
              <text
                x={padding.left - 10}
                y={y + 5}
                textAnchor="end"
                className="text-xs fill-slate-600"
              >
                Math.round(value)
              </text>
              <line
                x1={padding.left - 5}
                y1={y}
                x2={padding.left}
                y2={y}
                stroke="#9ca3af"
                strokeWidth="1"
              />
            </g>
          );
        })}

        {/* X轴刻度和标签 */}
        {filteredData.map((point, index) => {
          const x = padding.left + xStep * index;
          return (
            <g key={`x-${index}`}>
              <text
                x={x}
                y={height - padding.bottom + 20}
                textAnchor="middle"
                className="text-xs fill-slate-600"
                transform={`rotate(-45 ${x} ${height - padding.bottom + 20})`}
              >
                {point.date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })}
              </text>
              <line
                x1={x}
                y1={height - padding.bottom}
                x2={x}
                y2={height - padding.bottom + 5}
                stroke="#9ca3af"
                strokeWidth="1"
              />
            </g>
          );
        })}

        {/* 坐标轴 */}
        <line
          x1={padding.left}
          y1={padding.top}
          x2={padding.left}
          y2={height - padding.bottom}
          stroke="#374151"
          strokeWidth="2"
        />
        <line
          x1={padding.left}
          y1={height - padding.bottom}
          x2={width - padding.right}
          y2={height - padding.bottom}
          stroke="#374151"
          strokeWidth="2"
        />

        {/* 数据线 */}
        {abilities.map((ability, abilityIndex) => {
          if (selectedAbility !== 'all' && selectedAbility !== ability.key) return null;

          const scores = filteredData.map(point => point.abilityScores[ability.key as keyof typeof point.abilityScores]);

          return (
            <g key={ability.key}>
              {/* 连接线 */}
              {scores.map((score, index) => {
                if (index === 0) return null;
                const prevX = padding.left + xStep * (index - 1);
                const prevY = padding.top + chartHeight - (scores[index - 1] - minScore) * yScale;
                const currX = padding.left + xStep * index;
                const currY = padding.top + chartHeight - (score - minScore) * yScale;

                return (
                  <line
                    key={`line-${ability.key}-${index}`}
                    x1={prevX}
                    y1={prevY}
                    x2={currX}
                    y2={currY}
                    stroke={getColorForAbility(ability.color)}
                    strokeWidth="2"
                    opacity={selectedAbility === 'all' ? 0.8 : 1}
                  />
                );
              })}

              {/* 数据点 */}
              {scores.map((score, index) => {
                const x = padding.left + xStep * index;
                const y = padding.top + chartHeight - (score - minScore) * yScale;

                return (
                  <circle
                    key={`point-${ability.key}-${index}`}
                    cx={x}
                    cy={y}
                    r="4"
                    fill={getColorForAbility(ability.color)}
                    stroke="white"
                    strokeWidth="2"
                    className="hover:r-6 transition-all cursor-pointer"
                  />
                );
              })}
            </g>
          );
        })}

        {/* 综合评分线（如果显示全部） */}
        {selectedAbility === 'all' && (
          <g>
            {filteredData.map((point, index) => {
              if (index === 0) return null;
              const prevX = padding.left + xStep * (index - 1);
              const prevY = padding.top + chartHeight - (filteredData[index - 1].overallScore - minScore) * yScale;
              const currX = padding.left + xStep * index;
              const currY = padding.top + chartHeight - (point.overallScore - minScore) * yScale;

              return (
                <line
                  key={`overall-line-${index}`}
                  x1={prevX}
                  y1={prevY}
                  x2={currX}
                  y2={currY}
                  stroke="#1f2937"
                  strokeWidth="3"
                  strokeDasharray="5,3"
                />
              );
            })}

            {filteredData.map((point, index) => {
              const x = padding.left + xStep * index;
              const y = padding.top + chartHeight - (point.overallScore - minScore) * yScale;

              return (
                <circle
                  key={`overall-point-${index}`}
                  cx={x}
                  cy={y}
                  r="5"
                  fill="#1f2937"
                  stroke="white"
                  strokeWidth="2"
                />
              );
            })}
          </g>
        )}
      </svg>
    );
  };

  return (
    <Card className="bg-white border-slate-200 shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <LineChart className="w-5 h-5 text-blue-600" />
            {studentName} 的成长趋势
          </div>
          <div className="flex items-center gap-2">
            <Badge className="bg-blue-100 text-blue-700 border-blue-300">
              {filteredData.length} 场辩论
            </Badge>
            {filteredData.length >= 2 && (
              <Badge className="bg-emerald-100 text-emerald-700 border-emerald-300">
                持续进步中
              </Badge>
            )}
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* 时间框架选择 */}
        <div className="flex items-center justify-between">
          <div className="text-sm text-slate-600">
            <Calendar className="w-4 h-4 inline mr-1" />
            分析周期
          </div>
          <div className="flex items-center gap-1">
            {timeframeOptions.map((option) => (
              <Button
                key={option.value}
                variant={timeframeFilter === option.value ? 'default' : 'outline'}
                size="sm"
                onClick={() => setTimeframeFilter(option.value)}
                className="text-xs"
              >
                {option.label}
              </Button>
            ))}
          </div>
        </div>

        {/* 能力选择器 */}
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant={selectedAbility === 'all' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setSelectedAbility('all')}
            className="flex items-center gap-2"
          >
            <Activity className="w-4 h-4" />
            综合趋势
          </Button>
          {abilities.map((ability) => (
            <Button
              key={ability.key}
              variant={selectedAbility === ability.key ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedAbility(ability.key)}
              className="flex items-center gap-2"
              style={
                selectedAbility === ability.key
                  ? { backgroundColor: getColorForAbility(ability.color) }
                  : {}
              }
            >
              {ability.icon}
              {ability.name}
            </Button>
          ))}
        </div>

        {/* 主图表区域 */}
        <div className="border border-slate-200 rounded-lg p-4">
          {renderLineChart()}
        </div>

        {/* 能力统计卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {abilities.map((ability) => {
            const scores = filteredData.map(point => point.abilityScores[ability.key as keyof typeof point.abilityScores]);
            const growth = calculateGrowth(scores);
            const growthConfig = getGrowthConfig(growth);
            const currentScore = scores[scores.length - 1] || 0;

            return (
              <div
                key={ability.key}
                className={`p-4 rounded-lg border border-slate-200 ${growthConfig.bgColor}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center"
                      style={{ backgroundColor: getColorForAbility(ability.color) + '20' }}
                    >
                      <div style={{ color: getColorForAbility(ability.color) }}>
                        {ability.icon}
                      </div>
                    </div>
                    <div>
                      <div className="font-medium text-slate-900">{ability.name}</div>
                      <div className="text-xs text-slate-600">当前评分</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold text-slate-900">{currentScore}</div>
                    <div className={`flex items-center gap-1 text-xs ${growthConfig.color}`}>
                      {growthConfig.icon}
                      <span>{growthConfig.sign}{growth.toFixed(1)}%</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* 整体成长总结 */}
        <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg p-4 border border-blue-200">
          <div className="flex items-start gap-3">
            <Award className="w-5 h-5 text-blue-600 mt-0.5" />
            <div>
              <h3 className="font-semibold text-slate-900 mb-2">成长分析总结</h3>
              <div className="text-sm text-slate-700 space-y-1">
                <p>
                  在最近{filteredData.length}场辩论中，{studentName}的整体表现呈现
                  <span className="font-semibold text-emerald-600">
                    {calculateGrowth(filteredData.map(p => p.overallScore)) > 0 ? '上升' : '下降'}
                  </span>
                  趋势。
                </p>
                <p>
                  最佳表现能力：
                  <span className="font-semibold text-blue-600">
                    {abilities.reduce((best, ability) => {
                      const scores = filteredData.map(point => point.abilityScores[ability.key as keyof typeof point.abilityScores]);
                      const avg = scores.reduce((sum, score) => sum + score, 0) / scores.length;
                      const bestAvg = best ? filteredData.map(point => point.abilityScores[best.key as keyof typeof point.abilityScores]).reduce((sum, score) => sum + score, 0) / filteredData.length : 0;
                      return avg > bestAvg ? ability : best;
                    }, null as any)?.name || '未知'}
                  </span>
                </p>
                <p>
                  建议重点提升：
                  <span className="font-semibold text-amber-600">
                    {abilities.reduce((worst, ability) => {
                      const scores = filteredData.map(point => point.abilityScores[ability.key as keyof typeof point.abilityScores]);
                      const avg = scores.reduce((sum, score) => sum + score, 0) / scores.length;
                      const worstAvg = worst ? filteredData.map(point => point.abilityScores[worst.key as keyof typeof point.abilityScores]).reduce((sum, score) => sum + score, 0) / filteredData.length : 100;
                      return avg < worstAvg ? ability : worst;
                    }, null as any)?.name || '未知'}
                  </span>
                </p>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default GrowthTrendChart;
