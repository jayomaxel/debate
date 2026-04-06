import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { BrainCircuit, MessageSquare, TrendingUp, Shield, Target, Zap } from 'lucide-react';

interface SkillData {
  name: string;
  value: number;
  icon: React.ReactNode;
  description: string;
}

interface SkillsRadarProps {
  skills: SkillData[];
  onSkillChange?: (skillName: string, value: number) => void;
  readonly?: boolean;
}

const SkillsRadar: React.FC<SkillsRadarProps> = ({ skills, onSkillChange, readonly = false }) => {
  const getSkillLevel = (value: number) => {
    if (value >= 80) return { label: '精通', color: 'text-emerald-600 bg-emerald-50' };
    if (value >= 60) return { label: '熟练', color: 'text-blue-600 bg-blue-50' };
    if (value >= 40) return { label: '掌握', color: 'text-amber-600 bg-amber-50' };
    return { label: '入门', color: 'text-slate-600 bg-slate-50' };
  };

  return (
    <Card className="bg-white border-slate-200 shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-slate-900">
          <BrainCircuit className="w-5 h-5 text-blue-600" />
          个人能力评估
        </CardTitle>
        <p className="text-sm text-slate-600">
          {readonly ? '您的综合能力评估' : '评估您在各维度的能力水平，用于智能匹配'}
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        {skills.map((skill) => {
          const level = getSkillLevel(skill.value);

          return (
            <div key={skill.name} className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center">
                    {skill.icon}
                  </div>
                  <div>
                    <h3 className="font-medium text-slate-900">{skill.name}</h3>
                    <p className="text-xs text-slate-500">{skill.description}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge className={level.color} variant="outline">
                    {level.label}
                  </Badge>
                  <span className="text-sm font-medium text-slate-700 w-10 text-right">
                    {skill.value}%
                  </span>
                </div>
              </div>

              <div className="space-y-2">
                <Progress
                  value={skill.value}
                  className="h-2"
                />
                {!readonly && (
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>入门</span>
                    <span>掌握</span>
                    <span>熟练</span>
                    <span>精通</span>
                  </div>
                )}
              </div>

              {!readonly && onSkillChange && (
                <div className="flex items-center gap-3 pt-2">
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={skill.value}
                    onChange={(e) => onSkillChange(skill.name, parseInt(e.target.value))}
                    className="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer slider"
                  />
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={skill.value}
                    onChange={(e) => onSkillChange(skill.name, parseInt(e.target.value) || 0)}
                    className="w-16 px-2 py-1 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
};

// 默认技能数据
export const defaultSkills = [
  {
    name: 'AI核心知识运用',
    value: 65,
    icon: <Zap className="w-4 h-4" />,
    description: 'AI概念、案例与课程知识点的调用能力'
  },
  {
    name: 'AI伦理与科技素养',
    value: 50,
    icon: <Shield className="w-4 h-4" />,
    description: '对技术边界、伦理风险与社会影响的综合判断'
  },
  {
    name: '批判性思维',
    value: 75,
    icon: <Target className="w-4 h-4" />,
    description: '识别漏洞、提出质疑与展开反驳的能力'
  },
  {
    name: '逻辑建构力',
    value: 60,
    icon: <TrendingUp className="w-4 h-4" />,
    description: '观点结构、推理链条与论证严密性'
  },
  {
    name: '语言表达力',
    value: 70,
    icon: <MessageSquare className="w-4 h-4" />,
    description: '表达清晰度、感染力与说服效果'
  }
];

export default SkillsRadar;
