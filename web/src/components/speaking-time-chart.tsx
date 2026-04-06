import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Clock,
  Users,
  Bot,
  MessageSquare,
  TrendingUp,
  BarChart3,
  PieChart
} from 'lucide-react';

interface SpeakingData {
  name: string;
  time: number; // 秒
  percentage: number;
  isAI?: boolean;
  color: string;
}

interface SpeakingTimeChartProps {
  data: SpeakingData[];
  totalTime?: number;
  title?: string;
  showComparison?: boolean;
}

const SpeakingTimeChart: React.FC<SpeakingTimeChartProps> = ({
  data,
  totalTime = 1800, // 30分钟
  title = "发言时间分析",
  showComparison = false
}) => {
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const totalSpeakingTime = data.reduce((sum, item) => sum + (item.time || 0), 0);
  const humanSpeakingTime = data.filter(item => !item.isAI).reduce((sum, item) => sum + (item.time || 0), 0);
  const aiSpeakingTime = data.filter(item => item.isAI).reduce((sum, item) => sum + (item.time || 0), 0);
 
  const humanPercentage = totalSpeakingTime > 0 ? Math.round((humanSpeakingTime / totalSpeakingTime) * 100) : 0;
  const aiPercentage = totalSpeakingTime > 0 ? Math.round((aiSpeakingTime / totalSpeakingTime) * 100) : 0;

  const renderPieChart = () => {
    let currentAngle = -Math.PI / 2; // 从顶部开始

    return (
      <div className="relative">
        {data.length === 0 ? (
          <div className="text-center text-sm text-slate-500 py-10">暂无发言数据</div>
        ) : (
        <svg width="200" height="200" className="mx-auto">
          {/* 饼图扇形 */}
          {data.map((item, index) => {
            const angle = (item.percentage / 100) * 2 * Math.PI;
            const largeArcFlag = angle > Math.PI ? 1 : 0;

            const x1 = 100 + 80 * Math.cos(currentAngle);
            const y1 = 100 + 80 * Math.sin(currentAngle);
            const x2 = 100 + 80 * Math.cos(currentAngle + angle);
            const y2 = 100 + 80 * Math.sin(currentAngle + angle);

            const pathData = [
              `M 100 100`,
              `L ${x1} ${y1}`,
              `A 80 80 0 ${largeArcFlag} 1 ${x2} ${y2}`,
              'Z'
            ].join(' ');

            currentAngle += angle;

            return (
              <g key={index}>
                <path
                  d={pathData}
                  fill={item.color}
                  stroke="white"
                  strokeWidth="2"
                  className="hover:opacity-80 transition-opacity cursor-pointer"
                />
              </g>
            );
          })}

          {/* 中心圆 */}
          <circle
            cx="100"
            cy="100"
            r="40"
            fill="white"
          />

          {/* 中心文字 */}
          <text
            x="100"
            y="95"
            textAnchor="middle"
            className="text-lg font-bold fill-slate-900"
          >
            {formatTime(totalSpeakingTime)}
          </text>
          <text
            x="100"
            y="115"
            textAnchor="middle"
            className="text-xs text-slate-500"
          >
            总发言时间
          </text>
        </svg>
        )}

        {/* 图例 */}
        <div className="mt-4 space-y-2">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded bg-blue-500" />
              <span>人类团队</span>
            </div>
            <span className="font-medium">{humanPercentage}% ({formatTime(humanSpeakingTime)})</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded bg-purple-500" />
              <span>AI团队</span>
            </div>
            <span className="font-medium">{aiPercentage}% ({formatTime(aiSpeakingTime)})</span>
          </div>
        </div>
      </div>
    );
  };

  const renderBarChart = () => {
    if (data.length === 0) {
      return <div className="text-center text-sm text-slate-500 py-6">暂无发言数据</div>;
    }
    const maxTime = Math.max(...data.map(item => item.time));

    return (
      <div className="space-y-3">
        {data.map((item, index) => (
          <div key={index} className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded"
                  style={{ backgroundColor: item.color }}
                />
                <span className="font-medium text-slate-700">
                  {item.name}
                </span>
                {item.isAI && (
                  <Badge className="bg-purple-100 text-purple-700 border-purple-300 text-xs">
                    AI
                  </Badge>
                )}
              </div>
              <div className="text-right">
                <div className="font-medium text-slate-900">{formatTime(item.time)}</div>
                <div className="text-xs text-slate-500">{item.percentage}%</div>
              </div>
            </div>
            <Progress
              value={(item.time / maxTime) * 100}
              className="h-2"
              style={{
                backgroundColor: '#e2e8f0'
              }}
            />
          </div>
        ))}
      </div>
    );
  };

  return (
    <Card className="bg-white border-slate-200 shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-blue-600" />
            {title}
          </div>
          <div className="flex items-center gap-2">
            <Badge className="bg-blue-100 text-blue-700 border-blue-300">
              <Clock className="w-3 h-3 mr-1" />
              {formatTime(totalSpeakingTime)}
            </Badge>
            <Badge className="bg-emerald-100 text-emerald-700 border-emerald-300">
              <BarChart3 className="w-3 h-3 mr-1" />
              {data.length} 参与者
            </Badge>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* 总体统计 */}
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-3 bg-slate-50 rounded-lg">
            <div className="text-xl font-bold text-slate-900">
              {data.length}
            </div>
            <div className="text-xs text-slate-600">总发言人数</div>
          </div>
          <div className="text-center p-3 bg-blue-50 rounded-lg">
            <div className="text-xl font-bold text-blue-600">
              {humanPercentage}%
            </div>
            <div className="text-xs text-slate-600">人类发言占比</div>
          </div>
          <div className="text-center p-3 bg-purple-50 rounded-lg">
            <div className="text-xl font-bold text-purple-600">
              {aiPercentage}%
            </div>
            <div className="text-xs text-slate-600">AI发言占比</div>
          </div>
        </div>

        {/* 图表切换 */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-slate-900">发言时间分布</h4>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <PieChart className="w-4 h-4" />
              饼图 / 条形图
            </div>
          </div>

          {/* 饼图 */}
          <div className="border border-slate-200 rounded-lg p-4">
            {renderPieChart()}
          </div>

          {/* 条形图 */}
          <div className="border border-slate-200 rounded-lg p-4">
            <h4 className="font-medium text-slate-900 mb-4">详细时间分析</h4>
            {renderBarChart()}
          </div>
        </div>

        {/* 发言活跃度分析 */}
        <div className="border-t border-slate-200 pt-4">
          <h4 className="font-medium text-slate-900 mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            发言活跃度分析
          </h4>
          <div className="space-y-2">
            {data.length === 0 ? (
              <div className="text-center text-sm text-slate-500 py-6">暂无发言数据</div>
            ) : (
              data
                .sort((a, b) => b.time - a.time)
                .slice(0, 3)
                .map((item, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between p-2 bg-slate-50 rounded"
                  >
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-blue-100 text-blue-600 text-xs font-bold flex items-center justify-center">
                        {index + 1}
                      </div>
                      <span className="text-sm font-medium text-slate-700">{item.name}</span>
                      {item.isAI && (
                        <Badge className="bg-purple-100 text-purple-700 border-purple-300 text-xs">
                          AI
                        </Badge>
                      )}
                    </div>
                    <div className="text-sm text-slate-600">
                      {formatTime(item.time)} ({item.percentage}%)
                    </div>
                  </div>
                ))
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default SpeakingTimeChart;
