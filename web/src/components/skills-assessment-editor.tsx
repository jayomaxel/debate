import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { BrainCircuit } from 'lucide-react';
import type { SkillData, SkillKey } from './skills-radar';

interface SkillsAssessmentEditorProps {
  skills: SkillData[];
  onSkillChange: (skillKey: SkillKey, value: number) => void;
}

const normalizeValue = (value: number) => Math.max(0, Math.min(100, value));

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

const SkillsAssessmentEditor: React.FC<SkillsAssessmentEditorProps> = ({
  skills,
  onSkillChange,
}) => (
  <Card className="border-slate-200 bg-white shadow-sm">
    <CardHeader>
      <CardTitle className="flex items-center gap-2 text-slate-900">
        <BrainCircuit className="h-5 w-5 text-blue-600" />
        个人能力评估
      </CardTitle>
      <p className="text-sm text-slate-600">
        请完成 5 个维度的自评，系统不会再自动补入默认分值
      </p>
    </CardHeader>
    <CardContent className="space-y-6">
      {skills.map((skill) => {
        const rawValue = skill.value;
        const hasValue = typeof rawValue === 'number';
        const currentValue = hasValue ? normalizeValue(rawValue) : 0;
        const level = hasValue ? getSkillLevel(currentValue) : null;

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
              {hasValue && level ? (
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
                  待填写
                </Badge>
              )}
            </div>

            {hasValue ? (
              <Progress value={currentValue} className="h-2" />
            ) : (
              <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-500">
                请拖动滑块或输入分值完成自评
              </div>
            )}

            <div className="flex items-center gap-3 pt-2">
              <input
                type="range"
                min="0"
                max="100"
                value={currentValue}
                onChange={(event) =>
                  onSkillChange(skill.key, normalizeValue(Number.parseInt(event.target.value, 10)))
                }
                className="slider h-2 flex-1 cursor-pointer appearance-none rounded-lg bg-slate-200"
              />
              <input
                type="number"
                min="0"
                max="100"
                value={hasValue ? currentValue : ''}
                onChange={(event) =>
                  onSkillChange(
                    skill.key,
                    normalizeValue(Number.parseInt(event.target.value, 10) || 0)
                  )
                }
                placeholder="0-100"
                className="w-20 rounded border border-slate-300 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        );
      })}
    </CardContent>
  </Card>
);

export default SkillsAssessmentEditor;
