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

type EditableUserForm = {
  account: string;
  name: string;
  email: string;
  phone: string;
  student_id: string;
  class_id: string;
};

const EMPTY_FORM: EditableUserForm = {
  account: '',
  name: '',
  email: '',
  phone: '',
  student_id: '',
  class_id: '',
};

const UserManagement: React.FC = () => {
  const { toast } = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [filteredUsers, setFilteredUsers] = useState<User[]>([]);
  const [classes, setClasses] = useState<Class[]>([]);
  const [loading, setLoading] = useState(true);
  const [classesLoading, setClassesLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [dialogError, setDialogError] = useState<string>('');

  const [roleFilter, setRoleFilter] = useState<'all' | 'teacher' | 'student'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editForm, setEditForm] = useState<EditableUserForm>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadUsers();
  }, [roleFilter]);

  useEffect(() => {
    loadClasses();
  }, []);

  useEffect(() => {
    if (searchQuery.trim() === '') {
      setFilteredUsers(users);
      return;
    }

    const query = searchQuery.toLowerCase();
    const filtered = users.filter((user) =>
      user.account.toLowerCase().includes(query) ||
      user.name.toLowerCase().includes(query) ||
      user.email.toLowerCase().includes(query)
    );
    setFilteredUsers(filtered);
  }, [searchQuery, users]);

  const loadUsers = async () => {
    try {
      setLoading(true);
      setError('');

      const data = await AdminService.getUsers(
        roleFilter === 'all' ? undefined : roleFilter
      );
      setUsers(data);
      setFilteredUsers(data);
    } catch (err: any) {
      console.error('Failed to load users:', err);
      setError(formatErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const loadClasses = async () => {
    try {
      setClassesLoading(true);
      const data = await AdminService.getAllClasses();
      setClasses(data);
    } catch (err: any) {
      console.error('Failed to load classes:', err);
      toast({
        variant: 'destructive',
        title: '班级加载失败',
        description: formatErrorMessage(err),
      });
    } finally {
      setClassesLoading(false);
    }
  };

  const closeDialog = () => {
    setIsDialogOpen(false);
    setEditingUser(null);
    setEditForm(EMPTY_FORM);
    setDialogError('');
    setSubmitting(false);
  };

  const handleEdit = (user: User) => {
    setEditingUser(user);
    setDialogError('');
    setEditForm({
      account: user.account || '',
      name: user.name || '',
      email: user.email || '',
      phone: user.phone || '',
      student_id: user.student_id || '',
      class_id: user.class_id || '',
    });
    setIsDialogOpen(true);
  };

  const handleDialogOpenChange = (open: boolean) => {
    if (!open) {
      closeDialog();
      return;
    }
    setIsDialogOpen(true);
  };

  const handleFieldChange = (field: keyof EditableUserForm, value: string) => {
    setEditForm((prev) => ({
      ...prev,
      [field]: value,
    }));
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

    try {
      setSubmitting(true);
      setDialogError('');
      const updatedUser = await AdminService.updateUser(editingUser.id, payload);
      setUsers((prev) => prev.map((user) => (
        user.id === updatedUser.id ? updatedUser : user
      )));
      toast({
        title: '保存成功',
        description: '用户信息已更新',
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

  const stats = {
    total: users.length,
    teachers: users.filter((user) => user.user_type === 'teacher').length,
    students: users.filter((user) => user.user_type === 'student').length,
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

        <Card className="bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-purple-700">教师</p>
                <p className="text-2xl font-bold text-purple-900">{stats.teachers}</p>
              </div>
              <BookOpen className="w-8 h-8 text-purple-600 opacity-50" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-green-50 to-green-100 border-green-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-green-700">学生</p>
                <p className="text-2xl font-bold text-green-900">{stats.students}</p>
              </div>
              <GraduationCap className="w-8 h-8 text-green-600 opacity-50" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="role-filter">角色筛选</Label>
              <Select
                value={roleFilter}
                onValueChange={(value) => setRoleFilter(value as 'all' | 'teacher' | 'student')}
              >
                <SelectTrigger id="role-filter">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部用户</SelectItem>
                  <SelectItem value="teacher">教师</SelectItem>
                  <SelectItem value="student">学生</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="search">搜索用户</Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <Input
                  id="search"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="搜索账号、姓名或邮箱..."
                  className="pl-10"
                />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {filteredUsers.length === 0 ? (
            <div className="py-12 text-center">
              <Users className="w-16 h-16 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-500">
                {searchQuery ? '未找到匹配的用户' : '暂无用户数据'}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">
                      账号
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">
                      姓名
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">
                      邮箱
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">
                      角色
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">
                      班级
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">
                      注册时间
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-slate-700 uppercase tracking-wider">
                      操作
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-200">
                  {filteredUsers.map((user) => (
                    <tr key={user.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="w-8 h-8 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-sm font-medium mr-3">
                            {user.name.charAt(0)}
                          </div>
                          <span className="text-sm font-medium text-slate-900">
                            {user.account}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="text-sm text-slate-900">{user.name}</span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center text-sm text-slate-600">
                          <Mail className="w-4 h-4 mr-2" />
                          {user.email}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {getRoleBadge(user.user_type)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="text-sm text-slate-600">
                          {user.class_name || '-'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center text-sm text-slate-600">
                          <Calendar className="w-4 h-4 mr-2" />
                          {new Date(user.created_at).toLocaleDateString('zh-CN')}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleEdit(user)}
                        >
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

      {searchQuery && (
        <div className="text-sm text-slate-600 text-center">
          找到 {filteredUsers.length} 个匹配的用户
        </div>
      )}

      <Dialog open={isDialogOpen} onOpenChange={handleDialogOpenChange}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>编辑用户</DialogTitle>
            <DialogDescription>
              可修改账号、联系方式，以及学生的学号和班级信息。
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
                  <Label htmlFor="user-class">班级</Label>
                  <Select
                    value={editForm.class_id || '__none__'}
                    onValueChange={(value) => handleFieldChange('class_id', value === '__none__' ? '' : value)}
                    disabled={submitting || classesLoading}
                  >
                    <SelectTrigger id="user-class">
                      <SelectValue placeholder={classesLoading ? '加载班级中...' : '请选择班级'} />
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

          <DialogFooter>
            <Button variant="outline" onClick={closeDialog} disabled={submitting}>
              取消
            </Button>
            <Button onClick={handleSubmit} disabled={submitting}>
              {submitting ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Save className="w-4 h-4 mr-2" />
              )}
              保存修改
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default UserManagement;
