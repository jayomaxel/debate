import React, { useEffect, useRef, useState } from 'react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/hooks/use-toast';
import { formatErrorMessage } from '@/lib/error-handler';
import { shouldRenderAbilityPortrait } from '@/lib/ability-profile';
import type { UserInfo } from '@/lib/token-manager';
import { useAuth } from '@/store/auth.context';
import AuthService, { type DefaultAvatarOption } from '@/services/auth.service';
import StudentService, {
  type AssessmentResult,
  type GrowthTrendItem,
  type StudentAnalytics,
} from '@/services/student.service';
import SkillsRadar, {
  DEFAULT_SKILLS_EMPTY_STATE_MESSAGE,
  createEmptySkills,
  mergeAssessmentIntoSkills,
} from './skills-radar';
import {
  Activity,
  Camera,
  GraduationCap,
  Key,
  Loader2,
  Mail,
  Phone,
  Save,
  ShieldCheck,
  Trash2,
  TrendingUp,
  Upload,
  User,
  Users,
} from 'lucide-react';

interface UserProfileProps {
  user: UserInfo;
  onUpdate?: (user?: UserInfo) => void;
  initialTab?: 'info' | 'password' | 'ability';
}

interface ClassOption {
  id: string;
  name: string;
  code: string;
  teacher_name: string;
  student_count: number;
}

const buildFallbackText = (name?: string) => (name || '?').trim().slice(0, 2).toUpperCase();

const UserProfile: React.FC<UserProfileProps> = ({
  user,
  onUpdate,
  initialTab = 'info',
}) => {
  const { toast } = useToast();
  const { updateUser } = useAuth();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [activeTab, setActiveTab] = useState<'info' | 'password' | 'ability'>(initialTab);
  const [loading, setLoading] = useState(false);
  const [classesLoading, setClassesLoading] = useState(false);
  const [abilityLoading, setAbilityLoading] = useState(false);
  const [avatarLoading, setAvatarLoading] = useState(false);
  const [defaultAvatarsLoading, setDefaultAvatarsLoading] = useState(false);
  const [classes, setClasses] = useState<ClassOption[]>([]);
  const [defaultAvatars, setDefaultAvatars] = useState<DefaultAvatarOption[]>([]);
  const [currentUser, setCurrentUser] = useState<UserInfo>(user);
  const [profileForm, setProfileForm] = useState({
    name: user.name || '',
    email: user.email || '',
    phone: user.phone || '',
    student_id: user.student_id || '',
    class_id: user.class_id || '',
  });
  const [passwordForm, setPasswordForm] = useState({
    old_password: '',
    new_password: '',
    confirm_password: '',
  });
  const [lockedClassId, setLockedClassId] = useState(user.class_id || '');
  const [analytics, setAnalytics] = useState<StudentAnalytics | null>(null);
  const [growthTrend, setGrowthTrend] = useState<GrowthTrendItem[]>([]);
  const [assessmentResult, setAssessmentResult] = useState<AssessmentResult | null>(null);
  const [skills, setSkills] = useState(createEmptySkills);

  const isStudent = currentUser.user_type === 'student';
  const isAdmin = currentUser.user_type === 'administrator';
  const hasLockedClass = isStudent && Boolean(lockedClassId);
  const completedDebates = analytics?.completed_debates ?? 0;
  const averageScore = analytics?.average_score ?? 0;
  const abilityProfileVisible = shouldRenderAbilityPortrait({
    completedDebates,
    skillValues: skills.map((skill) => skill.value),
    isDefaultAssessment: assessmentResult?.is_default,
  });

  useEffect(() => {
    setCurrentUser(user);
    setProfileForm({
      name: user.name || '',
      email: user.email || '',
      phone: user.phone || '',
      student_id: user.student_id || '',
      class_id: user.class_id || '',
    });
    setLockedClassId(user.class_id || '');
  }, [user]);

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    void loadProfile();
    void loadDefaultAvatars();

    if (isStudent) {
      void loadClasses();
      void loadAbilityData();
    }
  }, [isStudent]);

  const syncUser = (nextUser: UserInfo) => {
    setCurrentUser(nextUser);
    updateUser(nextUser);
    setProfileForm((prev) => ({
      ...prev,
      name: nextUser.name || '',
      email: nextUser.email || '',
      phone: nextUser.phone || '',
      student_id: nextUser.student_id || '',
      class_id: nextUser.class_id || '',
    }));
  };

  const loadProfile = async () => {
    try {
      const profile = await AuthService.getProfile();
      syncUser(profile);
      if (isStudent) {
        setLockedClassId(profile.class_id || '');
      }
    } catch (error) {
      console.error('Failed to load profile:', error);
    }
  };

  const loadDefaultAvatars = async () => {
    try {
      setDefaultAvatarsLoading(true);
      const avatars = await AuthService.getDefaultAvatars();
      setDefaultAvatars(avatars);
    } catch (error) {
      console.error('Failed to load default avatars:', error);
    } finally {
      setDefaultAvatarsLoading(false);
    }
  };

  const loadClasses = async () => {
    try {
      setClassesLoading(true);
      const classList = await AuthService.getPublicClasses();
      setClasses(classList);
    } catch (error) {
      console.error('Failed to load classes:', error);
    } finally {
      setClassesLoading(false);
    }
  };

  const loadAbilityData = async () => {
    try {
      setAbilityLoading(true);
      const [analyticsData, growthData, assessmentData] = await Promise.all([
        StudentService.getAnalytics(),
        StudentService.getGrowthTrend(7),
        StudentService.getAssessment(),
      ]);

      const mergedSkills = mergeAssessmentIntoSkills(createEmptySkills(), assessmentData);
      const canUseAbilityData =
        (analyticsData?.completed_debates ?? 0) > 0 && !assessmentData?.is_default;

      setAnalytics(analyticsData);
      setGrowthTrend(growthData?.debates || []);
      setAssessmentResult(assessmentData);
      setSkills(canUseAbilityData ? mergedSkills : createEmptySkills());
    } catch (error) {
      console.error('Failed to load ability data:', error);
      setAnalytics(null);
      setGrowthTrend([]);
      setAssessmentResult(null);
      setSkills(createEmptySkills());
    } finally {
      setAbilityLoading(false);
    }
  };

  const handleProfileUpdate = async (event: React.FormEvent) => {
    event.preventDefault();

    try {
      setLoading(true);
      const nextUser = await AuthService.updateProfile({
        name: profileForm.name,
        email: profileForm.email || undefined,
        phone: profileForm.phone || undefined,
        student_id: isStudent ? profileForm.student_id || undefined : undefined,
        class_id: isStudent ? profileForm.class_id || undefined : undefined,
      });

      if (isStudent && nextUser.class_id) {
        setLockedClassId(nextUser.class_id);
      }

      syncUser(nextUser);
      toast({
        variant: 'success',
        title: '保存成功',
        description: '个人信息已更新。',
      });
      onUpdate?.(nextUser);
    } catch (error) {
      toast({
        variant: 'destructive',
        title: '保存失败',
        description: formatErrorMessage(error),
      });
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordChange = async (event: React.FormEvent) => {
    event.preventDefault();

    if (passwordForm.new_password !== passwordForm.confirm_password) {
      toast({
        variant: 'destructive',
        title: '密码不一致',
        description: '两次输入的新密码不一致。',
      });
      return;
    }

    if (passwordForm.new_password.length < 6) {
      toast({
        variant: 'destructive',
        title: '密码过短',
        description: '新密码长度至少为 6 位。',
      });
      return;
    }

    try {
      setLoading(true);
      await AuthService.changePassword({
        old_password: passwordForm.old_password,
        new_password: passwordForm.new_password,
      });

      setPasswordForm({
        old_password: '',
        new_password: '',
        confirm_password: '',
      });

      toast({
        variant: 'success',
        title: '修改成功',
        description: '密码已更新。',
      });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: '修改失败',
        description: formatErrorMessage(error),
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAvatarUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    try {
      setAvatarLoading(true);
      const nextUser = await AuthService.uploadAvatar(file);
      syncUser(nextUser);
      toast({
        variant: 'success',
        title: '头像上传成功',
        description: '已切换为自定义头像。',
      });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: '头像上传失败',
        description: formatErrorMessage(error),
      });
    } finally {
      setAvatarLoading(false);
    }
  };

  const handleSelectDefaultAvatar = async (avatarDefaultKey: string) => {
    try {
      setAvatarLoading(true);
      const nextUser = await AuthService.selectDefaultAvatar(avatarDefaultKey);
      syncUser(nextUser);
      toast({
        variant: 'success',
        title: '默认头像已更新',
        description: '已应用新的默认头像。',
      });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: '头像切换失败',
        description: formatErrorMessage(error),
      });
    } finally {
      setAvatarLoading(false);
    }
  };

  const handleClearAvatar = async () => {
    try {
      setAvatarLoading(true);
      const nextUser = await AuthService.clearAvatar();
      syncUser(nextUser);
      toast({
        variant: 'success',
        title: '头像已清除',
        description: '当前将使用姓名首字母占位。',
      });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: '清除失败',
        description: formatErrorMessage(error),
      });
    } finally {
      setAvatarLoading(false);
    }
  };

  const renderAvatarSection = () => (
    <Card className="border-slate-200">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Camera className="h-5 w-5 text-blue-600" />
          头像设置
        </CardTitle>
        <CardDescription>
          学生、教师和管理员都可以上传自定义头像，或从 AI 设计的极简色块头像中直接选择。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex flex-col gap-6 rounded-2xl border border-slate-200 bg-slate-50 p-5 md:flex-row md:items-center">
          <Avatar className="h-24 w-24 border-4 border-white shadow-lg">
            <AvatarImage src={currentUser.avatar || currentUser.avatar_url || undefined} alt={currentUser.name} />
            <AvatarFallback className="bg-slate-900 text-lg font-semibold text-white">
              {buildFallbackText(currentUser.name)}
            </AvatarFallback>
          </Avatar>
          <div className="flex-1 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">
                {currentUser.avatar_mode === 'custom'
                  ? '自定义头像'
                  : currentUser.avatar_mode === 'default'
                    ? '默认头像'
                    : '未设置头像'}
              </Badge>
              {currentUser.avatar_default_key && (
                <Badge variant="secondary">{currentUser.avatar_default_key}</Badge>
              )}
            </div>
            <p className="text-sm text-slate-600">
              推荐上传 512 x 512 以内的 PNG、JPG 或 WebP 图片，系统会自动压缩后存入数据库。
            </p>
            <div className="flex flex-wrap gap-3">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="hidden"
                onChange={handleAvatarUpload}
              />
              <Button
                type="button"
                variant="outline"
                disabled={avatarLoading}
                onClick={() => fileInputRef.current?.click()}
              >
                {avatarLoading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="mr-2 h-4 w-4" />
                )}
                上传头像
              </Button>
              <Button type="button" variant="ghost" disabled={avatarLoading} onClick={handleClearAvatar}>
                <Trash2 className="mr-2 h-4 w-4" />
                清除头像
              </Button>
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">默认头像库</h3>
              <p className="text-xs text-slate-500">五款极简色块头像，可一键切换。</p>
            </div>
            {defaultAvatarsLoading && <Loader2 className="h-4 w-4 animate-spin text-slate-500" />}
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            {defaultAvatars.map((avatarOption) => {
              const active =
                currentUser.avatar_default_key === avatarOption.key &&
                currentUser.avatar_mode === 'default';
              return (
                <button
                  key={avatarOption.key}
                  type="button"
                  disabled={avatarLoading}
                  onClick={() => handleSelectDefaultAvatar(avatarOption.key)}
                  className={`rounded-2xl border p-3 text-left transition ${
                    active
                      ? 'border-blue-500 bg-blue-50 shadow-sm'
                      : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                  }`}
                >
                  <Avatar className="mb-3 h-16 w-16 border border-white shadow">
                    <AvatarImage src={avatarOption.avatar_url} alt={avatarOption.label} />
                    <AvatarFallback>{avatarOption.label.slice(0, 2)}</AvatarFallback>
                  </Avatar>
                  <div className="text-sm font-medium text-slate-900">{avatarOption.label}</div>
                  <div className="mt-2 flex gap-1">
                    {avatarOption.palette.map((color) => (
                      <span
                        key={color}
                        className="h-3 w-3 rounded-full border border-white/70 shadow-sm"
                        style={{ backgroundColor: color }}
                      />
                    ))}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );

  const renderAbilitySummary = () => {
    if (abilityLoading) {
      return (
        <div className="flex items-center justify-center py-10 text-slate-500">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          正在加载能力评估数据
        </div>
      );
    }

    return (
      <>
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm text-slate-600">
            {abilityProfileVisible
              ? '以下画像基于系统记录的真实辩论表现生成，用于展示近期成长状态。'
              : DEFAULT_SKILLS_EMPTY_STATE_MESSAGE}
          </div>
          <Badge variant="outline">
            {abilityProfileVisible ? '已生成画像' : '暂无画像'}
          </Badge>
        </div>

        <SkillsRadar
          skills={abilityProfileVisible ? skills : createEmptySkills()}
          emptyStateMessage={DEFAULT_SKILLS_EMPTY_STATE_MESSAGE}
        />

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-blue-600" />
              能力成长概览
            </CardTitle>
            <CardDescription>展示最近 7 场辩论的成长趋势与统计摘要。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="rounded-lg bg-blue-50 p-4">
                <div className="text-sm font-medium text-blue-900">综合评分</div>
                <div className="mt-2 text-2xl font-bold text-blue-600">{averageScore}</div>
              </div>
              <div className="rounded-lg bg-emerald-50 p-4">
                <div className="text-sm font-medium text-emerald-900">已完成辩论</div>
                <div className="mt-2 text-2xl font-bold text-emerald-600">{completedDebates}</div>
              </div>
            </div>

            {growthTrend.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                暂无成长趋势数据
              </div>
            ) : (
              <div className="space-y-3">
                {growthTrend.map((item) => (
                  <div key={item.debate_id} className="rounded-lg border border-slate-200 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="font-medium text-slate-900">{item.topic}</div>
                        <div className="text-sm text-slate-500">
                          {new Date(item.date).toLocaleDateString('zh-CN')}
                        </div>
                      </div>
                      <Badge variant="outline">总分 {item.score}</Badge>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-sm text-slate-600 md:grid-cols-5">
                      <div>逻辑 {item.ability_scores.logic}</div>
                      <div>表达 {item.ability_scores.expression}</div>
                      <div>反驳 {item.ability_scores.rebuttal}</div>
                      <div>协作 {item.ability_scores.teamwork}</div>
                      <div>知识 {item.ability_scores.knowledge}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </>
    );
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div className="flex items-center gap-3">
        {isStudent ? (
          <GraduationCap className="h-8 w-8 text-blue-600" />
        ) : (
          <ShieldCheck className={`h-8 w-8 ${isAdmin ? 'text-amber-600' : 'text-blue-600'}`} />
        )}
        <div>
          <h1 className="text-3xl font-bold text-slate-900">个人中心</h1>
          <p className="text-slate-600">
            {isStudent ? '学生' : isAdmin ? '管理员' : '教师'} - {currentUser.name}
          </p>
        </div>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={(value) => setActiveTab(value as 'info' | 'password' | 'ability')}
        className="w-full"
      >
        <TabsList className={`mb-8 grid w-full ${isStudent ? 'grid-cols-3' : 'grid-cols-2'}`}>
          <TabsTrigger value="info" className="flex items-center gap-2">
            <User className="h-4 w-4" />
            个人信息
          </TabsTrigger>
          <TabsTrigger value="password" className="flex items-center gap-2">
            <Key className="h-4 w-4" />
            修改密码
          </TabsTrigger>
          {isStudent && (
            <TabsTrigger value="ability" className="flex items-center gap-2">
              <Activity className="h-4 w-4" />
              能力评估
            </TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="info" className="space-y-6">
          {renderAvatarSection()}

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="h-5 w-5" />
                基本资料
              </CardTitle>
              <CardDescription>查看和编辑您的账户信息。</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleProfileUpdate} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="account">账号</Label>
                  <Input id="account" value={currentUser.account} disabled className="bg-slate-50" />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="name">姓名</Label>
                  <Input
                    id="name"
                    value={profileForm.name}
                    onChange={(event) =>
                      setProfileForm((prev) => ({ ...prev, name: event.target.value }))
                    }
                    disabled={loading}
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="email" className="flex items-center gap-2">
                    <Mail className="h-4 w-4" />
                    邮箱
                  </Label>
                  <Input
                    id="email"
                    type="email"
                    value={profileForm.email}
                    onChange={(event) =>
                      setProfileForm((prev) => ({ ...prev, email: event.target.value }))
                    }
                    disabled={loading}
                    placeholder={isStudent ? '学生邮箱可选填写' : '请输入邮箱'}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="phone" className="flex items-center gap-2">
                    <Phone className="h-4 w-4" />
                    手机号
                  </Label>
                  <Input
                    id="phone"
                    value={profileForm.phone}
                    onChange={(event) =>
                      setProfileForm((prev) => ({ ...prev, phone: event.target.value }))
                    }
                    disabled={loading}
                    placeholder="请输入手机号"
                  />
                </div>

                {isStudent && (
                  <>
                    <div className="space-y-2">
                      <Label htmlFor="student_id">学号</Label>
                      <Input
                        id="student_id"
                        value={profileForm.student_id}
                        onChange={(event) =>
                          setProfileForm((prev) => ({ ...prev, student_id: event.target.value }))
                        }
                        disabled={loading}
                        placeholder="请输入学号"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label className="flex items-center gap-2">
                        <Users className="h-4 w-4" />
                        所属班级
                      </Label>
                      {classesLoading ? (
                        <div className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-500">
                          正在加载班级列表
                        </div>
                      ) : classes.length > 0 ? (
                        <Select
                          value={profileForm.class_id || undefined}
                          onValueChange={(value) =>
                            setProfileForm((prev) => ({ ...prev, class_id: value }))
                          }
                          disabled={loading || hasLockedClass}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="请选择班级" />
                          </SelectTrigger>
                          <SelectContent>
                            {classes.map((classOption) => (
                              <SelectItem key={classOption.id} value={classOption.id}>
                                {classOption.name} - {classOption.teacher_name} | 学生数：
                                {classOption.student_count}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      ) : (
                        <div className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-500">
                          暂无可选班级
                        </div>
                      )}
                      <p className="text-xs text-slate-500">
                        {hasLockedClass
                          ? '班级已锁定，首次选择后不可自行修改。'
                          : '班级仅能选择一次，请确认后再保存。'}
                      </p>
                    </div>
                  </>
                )}

                <Button type="submit" className="w-full bg-blue-600 hover:bg-blue-700" disabled={loading}>
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      保存中
                    </>
                  ) : (
                    <>
                      <Save className="mr-2 h-4 w-4" />
                      保存修改
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="password">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Key className="h-5 w-5" />
                安全设置
              </CardTitle>
              <CardDescription>定期修改密码以保护账户安全。</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handlePasswordChange} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="old_password">当前密码</Label>
                  <Input
                    id="old_password"
                    type="password"
                    value={passwordForm.old_password}
                    onChange={(event) =>
                      setPasswordForm((prev) => ({ ...prev, old_password: event.target.value }))
                    }
                    disabled={loading}
                    required
                  />
                </div>

                <Separator />

                <div className="space-y-2">
                  <Label htmlFor="new_password">新密码</Label>
                  <Input
                    id="new_password"
                    type="password"
                    value={passwordForm.new_password}
                    onChange={(event) =>
                      setPasswordForm((prev) => ({ ...prev, new_password: event.target.value }))
                    }
                    disabled={loading}
                    required
                    minLength={6}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="confirm_password">确认新密码</Label>
                  <Input
                    id="confirm_password"
                    type="password"
                    value={passwordForm.confirm_password}
                    onChange={(event) =>
                      setPasswordForm((prev) => ({ ...prev, confirm_password: event.target.value }))
                    }
                    disabled={loading}
                    required
                    minLength={6}
                  />
                </div>

                <Button type="submit" className="w-full bg-blue-600 hover:bg-blue-700" disabled={loading}>
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      修改中
                    </>
                  ) : (
                    <>
                      <Key className="mr-2 h-4 w-4" />
                      修改密码
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        {isStudent && (
          <TabsContent value="ability" className="space-y-6">
            {renderAbilitySummary()}
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
};

export default UserProfile;
