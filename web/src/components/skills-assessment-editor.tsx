import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { BrainCircuit } from 'lucide-react';
import type { SkillData, SkillKey } from './skills-radar';

interface SkillsAssessmentEditorProps {
  skills: SkillData[];
  onSkillChange: (skillKey: SkillKey, value: number) => void;
  studentMode?: boolean;
}

const normalizeValue = (value: number) => Math.max(0, Math.min(100, value));

const getSkillLevel = (value: number) => {
  if (value >= 80) {
    return { label: '优秀', color: 'text-emerald-700 bg-emerald-50' };
  }
  if (value >= 60) {
    return { label: '良好', color: 'text-[#6f5945] bg-[#f1e5d7]' };
  }
  if (value >= 40) {
    return { label: '基础', color: 'text-amber-700 bg-amber-50' };
  }

  return { label: '待提升', color: 'text-slate-700 bg-slate-100' };
};

const SkillsAssessmentEditor: React.FC<SkillsAssessmentEditorProps> = ({
  skills,
  onSkillChange,
  studentMode = false,
}) => (
  <Card
    className={
      studentMode
        ? 'student-card'
        : 'border-slate-200 bg-white shadow-sm'
    }
  >
    <CardHeader className="pb-4">
      <CardTitle className="flex items-center gap-2 text-slate-900">
        <BrainCircuit className="h-5 w-5 text-slate-700" />
        个人能力评估
      </CardTitle>
      <p className="text-sm leading-7 text-slate-600">
        请完成 5 个维度的自评，系统不会再自动补入默认分值。
      </p>
    </CardHeader>
    <CardContent className="space-y-4">
      {skills.map((skill, index) => {
        const rawValue = skill.value;
        const hasValue = typeof rawValue === 'number';
        const currentValue = hasValue ? normalizeValue(rawValue) : 0;
        const level = hasValue ? getSkillLevel(currentValue) : null;

        return (
          <div key={skill.key} className="space-y-3">
            <div
              className={`${
                studentMode
                  ? index % 3 === 0
                    ? 'student-card-soft-blue'
                    : index % 3 === 1
                    ? 'student-card-soft-peach'
                    : 'student-card-soft-lavender'
                  : 'rounded-2xl border border-slate-200 bg-slate-50'
              } ${studentMode ? 'p-4' : 'p-5'}`}
            >
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="student-icon-bubble h-9 w-9 bg-white text-slate-900">
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

              <div className="mt-4">
                {hasValue ? (
                  <Progress
                    value={currentValue}
                    className={
                      studentMode
                        ? 'h-2 bg-[#ece3d8] [&>div]:bg-[#171717]'
                        : 'h-2'
                    }
                  />
                ) : (
                  <div className="rounded-md border border-dashed border-black/10 bg-white/60 px-3 py-3 text-sm text-slate-500">
                    请拖动滑块或输入分值完成自评。
                  </div>
                )}
              </div>

              <div className="mt-4 flex items-center gap-3">
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={currentValue}
                  onChange={(event) =>
                    onSkillChange(
                      skill.key,
                      normalizeValue(Number.parseInt(event.target.value, 10))
                    )
                  }
                  className="slider h-2 flex-1 cursor-pointer appearance-none rounded-lg bg-white"
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
                  className="w-24 rounded-[14px] border border-black/10 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
                />
              </div>
            </div>
          </div>
        );
      })}
    </CardContent>
  </Card>
);

export default SkillsAssessmentEditor;
