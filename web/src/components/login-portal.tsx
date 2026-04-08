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
  Sparkles,
  BrainCircuit,
  Target,
  Award,
  Loader2
} from 'lucide-react';
import { useAuth } from '@/store/auth.context';
import AuthService from '@/services/auth.service';
import { formatErrorMessage } from '@/lib/error-handler';

interface LoginFormData {
  name: string;
  email: string;
  account: string;
  classCode?: string;
  classId?: string;  // 新增：班级ID
  teacherId?: string;
  password?: string;
}

type UserRole = 'student' | 'teacher' | 'administrator';

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

const LoginPortal: React.FC<LoginPortalProps> = ({ onLogin }) => {
  const { login } = useAuth();
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
    password: ''
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
        if (activeRole === 'student') {
          if (!formData.account || !formData.password || !formData.name) {
            toast({
              variant: 'destructive',
              title: '注册失败',
              description: '请填写所有必填字段',
            });
            return;
          }

          await AuthService.registerStudent({
            account: formData.account,
            password: formData.password,
            name: formData.name,
            class_id: formData.classId || undefined,  // 使用班级ID
            email: formData.email || undefined,
            student_id: formData.classCode || undefined,
          });

          // 注册成功，显示提示并切换到登录模式
          toast({
            variant: 'success',
            title: '注册成功',
            description: '请使用您的账号密码登录',
          });
          setIsLogin(true);
          // 清空密码字段
          setFormData(prev => ({ ...prev, password: '' }));
        } else {
          if (!formData.email || !formData.password || !formData.name || !formData.teacherId) {
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
            password: formData.password,
            name: formData.name,
          });

          // 注册成功，显示提示并切换到登录模式
          toast({
            variant: 'success',
            title: '注册成功',
            description: '请使用您的教工号和密码登录',
          });
          setIsLogin(true);
          // 清空密码字段
          setFormData(prev => ({ ...prev, password: '' }));
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
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-slate-50 to-amber-50">
      <div className="flex flex-col min-h-screen">
        {/* 顶部品牌区域 */}
        <div className="text-center pt-12 pb-8 px-4">
          <div className="mb-6">
            <div className="flex items-center justify-center gap-3 mb-4">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-600 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg">
                <BrainCircuit className="w-10 h-10 text-white" />
              </div>
              <div className="text-left">
                <h1 className="text-3xl font-bold leading-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-purple-600">
                  碳硅之辩·人机思辨平台
                </h1>
                <p className="text-lg text-slate-600 font-medium">
                  SpeculateAI: The Carbon-Silicon Debate Platform
                </p>
              </div>
            </div>

            <div className="max-w-2xl mx-auto">
              <p className="text-xl text-slate-700 font-light mb-4">
                人机协作，思辨通识未来
              </p>
              <div className="flex items-center justify-center gap-6 text-sm text-slate-500">
                <div className="flex items-center gap-2">
                  <Target className="w-4 h-4 text-blue-500" />
                  <span>AI辅助辩论</span>
                </div>
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-purple-500" />
                  <span>实时互动</span>
                </div>
                <div className="flex items-center gap-2">
                  <Award className="w-4 h-4 text-amber-500" />
                  <span>能力评估</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 登录表单区域 */}
        <div className="flex-1 flex items-center justify-center px-4 pb-12">
          <div className="w-full max-w-md">
            <Card className="bg-white border-slate-200 shadow-xl">
              <CardHeader className="text-center pb-4">
                <CardTitle className="text-2xl font-bold text-slate-900 mb-2">
                  欢迎登录
                </CardTitle>
                <CardDescription className="text-slate-600">
                  选择您的身份，开启智能辩论之旅
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-6">
                {/* 登录/注册切换 */}
                <div className="flex items-center justify-center gap-4 text-sm">
                  <button
                    type="button"
                    onClick={() => {
                      setIsLogin(true);
                    }}
                    className={`px-4 py-2 rounded-md transition-colors ${
                      isLogin
                        ? 'bg-blue-600 text-white'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    登录
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setIsLogin(false);
                    }}
                    className={`px-4 py-2 rounded-md transition-colors ${
                      !isLogin
                        ? 'bg-blue-600 text-white'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    注册
                  </button>
                </div>

                {/* 角色切换 */}
                <Tabs value={activeRole} onValueChange={(value) => setActiveRole(value as UserRole)}>
                  <TabsList className="grid w-full grid-cols-3 h-12 bg-slate-100">
                    <TabsTrigger
                      value="student"
                      className="flex items-center gap-2 data-[state=active]:bg-blue-600 data-[state=active]:text-white"
                    >
                      <GraduationCap className="w-4 h-4" />
                      我是学生
                    </TabsTrigger>
                    <TabsTrigger
                      value="teacher"
                      className="flex items-center gap-2 data-[state=active]:bg-blue-600 data-[state=active]:text-white"
                    >
                      <User className="w-4 h-4" />
                      我是老师
                    </TabsTrigger>
                    <TabsTrigger
                      value="administrator"
                      className="flex items-center gap-2 data-[state=active]:bg-blue-600 data-[state=active]:text-white"
                    >
                      <ShieldCheck className="w-4 h-4" />
                      管理员
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="student" className="space-y-4 mt-6">
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
                          className="border-slate-300 focus:border-blue-500 focus:ring-blue-500"
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
                          className="border-slate-300 focus:border-blue-500 focus:ring-blue-500"
                          required
                          disabled={loading}
                        />
                      </div>

                      {!isLogin && (
                        <>
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
                              className="border-slate-300 focus:border-blue-500 focus:ring-blue-500"
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
                              className="border-slate-300 focus:border-blue-500 focus:ring-blue-500"
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
                                <SelectTrigger className="border-slate-300 focus:border-blue-500 focus:ring-blue-500">
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
                              className="border-slate-300 focus:border-blue-500 focus:ring-blue-500"
                              disabled={loading}
                            />
                          </div>
                        </>
                      )}

                      <Button
                        type="submit"
                        className="w-full bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white py-3"
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
                            {isLogin ? '登录' : '注册并进入辩论课堂'}
                          </>
                        )}
                      </Button>
                    </form>
                  </TabsContent>

                  <TabsContent value="teacher" className="space-y-4 mt-6">
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
                          className="border-slate-300 focus:border-blue-500 focus:ring-blue-500"
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
                          className="border-slate-300 focus:border-blue-500 focus:ring-blue-500"
                          required
                          disabled={loading}
                        />
                      </div>

                      {!isLogin && (
                        <>
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
                              className="border-slate-300 focus:border-blue-500 focus:ring-blue-500"
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
                              className="border-slate-300 focus:border-blue-500 focus:ring-blue-500"
                              required
                              disabled={loading}
                            />
                          </div>

                          {/* 班级选择 - 仅注册时显示 */}
                          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                            教师账号注册后由管理员创建并管理班级，无需在注册时选择班级。
                          </div>
                        </>
                      )}

                      <Button
                        type="submit"
                        className="w-full bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white py-3"
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
                            {isLogin ? '登录' : '注册并进入教师控制台'}
                          </>
                        )}
                      </Button>
                    </form>
                  </TabsContent>

                  <TabsContent value="administrator" className="space-y-4 mt-6">
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
                          className="border-slate-300 focus:border-blue-500 focus:ring-blue-500"
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
                          className="border-slate-300 focus:border-blue-500 focus:ring-blue-500"
                          required
                          disabled={loading}
                        />
                      </div>

                      <Button
                        type="submit"
                        className="w-full bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white py-3"
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
                </Tabs>
              </CardContent>
            </Card>

            {/* 底部说明 */}
            <div className="mt-6 text-center">
              <div className="flex items-center justify-center gap-2 text-sm text-slate-500">
                <Sparkles className="w-4 h-4 text-blue-500" />
                <span>AI驱动的人机思辨平台</span>
                <Sparkles className="w-4 h-4 text-purple-500" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPortal;
