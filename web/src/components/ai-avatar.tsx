import React, { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Activity,
} from 'lucide-react';

export interface AIAvatar {
  id: string;
  name: string;
  position: '一辩' | '二辩' | '三辩' | '四辩';
  aiType: 'analytical' | 'creative' | 'aggressive' | 'balanced';
  skillLevel?: number;
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
          bgColor: 'from-white via-[#f7fbfe] to-[#e2eef8]',
          borderColor: 'border-[#d8e7f2]',
          traits: ['逻辑分析', '数据处理', '事实核查']
        };
      case 'creative':
        return {
          color: 'purple',
          bgColor: 'from-white via-[#fbfaff] to-[#eae6f6]',
          borderColor: 'border-[#e0d8ef]',
          traits: ['创新思维', '联想能力', '创意表达']
        };
      case 'aggressive':
        return {
          color: 'red',
          bgColor: 'from-white via-[#fffaf6] to-[#f9ecde]',
          borderColor: 'border-[#f0d6c0]',
          traits: ['攻击性辩论', '快速反应', '压力测试']
        };
      case 'balanced':
        return {
          color: 'emerald',
          bgColor: 'from-white via-[#f7fffb] to-emerald-50',
          borderColor: 'border-emerald-200',
          traits: ['均衡策略', '适应性强', '全面思考']
        };
      default:
        return {
          color: 'slate',
          bgColor: 'from-white to-[#f8f5f1]',
          borderColor: 'border-[#ece4da]',
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
              {ai.isSpeaking && (
                <Badge className="rounded-full border-slate-900 bg-slate-900 text-xs text-white">
                  发言中
                </Badge>
              )}
              <h3 className="mt-3 truncate text-lg font-semibold tracking-[-0.02em] text-slate-950">
                {ai.name}
              </h3>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Badge className="student-pill text-xs">
                  {ai.position}
                </Badge>
              </div>
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
            <div className="flex flex-wrap gap-1.5">
              {config.traits.slice(0, 2).map((trait, index) => (
                <span
                  key={index}
                  className="rounded-full border border-white/80 bg-white/70 px-2 py-1 text-xs text-slate-600"
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
