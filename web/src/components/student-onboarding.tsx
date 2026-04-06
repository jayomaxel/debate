import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import SkillsRadar, { defaultSkills } from './skills-radar';
import WaitingStatusBar from './waiting-status-bar';
import DebateTopicCard from './debate-topic-card';
import StudentService from '@/services/student.service';
import type { AssessmentResult, Debate } from '@/services/student.service';
import { useAuth } from '@/store/auth.context';
import {
  GraduationCap,
  User,
  ArrowRight,
  Save,
  Play,
  CheckCircle,
  AlertCircle,
  BrainCircuit,
  Clock,
  Loader2
} from 'lucide-react';

interface StudentOnboardingProps {
  initialDebate?: Debate | null;
  onDebateStart?: () => void;
  onBackToLogin?: () => void;
  onMatchFound?: () => void;
}

const StudentOnboarding: React.FC<StudentOnboardingProps> = ({ initialDebate, onDebateStart, onBackToLogin, onMatchFound }) => {
  const { user } = useAuth();
  const [skills, setSkills] = useState(defaultSkills);
  const [assessmentResult, setAssessmentResult] = useState<AssessmentResult | null>(null);
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

  // 加载已有的评估结果
  useEffect(() => {
    const loadAssessment = async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await StudentService.getAssessment();
        
        if (result) {
          setAssessmentResult(result);
          setAssessmentComplete(!result.is_default);
          
          // 将评估结果映射到技能雷达图
          // 注意：这里需要根据实际的评估数据结构调整
          setSkills(
            defaultSkills.map((skill) => {
              const valueMap: Record<string, number | undefined> = {
                'AI核心知识运用': result.financial_knowledge,
                'AI伦理与科技素养': result.stablecoin_knowledge,
                '批判性思维': result.critical_thinking,
                '逻辑建构力': result.logical_thinking,
                '语言表达力': result.expression_willingness,
              };
              const mappedValue = valueMap[skill.name];
              return { ...skill, value: typeof mappedValue === 'number' ? mappedValue : skill.value };
            })
          );
        }

        try {
          if (initialDebate) {
            if (initialDebate.role) {
              setAssignedRole({
                role: initialDebate.role,
                role_reason: initialDebate.role_reason,
                topic: initialDebate.topic,
              });
              setJoinedDebate(initialDebate);
            } else {
              setAssignedRole(null);
              setJoinedDebate(initialDebate);
            }
          } else {
            const debates = await StudentService.getAvailableDebates();
            const joinedCandidates = debates.filter((d) => d.is_joined);
            const statusPriority: Record<Debate['status'], number> = {
              in_progress: 0,
              published: 1,
              draft: 2,
              completed: 3,
            };
            const joined = joinedCandidates
              .slice()
              .sort((a, b) => {
                const statusDelta = (statusPriority[a.status] ?? 99) - (statusPriority[b.status] ?? 99);
                if (statusDelta !== 0) return statusDelta;
                const roleDelta = Number(!!b.role) - Number(!!a.role);
                if (roleDelta !== 0) return roleDelta;
                return Date.parse(b.created_at) - Date.parse(a.created_at);
              })[0];
            if (joined?.role) {
              setAssignedRole({
                role: joined.role,
                role_reason: joined.role_reason,
                topic: joined.topic,
              });
              setJoinedDebate(joined);
            } else {
              setAssignedRole(null);
              setJoinedDebate(joined ?? null);
            }
          }
        } catch {
          setAssignedRole(null);
          setJoinedDebate(null);
        }
      } catch (err: any) {
        console.error('Failed to load assessment:', err);
        setError(err.message || '加载评估结果失败');
      } finally {
        setLoading(false);
      }
    };

    loadAssessment();
  }, [initialDebate]);

  const handleSkillChange = (skillName: string, value: number) => {
    setSkills(prev =>
      prev.map(skill =>
        skill.name === skillName ? { ...skill, value } : skill
      )
    );
  };

  const handleSaveAssessment = async () => {
    try {
      setIsSaving(true);
      setError(null);

      const result = await StudentService.submitAssessment({
        logical_thinking: Math.max(0, Math.min(100, Math.round(skills.find(s => s.name === '逻辑建构力')?.value ?? 50))),
        expression_willingness: Math.max(0, Math.min(100, Math.round(skills.find(s => s.name === '语言表达力')?.value ?? 50))),
        stablecoin_knowledge: Math.max(0, Math.min(100, Math.round(skills.find(s => s.name === 'AI伦理与科技素养')?.value ?? 50))),
        financial_knowledge: Math.max(0, Math.min(100, Math.round(skills.find(s => s.name === 'AI核心知识运用')?.value ?? 50))),
        critical_thinking: Math.max(0, Math.min(100, Math.round(skills.find(s => s.name === '批判性思维')?.value ?? 50))),
        personality_type: 'balanced',
      });

      setAssessmentResult(result);
      setSkills(
        defaultSkills.map((skill) => {
          const valueMap: Record<string, number | undefined> = {
            'AI核心知识运用': result.financial_knowledge,
            'AI伦理与科技素养': result.stablecoin_knowledge,
            '批判性思维': result.critical_thinking,
            '逻辑建构力': result.logical_thinking,
            '语言表达力': result.expression_willingness,
          };
          const mappedValue = valueMap[skill.name];
          return { ...skill, value: typeof mappedValue === 'number' ? mappedValue : skill.value };
        })
      );

      setAssessmentComplete(true);
      setError(null);
    } catch (err: any) {
      console.error('Failed to save assessment:', err);
      setError(err.message || '保存评估失败');
    } finally {
      setIsSaving(false);
    }
  };

  const calculateOverallScore = () => {
    const total = skills.reduce((sum, skill) => sum + skill.value, 0);
    return Math.round(total / skills.length);
  };

  const overallScore = calculateOverallScore();

  const roleLabel: Record<NonNullable<Debate['role']>, string> = {
    debater_1: '一辩',
    debater_2: '二辩',
    debater_3: '三辩',
    debater_4: '四辩',
  };

  const roleDescription: Record<NonNullable<Debate['role']>, string> = {
    debater_1: '一辩 - 立论陈词，奠定基调',
    debater_2: '二辩 - 攻辩反击，定点堵塞',
    debater_3: '三辩 - 逻辑交锋，快速反应',
    debater_4: '四辩 - 总结陈词，价值升华',
  };

  // 加载状态
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
      {/* 错误提示 */}
      {error && (
        <div className="fixed top-4 right-4 z-50 max-w-md">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </div>
      )}

      <div className="flex flex-col min-h-screen">
        {/* 顶部导航 */}
        <header className="bg-white border-b border-slate-200 shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
                  <BrainCircuit className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-slate-900">碳硅之辩</h1>
                  <p className="text-sm text-slate-600">人机思辨平台 · 学生准备中心</p>
                </div>
              </div>

              <div className="flex items-center gap-4">
                {/* 用户信息 */}
                <div className="flex items-center gap-2">
                  <User className="w-4 h-4 text-slate-600" />
                  <span className="text-sm text-slate-700">{user?.name || '学生'}</span>
                </div>

                {/* 退出按钮 */}
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

        {/* 主要内容 */}
        <div className="flex-1 p-6">
          <div className="max-w-7xl mx-auto">
            {/* 页面标题 */}
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold text-slate-900 mb-2">
                辩论准备中心
              </h2>
              <p className="text-lg text-slate-600">
                完成能力评估，了解辩题背景，准备精彩的辩论表现
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* 左侧：能力评估 */}
              <div className="lg:col-span-2 space-y-6">
                {/* 能力评估状态 */}
                <Card className="bg-white border-slate-200 shadow-sm">
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <BrainCircuit className="w-5 h-5 text-blue-600" />
                        个人能力评估
                      </div>
                      {assessmentResult?.is_default ? (
                        <Badge className="bg-amber-100 text-amber-700 border-amber-300">
                          <AlertCircle className="w-3 h-3 mr-1" />
                          系统默认
                        </Badge>
                      ) : assessmentComplete && (
                        <Badge className="bg-emerald-100 text-emerald-700 border-emerald-300">
                          <CheckCircle className="w-3 h-3 mr-1" />
                          已完成
                        </Badge>
                      )}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-sm text-slate-600 mb-4">
                      评估您的各项能力，系统将根据评估结果为您匹配合适的辩论对手
                    </div>

                    <SkillsRadar
                      skills={skills}
                      onSkillChange={handleSkillChange}
                      readonly={assessmentComplete}
                    />

                    {/* 综合评分和推荐角色 */}
                    <div className="mt-6 space-y-4">
                      <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="font-medium text-blue-900">综合能力评分</h3>
                            <p className="text-sm text-blue-700">基于所有维度的综合评估</p>
                          </div>
                          <div className="text-right">
                            <div className="text-2xl font-bold text-blue-600">{overallScore}</div>
                            <div className="text-xs text-blue-600">综合评分</div>
                          </div>
                        </div>
                      </div>

                      {/* 显示推荐角色 */}
                      {assessmentResult && (
                        <div className="p-4 bg-emerald-50 rounded-lg border border-emerald-200">
                          <h3 className="font-medium text-emerald-900 mb-2">
                            {assignedRole ? '本场辩论角色（智能分组）' : '推荐辩论角色'}
                          </h3>
                          <div className="flex items-center gap-2 mb-2">
                            <Badge className="bg-emerald-600 text-white">
                              {assignedRole ? assignedRole.role : assessmentResult.recommended_role}
                            </Badge>
                            {assignedRole && (
                              <Badge variant="outline" className="bg-white text-emerald-700 border-emerald-200">
                                {roleLabel[assignedRole.role]}
                              </Badge>
                            )}
                          </div>
                          <p className="text-sm text-emerald-700">
                            {assignedRole
                              ? `${roleDescription[assignedRole.role]}${assignedRole.role_reason ? `（${assignedRole.role_reason}）` : ''}`
                              : assessmentResult.role_description}
                          </p>
                          {assignedRole?.topic && (
                            <p className="text-xs text-emerald-700 mt-1">
                              当前辩题：{assignedRole.topic}
                            </p>
                          )}
                        </div>
                      )}
                    </div>

                    {/* 保存按钮 */}
                    {!assessmentComplete && (
                      <div className="mt-6 flex gap-3">
                        <Button
                          onClick={handleSaveAssessment}
                          disabled={isSaving}
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
                  </CardContent>
                </Card>

                {/* 辩题信息 */}
                <DebateTopicCard debate={joinedDebate} />
              </div>

              {/* 右侧：状态和提示 */}
              <div className="space-y-6">
                {/* 等待状态 */}
                <WaitingStatusBar onMatchFound={onMatchFound} />

                {/* 准备清单 */}
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
                        <span className={`text-sm ${assessmentComplete ? 'text-slate-700' : 'text-slate-500'}`}>
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

                {/* 快速操作 */}
                <Card className="bg-gradient-to-br from-purple-50 to-blue-50 border-purple-200">
                  <CardContent className="p-6">
                    <h3 className="font-medium text-slate-900 mb-4">快速操作</h3>
                    <div className="space-y-3">
                      <Button
                        variant="outline"
                        className="w-full justify-start border-slate-300"
                        disabled={!assessmentComplete}
                      >
                        <BrainCircuit className="w-4 h-4 mr-2" />
                        查看能力分析报告
                      </Button>
                      <Button
                        variant="outline"
                        className="w-full justify-start border-slate-300"
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
