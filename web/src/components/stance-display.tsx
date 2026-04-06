import React, { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  TrendingUp,
  TrendingDown,
  Clock,
  Zap,
  Target,
  Award,
  Users,
  Bot
} from 'lucide-react';

interface StanceDisplayProps {
  stance: 'positive' | 'negative';
  topic: string;
  onCountdownEnd?: () => void;
}

const StanceDisplay: React.FC<StanceDisplayProps> = ({
  stance,
  topic,
  onCountdownEnd
}) => {
  const [countdown, setCountdown] = useState(30);
  const [isPulsing, setIsPulsing] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          onCountdownEnd?.();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [onCountdownEnd]);

  useEffect(() => {
    // 最后10秒开始脉冲动画
    if (countdown <= 10 && countdown > 0) {
      setIsPulsing(true);
    } else {
      setIsPulsing(false);
    }
  }, [countdown]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const getCountdownColor = () => {
    if (countdown <= 5) return 'text-red-600 bg-red-50 border-red-200';
    if (countdown <= 10) return 'text-amber-600 bg-amber-50 border-amber-200';
    return 'text-blue-600 bg-blue-50 border-blue-200';
  };

  const getStanceConfig = () => {
    if (stance === 'positive') {
      return {
        title: '正方立场',
        subtitle: '支持稳定币发展',
        color: 'from-emerald-500 to-blue-600',
        bgColor: 'bg-gradient-to-br from-emerald-50 to-blue-50',
        borderColor: 'border-emerald-200',
        icon: <TrendingUp className="w-8 h-8 text-emerald-600" />,
        keywords: ['金融创新', '技术进步', '市场机遇', '数字未来']
      };
    } else {
      return {
        title: '反方立场',
        subtitle: '反对稳定币发展',
        color: 'from-red-500 to-orange-600',
        bgColor: 'bg-gradient-to-br from-red-50 to-orange-50',
        borderColor: 'border-red-200',
        icon: <TrendingDown className="w-8 h-8 text-red-600" />,
        keywords: ['金融风险', '监管挑战', '市场波动', '系统安全']
      };
    }
  };

  const stanceConfig = getStanceConfig();

  return (
    <div className="relative">
      {/* 背景装饰 */}
      <div className="absolute inset-0 bg-gradient-to-br from-slate-50 via-blue-50 to-purple-50 rounded-2xl" />

      {/* 主要内容 */}
      <Card className={`relative ${stanceConfig.bgColor} ${stanceConfig.borderColor} border-2 shadow-2xl overflow-hidden`}>
        <CardContent className="p-8">
          <div className="text-center space-y-6">
            {/* 立场标题 */}
            <div className="space-y-3">
              <div className="flex items-center justify-center gap-3">
                {stanceConfig.icon}
                <h1 className={`text-4xl font-bold bg-gradient-to-r ${stanceConfig.color} bg-clip-text text-transparent`}>
                  {stanceConfig.title}
                </h1>
              </div>
              <h2 className="text-2xl font-semibold text-slate-800">
                {stanceConfig.subtitle}
              </h2>
            </div>

            {/* 辩题 */}
            <div className="p-4 bg-white/80 rounded-xl border border-slate-200">
              <h3 className="text-xl font-medium text-slate-900 mb-2">今日辩题</h3>
              <p className="text-lg text-slate-700">{topic}</p>
            </div>

            {/* 关键词标签 */}
            <div className="flex items-center justify-center gap-3 flex-wrap">
              {stanceConfig.keywords.map((keyword, index) => (
                <Badge
                  key={index}
                  variant="outline"
                  className={`px-4 py-2 text-sm font-medium ${
                    stance === 'positive'
                      ? 'border-emerald-300 text-emerald-700 bg-emerald-50'
                      : 'border-red-300 text-red-700 bg-red-50'
                  }`}
                >
                  {keyword}
                </Badge>
              ))}
            </div>

            {/* 倒计时 */}
            <div className={`relative ${isPulsing ? 'animate-pulse' : ''}`}>
              <div className={`inline-flex items-center gap-3 px-6 py-4 rounded-xl border-2 ${getCountdownColor()}`}>
                <Clock className={`w-6 h-6 ${countdown <= 5 ? 'animate-spin' : ''}`} />
                <div className="text-center">
                  <p className="text-sm font-medium">距离辩论开始还有</p>
                  <p className={`text-3xl font-bold ${countdown <= 5 ? 'animate-pulse' : ''}`}>
                    {formatTime(countdown)}
                  </p>
                </div>
              </div>
            </div>

            {/* 准备提示 */}
            <div className="flex items-center justify-center gap-6 text-sm text-slate-600">
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-blue-500" />
                <span>人类团队已就绪</span>
              </div>
              <div className="flex items-center gap-2">
                <Bot className="w-4 h-4 text-purple-500" />
                <span>AI团队待命中</span>
              </div>
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-500" />
                <span>系统准备就绪</span>
              </div>
            </div>

            {/* 准备进度条 */}
            <div className="w-full max-w-md mx-auto">
              <div className="flex items-center justify-between text-xs text-slate-600 mb-2">
                <span>准备进度</span>
                <span>{Math.max(0, 100 - (countdown * 3.3))}%</span>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-3 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-1000 ease-out bg-gradient-to-r ${stanceConfig.color}`}
                  style={{
                    width: `${Math.max(0, 100 - (countdown * 3.3))}%`
                  }}
                />
              </div>
            </div>

            {/* 辩论角色提示 */}
            <div className="grid grid-cols-4 gap-4 max-w-2xl mx-auto">
              {['一辩立论', '二辩攻辩', '三辩质询', '四辩总结'].map((role, index) => (
                <div key={index} className="text-center">
                  <div className="w-12 h-12 mx-auto mb-2 rounded-full bg-white border-2 border-slate-300 flex items-center justify-center">
                    <span className="font-bold text-slate-700">{index + 1}</span>
                  </div>
                  <p className="text-xs text-slate-600">{role}</p>
                </div>
              ))}
            </div>
          </div>
        </CardContent>

        {/* 角落装饰 */}
        <div className="absolute top-4 left-4 w-20 h-20 opacity-10">
          <Target className="w-full h-full text-slate-600" />
        </div>
        <div className="absolute bottom-4 right-4 w-20 h-20 opacity-10">
          <Award className="w-full h-full text-slate-600" />
        </div>
      </Card>
    </div>
  );
};

export default StanceDisplay;