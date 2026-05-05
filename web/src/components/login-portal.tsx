import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  User,
  GraduationCap,
  Mail,
  Key,
  Users,
  ShieldCheck,
  BookOpen,
  Loader2
} from 'lucide-react';
import { useAuth } from '@/store/auth.context';
import { useAppRouter } from '@/lib/router';
import AuthService from '@/services/auth.service';
import { formatErrorMessage } from '@/lib/error-handler';
import { markAssessmentOnboardingPendingForAccount } from '@/lib/student-assessment-onboarding';
import brandLogo from '../pic/c99ec0bb69f6f215f2fe76bc7536d56a.jpg';
import loginHeroImage from '../pic/23c8a94f8f1e972166535d35cf5fd020.jpg';

interface LoginFormData {
  name: string;
  email: string;
  account: string;
  classCode?: string;
  classId?: string;  // 新增：班级ID
  teacherId?: string;
  password?: string;
  confirmPassword?: string;
}

type UserRole = 'student' | 'teacher' | 'administrator';

const DEFAULT_REGISTER_ROLE: UserRole = 'student';

interface LoginPortalProps {
  onLogin: (role: UserRole) => void | Promise<void>;
}

interface ClassOption {
  id: string;
  name: string;
  code: string;
  teacher_name: string;
  student_count: number;
}

const authInputClass =
  'h-11 rounded-[12px] border-black/10 bg-white/88 text-slate-900 placeholder:text-slate-400 focus-visible:ring-black/10 focus-visible:ring-offset-0';

const authSelectTriggerClass =
  'h-11 rounded-[12px] border-black/10 bg-white/88 focus-visible:ring-black/10 focus-visible:ring-offset-0';

const authTabTriggerClass =
  'flex items-center gap-2 rounded-[10px] data-[state=active]:bg-[#171717] data-[state=active]:text-white';

const authSubmitButtonClass =
  'student-dark-button h-auto w-full justify-center py-3';

const LoginPortal: React.FC<LoginPortalProps> = ({ onLogin }) => {
  const { login } = useAuth();
  const { navigate } = useAppRouter();
  const { toast } = useToast();
  const [activeRole, setActiveRole] = useState<UserRole>('student');
  const [isLogin, setIsLogin] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(false);
  const [loadingClasses, setLoadingClasses] = useState<boolean>(false);
  const [classes, setClasses] = useState<ClassOption[]>([]);
  const [formData, setFormData] = useState<LoginFormData>({
    name: '',
    email: '',
    account: '',
    classCode: '',
    classId: '',
    teacherId: '',
    password: '',
    confirmPassword: '',
  });

  // 加载班级列表
  useEffect(() => {
    if (!isLogin && activeRole === 'student') {
      loadClasses();
      return;
    }

    setClasses([]);
    setLoadingClasses(false);
  }, [isLogin, activeRole]);

  useEffect(() => {
    if (!isLogin && activeRole === 'administrator') {
      setActiveRole(DEFAULT_REGISTER_ROLE);
    }
  }, [isLogin, activeRole]);

  const loadClasses = async () => {
    try {
      setLoadingClasses(true);
      const classList = await AuthService.getPublicClasses();
      setClasses(classList);
    } catch (err) {
      console.error('Failed to load classes:', err);
      // 不显示错误，允许用户继续注册（班级为可选）
    } finally {
      setLoadingClasses(false);
    }
  };

  const handleInputChange = (field: keyof LoginFormData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleModeChange = (nextIsLogin: boolean) => {
    setIsLogin(nextIsLogin);
    setFormData(prev => ({ ...prev, confirmPassword: '' }));

    if (!nextIsLogin && activeRole === 'administrator') {
      setActiveRole(DEFAULT_REGISTER_ROLE);
    }
  };

  const handleRegisterSuccess = (description: string) => {
    toast({
      variant: 'success',
      title: '注册成功',
      description,
    });
    setIsLogin(true);
    setFormData(prev => ({
      ...prev,
      password: '',
      confirmPassword: '',
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      setLoading(true);

      if (isLogin) {
        // 登录逻辑
        let account = '';
        if (activeRole === 'student') {
          account = formData.account;
        } else if (activeRole === 'teacher') {
          account = formData.teacherId || '';
        } else if (activeRole === 'administrator') {
          account = formData.account;
        }

        const password = formData.password || '';

        if (!account || !password) {
          toast({
            variant: 'destructive',
            title: '登录失败',
            description: '请填写账号和密码',
          });
          return;
        }

        await login({
          account,
          password,
          user_type: activeRole,
        });

        // 登录成功，触发回调
        await onLogin(activeRole);
      } else {
        // 管理员不支持注册
        if (activeRole === 'administrator') {
          toast({
            variant: 'destructive',
            title: '注册失败',
            description: '管理员账号不支持注册',
          });
          return;
        }

        // 注册逻辑
        const password = formData.password || '';
        const confirmPassword = formData.confirmPassword || '';

        if (!password || !confirmPassword) {
          toast({
            variant: 'destructive',
            title: '注册失败',
            description: '请填写密码并确认密码',
          });
          return;
        }

        if (password !== confirmPassword) {
          toast({
            variant: 'destructive',
            title: '注册失败',
            description: '两次输入的密码不一致',
          });
          return;
        }

        if (activeRole === 'student') {
          if (!formData.account || !formData.name) {
            toast({
              variant: 'destructive',
              title: '注册失败',
              description: '请填写所有必填字段',
            });
            return;
          }

          await AuthService.registerStudent({
            account: formData.account,
            password,
            name: formData.name,
            class_id: formData.classId || undefined,  // 使用班级ID
            email: formData.email || undefined,
            student_id: formData.classCode || undefined,
          });

          markAssessmentOnboardingPendingForAccount(formData.account);
          handleRegisterSuccess('请使用您的账号密码登录');
        } else {
          if (!formData.email || !formData.name || !formData.teacherId) {
            toast({
              variant: 'destructive',
              title: '注册失败',
              description: '请填写所有必填字段',
            });
            return;
          }

          await AuthService.registerTeacher({
            account: formData.teacherId, // 教工号作为account
            email: formData.email,
            phone: '', // 暂时使用教工号作为phone，后续可以添加单独的phone字段
            password,
            name: formData.name,
          });

          handleRegisterSuccess('请使用您的教工号和密码登录');
        }
      }
    } catch (err: any) {
      console.error('Authentication error:', err);
      toast({
        variant: 'destructive',
        title: isLogin ? '登录失败' : '注册失败',
        description: formatErrorMessage(err),
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="student-theme">
      <div className="student-shell">
        <header className="sticky top-0 z-40">
          <div className="w-full">
            <div className="student-header-frame flex items-center justify-between gap-4 rounded-none px-5 py-3 sm:px-6">
              <button
                type="button"
                onClick={() => navigate('/')}
                className="flex items-center gap-3 text-left"
              >
                <div className="student-icon-bubble overflow-hidden bg-white p-0 shadow-[0_14px_30px_rgba(15,23,42,0.18)]">
                  <img src={brandLogo} alt="" className="h-full w-full object-cover" />
                </div>
                <div>
                  <div className="text-lg font-semibold tracking-[-0.03em] text-slate-900">
                    碳硅之辩
                  </div>
                </div>
              </button>

              <Button
                variant="outline"
                className="student-light-button h-auto"
                onClick={() => navigate('/')}
              >
                暂不登录
              </Button>
            </div>
          </div>
        </header>

        <main className="student-container flex min-h-[calc(100vh-72px)] items-center py-4 pb-8 sm:py-6 lg:pb-10">
          <Card className="student-card mx-auto grid w-full max-w-[min(1180px,calc(100vw_-_2rem))] overflow-hidden border-[#d7ccbf] p-0 shadow-[0_22px_56px_rgba(58,42,28,0.1)] xl:grid-cols-[minmax(0,1fr)_minmax(360px,440px)]">
            <div className="relative min-h-[220px] overflow-hidden bg-slate-100 sm:min-h-[280px] xl:min-h-[min(720px,calc(100vh_-_8rem))]">
              <img
                src={loginHeroImage}
                alt=""
                className="absolute inset-0 h-full w-full object-cover"
              />
            </div>

            <div className="flex min-h-0 items-center xl:max-h-[calc(100vh-8rem)]">
              <div className="max-h-full w-full overflow-y-auto px-5 py-6 sm:px-8 xl:px-9">
                <CardHeader className="px-0 pb-4 text-left">
                  <CardTitle className="mb-2 text-[1.65rem] font-semibold text-slate-900">
                    {isLogin ? '欢迎登录' : '欢迎注册'}
                  </CardTitle>
                  <CardDescription className="text-slate-600">
                    {isLogin ? '选择你的身份后登录' : '选择你的身份后创建账号'}
                  </CardDescription>
                </CardHeader>

                <CardContent className="space-y-6 px-0 pb-0">
                  <Tabs value={activeRole} onValueChange={(value) => setActiveRole(value as UserRole)}>
                    <TabsList
                      className="grid h-auto w-full grid-cols-2 rounded-[12px] border border-[#d7ccbf] bg-[#f6f0e8] p-1.5"
                    >
                      <TabsTrigger value="student" className={authTabTriggerClass}>
                        <GraduationCap className="h-4 w-4" />
                        我是学生
                      </TabsTrigger>
                      <TabsTrigger value="teacher" className={authTabTriggerClass}>
                        <User className="h-4 w-4" />
                        我是老师
                      </TabsTrigger>
                    </TabsList>

                    <TabsContent value="student" className="mt-6 space-y-4">
                      <form onSubmit={handleSubmit} className="space-y-4">
                        {/* 账号 */}
                        <div className="space-y-2">
                          <Label htmlFor="student-account" className="text-slate-700 font-medium flex items-center gap-2">
                            <User className="w-4 h-4" />
                            账号
                          <Badge variant="outline" className="bg-red-50 text-red-600 border-red-200 text-xs ml-auto">
                            必填
                          </Badge>
                        </Label>
                        <Input
                          id="student-account"
                          type="text"
                          placeholder="请输入账号"
                          value={formData.account}
                          onChange={(e) => handleInputChange('account', e.target.value)}
                          className={authInputClass}
                          required
                          disabled={loading}
                        />
                      </div>

                      {/* 密码 */}
                      <div className="space-y-2">
                        <Label htmlFor="student-password" className="text-slate-700 font-medium flex items-center gap-2">
                          <Key className="w-4 h-4" />
                          密码
                          <Badge variant="outline" className="bg-red-50 text-red-600 border-red-200 text-xs ml-auto">
                            必填
                          </Badge>
                        </Label>
                        <Input
                          id="student-password"
                          type="password"
                          placeholder="请输入密码"
                          value={formData.password}
                          onChange={(e) => handleInputChange('password', e.target.value)}
                          className={authInputClass}
                          required
                          disabled={loading}
                        />
                      </div>

                      {!isLogin && (
                        <>
                          <div className="space-y-2">
                            <Label htmlFor="student-confirm-password" className="text-slate-700 font-medium flex items-center gap-2">
                              <Key className="w-4 h-4" />
                              确认密码
                              <Badge variant="outline" className="bg-red-50 text-red-600 border-red-200 text-xs ml-auto">
                                必填
                              </Badge>
                            </Label>
                            <Input
                              id="student-confirm-password"
                              type="password"
                              placeholder="请再次输入密码"
                              value={formData.confirmPassword}
                              onChange={(e) => handleInputChange('confirmPassword', e.target.value)}
                              className={authInputClass}
                              required
                              disabled={loading}
                            />
                          </div>

                          {/* 姓名 - 仅注册时显示 */}
                          <div className="space-y-2">
                            <Label htmlFor="student-name" className="text-slate-700 font-medium flex items-center gap-2">
                              <User className="w-4 h-4" />
                              姓名
                            </Label>
                            <Input
                              id="student-name"
                              type="text"
                              placeholder="请输入您的姓名"
                              value={formData.name}
                              onChange={(e) => handleInputChange('name', e.target.value)}
                              className={authInputClass}
                              required
                              disabled={loading}
                            />
                          </div>

                          {/* 邮箱 - 仅注册时显示 */}
                          <div className="space-y-2">
                            <Label htmlFor="student-email" className="text-slate-700 font-medium flex items-center gap-2">
                              <Mail className="w-4 h-4" />
                              邮箱地址（可选）
                            </Label>
                            <Input
                              id="student-email"
                              type="email"
                              placeholder="请输入您的邮箱"
                              value={formData.email}
                              onChange={(e) => handleInputChange('email', e.target.value)}
                              className={authInputClass}
                              disabled={loading}
                            />
                          </div>

                          {/* 班级选择 - 仅注册时显示 */}
                          <div className="space-y-2">
                            <Label htmlFor="class-select" className="text-slate-700 font-medium flex items-center gap-2">
                              <Users className="w-4 h-4" />
                              选择班级
                              <Badge variant="outline" className="bg-red-50 text-red-600 border-red-200 text-xs ml-auto">
                                必填
                              </Badge>
                            </Label>
                            {loadingClasses ? (
                              <div className="flex items-center justify-center py-3 text-slate-500">
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                加载班级列表...
                              </div>
                            ) : classes.length > 0 ? (
                              <Select
                                value={formData.classId}
                                onValueChange={(value) => handleInputChange('classId', value)}
                                disabled={loading}
                              >
                                <SelectTrigger className={authSelectTriggerClass}>
                                  <SelectValue placeholder="请选择班级" />
                                </SelectTrigger>
                                <SelectContent>
                                  {classes.map((cls) => (
                                    <SelectItem key={cls.id} value={cls.id}>
                                      <div className="flex flex-col">
                                        <span className="font-medium">{cls.name}</span>
                                        <span className="text-xs text-slate-500">
                                          教师：{cls.teacher_name} | 学生数：{cls.student_count}
                                        </span>
                                      </div>
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            ) : (
                              <div className="text-sm text-slate-500 py-2">
                                暂无可选班级，您可以先注册，稍后加入班级
                              </div>
                            )}
                          </div>

                          {/* 学号 - 仅注册时显示 */}
                          <div className="space-y-2">
                            <Label htmlFor="class-code" className="text-slate-700 font-medium flex items-center gap-2">
                              <Key className="w-4 h-4" />
                              学号（可选）
                            </Label>
                            <Input
                              id="class-code"
                              type="text"
                              placeholder="请输入学号"
                              value={formData.classCode}
                              onChange={(e) => handleInputChange('classCode', e.target.value)}
                              className={authInputClass}
                              disabled={loading}
                            />
                          </div>
                        </>
                      )}

                      <Button
                        type="submit"
                        className={authSubmitButtonClass}
                        disabled={loading}
                      >
                        {loading ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            {isLogin ? '登录中...' : '注册中...'}
                          </>
                        ) : (
                          <>
                            <GraduationCap className="w-4 h-4 mr-2" />
                            {isLogin ? '登录' : '注册账号'}
                          </>
                        )}
                      </Button>
                      <div className="pt-1 text-center">
                        <button
                          type="button"
                          onClick={() => handleModeChange(!isLogin)}
                          className="text-sm text-slate-500 underline-offset-4 transition-colors hover:text-slate-900 hover:underline"
                        >
                          {isLogin ? '注册账号' : '返回登录'}
                        </button>
                      </div>
                      </form>
                    </TabsContent>

                    <TabsContent value="teacher" className="mt-6 space-y-4">
                      <form onSubmit={handleSubmit} className="space-y-4">
                      {/* 邮箱/教工号 */}
                      <div className="space-y-2">
                        <Label htmlFor="teacher-id" className="text-slate-700 font-medium flex items-center gap-2">
                          <ShieldCheck className="w-4 h-4" />
                          {isLogin ? '邮箱/教工号' : '教工号'}
                          <Badge variant="outline" className="bg-red-50 text-red-600 border-red-200 text-xs ml-auto">
                            必填
                          </Badge>
                        </Label>
                        <Input
                          id="teacher-id"
                          type="text"
                          placeholder={isLogin ? '请输入邮箱或教工号' : '请输入教工号'}
                          value={formData.teacherId}
                          onChange={(e) => handleInputChange('teacherId', e.target.value)}
                          className={authInputClass}
                          required
                          disabled={loading}
                        />
                      </div>

                      {/* 密码 */}
                      <div className="space-y-2">
                        <Label htmlFor="password" className="text-slate-700 font-medium flex items-center gap-2">
                          <Key className="w-4 h-4" />
                          密码
                          <Badge variant="outline" className="bg-red-50 text-red-600 border-red-200 text-xs ml-auto">
                            必填
                          </Badge>
                        </Label>
                        <Input
                          id="password"
                          type="password"
                          placeholder="请输入密码"
                          value={formData.password}
                          onChange={(e) => handleInputChange('password', e.target.value)}
                          className={authInputClass}
                          required
                          disabled={loading}
                        />
                      </div>

                      {!isLogin && (
                        <>
                          <div className="space-y-2">
                            <Label htmlFor="teacher-confirm-password" className="text-slate-700 font-medium flex items-center gap-2">
                              <Key className="w-4 h-4" />
                              确认密码
                              <Badge variant="outline" className="bg-red-50 text-red-600 border-red-200 text-xs ml-auto">
                                必填
                              </Badge>
                            </Label>
                            <Input
                              id="teacher-confirm-password"
                              type="password"
                              placeholder="请再次输入密码"
                              value={formData.confirmPassword}
                              onChange={(e) => handleInputChange('confirmPassword', e.target.value)}
                              className={authInputClass}
                              required
                              disabled={loading}
                            />
                          </div>

                          {/* 姓名 - 仅注册时显示 */}
                          <div className="space-y-2">
                            <Label htmlFor="teacher-name" className="text-slate-700 font-medium flex items-center gap-2">
                              <User className="w-4 h-4" />
                              姓名
                            </Label>
                            <Input
                              id="teacher-name"
                              type="text"
                              placeholder="请输入您的姓名"
                              value={formData.name}
                              onChange={(e) => handleInputChange('name', e.target.value)}
                              className={authInputClass}
                              required
                              disabled={loading}
                            />
                          </div>

                          {/* 邮箱 - 仅注册时显示 */}
                          <div className="space-y-2">
                            <Label htmlFor="teacher-email" className="text-slate-700 font-medium flex items-center gap-2">
                              <Mail className="w-4 h-4" />
                              邮箱地址
                              <Badge variant="outline" className="bg-red-50 text-red-600 border-red-200 text-xs ml-auto">
                                必填
                              </Badge>
                            </Label>
                            <Input
                              id="teacher-email"
                              type="email"
                              placeholder="请输入您的邮箱"
                              value={formData.email}
                              onChange={(e) => handleInputChange('email', e.target.value)}
                              className={authInputClass}
                              required
                              disabled={loading}
                            />
                          </div>

                          {/* 班级选择 - 仅注册时显示 */}
                          <div className="student-card-muted px-3 py-2 text-sm text-slate-600">
                            教师账号注册后由管理员创建并管理班级，无需在注册时选择班级。
                          </div>
                        </>
                      )}

                      <Button
                        type="submit"
                        className={authSubmitButtonClass}
                        disabled={loading}
                      >
                        {loading ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            {isLogin ? '登录中...' : '注册中...'}
                          </>
                        ) : (
                          <>
                            <BookOpen className="w-4 h-4 mr-2" />
                            {isLogin ? '登录' : '注册账号'}
                          </>
                        )}
                      </Button>
                      <div className="pt-1 text-center">
                        <button
                          type="button"
                          onClick={() => handleModeChange(!isLogin)}
                          className="text-sm text-slate-500 underline-offset-4 transition-colors hover:text-slate-900 hover:underline"
                        >
                          {isLogin ? '注册账号' : '返回登录'}
                        </button>
                      </div>
                      {isLogin ? (
                        <div className="pt-1 text-center">
                          <button
                            type="button"
                            onClick={() => setActiveRole('administrator')}
                            className="text-xs text-slate-400 underline-offset-4 transition-colors hover:text-slate-700 hover:underline"
                          >
                            管理员登录
                          </button>
                        </div>
                      ) : null}
                      </form>
                    </TabsContent>

                    {isLogin && (
                      <TabsContent value="administrator" className="mt-6 space-y-4">
                        <form onSubmit={handleSubmit} className="space-y-4">
                        {/* 账号 */}
                        <div className="space-y-2">
                          <Label htmlFor="admin-account" className="text-slate-700 font-medium flex items-center gap-2">
                            <ShieldCheck className="w-4 h-4" />
                            管理员账号
                            <Badge variant="outline" className="bg-red-50 text-red-600 border-red-200 text-xs ml-auto">
                              必填
                            </Badge>
                          </Label>
                          <Input
                            id="admin-account"
                            type="text"
                            placeholder="请输入管理员账号"
                            value={formData.account}
                            onChange={(e) => handleInputChange('account', e.target.value)}
                            className={authInputClass}
                            required
                            disabled={loading}
                          />
                        </div>

                        {/* 密码 */}
                        <div className="space-y-2">
                          <Label htmlFor="admin-password" className="text-slate-700 font-medium flex items-center gap-2">
                            <Key className="w-4 h-4" />
                            密码
                            <Badge variant="outline" className="bg-red-50 text-red-600 border-red-200 text-xs ml-auto">
                              必填
                            </Badge>
                          </Label>
                          <Input
                            id="admin-password"
                            type="password"
                            placeholder="请输入密码"
                            value={formData.password}
                            onChange={(e) => handleInputChange('password', e.target.value)}
                            className={authInputClass}
                            required
                            disabled={loading}
                          />
                        </div>

                        <Button
                          type="submit"
                          className="w-full bg-gradient-to-r from-slate-700 to-slate-800 hover:from-slate-800 hover:to-slate-900 text-white py-3"
                          disabled={loading}
                        >
                          {loading ? (
                            <>
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                              登录中...
                            </>
                          ) : (
                            <>
                              <ShieldCheck className="w-4 h-4 mr-2" />
                              登录管理控制台
                            </>
                          )}
                        </Button>
                        </form>
                      </TabsContent>
                    )}
                  </Tabs>
                </CardContent>
              </div>
            </div>
          </Card>
        </main>
      </div>
    </div>
  );
};

export default LoginPortal;

