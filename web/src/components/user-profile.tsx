/**
 * User Profile Component
 * 用户个人中心 - 显示和编辑个人信息、修改密码、个人能力评估
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  User,
  Mail,
  Phone,
  Key,
  Save,
  Loader2,
  GraduationCap,
  ShieldCheck,
  Users,
  TrendingUp,
  Activity,
  Target
} from 'lucide-react';
import AuthService from '@/services/auth.service';
import StudentService from '@/services/student.service';
import { formatErrorMessage } from '@/lib/error-handler';
import type { UserInfo } from '@/lib/token-manager';
import type { GrowthTrendItem, StudentAnalytics } from '@/services/student.service';

import SkillsRadar, { defaultSkills } from './skills-radar';
import type { AssessmentResult } from '@/services/student.service';

interface UserProfileProps {
  user: UserInfo;
  onUpdate?: () => void;
  initialTab?: 'info' | 'password' | 'ability';
}

interface AbilityGrowth {
  logic: number[];
  argument: number[];
  response: number[];
  persuasion: number[];
  teamwork: number[];
  dates: string[];
}

const UserProfile: React.FC<UserProfileProps> = ({ user, initialTab = 'info' }) => {
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<'info' | 'password' | 'ability'>(initialTab);
  
  // 个人信息表单
  const [profileForm, setProfileForm] = useState({
    name: user.name || '',
    email: user.email || '',
    phone: '',
    student_id: '',
    class_id: '',
    class_name: ''
  });
  const [lockedClassId, setLockedClassId] = useState(user.class_id || '');

  // 班级列表（用于学生更换班级）
  const [classes, setClasses] = useState<Array<{
    id: string;
    name: string;
    code: string;
    teacher_name: string;
    student_count: number;
  }>>([]);

  // 修改密码表单
  const [passwordForm, setPasswordForm] = useState({
    old_password: '',
    new_password: '',
    confirm_password: ''
  });

  // 个人能力评估数据
  const [growthTrend, setGrowthTrend] = useState<GrowthTrendItem[]>([]);
  const [analytics, setAnalytics] = useState<StudentAnalytics | null>(null);
  const [selectedAbilities, setSelectedAbilities] = useState<string[]>(['logic', 'argument', 'response', 'persuasion', 'teamwork']);
  
  // 个人能力评估相关状态
  const [skills, setSkills] = useState(defaultSkills);
  const [assessmentResult, setAssessmentResult] = useState<AssessmentResult | null>(null);
  const [isSavingAssessment, setIsSavingAssessment] = useState(false);
  const hasLockedClass = user.user_type === 'student' && Boolean(lockedClassId);

  // 加载完整的个人信息
  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    loadProfile();
    // 加载所有班级供选择（学生和教师都可以选择/修改班级）
    if (user.user_type === 'student') {
      loadClasses();
    }
    
    // 如果是学生，加载能力评估数据
    if (user.user_type === 'student') {
      loadAbilityData();
    }
  }, []);

  const loadProfile = async () => {
    try {
      const profile = await AuthService.getProfile();
      const currentClassId = profile.class_id || '';
      setProfileForm({
        name: profile.name || '',
        email: profile.email || '',
        phone: profile.phone || '',
        student_id: profile.student_id || '',
        class_id: currentClassId,
        class_name: '' // 将从班级列表中获取
      });
      if (user.user_type === 'student') {
        setLockedClassId(currentClassId);
      }
    } catch (err) {
      console.error('Failed to load profile:', err);
    }
  };

  const loadClasses = async () => {
    try {
      const classList = await AuthService.getPublicClasses();
      setClasses(classList);
    } catch (err) {
      console.error('Failed to load classes:', err);
    }
  };

  const loadAbilityData = async () => {
    try {
      const [analyticsData, growthData, assessmentData] = await Promise.all([
        StudentService.getAnalytics(),
        StudentService.getGrowthTrend(7),
        StudentService.getAssessment()
      ]);
      setAnalytics(analyticsData);
      setGrowthTrend(growthData?.debates || []);
      
      if (assessmentData) {
        setAssessmentResult(assessmentData);
        setSkills(
          defaultSkills.map((skill) => {
            const valueMap: Record<string, number | undefined> = {
              'AI核心知识运用': assessmentData.financial_knowledge,
              'AI伦理与科技素养': assessmentData.stablecoin_knowledge,
              '批判性思维': assessmentData.critical_thinking,
              '逻辑建构力': assessmentData.logical_thinking,
              '语言表达力': assessmentData.expression_willingness,
            };
            const mappedValue = valueMap[skill.name];
            return { ...skill, value: typeof mappedValue === 'number' ? mappedValue : skill.value };
          })
        );
      }
    } catch (err) {
      console.error('Failed to load ability data:', err);
    }
  };

  const handleSkillChange = (skillName: string, value: number) => {
    setSkills(prev =>
      prev.map(skill =>
        skill.name === skillName ? { ...skill, value } : skill
      )
    );
  };

  const handleSaveAssessment = async () => {
    try {
      setIsSavingAssessment(true);

      const getSkillValue = (name: string, fallback: number = 50) => {
        const raw = skills.find(s => s.name === name)?.value;
        const num = typeof raw === 'number' && Number.isFinite(raw) ? raw : fallback;
        return Math.max(0, Math.min(100, Math.round(num)));
      };

      const result = await StudentService.submitAssessment({
        logical_thinking: getSkillValue('逻辑建构力'),
        expression_willingness: getSkillValue('语言表达力'),
        stablecoin_knowledge: getSkillValue('AI伦理与科技素养'),
        financial_knowledge: getSkillValue('AI核心知识运用'),
        critical_thinking: getSkillValue('批判性思维'),
        personality_type: 'balanced'
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

      toast({
        variant: 'success',
        title: '评估保存成功',
        description: '您的能力评估已更新',
      });
    } catch (err: any) {
      toast({
        variant: 'destructive',
        title: '保存失败',
        description: formatErrorMessage(err),
      });
    } finally {
      setIsSavingAssessment(false);
    }
  };

  const handleProfileUpdate = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      setLoading(true);
      await AuthService.updateProfile({
        name: profileForm.name,
        email: profileForm.email,
        phone: profileForm.phone,
        student_id: user.user_type === 'student' ? profileForm.student_id : undefined,
        class_id: profileForm.class_id || undefined
      });
      if (user.user_type === 'student' && profileForm.class_id) {
        setLockedClassId(profileForm.class_id);
      }

      toast({
        variant: 'success',
        title: '保存成功',
        description: '个人信息已更新',
      });
      // 不再自动调用 onUpdate，让用户看到提示后自己决定是否返回
    } catch (err) {
      toast({
        variant: 'destructive',
        title: '保存失败',
        description: formatErrorMessage(err),
      });
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();

    // 验证新密码
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      toast({
        variant: 'destructive',
        title: '密码不匹配',
        description: '两次输入的新密码不一致',
      });
      return;
    }

    if (passwordForm.new_password.length < 6) {
      toast({
        variant: 'destructive',
        title: '密码太短',
        description: '新密码长度至少为6位',
      });
      return;
    }

    try {
      setLoading(true);
      await AuthService.changePassword({
        old_password: passwordForm.old_password,
        new_password: passwordForm.new_password
      });

      toast({
        variant: 'success',
        title: '修改成功',
        description: '密码已更新',
      });
      setPasswordForm({
        old_password: '',
        new_password: '',
        confirm_password: ''
      });
    } catch (err) {
      toast({
        variant: 'destructive',
        title: '修改失败',
        description: formatErrorMessage(err),
      });
    } finally {
      setLoading(false);
    }
  };

  // 从成长趋势数据转换为图表数据
  const abilityGrowth: AbilityGrowth = {
    logic: growthTrend?.map(item => item.ability_scores.logic) || [],
    argument: growthTrend?.map(item => item.ability_scores.expression) || [],
    response: growthTrend?.map(item => item.ability_scores.rebuttal) || [],
    persuasion: growthTrend?.map(item => item.ability_scores.knowledge) || [],
    teamwork: growthTrend?.map(item => item.ability_scores.teamwork) || [],
    dates: growthTrend?.map(item => {
      const date = new Date(item.date);
      return `${date.getMonth() + 1}-${date.getDate()}`;
    }) || []
  };

  const toggleAbility = (ability: string) => {
    setSelectedAbilities(prev =>
      prev.includes(ability)
        ? prev.filter(a => a !== ability)
        : [...prev, ability]
    );
  };

  const renderGrowthChart = () => {
    const chartWidth = 600;
    const chartHeight = 300;
    const padding = { top: 20, right: 40, bottom: 40, left: 50 };
    const chartWidthInner = chartWidth - padding.left - padding.right;
    const chartHeightInner = chartHeight - padding.top - padding.bottom;

    const abilities = [
      { key: 'logic', name: '逻辑建构力', color: '#3b82f6' },
      { key: 'argument', name: 'AI核心知识运用', color: '#8b5cf6' },
      { key: 'response', name: '批判性思维', color: '#f59e0b' },
      { key: 'persuasion', name: '语言表达力', color: '#ef4444' },
      { key: 'teamwork', name: 'AI伦理与科技素养', color: '#10b981' }
    ];

    // 如果没有数据，显示空状态
    if (!abilityGrowth.dates || abilityGrowth.dates.length === 0) {
      return (
        <div className="flex items-center justify-center h-64 text-slate-400">
          <div className="text-center">
            <TrendingUp className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p>暂无成长数据</p>
          </div>
        </div>
      );
    }

    const xStep = chartWidthInner / Math.max(abilityGrowth.dates.length - 1, 1);

    return (
      <div className="w-full h-full">
        <svg width="100%" height="100%" viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="xMidYMid meet">
          {/* 网格线 */}
          {Array.from({ length: 6 }, (_, i) => {
            const y = padding.top + (chartHeightInner / 5) * i;
            return (
              <line
                key={`grid-${i}`}
                x1={padding.left}
                y1={y}
                x2={chartWidth - padding.right}
                y2={y}
                stroke="#e5e7eb"
                strokeWidth="1"
                strokeDasharray="2,2"
              />
            );
          })}

          {/* Y轴标签 */}
          {Array.from({ length: 6 }, (_, i) => {
            const value = 100 - (i * 20);
            const y = padding.top + (chartHeightInner / 5) * i;
            return (
              <text
                key={`y-${i}`}
                x={padding.left - 10}
                y={y + 5}
                textAnchor="end"
                className="text-xs fill-slate-600"
              >
                {value}
              </text>
            );
          })}

          {/* X轴标签 */}
          {abilityGrowth.dates.map((date, index) => {
            const x = padding.left + xStep * index;
            return (
              <text
                key={`x-${index}`}
                x={x}
                y={chartHeight - padding.bottom + 20}
                textAnchor="middle"
                className="text-xs fill-slate-600"
              >
                {date}
              </text>
            );
          })}

          {/* 坐标轴 */}
          <line
            x1={padding.left}
            y1={padding.top}
            x2={padding.left}
            y2={chartHeight - padding.bottom}
            stroke="#374151"
            strokeWidth="2"
          />
          <line
            x1={padding.left}
            y1={chartHeight - padding.bottom}
            x2={chartWidth - padding.right}
            y2={chartHeight - padding.bottom}
            stroke="#374151"
            strokeWidth="2"
          />

          {/* 数据线 */}
          {abilities.map((ability) => {
            if (!selectedAbilities.includes(ability.key)) return null;

            const scores = abilityGrowth[ability.key as keyof AbilityGrowth] as number[];
            if (!scores || scores.length === 0) return null;

            return (
              <g key={ability.key}>
                {/* 连接线 */}
                {scores.map((score, index) => {
                  if (index === 0) return null;
                  const prevX = padding.left + xStep * (index - 1);
                  const prevY = padding.top + chartHeightInner - ((scores[index - 1] / 100) * chartHeightInner);
                  const currX = padding.left + xStep * index;
                  const currY = padding.top + chartHeightInner - ((score / 100) * chartHeightInner);

                  return (
                    <line
                      key={`line-${ability.key}-${index}`}
                      x1={prevX}
                      y1={prevY}
                      x2={currX}
                      y2={currY}
                      stroke={ability.color}
                      strokeWidth="2"
                      opacity="0.8"
                    />
                  );
                })}

                {/* 数据点 */}
                {scores.map((score, index) => {
                  const x = padding.left + xStep * index;
                  const y = padding.top + chartHeightInner - ((score / 100) * chartHeightInner);

                  return (
                    <circle
                      key={`point-${ability.key}-${index}`}
                      cx={x}
                      cy={y}
                      r="4"
                      fill={ability.color}
                      stroke="white"
                      strokeWidth="2"
                      className="hover:r-6 transition-all"
                    />
                  );
                })}
              </g>
            );
          })}
        </svg>

        {/* 图例 */}
        <div className="flex flex-wrap gap-2 mt-4">
          {abilities.map((ability) => (
            <Button
              key={ability.key}
              variant={selectedAbilities.includes(ability.key) ? 'default' : 'outline'}
              size="sm"
              onClick={() => toggleAbility(ability.key)}
              className="text-xs"
              style={{
                backgroundColor: selectedAbilities.includes(ability.key) ? ability.color : undefined
              }}
            >
              <div
                className="w-3 h-3 rounded-full mr-1"
                style={{ backgroundColor: ability.color }}
              />
              {ability.name}
            </Button>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center gap-3">
        {user.user_type === 'student' ? (
          <GraduationCap className="w-8 h-8 text-blue-600" />
        ) : (
          <ShieldCheck className="w-8 h-8 text-blue-600" />
        )}
        <div>
          <h1 className="text-3xl font-bold text-slate-900">个人中心</h1>
          <p className="text-slate-600">
            {user.user_type === 'student' ? '学生' : '教师'} - {user.name}
          </p>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as 'info' | 'password' | 'ability')} className="w-full">
        <TabsList className="grid w-full grid-cols-3 mb-8">
          <TabsTrigger value="info" className="flex items-center gap-2">
            <User className="w-4 h-4" />
            个人信息
          </TabsTrigger>
          <TabsTrigger value="password" className="flex items-center gap-2">
            <Key className="w-4 h-4" />
            修改密码
          </TabsTrigger>
          {user.user_type === 'student' && (
            <TabsTrigger value="ability" className="flex items-center gap-2">
              <Activity className="w-4 h-4" />
              能力评估
            </TabsTrigger>
          )}
        </TabsList>

        {/* 个人信息内容 */}
        <TabsContent value="info">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="w-5 h-5" />
                基本资料
              </CardTitle>
              <CardDescription>查看和编辑您的个人信息</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleProfileUpdate} className="space-y-4">
                {/* 账号（只读） */}
                <div className="space-y-2">
                  <Label htmlFor="account" className="text-slate-700 font-medium flex items-center gap-2">
                    <User className="w-4 h-4" />
                    账号
                  </Label>
                  <Input
                    id="account"
                    type="text"
                    value={user.account}
                    disabled
                    className="bg-slate-50"
                  />
                  <p className="text-xs text-slate-500">账号不可修改</p>
                </div>

                {/* 姓名 */}
                <div className="space-y-2">
                  <Label htmlFor="name" className="text-slate-700 font-medium flex items-center gap-2">
                    <User className="w-4 h-4" />
                    姓名
                  </Label>
                  <Input
                    id="name"
                    type="text"
                    value={profileForm.name}
                    onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })}
                    disabled={loading}
                    required
                  />
                </div>

                {/* 邮箱 */}
                <div className="space-y-2">
                  <Label htmlFor="email" className="text-slate-700 font-medium flex items-center gap-2">
                    <Mail className="w-4 h-4" />
                    邮箱
                  </Label>
                  <Input
                    id="email"
                    type="email"
                    value={profileForm.email}
                    onChange={(e) => setProfileForm({ ...profileForm, email: e.target.value })}
                    disabled={loading}
                    required={user.user_type !== 'student'}
                    placeholder={user.user_type === 'student' ? '可选，留空则不展示邮箱' : '请输入邮箱'}
                  />
                  {user.user_type === 'student' && (
                    <p className="text-xs text-slate-500">学生邮箱为可选项，留空时个人资料中不会显示邮箱。</p>
                  )}
                </div>

                {/* 手机号 */}
                <div className="space-y-2">
                  <Label htmlFor="phone" className="text-slate-700 font-medium flex items-center gap-2">
                    <Phone className="w-4 h-4" />
                    手机号
                  </Label>
                  <Input
                    id="phone"
                    type="tel"
                    value={profileForm.phone}
                    onChange={(e) => setProfileForm({ ...profileForm, phone: e.target.value })}
                    disabled={loading}
                    placeholder="请输入手机号"
                  />
                </div>

                {/* 学号（仅学生） */}
                {user.user_type === 'student' && (
                  <div className="space-y-2">
                    <Label htmlFor="student_id" className="text-slate-700 font-medium flex items-center gap-2">
                      <GraduationCap className="w-4 h-4" />
                      学号
                    </Label>
                    <Input
                      id="student_id"
                      type="text"
                      value={profileForm.student_id}
                      onChange={(e) => setProfileForm({ ...profileForm, student_id: e.target.value })}
                      disabled={loading}
                      placeholder="请输入学号"
                    />
                  </div>
                )}

                {/* 班级选择（学生和教师） */}
                {user.user_type === 'student' && (
                  <div className="space-y-2">
                    <Label htmlFor="class_select" className="text-slate-700 font-medium flex items-center gap-2">
                      <Users className="w-4 h-4" />
                      所属班级
                    </Label>
                    {classes.length > 0 ? (
                      <Select
                        value={profileForm.class_id || undefined}
                        onValueChange={(value) => setProfileForm({ ...profileForm, class_id: value })}
                        disabled={loading || hasLockedClass}
                      >
                        <SelectTrigger className="border-slate-300 focus:border-blue-500 focus:ring-blue-500">
                          <SelectValue placeholder="请选择班级" />
                        </SelectTrigger>
                        <SelectContent>
                          {classes.map((cls) => (
                            <SelectItem key={cls.id} value={cls.id}>
                              {cls.name} - 教师：{cls.teacher_name} | 学生数：{cls.student_count}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    ) : (
                      <div className="text-sm text-slate-500 py-2 px-3 bg-slate-50 rounded-md">
                        暂无可选班级
                      </div>
                    )}
                    <p className="text-xs text-slate-500">
                      {hasLockedClass
                        ? '班级已锁定，学生首次选择后不可自行修改。'
                        : '班级只能选择一次，请确认后再保存。'}
                    </p>
                  </div>
                )}

                <Button
                  type="submit"
                  className="w-full bg-blue-600 hover:bg-blue-700"
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      保存中...
                    </>
                  ) : (
                    <>
                      <Save className="w-4 h-4 mr-2" />
                      保存修改
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 修改密码内容 */}
        <TabsContent value="password">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Key className="w-5 h-5" />
                安全设置
              </CardTitle>
              <CardDescription>定期修改密码以保护账户安全</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handlePasswordChange} className="space-y-4">
                {/* 旧密码 */}
                <div className="space-y-2">
                  <Label htmlFor="old_password" className="text-slate-700 font-medium">
                    当前密码
                  </Label>
                  <Input
                    id="old_password"
                    type="password"
                    value={passwordForm.old_password}
                    onChange={(e) => setPasswordForm({ ...passwordForm, old_password: e.target.value })}
                    disabled={loading}
                    required
                    placeholder="请输入当前密码"
                  />
                </div>

                <Separator />

                {/* 新密码 */}
                <div className="space-y-2">
                  <Label htmlFor="new_password" className="text-slate-700 font-medium">
                    新密码
                  </Label>
                  <Input
                    id="new_password"
                    type="password"
                    value={passwordForm.new_password}
                    onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
                    disabled={loading}
                    required
                    placeholder="请输入新密码（至少6位）"
                    minLength={6}
                  />
                </div>

                {/* 确认新密码 */}
                <div className="space-y-2">
                  <Label htmlFor="confirm_password" className="text-slate-700 font-medium">
                    确认新密码
                  </Label>
                  <Input
                    id="confirm_password"
                    type="password"
                    value={passwordForm.confirm_password}
                    onChange={(e) => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })}
                    disabled={loading}
                    required
                    placeholder="请再次输入新密码"
                    minLength={6}
                  />
                </div>

                <Button
                  type="submit"
                  className="w-full bg-blue-600 hover:bg-blue-700"
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      修改中...
                    </>
                  ) : (
                    <>
                      <Key className="w-4 h-4 mr-2" />
                      修改密码
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 个人能力评估内容 */}
        {user.user_type === 'student' && (
          <TabsContent value="ability" className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="text-sm text-slate-600">
                {assessmentResult?.is_default ? '当前为系统默认值，请根据自身情况调整并保存' : '当前为您的个人设置'}
              </div>
              <Badge variant="outline">
                {assessmentResult?.is_default ? '系统默认' : '个人设置'}
              </Badge>
            </div>
            {/* 能力自评卡片 */}
            <SkillsRadar
              skills={skills}
              onSkillChange={handleSkillChange}
              readonly={false}
            />

            <div className="flex justify-end">
              <Button
                onClick={handleSaveAssessment}
                disabled={isSavingAssessment}
                className="bg-blue-600 hover:bg-blue-700 text-white"
              >
                {isSavingAssessment ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
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

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-blue-600" />
                  能力成长轨迹
                  <Badge variant="outline" className="ml-auto">
                    过去7场
                  </Badge>
                </CardTitle>
                <CardDescription>分析您在各个维度的辩论能力变化</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="h-64">
                    {renderGrowthChart()}
                  </div>

                  <div className="grid grid-cols-2 gap-4 text-sm mt-6">
                    <div className="bg-blue-50 rounded-lg p-3">
                      <div className="font-medium text-blue-900">综合能力评分</div>
                      <div className="text-xl font-bold text-blue-600">{analytics?.average_score || 0}</div>
                    </div>
                    <div className="bg-emerald-50 rounded-lg p-3">
                      <div className="font-medium text-emerald-900">参与场次</div>
                      <div className="text-xl font-bold text-emerald-600">{analytics?.completed_debates || 0}</div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
};

export default UserProfile;
