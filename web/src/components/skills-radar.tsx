import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import type { AssessmentResult } from '@/services/student.service';
import { hasRecordedAbilityValues } from '@/lib/ability-profile';
import {
  BrainCircuit,
  MessageSquare,
  Shield,
  Target,
  TrendingUp,
  Zap,
} from 'lucide-react';

export type SkillKey =
  | 'financial_knowledge'
  | 'stablecoin_knowledge'
  | 'critical_thinking'
  | 'logical_thinking'
  | 'expression_willingness';

export interface SkillData {
  key: SkillKey;
  name: string;
  value: number | null;
  icon: React.ReactNode;
  description: string;
}

interface SkillsRadarProps {
  skills: SkillData[];
  emptyStateMessage?: string;
}

const skillTemplates: Array<Omit<SkillData, 'value'>> = [
  {
    key: 'financial_knowledge',
    name: 'AI核心知识运用',
    icon: <Zap className="h-4 w-4" />,
    description: 'AI概念、案例与课程知识点的理解和迁移能力',
  },
  {
    key: 'stablecoin_knowledge',
    name: 'AI伦理与科技素养',
    icon: <Shield className="h-4 w-4" />,
    description: '对技术边界、伦理风险与社会影响的综合判断能力',
  },
  {
    key: 'critical_thinking',
    name: '批判性思维',
    icon: <Target className="h-4 w-4" />,
    description: '识别漏洞、提出质疑并展开反驳的能力',
  },
  {
    key: 'logical_thinking',
    name: '逻辑建构力',
    icon: <TrendingUp className="h-4 w-4" />,
    description: '观点结构、推理链条与论证严密性的表现',
  },
  {
    key: 'expression_willingness',
    name: '语言表达力',
    icon: <MessageSquare className="h-4 w-4" />,
    description: '表达清晰度、感染力与说服效果',
  },
];

export const DEFAULT_SKILLS_EMPTY_STATE_MESSAGE =
  '暂无能力评估画像，请先前往参与辩论';

export const createEmptySkills = (): SkillData[] =>
  skillTemplates.map((skill) => ({
    ...skill,
    value: null,
  }));

export const createEditableDefaultSkills = (): SkillData[] => createEmptySkills();

export const mergeAssessmentIntoSkills = (
  skills: SkillData[],
  assessment: AssessmentResult | null | undefined
): SkillData[] =>
  skills.map((skill) => {
    const nextValue = assessment?.[skill.key];

    return {
      ...skill,
      value: typeof nextValue === 'number' ? nextValue : skill.value,
    };
  });

const getSkillLevel = (value: number) => {
  if (value >= 80) {
    return { label: '优秀', color: 'text-emerald-600 bg-emerald-50' };
  }
  if (value >= 60) {
    return { label: '良好', color: 'text-blue-600 bg-blue-50' };
  }
  if (value >= 40) {
    return { label: '基础', color: 'text-amber-600 bg-amber-50' };
  }

  return { label: '待提升', color: 'text-slate-600 bg-slate-50' };
};

const normalizeValue = (value: number) => Math.max(0, Math.min(100, value));

const SkillsRadar: React.FC<SkillsRadarProps> = ({
  skills,
  emptyStateMessage = DEFAULT_SKILLS_EMPTY_STATE_MESSAGE,
}) => {
  const hasAnySkillValue = hasRecordedAbilityValues(skills.map((skill) => skill.value));

  return (
    <Card className="border-slate-200 bg-white shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-slate-900">
          <BrainCircuit className="h-5 w-5 text-blue-600" />
          个人能力评估
        </CardTitle>
        <p className="text-sm text-slate-600">
          以下内容仅用于展示系统记录的能力评估结果
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        {!hasAnySkillValue ? (
          <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center">
            <BrainCircuit className="mx-auto mb-3 h-10 w-10 text-slate-300" />
            <p className="text-sm text-slate-500">{emptyStateMessage}</p>
          </div>
        ) : (
          skills.map((skill) => {
            const hasValue = typeof skill.value === 'number';
            const currentValue = hasValue ? normalizeValue(skill.value) : null;
            const level = currentValue === null ? null : getSkillLevel(currentValue);

            return (
              <div key={skill.key} className="space-y-3">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
                      {skill.icon}
                    </div>
                    <div>
                      <h3 className="font-medium text-slate-900">{skill.name}</h3>
                      <p className="text-xs text-slate-500">{skill.description}</p>
                    </div>
                  </div>
                  {currentValue !== null && level ? (
                    <div className="flex items-center gap-2">
                      <Badge className={level.color} variant="outline">
                        {level.label}
                      </Badge>
                      <span className="w-10 text-right text-sm font-medium text-slate-700">
                        {currentValue}%
                      </span>
                    </div>
                  ) : (
                    <Badge className="bg-slate-50 text-slate-500" variant="outline">
                      暂无数据
                    </Badge>
                  )}
                </div>

                {currentValue !== null ? (
                  <Progress value={currentValue} className="h-2" />
                ) : (
                  <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-500">
                    {emptyStateMessage}
                  </div>
                )}
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
};

export default SkillsRadar;
