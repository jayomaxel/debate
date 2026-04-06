import React, { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Bot,
  Brain,
  Zap,
  Target,
  TrendingUp,
  Cpu,
  Activity,
  Volume2,
  Circle
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
          gradient: 'from-blue-600 to-cyan-600',
          bgColor: 'from-blue-950 to-blue-900',
          borderColor: 'border-blue-500',
          icon: <Brain className="w-8 h-8 text-blue-400" />,
          traits: ['逻辑分析', '数据处理', '事实核查']
        };
      case 'creative':
        return {
          color: 'purple',
          gradient: 'from-purple-600 to-pink-600',
          bgColor: 'from-purple-950 to-purple-900',
          borderColor: 'border-purple-500',
          icon: <Zap className="w-8 h-8 text-purple-400" />,
          traits: ['创新思维', '联想能力', '创意表达']
        };
      case 'aggressive':
        return {
          color: 'red',
          gradient: 'from-red-600 to-orange-600',
          bgColor: 'from-red-950 to-red-900',
          borderColor: 'border-red-500',
          icon: <Target className="w-8 h-8 text-red-400" />,
          traits: ['攻击性辩论', '快速反应', '压力测试']
        };
      case 'balanced':
        return {
          color: 'emerald',
          gradient: 'from-emerald-600 to-teal-600',
          bgColor: 'from-emerald-950 to-emerald-900',
          borderColor: 'border-emerald-500',
          icon: <Cpu className="w-8 h-8 text-emerald-400" />,
          traits: ['均衡策略', '适应性强', '全面思考']
        };
      default:
        return {
          color: 'slate',
          gradient: 'from-slate-600 to-slate-600',
          bgColor: 'from-slate-950 to-slate-900',
          borderColor: 'border-slate-500',
          icon: <Bot className="w-8 h-8 text-slate-400" />,
          traits: ['通用智能']
        };
    }
  };

  const config = getAIConfig(ai.aiType);

  const getActiveStyles = () => {
    if (!isActive) return '';

    return `ring-4 ring-${config.color}-500/50 ring-offset-2 ring-offset-slate-900 scale-105 animate-pulse`;
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
          className={`w-1 bg-${config.color}-400 rounded-full transition-all duration-200`}
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
      border-2 ${config.borderColor}
      ${getActiveStyles()}
      ${ai.isSpeaking ? 'animate-pulse' : ''}
    `}>
      <CardContent className="p-0 h-40">
        <div className="relative h-full">
          {/* AI 核心区域 */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            {/* 机器人头像 */}
            <div className={`
              relative w-16 h-16 rounded-full bg-gradient-to-br ${config.gradient}
              flex items-center justify-center shadow-lg
              ${ai.isSpeaking ? 'animate-bounce' : ''}
            `}>
              {config.icon}

              {/* 发言光环 */}
              {ai.isSpeaking && (
                <div className={`absolute inset-0 rounded-full bg-${config.color}-400 opacity-30 animate-ping`} />
              )}
            </div>

            {/* AI 名称和职位 */}
            <div className="mt-2 text-center">
              <h3 className="text-white text-sm font-bold">
                {ai.name}
              </h3>
              <Badge className={`bg-${config.color}-600/30 text-${config.color}-300 border-${config.color}-500 text-xs mt-1`}>
                {ai.position}
              </Badge>
            </div>

            {/* 技能等级 */}
            <div className="mt-1 text-xs text-slate-400">
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
              <div className="bg-slate-800/90 backdrop-blur rounded-lg p-2 border border-slate-600">
                <div className="flex items-center gap-1 mb-1">
                  <Activity className="w-3 h-3 text-emerald-400 animate-pulse" />
                  <span className="text-xs text-emerald-400 font-medium">思考中</span>
                </div>
                <p className="text-xs text-slate-300">
                  {thinkingBubbles[0]}
                </p>
              </div>
            </div>
          )}

          {/* AI 类型标识 */}
          <div className="absolute top-2 left-2">
            <Badge className={`bg-${config.color}-600 text-white text-xs`}>
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
                    className={`w-2 h-2 text-${config.color}-400 fill-current`}
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
            <div className="w-full bg-slate-700 rounded-full h-1 mt-1">
              <div
                className={`h-full bg-${config.color}-500 rounded-full transition-all duration-300`}
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
                  className={`text-xs px-2 py-1 bg-${config.color}-600/30 text-${config.color}-300 rounded`}
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