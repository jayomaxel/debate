import React, { useEffect, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import SkillsAssessmentEditor from './skills-assessment-editor';
import SkillsRadar, {
  createEmptySkills,
  mergeAssessmentIntoSkills,
  type SkillKey,
} from './skills-radar';
import WaitingStatusBar from './waiting-status-bar';
import DebateTopicCard from './debate-topic-card';
import StudentService from '@/services/student.service';
import { hasCompleteAbilityValues } from '@/lib/ability-profile';
import type { AssessmentResult, Debate } from '@/services/student.service';
import { useAuth } from '@/store/auth.context';
import {
  AlertCircle,
  BrainCircuit,
  CheckCircle,
  Clock,
  Loader2,
  Save,
  User,
} from 'lucide-react';

interface StudentOnboardingProps {
  initialDebate?: Debate | null;
  onDebateStart?: () => void;
  onBackToLogin?: () => void;
  onMatchFound?: () => void;
  onNavigateToAnalytics?: (tab: 'history' | 'growth') => void;
}

type DebateRole = NonNullable<Debate['role']>;

const roleLabel: Record<NonNullable<Debate['role']>, string> = {
  debater_1: '一辩',
  debater_2: '二辩',
  debater_3: '三辩',
  debater_4: '四辩',
};

const roleDescription: Record<NonNullable<Debate['role']>, string> = {
  debater_1: '一辩 - 立论陈词，奠定基调',
  debater_2: '二辩 - 攻辩反击，定点补强',
  debater_3: '三辩 - 逻辑交锋，快速反应',
  debater_4: '四辩 - 总结陈词，价值升华',
};

const isDebateRole = (role: unknown): role is DebateRole =>
  typeof role === 'string' && role in roleLabel;

const StudentOnboarding: React.FC<StudentOnboardingProps> = ({
  initialDebate,
  onDebateStart,
  onBackToLogin,
  onMatchFound,
  onNavigateToAnalytics,
}) => {
  const { user } = useAuth();
  const [skills, setSkills] = useState(createEmptySkills);
  const [assessmentResult, setAssessmentResult] =
    useState<AssessmentResult | null>(null);
  const [assessmentComplete, setAssessmentComplete] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [assignedRole, setAssignedRole] = useState<{
    role: NonNullable<Debate['role']>;
    role_reason?: string | null;
    topic?: string;
  } | null>(null);
  const [joinedDebate, setJoinedDebate] = useState<Debate | null>(null);

  useEffect(() => {
    const loadDebateContext = async () => {
      try {
        if (initialDebate) {
          if (initialDebate.role) {
            setAssignedRole({
              role: initialDebate.role,
              role_reason: initialDebate.role_reason,
              topic: initialDebate.topic,
            });
          } else {
            setAssignedRole(null);
          }
          setJoinedDebate(initialDebate);
          return;
        }

        const debates = await StudentService.getAvailableDebates();
        const joinedCandidates = debates.filter((debate) => debate.is_joined);
        const statusPriority: Record<Debate['status'], number> = {
          in_progress: 0,
          published: 1,
          draft: 2,
          completed: 3,
        };

        const joined = joinedCandidates
          .slice()
          .sort((a, b) => {
            const statusDelta =
              (statusPriority[a.status] ?? 99) - (statusPriority[b.status] ?? 99);
            if (statusDelta !== 0) {
              return statusDelta;
            }

            const roleDelta = Number(!!b.role) - Number(!!a.role);
            if (roleDelta !== 0) {
              return roleDelta;
            }

            return Date.parse(b.created_at) - Date.parse(a.created_at);
          })[0];

        if (joined?.role) {
          setAssignedRole({
            role: joined.role,
            role_reason: joined.role_reason,
            topic: joined.topic,
          });
        } else {
          setAssignedRole(null);
        }

        setJoinedDebate(joined ?? null);
      } catch {
        setAssignedRole(null);
        setJoinedDebate(null);
      }
    };

    const loadAssessment = async () => {
      try {
        setLoading(true);
        setError(null);

        const result = await StudentService.getAssessment();
        if (result && !result.is_default) {
          setAssessmentResult(result);
          setAssessmentComplete(true);
          setSkills(mergeAssessmentIntoSkills(createEmptySkills(), result));
        } else {
          setAssessmentResult(null);
          setAssessmentComplete(false);
          setSkills(createEmptySkills());
        }

        await loadDebateContext();
      } catch (err: any) {
        console.error('Failed to load assessment:', err);
        setError(err.message || '加载评估结果失败');
      } finally {
        setLoading(false);
      }
    };

    void loadAssessment();
  }, [initialDebate]);

  const handleSkillChange = (skillKey: SkillKey, value: number) => {
    setSkills((prev) =>
      prev.map((skill) =>
        skill.key === skillKey ? { ...skill, value } : skill
      )
    );
  };

  const skillValues = skills.map((skill) => skill.value);
  const isAssessmentReady = hasCompleteAbilityValues(skillValues);

  const getSkillValue = (skillKey: SkillKey) => {
    const skill = skills.find((item) => item.key === skillKey);

    if (typeof skill?.value !== 'number') {
      throw new Error('请先完成 5 个维度的能力自评');
    }

    return Math.max(0, Math.min(100, Math.round(skill.value)));
  };

  const handleSaveAssessment = async () => {
    try {
      if (!isAssessmentReady) {
        setError('请先完成 5 个维度的能力自评');
        return;
      }

      setIsSaving(true);
      setError(null);

      const result = await StudentService.submitAssessment({
        logical_thinking: getSkillValue('logical_thinking'),
        expression_willingness: getSkillValue('expression_willingness'),
        stablecoin_knowledge: getSkillValue('stablecoin_knowledge'),
        financial_knowledge: getSkillValue('financial_knowledge'),
        critical_thinking: getSkillValue('critical_thinking'),
        personality_type: 'balanced',
      });

      setAssessmentResult(result);
      setAssessmentComplete(true);
      setSkills(mergeAssessmentIntoSkills(createEmptySkills(), result));
    } catch (err: any) {
      console.error('Failed to save assessment:', err);
      setError(err.message || '保存评估失败');
    } finally {
      setIsSaving(false);
    }
  };

  const calculateOverallScore = () => {
    if (!isAssessmentReady) {
      return null;
    }

    const total = skills.reduce((sum, skill) => sum + (skill.value ?? 0), 0);
    return Math.round(total / skills.length);
  };

  const overallScore = calculateOverallScore();
  const effectiveRole = assignedRole?.role || assessmentResult?.recommended_role;
  const displayRole = isDebateRole(effectiveRole) ? effectiveRole : null;

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-slate-50 to-amber-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-slate-600">加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-slate-50 to-amber-50">
      {error && (
        <div className="fixed top-4 right-4 z-50 max-w-md">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </div>
      )}

      <div className="flex min-h-screen flex-col">
        <header className="bg-white border-b border-slate-200 shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
                  <BrainCircuit className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-slate-900">碳辩之辩</h1>
                  <p className="text-sm text-slate-600">人机思辨平台 · 学生准备中心</p>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <User className="w-4 h-4 text-slate-600" />
                  <span className="text-sm text-slate-700">
                    {user?.name || '学生'}
                  </span>
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={onBackToLogin}
                  className="border-slate-300 text-slate-700 hover:bg-slate-50"
                >
                  退出
                </Button>
              </div>
            </div>
          </div>
        </header>

        <div className="flex-1 p-6">
          <div className="max-w-7xl mx-auto">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold text-slate-900 mb-2">
                辩论准备中心
              </h2>
              <p className="text-lg text-slate-600">
                完成能力评估，了解辩题背景，准备精彩的辩论表现
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2 space-y-6">
                <Card className="bg-white border-slate-200 shadow-sm">
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <BrainCircuit className="w-5 h-5 text-blue-600" />
                        个人能力评估
                      </div>
                      {assessmentComplete && (
                        <Badge className="bg-emerald-100 text-emerald-700 border-emerald-300">
                          <CheckCircle className="w-3 h-3 mr-1" />
                          已完成
                        </Badge>
                      )}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-sm text-slate-600 mb-4">
                      这里直接读取和个人中心相同的能力评估数据。没有已保存评估时，不再自动填充默认值，保持空白待填写。
                    </div>

                    {assessmentComplete ? (
                      <SkillsRadar skills={skills} />
                    ) : (
                      <SkillsAssessmentEditor
                        skills={skills}
                        onSkillChange={handleSkillChange}
                      />
                    )}

                    <div className="mt-6 space-y-4">
                      <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="font-medium text-blue-900">综合能力评分</h3>
                            <p className="text-sm text-blue-700">
                              {isAssessmentReady
                                ? '基于所有维度的综合评估'
                                : '完成 5 项自评后生成'}
                            </p>
                          </div>
                          <div className="text-right">
                            <div className="text-2xl font-bold text-blue-600">
                              {overallScore ?? '--'}
                            </div>
                            <div className="text-xs text-blue-600">
                              {isAssessmentReady ? '综合评分' : '待完成'}
                            </div>
                          </div>
                        </div>
                      </div>

                      {displayRole && (
                        <div className="p-4 bg-emerald-50 rounded-lg border border-emerald-200">
                          <h3 className="font-medium text-emerald-900 mb-2">
                            {assignedRole
                              ? '本场辩论角色（智能分组）'
                              : '推荐辩论角色'}
                          </h3>
                          <div className="flex items-center gap-2 mb-2">
                            <Badge className="bg-emerald-600 text-white">
                              {displayRole}
                            </Badge>
                            <Badge
                              variant="outline"
                              className="bg-white text-emerald-700 border-emerald-200"
                            >
                              {roleLabel[displayRole]}
                            </Badge>
                          </div>
                          <p className="text-sm text-emerald-700">
                            {assignedRole
                              ? `${roleDescription[assignedRole.role]}${
                                  assignedRole.role_reason
                                    ? `，${assignedRole.role_reason}`
                                    : ''
                                }`
                              : assessmentResult?.role_description}
                          </p>
                          {assignedRole?.topic && (
                            <p className="text-xs text-emerald-700 mt-1">
                              当前辩题：{assignedRole.topic}
                            </p>
                          )}
                        </div>
                      )}
                    </div>

                    {!assessmentComplete && (
                      <div className="mt-6 flex gap-3">
                        <Button
                          onClick={handleSaveAssessment}
                          disabled={isSaving || !isAssessmentReady}
                          className="flex-1 bg-blue-600 hover:bg-blue-700 text-white"
                        >
                          {isSaving ? (
                            <>
                              <Clock className="w-4 h-4 mr-2 animate-spin" />
                              保存中...
                            </>
                          ) : (
                            <>
                              <Save className="w-4 h-4 mr-2" />
                              保存评估结果
                            </>
                          )}
                        </Button>
                      </div>
                    )}

                    {!assessmentComplete && !isAssessmentReady && (
                      <p className="mt-3 text-sm text-slate-500">
                        请先完成 5 个维度的填写，系统不会自动补入默认分值。
                      </p>
                    )}
                  </CardContent>
                </Card>

                <DebateTopicCard debate={joinedDebate} />
              </div>

              <div className="space-y-6">
                <WaitingStatusBar
                  onMatchFound={() => {
                    onDebateStart?.();
                    onMatchFound?.();
                  }}
                />

                <Card className="bg-white border-slate-200 shadow-sm">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-slate-900">
                      <AlertCircle className="w-5 h-5 text-amber-600" />
                      准备清单
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div className="flex items-center gap-2">
                        {assessmentComplete ? (
                          <CheckCircle className="w-4 h-4 text-emerald-600" />
                        ) : (
                          <div className="w-4 h-4 border-2 border-slate-300 rounded-full" />
                        )}
                        <span
                          className={`text-sm ${
                            assessmentComplete ? 'text-slate-700' : 'text-slate-500'
                          }`}
                        >
                          完成个人能力评估
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 border-2 border-slate-300 rounded-full" />
                        <span className="text-sm text-slate-500">了解辩题背景资料</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 border-2 border-slate-300 rounded-full" />
                        <span className="text-sm text-slate-500">准备辩论论据和例子</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 border-2 border-slate-300 rounded-full" />
                        <span className="text-sm text-slate-500">测试麦克风和摄像头</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-gradient-to-br from-purple-50 to-blue-50 border-purple-200">
                  <CardContent className="p-6">
                    <h3 className="font-medium text-slate-900 mb-4">快速操作</h3>
                    <div className="space-y-3">
                      <Button
                        variant="outline"
                        className="w-full justify-start border-slate-300"
                        disabled={!assessmentComplete}
                        onClick={() => onNavigateToAnalytics?.('growth')}
                      >
                        <BrainCircuit className="w-4 h-4 mr-2" />
                        查看能力分析报告
                      </Button>
                      <Button
                        variant="outline"
                        className="w-full justify-start border-slate-300"
                        onClick={() => onNavigateToAnalytics?.('history')}
                      >
                        <Clock className="w-4 h-4 mr-2" />
                        查看历史辩论记录
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StudentOnboarding;
