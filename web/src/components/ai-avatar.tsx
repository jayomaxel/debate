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
  const [thinkingBubbles, setThinkingBubbles] = useState<string[]>([]);

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
          gradient: 'from-white to-[#e2eef8]',
          bgColor: 'from-white via-[#f7fbfe] to-[#e2eef8]',
          borderColor: 'border-[#d8e7f2]',
          icon: <Brain className="h-8 w-8 text-slate-800" />,
          traits: ['逻辑分析', '数据处理', '事实核查']
        };
      case 'creative':
        return {
          color: 'purple',
          gradient: 'from-white to-[#eae6f6]',
          bgColor: 'from-white via-[#fbfaff] to-[#eae6f6]',
          borderColor: 'border-[#e0d8ef]',
          icon: <Zap className="h-8 w-8 text-slate-800" />,
          traits: ['创新思维', '联想能力', '创意表达']
        };
      case 'aggressive':
        return {
          color: 'red',
          gradient: 'from-white to-[#f9ecde]',
          bgColor: 'from-white via-[#fffaf6] to-[#f9ecde]',
          borderColor: 'border-[#f0d6c0]',
          icon: <Target className="h-8 w-8 text-slate-800" />,
          traits: ['攻击性辩论', '快速反应', '压力测试']
        };
      case 'balanced':
        return {
          color: 'emerald',
          gradient: 'from-white to-emerald-50',
          bgColor: 'from-white via-[#f7fffb] to-emerald-50',
          borderColor: 'border-emerald-200',
          icon: <Cpu className="h-8 w-8 text-slate-800" />,
          traits: ['均衡策略', '适应性强', '全面思考']
        };
      default:
        return {
          color: 'slate',
          gradient: 'from-white to-[#f8f5f1]',
          bgColor: 'from-white to-[#f8f5f1]',
          borderColor: 'border-[#ece4da]',
          icon: <Bot className="h-8 w-8 text-slate-400" />,
          traits: ['通用智能']
        };
    }
  };

  const config = getAIConfig(ai.aiType);

  const getActiveStyles = () => {
    if (!isActive) return '';

    return 'scale-[1.015] ring-2 ring-slate-900/20 ring-offset-4 ring-offset-[#f8f5f1]';
  };

  return (
    <Card className={`
      group relative overflow-hidden rounded-[26px] transition-all duration-300
      bg-gradient-to-br ${config.bgColor}
      border ${ai.isSpeaking ? 'border-slate-300' : config.borderColor}
      ${getActiveStyles()}
      shadow-[0_22px_54px_rgba(82,72,61,0.10)]
    `}>
      <CardContent className="relative h-[218px] p-5">
        <div className="pointer-events-none absolute inset-0 opacity-70">
          <div className="absolute -right-12 -top-14 h-32 w-32 rounded-full bg-[#eae6f6]" />
          <div className="absolute -bottom-16 left-8 h-28 w-28 rounded-full bg-[#f9ecde]" />
        </div>

        <div className="relative flex h-full flex-col">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Badge className="rounded-full border-[#e0d8ef] bg-white/80 text-xs text-slate-700">
                  反方 AI
                </Badge>
                <Badge className={ai.isSpeaking ? 'rounded-full border-slate-900 bg-slate-900 text-xs text-white' : 'student-pill text-xs'}>
                  {ai.isSpeaking ? '发言中' : '待命'}
                </Badge>
              </div>
              <h3 className="mt-3 truncate text-lg font-semibold tracking-[-0.02em] text-slate-950">
                {ai.name}
              </h3>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Badge className="student-pill text-xs">
                  {ai.position}
                </Badge>
                <span className="rounded-full border border-[#ece4da] bg-white/70 px-2 py-1 text-xs text-slate-500">
                  LV.{ai.skillLevel}
                </span>
              </div>
            </div>

            <div className={`
              flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br ${config.gradient}
              border border-white shadow-[0_16px_34px_rgba(82,72,61,0.14)]
            `}>
              {config.icon}
            </div>
          </div>

          {/* 思考气泡 */}
          {thinkingBubbles.length > 0 && (
            <div className="mt-4">
              <div className="rounded-[14px] border border-emerald-200 bg-emerald-50/90 p-3">
                <div className="mb-1 flex items-center gap-1">
                  <Activity className="h-3 w-3 text-emerald-700" />
                  <span className="text-xs font-medium text-emerald-800">思考中</span>
                </div>
                <p className="text-xs text-slate-700">
                  {thinkingBubbles[0]}
                </p>
              </div>
            </div>
          )}

          <div className="mt-auto">
            <div className="mb-3 flex flex-wrap gap-1.5">
              {config.traits.slice(0, 2).map((trait, index) => (
                <span
                  key={index}
                  className="rounded-full border border-white/80 bg-white/70 px-2 py-1 text-xs text-slate-600"
                >
                  {trait}
                </span>
              ))}
            </div>

            <div className="rounded-[14px] border border-white/80 bg-white/72 p-3 backdrop-blur">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>{ai.isSpeaking ? '正在输出观点' : '策略待命'}</span>
                <TrendingUp className="h-3 w-3" />
              </div>
              <div className="mt-2 h-1.5 w-full rounded-full bg-[#ede4da]">
                <div
                  className="h-full rounded-full bg-slate-900 transition-all duration-300"
                  style={{ width: `${ai.processingPower || 50}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default AIAvatar;
