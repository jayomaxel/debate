import React, { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Bot,
  Brain,
  Zap,
  Target,
  TrendingUp,
  Cpu,
  Activity,
  Circle,
} from 'lucide-react';

export interface AIAvatar {
  id: string;
  name: string;
  position: '一辩' | '二辩' | '三辩' | '四辩';
  aiType: 'analytical' | 'creative' | 'aggressive' | 'balanced';
  skillLevel: number;
  isSpeaking?: boolean;
  processingPower?: number;
  thoughtProcess?: string;
}

interface AIAvatarProps {
  ai: AIAvatar;
  isActive?: boolean;
}

const AIAvatar: React.FC<AIAvatarProps> = ({ ai, isActive = false }) => {
  const [animationFrame, setAnimationFrame] = useState(0);
  const [thinkingBubbles, setThinkingBubbles] = useState<string[]>([]);

  useEffect(() => {
    const interval = setInterval(() => {
      setAnimationFrame(prev => (prev + 1) % 60);
    }, 50);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (ai.isSpeaking) {
      const thoughtInterval = setInterval(() => {
        setThinkingBubbles(prev => {
          const thoughts = [
            '分析论点...',
            '验证数据...',
            '构建反驳...',
            '优化表达...',
            '检查逻辑...'
          ];
          return [thoughts[Math.floor(Math.random() * thoughts.length)]];
        });
      }, 2000);

      return () => clearInterval(thoughtInterval);
    } else {
      setThinkingBubbles([]);
    }
  }, [ai.isSpeaking]);

  const getAIConfig = (type: string) => {
    switch (type) {
      case 'analytical':
        return {
          color: 'blue',
          gradient: 'from-[#e2eef8] to-white',
          bgColor: 'from-white to-[#e2eef8]',
          borderColor: 'border-[#d8e7f2]',
          icon: <Brain className="w-8 h-8 text-slate-800" />,
          traits: ['逻辑分析', '数据处理', '事实核查']
        };
      case 'creative':
        return {
          color: 'purple',
          gradient: 'from-[#eae6f6] to-white',
          bgColor: 'from-white to-[#eae6f6]',
          borderColor: 'border-[#e0d8ef]',
          icon: <Zap className="w-8 h-8 text-slate-800" />,
          traits: ['创新思维', '联想能力', '创意表达']
        };
      case 'aggressive':
        return {
          color: 'red',
          gradient: 'from-[#f9ecde] to-white',
          bgColor: 'from-white to-[#f9ecde]',
          borderColor: 'border-[#f0d6c0]',
          icon: <Target className="w-8 h-8 text-slate-800" />,
          traits: ['攻击性辩论', '快速反应', '压力测试']
        };
      case 'balanced':
        return {
          color: 'emerald',
          gradient: 'from-emerald-50 to-white',
          bgColor: 'from-white to-emerald-50',
          borderColor: 'border-emerald-200',
          icon: <Cpu className="w-8 h-8 text-slate-800" />,
          traits: ['均衡策略', '适应性强', '全面思考']
        };
      default:
        return {
          color: 'slate',
          gradient: 'from-white to-[#f8f5f1]',
          bgColor: 'from-white to-[#f8f5f1]',
          borderColor: 'border-[#ece4da]',
          icon: <Bot className="w-8 h-8 text-slate-400" />,
          traits: ['通用智能']
        };
    }
  };

  const config = getAIConfig(ai.aiType);

  const getActiveStyles = () => {
    if (!isActive) return '';

    return 'ring-2 ring-slate-900/15 ring-offset-2 ring-offset-white';
  };

  const getProcessingBars = () => {
    const bars = 12;
    const barHeight = ai.processingPower || 50;

    return Array.from({ length: bars }, (_, i) => {
      const delay = i * 100;
      const height = Math.sin((animationFrame + delay) / 10) * barHeight + barHeight;

      return (
        <div
          key={i}
          className="w-1 rounded-full bg-slate-700 transition-all duration-200"
          style={{
            height: `${Math.max(4, height)}px`,
            opacity: ai.isSpeaking ? 0.8 + Math.random() * 0.2 : 0.3
          }}
        />
      );
    });
  };

  return (
    <Card className={`
      relative overflow-hidden transition-all duration-300
      bg-gradient-to-br ${config.bgColor}
      border ${config.borderColor}
      ${getActiveStyles()}
      shadow-[0_12px_28px_rgba(174,154,126,0.08)]
    `}>
      <CardContent className="p-0 h-40">
        <div className="relative h-full">
          {/* AI 核心区域 */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            {/* 机器人头像 */}
            <div className={`
              relative w-16 h-16 rounded-full bg-gradient-to-br ${config.gradient}
              flex items-center justify-center border border-white shadow-[0_12px_28px_rgba(174,154,126,0.10)]
            `}>
              {config.icon}

              {/* 发言光环 */}
              {ai.isSpeaking && (
                <div className="absolute inset-0 rounded-full border-2 border-slate-900/20" />
              )}
            </div>

            {/* AI 名称和职位 */}
            <div className="mt-2 text-center">
              <h3 className="text-sm font-semibold text-slate-900">
                {ai.name}
              </h3>
              <Badge className="student-pill mt-1 text-xs">
                {ai.position}
              </Badge>
            </div>

            {/* 技能等级 */}
            <div className="mt-1 text-xs text-slate-500">
              LV.{ai.skillLevel}
            </div>
          </div>

          {/* 音频处理可视化 */}
          <div className="absolute bottom-8 left-0 right-0 flex items-center justify-center gap-0.5 px-8">
            {getProcessingBars()}
          </div>

          {/* 思考气泡 */}
          {thinkingBubbles.length > 0 && (
            <div className="absolute top-2 right-2 max-w-32">
              <div className="rounded-[10px] border border-emerald-200 bg-emerald-50 p-2">
                <div className="flex items-center gap-1 mb-1">
                  <Activity className="h-3 w-3 text-emerald-700" />
                  <span className="text-xs font-medium text-emerald-800">思考中</span>
                </div>
                <p className="text-xs text-slate-700">
                  {thinkingBubbles[0]}
                </p>
              </div>
            </div>
          )}

          {/* AI 类型标识 */}
          <div className="absolute top-2 left-2">
            <Badge className="student-pill text-xs">
              {ai.aiType === 'analytical' && '分析型'}
              {ai.aiType === 'creative' && '创意型'}
              {ai.aiType === 'aggressive' && '激进型'}
              {ai.aiType === 'balanced' && '平衡型'}
            </Badge>
          </div>

          {/* 发言指示器 */}
          {ai.isSpeaking && (
            <div className="absolute top-12 left-0 right-0 flex justify-center">
              <div className="flex items-center gap-1">
                {[0, 1, 2].map((i) => (
                  <Circle
                    key={i}
                    className="h-2 w-2 fill-current text-slate-700"
                    style={{
                      animation: `pulse 1s infinite ${i * 0.2}s`
                    }}
                  />
                ))}
              </div>
            </div>
          )}

          {/* 处理状态指示 */}
          <div className="absolute bottom-2 left-2 right-2">
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>处理中...</span>
              <TrendingUp className="w-3 h-3" />
            </div>
            <div className="mt-1 h-1 w-full rounded-full bg-[#ede4da]">
              <div
                className="h-full rounded-full bg-slate-900 transition-all duration-300"
                style={{ width: `${ai.processingPower || 50}%` }}
              />
            </div>
          </div>

          {/* AI 特征标签（悬停显示） */}
          <div className="absolute inset-x-0 -bottom-8 opacity-0 hover:opacity-100 transition-opacity duration-200">
            <div className="flex flex-wrap gap-1 justify-center">
              {config.traits.map((trait, index) => (
                <span
                  key={index}
                  className="rounded border border-[#ece4da] bg-white/90 px-2 py-1 text-xs text-slate-700"
                >
                  {trait}
                </span>
              ))}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default AIAvatar;
