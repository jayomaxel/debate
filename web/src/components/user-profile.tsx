import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Key,
  Loader2,
  Lock,
  Save,
  ShieldCheck,
  User,
} from 'lucide-react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useToast } from '@/hooks/use-toast';
import { useStudentAssessment } from '@/hooks/use-student-assessment';
import AuthService from '@/services/auth.service';
import StudentService from '@/services/student.service';
import { formatErrorMessage } from '@/lib/error-handler';
import type { UserInfo } from '@/lib/token-manager';
import SkillsAssessmentEditor from './skills-assessment-editor';
import SkillsRadar, {
  createEditableDefaultSkills,
  mergeAssessmentIntoSkills,
} from './skills-radar';
import { hasCompleteAbilityValues } from '@/lib/ability-profile';
import { formatDebateRole } from '@/lib/student-display';

interface UserProfileProps {
  user: UserInfo;
  onUpdate?: (user: Partial<UserInfo>) => void;
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
    description: '更新昵称、邮箱、手机号和班级信息。',
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

const UserProfile: React.FC<UserProfileProps> = ({
  user,
  onUpdate,
  initialTab = 'info',
}) => {
  const { toast } = useToast();
  const isStudent = user.user_type === 'student';
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
  const [classes, setClasses] = useState<ClassOption[]>([]);
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

  const availableTabs = useMemo(
    () =>
      tabItems.filter((item) => {
        if (!isStudent && item.key === 'ability') {
          return false;
        }

        if (isStudent && isAssessmentLocked && item.key === 'ability') {
          return false;
        }

        return true;
      }),
    [isAssessmentLocked, isStudent]
  );

  useEffect(() => {
    setActiveTab(normalizeTab(initialTab, isStudent, isAssessmentLocked));
  }, [initialTab, isAssessmentLocked, isStudent]);

  useEffect(() => {
    if (!isStudent) {
      return;
    }

    setSkills(mergeAssessmentIntoSkills(createEditableDefaultSkills(), assessment));
  }, [assessment, isStudent]);

  useEffect(() => {
    void loadProfile();

    if (isStudent) {
      void loadClasses();
    }
  }, [isStudent]);

  const loadProfile = async () => {
    try {
      const profile = await AuthService.getProfile();
      setProfileForm({
        name: profile.name || '',
        email: profile.email || '',
        phone: profile.phone || '',
        student_id: profile.student_id || '',
        class_id: profile.class_id || '',
      });
    } catch (error) {
      console.error('Failed to load profile:', error);
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
      await AuthService.updateProfile({
        name: profileForm.name,
        email: profileForm.email || undefined,
        phone: profileForm.phone || undefined,
        student_id: isStudent ? profileForm.student_id || undefined : undefined,
        class_id: isStudent ? profileForm.class_id || undefined : undefined,
      });

      const refreshedProfile = await AuthService.getProfile();
      setProfileForm({
        name: refreshedProfile.name || '',
        email: refreshedProfile.email || '',
        phone: refreshedProfile.phone || '',
        student_id: refreshedProfile.student_id || '',
        class_id: refreshedProfile.class_id || '',
      });

      toast({
        variant: 'success',
        title: '保存成功',
        description: '个人资料已更新。',
      });

      onUpdate?.(refreshedProfile);
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

  const renderInfoPanel = () => (
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
              value={user.account}
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
            <Label htmlFor="email">邮箱</Label>
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
            <Label htmlFor="phone">手机号</Label>
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
                <Label>所属班级</Label>
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
                    disabled={loading}
                  >
                    <SelectTrigger className="h-12 rounded-[12px] border-black/10 bg-white/80">
                      <SelectValue placeholder="请选择班级" />
                    </SelectTrigger>
                    <SelectContent>
                      {classes.map((classOption) => (
                        <SelectItem key={classOption.id} value={classOption.id}>
                          {classOption.name} - {classOption.teacher_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <div className="student-card-muted px-4 py-3 text-sm text-slate-500">
                    暂无可选班级
                  </div>
                )}
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
              <User className="h-5 w-5" />
            ) : (
              <ShieldCheck className="h-5 w-5" />
            )}
          </div>
          <div>
            <div className="font-semibold text-slate-900">{user.name}</div>
            <div className="text-sm text-slate-500">
              {isStudent ? '学生设置中心' : '教师设置中心'}
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
              <div className="font-medium text-slate-900">{item.label}</div>
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
