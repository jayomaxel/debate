import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlertCircle,
  Camera,
  GraduationCap,
  Key,
  Loader2,
  Lock,
  Mail,
  Phone,
  Save,
  ShieldCheck,
  Trash2,
  Upload,
  User,
  Users,
} from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
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
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useToast } from '@/hooks/use-toast';
import { useStudentAssessment } from '@/hooks/use-student-assessment';
import { formatErrorMessage } from '@/lib/error-handler';
import type { UserInfo } from '@/lib/token-manager';
import { useAuth } from '@/store/auth.context';
import AuthService, { type DefaultAvatarOption } from '@/services/auth.service';
import StudentService from '@/services/student.service';
import SkillsAssessmentEditor from './skills-assessment-editor';
import SkillsRadar, {
  createEditableDefaultSkills,
  mergeAssessmentIntoSkills,
} from './skills-radar';
import { hasCompleteAbilityValues } from '@/lib/ability-profile';
import { formatDebateRole } from '@/lib/student-display';

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

type SettingsTab = 'info' | 'password' | 'ability';

const tabItems: Array<{
  key: SettingsTab;
  label: string;
  description: string;
  tone: string;
}> = [
  {
    key: 'info',
    label: '个人资料',
    description: '更新昵称、邮箱、手机号、头像和班级信息。',
    tone: 'student-card-soft-blue',
  },
  {
    key: 'password',
    label: '账号安全',
    description: '修改登录密码，维护账户安全。',
    tone: 'student-card-soft-peach',
  },
  {
    key: 'ability',
    label: '能力评估',
    description: '完成或查看你的辩论能力评估。',
    tone: 'student-card-soft-lavender',
  },
];

const DEFAULT_READONLY_MESSAGE =
  '完成首场正式辩论后，能力评估会自动锁定，仅保留结果展示。';

const DEFAULT_EMPTY_MESSAGE = '还没有可展示的能力评估结果，请先完成评估。';

const normalizeTab = (
  tab: SettingsTab,
  isStudent: boolean,
  isAssessmentLocked: boolean
): SettingsTab => {
  if (!isStudent && tab === 'ability') {
    return 'info';
  }

  if (isStudent && isAssessmentLocked && tab === 'ability') {
    return 'info';
  }

  return tab;
};

const fieldClassName =
  'h-12 rounded-[12px] border-black/10 bg-white/80 text-slate-900 placeholder:text-slate-400 focus-visible:ring-black/10';

const buildFallbackText = (name?: string) =>
  (name || '?').trim().slice(0, 2).toUpperCase();

const UserProfile: React.FC<UserProfileProps> = ({
  user,
  onUpdate,
  initialTab = 'info',
}) => {
  const { toast } = useToast();
  const { updateUser } = useAuth();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [currentUser, setCurrentUser] = useState<UserInfo>(user);
  const isStudent = currentUser.user_type === 'student';
  const isAdmin = currentUser.user_type === 'administrator';

  const {
    assessment,
    analytics,
    needsAssessment,
    isAssessmentLocked,
    loading: assessmentLoading,
    refresh: refreshAssessmentState,
  } = useStudentAssessment(isStudent);

  const [activeTab, setActiveTab] = useState<SettingsTab>('info');
  const [loading, setLoading] = useState(false);
  const [classesLoading, setClassesLoading] = useState(false);
  const [avatarLoading, setAvatarLoading] = useState(false);
  const [defaultAvatarsLoading, setDefaultAvatarsLoading] = useState(false);
  const [classes, setClasses] = useState<ClassOption[]>([]);
  const [defaultAvatars, setDefaultAvatars] = useState<DefaultAvatarOption[]>([]);
  const [lockedClassId, setLockedClassId] = useState(user.class_id || '');
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
  const [skills, setSkills] = useState(createEditableDefaultSkills);

  const hasLockedClass = isStudent && Boolean(lockedClassId);

  const availableTabs = useMemo(
    () =>
      tabItems.filter((item) => {
        if (!isStudent && item.key === 'ability') return false;
        if (isStudent && isAssessmentLocked && item.key === 'ability') return false;
        return true;
      }),
    [isAssessmentLocked, isStudent]
  );

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
    setActiveTab(normalizeTab(initialTab, isStudent, isAssessmentLocked));
  }, [initialTab, isAssessmentLocked, isStudent]);

  useEffect(() => {
    if (!isStudent) return;
    setSkills(mergeAssessmentIntoSkills(createEditableDefaultSkills(), assessment));
  }, [assessment, isStudent]);

  useEffect(() => {
    void loadProfile();
    void loadDefaultAvatars();

    if (isStudent) {
      void loadClasses();
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
      if (profile.class_id) {
        setLockedClassId(profile.class_id);
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
        description: '个人资料已更新。',
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
        title: '两次密码不一致',
        description: '请重新确认新密码。',
      });
      return;
    }

    if (passwordForm.new_password.length < 6) {
      toast({
        variant: 'destructive',
        title: '新密码过短',
        description: '密码长度至少需要 6 位。',
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
        description: '账户密码已更新。',
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
      onUpdate?.(nextUser);
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
      onUpdate?.(nextUser);
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
      onUpdate?.(nextUser);
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

  const handleAbilitySave = async () => {
    if (!isStudent || isAssessmentLocked) {
      return;
    }

    const values = skills.map((skill) => skill.value);
    if (!hasCompleteAbilityValues(values)) {
      toast({
        variant: 'destructive',
        title: '评估未完成',
        description: '请完成 5 个维度的评分后再保存。',
      });
      return;
    }

    try {
      setLoading(true);
      await StudentService.submitAssessment({
        expression_willingness: Number(
          skills.find((item) => item.key === 'expression_willingness')?.value || 0
        ),
        logical_thinking: Number(
          skills.find((item) => item.key === 'logical_thinking')?.value || 0
        ),
        stablecoin_knowledge: Number(
          skills.find((item) => item.key === 'stablecoin_knowledge')?.value || 0
        ),
        financial_knowledge: Number(
          skills.find((item) => item.key === 'financial_knowledge')?.value || 0
        ),
        critical_thinking: Number(
          skills.find((item) => item.key === 'critical_thinking')?.value || 0
        ),
        personality_type: 'balanced',
      });

      await refreshAssessmentState();

      toast({
        variant: 'success',
        title: '评估已保存',
        description: '你现在可以返回首页加入本场辩论。',
      });
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

  const renderAvatarSection = () => (
    <Card className="student-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-slate-900">
          <Camera className="h-5 w-5" />
          头像设置
        </CardTitle>
        <CardDescription className="leading-7">
          上传自定义头像，或从默认头像库中选择一款。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex flex-col gap-6 rounded-[16px] border border-black/10 bg-white/70 p-5 md:flex-row md:items-center">
          <Avatar className="h-24 w-24 border-4 border-white shadow-lg">
            <AvatarImage
              src={currentUser.avatar || currentUser.avatar_url || undefined}
              alt={currentUser.name}
            />
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
              {currentUser.avatar_default_key ? (
                <Badge variant="secondary">{currentUser.avatar_default_key}</Badge>
              ) : null}
            </div>

            <p className="text-sm leading-7 text-slate-600">
              推荐上传 PNG、JPG 或 WebP 图片，系统会自动处理后用于个人中心和比赛页面展示。
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
              <Button
                type="button"
                variant="ghost"
                disabled={avatarLoading}
                onClick={handleClearAvatar}
              >
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
              <p className="text-xs text-slate-500">选择一款系统内置头像。</p>
            </div>
            {defaultAvatarsLoading ? (
              <Loader2 className="h-4 w-4 animate-spin text-slate-500" />
            ) : null}
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
                  className={`rounded-[14px] border p-3 text-left transition ${
                    active
                      ? 'border-blue-500 bg-blue-50 shadow-sm'
                      : 'border-black/10 bg-white hover:border-slate-300 hover:bg-slate-50'
                  }`}
                >
                  <Avatar className="mb-3 h-16 w-16 border border-white shadow">
                    <AvatarImage src={avatarOption.avatar_url} alt={avatarOption.label} />
                    <AvatarFallback>{avatarOption.label.slice(0, 2)}</AvatarFallback>
                  </Avatar>
                  <div className="text-sm font-medium text-slate-900">
                    {avatarOption.label}
                  </div>
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

  const renderInfoPanel = () => (
    <div className="space-y-6">
      {renderAvatarSection()}

      <Card className="student-card">
        <CardHeader>
          <CardTitle className="text-slate-900">个人资料</CardTitle>
          <CardDescription className="leading-7">
            更新基础信息，保持账户资料完整。
            {isStudent && needsAssessment
              ? ' 你还未完成能力评估，比赛区入口仍会保持锁定。'
              : ''}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleProfileUpdate} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="account">账号</Label>
              <Input
                id="account"
                value={currentUser.account}
                disabled
                className={`${fieldClassName} bg-slate-50`}
              />
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
                className={fieldClassName}
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
                className={fieldClassName}
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
                className={fieldClassName}
              />
            </div>

            {isStudent ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="student_id">学号</Label>
                  <Input
                    id="student_id"
                    value={profileForm.student_id}
                    onChange={(event) =>
                      setProfileForm((prev) => ({
                        ...prev,
                        student_id: event.target.value,
                      }))
                    }
                    disabled={loading}
                    className={fieldClassName}
                  />
                </div>

                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Users className="h-4 w-4" />
                    所属班级
                  </Label>
                  {classesLoading ? (
                    <div className="student-card-muted px-4 py-3 text-sm text-slate-500">
                      正在加载班级列表...
                    </div>
                  ) : classes.length > 0 ? (
                    <Select
                      value={profileForm.class_id || undefined}
                      onValueChange={(value) =>
                        setProfileForm((prev) => ({ ...prev, class_id: value }))
                      }
                      disabled={loading || hasLockedClass}
                    >
                      <SelectTrigger className="h-12 rounded-[12px] border-black/10 bg-white/80">
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
                    <div className="student-card-muted px-4 py-3 text-sm text-slate-500">
                      暂无可选班级
                    </div>
                  )}
                  <p className="text-xs leading-6 text-slate-500">
                    {hasLockedClass
                      ? '班级已锁定，首次选择后不可自行修改。'
                      : '班级仅能选择一次，请确认后再保存。'}
                  </p>
                </div>
              </>
            ) : null}

            <Button
              type="submit"
              className="student-dark-button h-auto w-full justify-center"
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  保存中...
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
    </div>
  );

  const renderPasswordPanel = () => (
    <Card className="student-card">
      <CardHeader>
        <CardTitle className="text-slate-900">账号安全</CardTitle>
        <CardDescription className="leading-7">
          定期更换密码，降低账户风险。
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handlePasswordChange} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="old_password">当前密码</Label>
            <Input
              id="old_password"
              type="password"
              value={passwordForm.old_password}
              onChange={(event) =>
                setPasswordForm((prev) => ({
                  ...prev,
                  old_password: event.target.value,
                }))
              }
              disabled={loading}
              required
              className={fieldClassName}
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
                setPasswordForm((prev) => ({
                  ...prev,
                  new_password: event.target.value,
                }))
              }
              disabled={loading}
              required
              minLength={6}
              className={fieldClassName}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirm_password">确认新密码</Label>
            <Input
              id="confirm_password"
              type="password"
              value={passwordForm.confirm_password}
              onChange={(event) =>
                setPasswordForm((prev) => ({
                  ...prev,
                  confirm_password: event.target.value,
                }))
              }
              disabled={loading}
              required
              minLength={6}
              className={fieldClassName}
            />
          </div>

          <Button
            type="submit"
            className="student-dark-button h-auto w-full justify-center"
            disabled={loading}
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                提交中...
              </>
            ) : (
              <>
                <Key className="mr-2 h-4 w-4" />
                更新密码
              </>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );

  const renderAbilityPanel = (forceReadOnly = false) => {
    if (!isStudent) {
      return null;
    }

    if (assessmentLoading) {
      return (
        <Card className="student-card">
          <CardContent className="flex items-center justify-center py-16 text-slate-500">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            正在加载能力评估...
          </CardContent>
        </Card>
      );
    }

    if (isAssessmentLocked || forceReadOnly) {
      return (
        <div className="space-y-6">
          <Alert className="rounded-[14px] border-[#dbc5ad] bg-[#f8efe3] text-slate-900">
            <Lock className="h-4 w-4" />
            <AlertDescription>{DEFAULT_READONLY_MESSAGE}</AlertDescription>
          </Alert>
          <SkillsRadar
            studentMode
            skills={mergeAssessmentIntoSkills(createEditableDefaultSkills(), assessment)}
            emptyStateMessage={DEFAULT_EMPTY_MESSAGE}
          />
        </div>
      );
    }

    return (
      <div className="space-y-6">
        <Alert className="rounded-[14px] border-[#d9cdbf] bg-[#f4ede5] text-slate-900">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {needsAssessment
              ? '完成能力评估后，首页的“加入本场辩论”入口才会解锁。'
              : '你已经保存过能力评估，可以继续调整，直到完成首场正式辩论为止。'}
          </AlertDescription>
        </Alert>

        <SkillsAssessmentEditor
          studentMode
          skills={skills}
          onSkillChange={(skillKey, value) =>
            setSkills((prev) =>
              prev.map((skill) =>
                skill.key === skillKey ? { ...skill, value } : skill
              )
            )
          }
        />

        {assessment?.recommended_role ? (
          <Card className="student-card-soft-blue">
            <CardContent className="p-5">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-sm font-medium text-slate-600">
                    当前推荐角色
                  </div>
                  <div className="mt-1 text-lg font-semibold text-slate-950">
                    {formatDebateRole(assessment.recommended_role)}
                  </div>
                  <div className="mt-2 text-sm text-slate-600">
                    {assessment.role_description}
                  </div>
                </div>
                <Badge className="student-pill">已保存</Badge>
              </div>
            </CardContent>
          </Card>
        ) : null}

        <Button
          onClick={handleAbilitySave}
          className="student-dark-button h-auto w-full justify-center"
          disabled={loading}
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              保存中...
            </>
          ) : (
            <>
              <Save className="mr-2 h-4 w-4" />
              保存能力评估
            </>
          )}
        </Button>

        {typeof analytics?.completed_debates === 'number' ? (
          <div className="student-card-muted p-4 text-sm leading-7 text-slate-600">
            已完成正式辩论：{analytics.completed_debates} 场。完成首场后，这里的评估入口会自动锁定。
          </div>
        ) : null}
      </div>
    );
  };

  const renderMainPanel = () => {
    switch (activeTab) {
      case 'info':
        return isStudent && isAssessmentLocked ? (
          <div className="space-y-6">
            {renderInfoPanel()}
            {renderAbilityPanel(true)}
          </div>
        ) : (
          renderInfoPanel()
        );
      case 'password':
        return renderPasswordPanel();
      case 'ability':
        return renderAbilityPanel();
      default:
        if (isStudent && isAssessmentLocked) {
          return renderAbilityPanel(true);
        }

        return renderInfoPanel();
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[300px,1fr]">
      <aside className="student-card h-fit px-4 py-4">
        <div className="mb-4 flex items-center gap-3 px-2">
          <div className="student-icon-bubble h-12 w-12 bg-[#151515] text-white">
            {isStudent ? (
              <GraduationCap className="h-5 w-5" />
            ) : isAdmin ? (
              <ShieldCheck className="h-5 w-5 text-amber-200" />
            ) : (
              <ShieldCheck className="h-5 w-5" />
            )}
          </div>
          <div>
            <div className="font-semibold text-slate-900">{currentUser.name}</div>
            <div className="text-sm text-slate-500">
              {isStudent ? '学生设置中心' : isAdmin ? '管理员设置中心' : '教师设置中心'}
            </div>
            {isStudent && isAssessmentLocked ? (
              <div className="mt-1 text-xs text-amber-700">
                能力评估已锁定，右侧展示只读结果。
              </div>
            ) : null}
          </div>
        </div>

        <nav className="space-y-2">
          {availableTabs.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setActiveTab(item.key)}
              className={`w-full p-3.5 text-left transition-colors duration-150 ${
                activeTab === item.key ? item.tone : 'student-card-muted'
              }`}
            >
              <div className="font-medium text-slate-900">
                {item.key === 'ability' ? (
                  <Activity className="mr-2 inline h-4 w-4" />
                ) : item.key === 'password' ? (
                  <Key className="mr-2 inline h-4 w-4" />
                ) : (
                  <User className="mr-2 inline h-4 w-4" />
                )}
                {item.label}
              </div>
              <div className="mt-1 text-xs leading-6 text-slate-500">
                {item.description}
              </div>
            </button>
          ))}
        </nav>
      </aside>

      <section className="space-y-6">{renderMainPanel()}</section>
    </div>
  );
};

export default UserProfile;
