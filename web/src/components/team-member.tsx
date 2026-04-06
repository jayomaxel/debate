import React from 'react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { User, Bot, Star, TrendingUp } from 'lucide-react';

export interface TeamMember {
  id: string;
  name: string;
  avatar?: string;
  position: '一辩' | '二辩' | '三辩' | '四辩';
  skillLevel: number;
  isAI?: boolean;
  aiType?: 'analytical' | 'creative' | 'aggressive' | 'balanced';
}

interface TeamMemberProps {
  member: TeamMember;
  isAnimating?: boolean;
  animationDelay?: number;
}

const TeamMember: React.FC<TeamMemberProps> = ({
  member,
  isAnimating = false,
  animationDelay = 0
}) => {
  const getSkillColor = (level: number) => {
    if (level >= 80) return 'text-emerald-600 bg-emerald-50';
    if (level >= 60) return 'text-blue-600 bg-blue-50';
    if (level >= 40) return 'text-amber-600 bg-amber-50';
    return 'text-slate-600 bg-slate-50';
  };

  const getSkillLabel = (level: number) => {
    if (level >= 80) return '专家';
    if (level >= 60) return '熟练';
    if (level >= 40) return '进阶';
    return '入门';
  };

  const getAIColor = (type?: string) => {
    switch (type) {
      case 'analytical': return 'border-blue-500 bg-blue-50';
      case 'creative': return 'border-purple-500 bg-purple-50';
      case 'aggressive': return 'border-red-500 bg-red-50';
      case 'balanced': return 'border-green-500 bg-green-50';
      default: return 'border-slate-500 bg-slate-50';
    }
  };

  const getAITypeLabel = (type?: string) => {
    switch (type) {
      case 'analytical': return '分析型';
      case 'creative': return '创意型';
      case 'aggressive': return '激进型';
      case 'balanced': return '平衡型';
      default: return '智能AI';
    }
  };

  return (
    <Card
      className={`border-2 transition-all duration-500 ${
        isAnimating
          ? 'opacity-0 transform scale-95'
          : 'opacity-100 transform scale-100'
      } ${member.isAI ? getAIColor(member.aiType) : 'border-slate-200 bg-white'}`}
      style={{
        animationDelay: isAnimating ? `${animationDelay}ms` : '0ms',
        animation: isAnimating ? 'fadeInScale 0.6s ease-out forwards' : 'none'
      }}
    >
      <CardContent className="p-4">
        <div className="flex items-center gap-4">
          {/* 头像 */}
          <div className="relative">
            <Avatar className="w-16 h-16 border-2 border-white shadow-lg">
              <AvatarImage src={member.avatar} alt={member.name} />
              <AvatarFallback className={member.isAI ? getAIColor(member.aiType) : 'bg-blue-100'}>
                {member.isAI ? (
                  <Bot className="w-8 h-8 text-slate-700" />
                ) : (
                  <User className="w-8 h-8 text-blue-600" />
                )}
              </AvatarFallback>
            </Avatar>

            {/* 辩位标记 */}
            <Badge
              className="absolute -top-2 -right-2 text-xs px-2 py-1"
              variant="secondary"
            >
              {member.position}
            </Badge>
          </div>

          {/* 成员信息 */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <h3 className="font-bold text-slate-900 truncate">
                {member.name}
              </h3>
              {member.isAI && (
                <Badge variant="outline" className="text-xs">
                  {getAITypeLabel(member.aiType)}
                </Badge>
              )}
            </div>

            {/* 技能等级 */}
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1">
                <Star className="w-4 h-4 text-amber-500" />
                <TrendingUp className="w-4 h-4 text-blue-500" />
                <span className="text-sm font-medium text-slate-700">
                  {member.skillLevel}
                </span>
              </div>
              <Badge
                variant="outline"
                className={`text-xs ${getSkillColor(member.skillLevel)}`}
              >
                {getSkillLabel(member.skillLevel)}
              </Badge>
            </div>

            {/* 角色描述 */}
            <p className="text-xs text-slate-500 mt-1">
              {member.position === '一辩' && '立论陈词，奠定基调'}
              {member.position === '二辩' && '攻辩反击，逻辑交锋'}
              {member.position === '三辩' && '质询小结，深化论证'}
              {member.position === '四辩' && '总结陈词，升华观点'}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default TeamMember;