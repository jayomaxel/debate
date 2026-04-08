import React, { useEffect, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Users,
  Search,
  Loader2,
  AlertCircle,
  GraduationCap,
  BookOpen,
  Calendar,
  Mail,
  Edit,
  Phone,
  Save,
} from 'lucide-react';
import AdminService, {
  type Class,
  type User,
  type UserUpdate,
} from '@/services/admin.service';
import { formatErrorMessage } from '@/lib/error-handler';
import { useToast } from '@/hooks/use-toast';

type UserRoleTab = 'teacher' | 'student';

type EditableUserForm = {
  account: string;
  name: string;
  email: string;
  phone: string;
  student_id: string;
  class_id: string;
  managed_class_ids: string[];
};

const EMPTY_FORM: EditableUserForm = {
  account: '',
  name: '',
  email: '',
  phone: '',
  student_id: '',
  class_id: '',
  managed_class_ids: [],
};

const UserManagement: React.FC = () => {
  const { toast } = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [classes, setClasses] = useState<Class[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [dialogError, setDialogError] = useState('');
  const [activeRole, setActiveRole] = useState<UserRoleTab>('teacher');
  const [searchQuery, setSearchQuery] = useState('');
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editForm, setEditForm] = useState<EditableUserForm>(EMPTY_FORM);
  const [lockedManagedClassIds, setLockedManagedClassIds] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    void loadData(true);
  }, []);

  const loadData = async (withLoading: boolean = false) => {
    try {
      if (withLoading) {
        setLoading(true);
      } else {
        setRefreshing(true);
      }
      setError('');

      const [userData, classData] = await Promise.all([
        AdminService.getUsers(),
        AdminService.getAllClasses(),
      ]);

      setUsers(userData);
      setClasses(classData);
    } catch (err: any) {
      console.error('Failed to load user management data:', err);
      setError(formatErrorMessage(err));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const closeDialog = () => {
    setIsDialogOpen(false);
    setEditingUser(null);
    setEditForm(EMPTY_FORM);
    setLockedManagedClassIds([]);
    setDialogError('');
    setSubmitting(false);
  };

  const handleDialogOpenChange = (open: boolean) => {
    if (!open) {
      closeDialog();
      return;
    }
    setIsDialogOpen(true);
  };

  const handleEdit = (user: User) => {
    const managedClassIds = user.managed_class_ids || [];
    setEditingUser(user);
    setDialogError('');
    setLockedManagedClassIds(managedClassIds);
    setEditForm({
      account: user.account || '',
      name: user.name || '',
      email: user.email || '',
      phone: user.phone || '',
      student_id: user.student_id || '',
      class_id: user.class_id || '',
      managed_class_ids: managedClassIds,
    });
    setIsDialogOpen(true);
  };

  const handleFieldChange = <K extends keyof EditableUserForm>(field: K, value: EditableUserForm[K]) => {
    setEditForm((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleManagedClassToggle = (classId: string, checked: boolean) => {
    if (lockedManagedClassIds.includes(classId) && !checked) {
      return;
    }

    setEditForm((prev) => {
      const managedClassIds = new Set(prev.managed_class_ids);
      if (checked) {
        managedClassIds.add(classId);
      } else {
        managedClassIds.delete(classId);
      }
      return {
        ...prev,
        managed_class_ids: Array.from(managedClassIds),
      };
    });
  };

  const handleSubmit = async () => {
    if (!editingUser) {
      return;
    }

    const payload: UserUpdate = {
      account: editForm.account.trim(),
      name: editForm.name.trim(),
      email: editForm.email.trim(),
      phone: editForm.phone.trim() || null,
    };

    if (!payload.account || !payload.name || !payload.email) {
      setDialogError('账号、姓名和邮箱不能为空');
      return;
    }

    if (editingUser.user_type === 'student') {
      payload.student_id = editForm.student_id.trim() || null;
      payload.class_id = editForm.class_id || null;
    }

    if (editingUser.user_type === 'teacher') {
      payload.managed_class_ids = Array.from(new Set(editForm.managed_class_ids));
    }

    try {
      setSubmitting(true);
      setDialogError('');
      await AdminService.updateUser(editingUser.id, payload);
      await loadData();
      toast({
        title: '保存成功',
        description: editingUser.user_type === 'teacher' ? '教师信息与负责班级已更新' : '学生信息已更新',
      });
      closeDialog();
    } catch (err: any) {
      console.error('Failed to update user:', err);
      setDialogError(formatErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const getRoleBadge = (userType: string) => {
    if (userType === 'teacher') {
      return (
        <Badge className="bg-blue-100 text-blue-700 border-blue-200">
          <BookOpen className="w-3 h-3 mr-1" />
          教师
        </Badge>
      );
    }
    if (userType === 'student') {
      return (
        <Badge className="bg-green-100 text-green-700 border-green-200">
          <GraduationCap className="w-3 h-3 mr-1" />
          学生
        </Badge>
      );
    }
    return <Badge variant="outline">{userType}</Badge>;
  };

  const getTeacherClasses = (user: User) => user.managed_classes || [];

  const matchesSearch = (user: User) => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) {
      return true;
    }

    const managedClassText = getTeacherClasses(user)
      .map((cls) => `${cls.name} ${cls.code}`)
      .join(' ')
      .toLowerCase();

    return [
      user.account,
      user.name,
      user.email,
      user.class_name || '',
      user.student_id || '',
      managedClassText,
    ].some((value) => value.toLowerCase().includes(query));
  };

  const teacherUsers = users.filter((user) => user.user_type === 'teacher' && matchesSearch(user));
  const studentUsers = users.filter((user) => user.user_type === 'student' && matchesSearch(user));
  const visibleUsers = activeRole === 'teacher' ? teacherUsers : studentUsers;

  const stats = {
    total: users.length,
    teachers: users.filter((user) => user.user_type === 'teacher').length,
    students: users.filter((user) => user.user_type === 'student').length,
  };

  const renderTeacherClassBadges = (user: User) => {
    const managedClasses = getTeacherClasses(user);
    if (managedClasses.length === 0) {
      return <span className="text-sm text-slate-500">未分配班级</span>;
    }

    return (
      <div className="flex flex-wrap gap-2">
        {managedClasses.map((cls) => (
          <Badge key={cls.id} variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
            {cls.name}
          </Badge>
        ))}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-blue-700">总用户数</p>
                <p className="text-2xl font-bold text-blue-900">{stats.total}</p>
              </div>
              <Users className="w-8 h-8 text-blue-600 opacity-50" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-indigo-50 to-indigo-100 border-indigo-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-indigo-700">教师</p>
                <p className="text-2xl font-bold text-indigo-900">{stats.teachers}</p>
              </div>
              <BookOpen className="w-8 h-8 text-indigo-600 opacity-50" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-emerald-50 to-emerald-100 border-emerald-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-emerald-700">学生</p>
                <p className="text-2xl font-bold text-emerald-900">{stats.students}</p>
              </div>
              <GraduationCap className="w-8 h-8 text-emerald-600 opacity-50" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="p-4 space-y-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap gap-2">
              <Button
                variant={activeRole === 'teacher' ? 'default' : 'outline'}
                className={activeRole === 'teacher' ? 'bg-blue-600 hover:bg-blue-700' : ''}
                onClick={() => setActiveRole('teacher')}
              >
                教师管理
              </Button>
              <Button
                variant={activeRole === 'student' ? 'default' : 'outline'}
                className={activeRole === 'student' ? 'bg-emerald-600 hover:bg-emerald-700' : ''}
                onClick={() => setActiveRole('student')}
              >
                学生管理
              </Button>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="relative min-w-[260px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder={activeRole === 'teacher' ? '搜索教师账号、姓名、邮箱或班级' : '搜索学生账号、姓名、邮箱或学号'}
                  className="pl-10"
                />
              </div>
              <Button variant="outline" onClick={() => void loadData()} disabled={refreshing}>
                {refreshing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                刷新数据
              </Button>
            </div>
          </div>

          <Alert className="border-slate-200 bg-slate-50">
            <AlertCircle className="h-4 w-4 text-slate-600" />
            <AlertDescription className="text-slate-700">
              {activeRole === 'teacher'
                ? '教师管理中可补充分配负责班级；如果需要移除或精确转移当前班级，请到“班级管理”中操作。'
                : '学生管理中可直接调整所属班级与学号。'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {visibleUsers.length === 0 ? (
            <div className="py-12 text-center">
              <Users className="w-16 h-16 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-500">
                {searchQuery ? '没有找到匹配的用户' : activeRole === 'teacher' ? '暂无教师数据' : '暂无学生数据'}
              </p>
            </div>
          ) : activeRole === 'teacher' ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">账号</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">教师信息</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">负责班级</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">注册时间</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-slate-700 uppercase tracking-wider">操作</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-200">
                  {teacherUsers.map((user) => (
                    <tr key={user.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="w-8 h-8 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-sm font-medium mr-3">
                            {user.name.charAt(0)}
                          </div>
                          <div>
                            <div className="text-sm font-medium text-slate-900">{user.account}</div>
                            <div className="mt-1">{getRoleBadge(user.user_type)}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="space-y-1">
                          <div className="text-sm font-medium text-slate-900">{user.name}</div>
                          <div className="flex items-center text-sm text-slate-600">
                            <Mail className="w-4 h-4 mr-2" />
                            {user.email}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">{renderTeacherClassBadges(user)}</td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center text-sm text-slate-600">
                          <Calendar className="w-4 h-4 mr-2" />
                          {new Date(user.created_at).toLocaleDateString('zh-CN')}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right">
                        <Button variant="outline" size="sm" onClick={() => handleEdit(user)}>
                          <Edit className="w-4 h-4 mr-2" />
                          编辑
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">账号</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">学生信息</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">学号</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">所属班级</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">注册时间</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-slate-700 uppercase tracking-wider">操作</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-200">
                  {studentUsers.map((user) => (
                    <tr key={user.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="w-8 h-8 bg-emerald-100 text-emerald-700 rounded-full flex items-center justify-center text-sm font-medium mr-3">
                            {user.name.charAt(0)}
                          </div>
                          <div>
                            <div className="text-sm font-medium text-slate-900">{user.account}</div>
                            <div className="mt-1">{getRoleBadge(user.user_type)}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="space-y-1">
                          <div className="text-sm font-medium text-slate-900">{user.name}</div>
                          <div className="flex items-center text-sm text-slate-600">
                            <Mail className="w-4 h-4 mr-2" />
                            {user.email}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600">{user.student_id || '-'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600">{user.class_name || '未加入班级'}</td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center text-sm text-slate-600">
                          <Calendar className="w-4 h-4 mr-2" />
                          {new Date(user.created_at).toLocaleDateString('zh-CN')}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right">
                        <Button variant="outline" size="sm" onClick={() => handleEdit(user)}>
                          <Edit className="w-4 h-4 mr-2" />
                          编辑
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {(searchQuery || users.length > 0) && (
        <div className="text-sm text-slate-600 text-center">
          当前显示 {visibleUsers.length} 个{activeRole === 'teacher' ? '教师' : '学生'}
        </div>
      )}

      <Dialog open={isDialogOpen} onOpenChange={handleDialogOpenChange}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>{editingUser?.user_type === 'teacher' ? '编辑教师' : '编辑学生'}</DialogTitle>
            <DialogDescription>
              {editingUser?.user_type === 'teacher'
                ? '可修改教师基本信息，并补充分配负责班级。'
                : '可修改学生基本信息、学号与所属班级。'}
            </DialogDescription>
          </DialogHeader>

          {dialogError && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{dialogError}</AlertDescription>
            </Alert>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="user-account">账号</Label>
              <Input
                id="user-account"
                value={editForm.account}
                onChange={(e) => handleFieldChange('account', e.target.value)}
                disabled={submitting}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="user-name">姓名</Label>
              <Input
                id="user-name"
                value={editForm.name}
                onChange={(e) => handleFieldChange('name', e.target.value)}
                disabled={submitting}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="user-email">邮箱</Label>
              <Input
                id="user-email"
                type="email"
                value={editForm.email}
                onChange={(e) => handleFieldChange('email', e.target.value)}
                disabled={submitting}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="user-phone">手机号</Label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <Input
                  id="user-phone"
                  value={editForm.phone}
                  onChange={(e) => handleFieldChange('phone', e.target.value)}
                  disabled={submitting}
                  className="pl-10"
                  placeholder="选填"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>角色</Label>
              <div className="h-10 px-3 border rounded-md bg-slate-50 flex items-center">
                {editingUser ? getRoleBadge(editingUser.user_type) : null}
              </div>
            </div>

            <div className="space-y-2">
              <Label>注册时间</Label>
              <div className="h-10 px-3 border rounded-md bg-slate-50 flex items-center text-sm text-slate-600">
                {editingUser ? new Date(editingUser.created_at).toLocaleString('zh-CN') : '-'}
              </div>
            </div>

            {editingUser?.user_type === 'student' && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="user-student-id">学号</Label>
                  <Input
                    id="user-student-id"
                    value={editForm.student_id}
                    onChange={(e) => handleFieldChange('student_id', e.target.value)}
                    disabled={submitting}
                    placeholder="选填"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="user-class">所属班级</Label>
                  <Select
                    value={editForm.class_id || '__none__'}
                    onValueChange={(value) => handleFieldChange('class_id', value === '__none__' ? '' : value)}
                    disabled={submitting}
                  >
                    <SelectTrigger id="user-class">
                      <SelectValue placeholder="请选择班级" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">未加入班级</SelectItem>
                      {classes.map((cls) => (
                        <SelectItem key={cls.id} value={cls.id}>
                          {cls.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}
          </div>

          {editingUser?.user_type === 'teacher' && (
            <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="space-y-1">
                <Label className="text-slate-900">负责班级</Label>
                <p className="text-sm text-slate-600">
                  已负责的班级会锁定保留；勾选其他班级后，保存时会改派给当前教师。
                </p>
              </div>

              <div className="grid grid-cols-1 gap-3 max-h-72 overflow-y-auto pr-1">
                {classes.length === 0 ? (
                  <div className="rounded-md border border-dashed border-slate-300 bg-white px-4 py-6 text-sm text-slate-500 text-center">
                    暂无可分配班级
                  </div>
                ) : (
                  classes.map((cls) => {
                    const isChecked = editForm.managed_class_ids.includes(cls.id);
                    const isLocked = lockedManagedClassIds.includes(cls.id);
                    const belongsToCurrentTeacher = cls.teacher_id === editingUser.id;
                    const helperText = belongsToCurrentTeacher
                      ? '当前已负责'
                      : isChecked
                        ? `保存后将从 ${cls.teacher_name} 改派给当前教师`
                        : `当前教师：${cls.teacher_name}`;

                    return (
                      <label
                        key={cls.id}
                        className={`flex items-start gap-3 rounded-lg border px-4 py-3 transition-colors ${
                          isChecked ? 'border-blue-200 bg-blue-50' : 'border-slate-200 bg-white'
                        } ${isLocked ? 'cursor-not-allowed opacity-80' : 'cursor-pointer hover:border-blue-200 hover:bg-blue-50/60'}`}
                      >
                        <Checkbox
                          checked={isChecked}
                          disabled={submitting || isLocked}
                          onCheckedChange={(checked) => handleManagedClassToggle(cls.id, checked === true)}
                          className="mt-0.5"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium text-slate-900">{cls.name}</span>
                            <Badge variant="outline" className="bg-white">
                              {cls.code}
                            </Badge>
                          </div>
                          <p className="mt-1 text-sm text-slate-600">{helperText}</p>
                        </div>
                      </label>
                    );
                  })
                )}
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={closeDialog} disabled={submitting}>
              取消
            </Button>
            <Button onClick={handleSubmit} disabled={submitting}>
              {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
              保存修改
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default UserManagement;
