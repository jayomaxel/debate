import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Clock,
  MessageSquare,
  TrendingUp,
  BarChart3,
  PieChart,
} from 'lucide-react';

interface SpeakingData {
  name: string;
  role?: string | null;
  time: number;
  percentage: number;
  isAI?: boolean;
  color: string;
}

interface SpeakingTimeChartProps {
  data: SpeakingData[];
  totalTime?: number;
  title?: string;
  showComparison?: boolean;
  studentMode?: boolean;
}

const mojibakePattern =
  /[锟絔|[閼惧▔鐎涢惂閺囬弫閹撮妴閿涚拠鏉堥懡闁弻閻濇稉闁挎瀵悽閺傞崶婢舵担閳ヤ繐姝曠瘻鍑猐|[\uE000-\uF8FF]/;

const getRoleNumber = (role?: string | null) => {
  const match = String(role || '').match(/(?:debater|ai)_(\d+)/);
  return match?.[1];
};

const getDisplayName = (item: SpeakingData) => {
  const roleNumber = getRoleNumber(item.role);

  if (item.isAI) {
    return roleNumber ? `AI 辩手 ${roleNumber}` : 'AI 辩手';
  }

  const name = String(item.name || '').trim();
  if (name && !mojibakePattern.test(name)) {
    return name;
  }

  return roleNumber ? `辩手 ${roleNumber}` : '辩手';
};

const themeCard = (studentMode: boolean) =>
  studentMode
    ? 'rounded-[16px] border border-[#d7ccbf] bg-white/88 shadow-[0_14px_34px_rgba(58,42,28,0.07)]'
    : 'bg-white border-slate-200 shadow-sm';

const SpeakingTimeChart: React.FC<SpeakingTimeChartProps> = ({
  data,
  title = '发言时间分析',
  studentMode = false,
}) => {
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const totalSpeakingTime = data.reduce((sum, item) => sum + (item.time || 0), 0);
  const humanSpeakingTime = data
    .filter((item) => !item.isAI)
    .reduce((sum, item) => sum + (item.time || 0), 0);
  const aiSpeakingTime = data
    .filter((item) => item.isAI)
    .reduce((sum, item) => sum + (item.time || 0), 0);

  const humanPercentage =
    totalSpeakingTime > 0 ? Math.round((humanSpeakingTime / totalSpeakingTime) * 100) : 0;
  const aiPercentage =
    totalSpeakingTime > 0 ? Math.round((aiSpeakingTime / totalSpeakingTime) * 100) : 0;

  const renderPieChart = () => {
    let currentAngle = -Math.PI / 2;
    return (
      <div className="relative">
        {data.length === 0 ? (
          <div className="py-10 text-center text-sm text-slate-500">暂无发言数据</div>
        ) : (
          <svg width="200" height="200" className="mx-auto">
            {data.map((item, index) => {
              const angle = (item.percentage / 100) * 2 * Math.PI;
              const largeArcFlag = angle > Math.PI ? 1 : 0;
              const x1 = 100 + 80 * Math.cos(currentAngle);
              const y1 = 100 + 80 * Math.sin(currentAngle);
              const x2 = 100 + 80 * Math.cos(currentAngle + angle);
              const y2 = 100 + 80 * Math.sin(currentAngle + angle);

              const pathData = [
                'M 100 100',
                `L ${x1} ${y1}`,
                `A 80 80 0 ${largeArcFlag} 1 ${x2} ${y2}`,
                'Z',
              ].join(' ');

              currentAngle += angle;

              return (
                <path
                  key={index}
                  d={pathData}
                  fill={item.color}
                  stroke="white"
                  strokeWidth="2"
                  className="cursor-pointer transition-opacity hover:opacity-80"
                />
              );
            })}

            <circle cx="100" cy="100" r="40" fill="white" />
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
              className="text-xs fill-slate-500"
            >
              总发言时间
            </text>
          </svg>
        )}

        <div className="mt-4 space-y-2">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded bg-[#171717]" />
              <span>人类团队</span>
            </div>
            <span className="font-medium">
              {humanPercentage}% ({formatTime(humanSpeakingTime)})
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded bg-[#b59676]" />
              <span>AI 团队</span>
            </div>
            <span className="font-medium">
              {aiPercentage}% ({formatTime(aiSpeakingTime)})
            </span>
          </div>
        </div>
      </div>
    );
  };

  const renderBarChart = () => {
    if (data.length === 0) {
      return <div className="py-6 text-center text-sm text-slate-500">暂无发言数据</div>;
    }
    const maxTime = Math.max(...data.map((item) => item.time));

    return (
      <div className="space-y-3">
        {data.map((item, index) => (
          <div key={index} className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 rounded" style={{ backgroundColor: item.color }} />
                <span className="font-medium text-slate-700">{getDisplayName(item)}</span>
                {item.isAI ? <Badge className="student-pill">AI</Badge> : null}
              </div>
              <div className="text-right">
                <div className="font-medium text-slate-900">{formatTime(item.time)}</div>
                <div className="text-xs text-slate-500">{item.percentage}%</div>
              </div>
            </div>
            <Progress
              value={(item.time / maxTime) * 100}
              className="h-2 bg-[#ece3d8] [&>div]:bg-[#171717]"
            />
          </div>
        ))}
      </div>
    );
  };

  return (
    <Card className={themeCard(studentMode)}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-slate-700" />
            {title}
          </div>
          <div className="flex items-center gap-2">
            <Badge className="student-pill">
              <Clock className="mr-1 h-3 w-3" />
              {formatTime(totalSpeakingTime)}
            </Badge>
            <Badge className="student-pill">
              <BarChart3 className="mr-1 h-3 w-3" />
              {data.length} 位参与者
            </Badge>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid grid-cols-3 gap-3">
          <div className="student-card-muted p-4 text-center">
            <div className="text-xl font-bold text-slate-900">{data.length}</div>
            <div className="text-xs text-slate-600">总发言人数</div>
          </div>
          <div className="student-card-soft-blue p-4 text-center">
            <div className="text-xl font-bold text-slate-900">{humanPercentage}%</div>
            <div className="text-xs text-slate-600">人类发言占比</div>
          </div>
          <div className="student-card-soft-lavender p-4 text-center">
            <div className="text-xl font-bold text-slate-900">{aiPercentage}%</div>
            <div className="text-xs text-slate-600">AI 发言占比</div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-slate-900">发言时间分布</h4>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <PieChart className="h-4 w-4" />
              饼图 / 条形图
            </div>
          </div>

          <div className="student-card-muted p-4">{renderPieChart()}</div>
          <div className="student-card-muted p-4">
            <h4 className="mb-4 font-medium text-slate-900">详细时间分析</h4>
            {renderBarChart()}
          </div>
        </div>

        <div className="border-t border-black/5 pt-4">
          <h4 className="mb-3 flex items-center gap-2 font-medium text-slate-900">
            <TrendingUp className="h-4 w-4" />
            发言活跃度分析
          </h4>
          <div className="space-y-2">
            {data.length === 0 ? (
              <div className="py-6 text-center text-sm text-slate-500">暂无发言数据</div>
            ) : (
              data
                .slice()
                .sort((a, b) => b.time - a.time)
                .slice(0, 3)
                .map((item, index) => (
                  <div key={index} className="student-card-muted flex items-center justify-between p-3">
                    <div className="flex items-center gap-2">
                      <div className="student-icon-bubble h-7 w-7 bg-white text-xs font-semibold text-slate-900">
                        {index + 1}
                      </div>
                      <span className="text-sm font-medium text-slate-700">
                        {getDisplayName(item)}
                      </span>
                      {item.isAI ? <Badge className="student-pill">AI</Badge> : null}
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
