import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import TeamMember, { TeamMember as TeamMemberType } from './team-member';
import { Users, Bot, TrendingUp, Shield } from 'lucide-react';

interface TeamDisplayProps {
  title: string;
  members: TeamMemberType[];
  isHuman?: boolean;
  isAnimating?: boolean;
  teamColor?: 'blue' | 'purple';
}

const TeamDisplay: React.FC<TeamDisplayProps> = ({
  title,
  members,
  isHuman = true,
  isAnimating = false,
  teamColor = 'blue'
}) => {
  const [showMembers, setShowMembers] = useState(!isAnimating);

  useEffect(() => {
    if (isAnimating) {
      const timer = setTimeout(() => {
        setShowMembers(true);
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [isAnimating]);

  const getTeamBgColor = () => {
    if (!isHuman) {
      return teamColor === 'blue'
        ? 'bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200'
        : 'bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200';
    }
    return teamColor === 'blue'
      ? 'bg-gradient-to-br from-blue-50 to-emerald-50 border-blue-200'
      : 'bg-gradient-to-br from-purple-50 to-pink-50 border-purple-200';
  };

  const getAverageSkill = () => {
    if (members.length === 0) return 0;
    const total = members.reduce((sum, member) => sum + member.skillLevel, 0);
    return Math.round(total / members.length);
  };

  const getTeamIcon = () => {
    if (isHuman) {
      return <Users className="w-6 h-6 text-blue-600" />;
    }
    return <Bot className="w-6 h-6 text-purple-600" />;
  };

  const getTeamTypeLabel = () => {
    return isHuman ? '人类团队' : 'AI智能团队';
  };

  const getAIDiversity = () => {
    if (isHuman) return null;
    const aiTypes = members.map(m => m.aiType).filter(Boolean);
    const uniqueTypes = [...new Set(aiTypes)];
    if (uniqueTypes.length <= 1) return null;

    return (
      <div className="flex items-center gap-2 mt-2">
        <span className="text-xs text-slate-600">AI策略多样性:</span>
        <div className="flex gap-1">
          {uniqueTypes.map((type, index) => (
            <Badge
              key={index}
              variant="outline"
              className="text-xs px-2 py-0"
            >
              {type === 'analytical' && '分析型'}
              {type === 'creative' && '创意型'}
              {type === 'aggressive' && '激进型'}
              {type === 'balanced' && '平衡型'}
            </Badge>
          ))}
        </div>
      </div>
    );
  };

  return (
    <Card className={`${getTeamBgColor()} border-2 shadow-xl overflow-hidden`}>
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {getTeamIcon()}
            <div>
              <CardTitle className="text-xl font-bold text-slate-900">
                {title}
              </CardTitle>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant="outline" className="text-xs">
                  {getTeamTypeLabel()}
                </Badge>
                <Badge variant="outline" className="text-xs bg-blue-100 text-blue-700">
                  {members.length}名成员
                </Badge>
              </div>
            </div>
          </div>

          {/* 团队实力评分 */}
          <div className="text-right">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-amber-500" />
              <span className="text-2xl font-bold text-slate-900">
                {getAverageSkill()}
              </span>
            </div>
            <p className="text-xs text-slate-600">团队综合实力</p>
          </div>
        </div>

        {getAIDiversity()}
      </CardHeader>

      <CardContent className="space-y-3">
        {members.map((member, index) => (
          <div
            key={member.id}
            className={`transition-all duration-500 ${
              showMembers
                ? 'opacity-100 transform translate-y-0'
                : 'opacity-0 transform translate-y-4'
            }`}
            style={{
              transitionDelay: showMembers ? `${index * 150}ms` : '0ms'
            }}
          >
            <TeamMember
              member={member}
              isAnimating={!showMembers}
              animationDelay={index * 150}
            />
          </div>
        ))}

        {/* 团队统计 */}
        <div className="mt-4 p-3 bg-white/60 rounded-lg border border-slate-200">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-blue-500" />
              <span className="font-medium text-slate-700">团队优势</span>
            </div>
            <div className="flex gap-3 text-xs text-slate-600">
              <span>立论: {members.filter(m => m.position === '一辩').length}</span>
              <span>攻辩: {members.filter(m => m.position === '二辩').length}</span>
              <span>质询: {members.filter(m => m.position === '三辩').length}</span>
              <span>总结: {members.filter(m => m.position === '四辩').length}</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default TeamDisplay;
