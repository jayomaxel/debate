import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import {
  Plus,
  Edit,
  Trash2,
  Users,
  Calendar,
  Loader2,
  AlertCircle,
  CheckCircle
} from 'lucide-react';
import AdminService, { type Class, type ClassCreate, type ClassUpdate } from '@/services/admin.service';
import { formatErrorMessage } from '@/lib/error-handler';

interface Teacher {
  id: string;
  name: string;
  email: string;
}

const ClassManagement: React.FC = () => {
  const [classes, setClasses] = useState<Class[]>([]);
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [success, setSuccess] = useState<string>('');
  
  // 创建/编辑对话框状态
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingClass, setEditingClass] = useState<Class | null>(null);
  const [formData, setFormData] = useState<ClassCreate>({
    name: '',
    teacher_id: ''
  });
  const [submitting, setSubmitting] = useState(false);
  
  // 删除确认对话框状态
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingClass, setDeletingClass] = useState<Class | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError('');
      
      // 分别加载数据，避免一个失败导致全部失败
      let classesData: Class[] = [];
      let teachersData: Teacher[] = [];
      
      try {
        classesData = await AdminService.getAllClasses();
        setClasses(classesData);
      } catch (err: any) {
        console.error('Failed to load classes:', err);
        setError(prev => prev ? `${prev}; 加载班级失败` : '加载班级失败');
      }
      
      try {
        const usersData = await AdminService.getUsers('teacher');
        teachersData = usersData.map(u => ({
          id: u.id,
          name: u.name,
          email: u.email
        }));
        setTeachers(teachersData);
        
        if (teachersData.length === 0) {
          setError(prev => prev ? `${prev}; 系统中暂无教师用户，请先创建教师账号` : '系统中暂无教师用户，请先创建教师账号');
        }
      } catch (err: any) {
        console.error('Failed to load teachers:', err);
        setError(prev => prev ? `${prev}; 加载教师列表失败` : '加载教师列表失败');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    if (teachers.length === 0) {
      setError('系统中暂无教师用户，无法创建班级。请先在用户管理中创建教师账号。');
      return;
    }
    setEditingClass(null);
    setFormData({ name: '', teacher_id: '' });
    setIsDialogOpen(true);
  };

  const handleEdit = (cls: Class) => {
    setEditingClass(cls);
    setFormData({
      name: cls.name,
      teacher_id: cls.teacher_id
    });
    setIsDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!formData.name || !formData.teacher_id) {
      setError('请填写所有必填字段');
      return;
    }

    try {
      setSubmitting(true);
      setError('');
      
      if (editingClass) {
        // 更新班级
        await AdminService.updateClass(editingClass.id, formData);
        setSuccess('班级更新成功');
      } else {
        // 创建班级
        await AdminService.createClass(formData);
        setSuccess('班级创建成功');
      }
      
      setIsDialogOpen(false);
      await loadData();
      
      // 3秒后清除成功消息
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      console.error('Failed to save class:', err);
      setError(formatErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteClick = (cls: Class) => {
    setDeletingClass(cls);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!deletingClass) return;

    try {
      setDeleting(true);
      setError('');
      
      await AdminService.deleteClass(deletingClass.id);
      setSuccess('班级删除成功');
      setDeleteDialogOpen(false);
      await loadData();
      
      // 3秒后清除成功消息
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      console.error('Failed to delete class:', err);
      setError(formatErrorMessage(err));
    } finally {
      setDeleting(false);
    }
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
      {/* 成功提示 */}
      {success && (
        <Alert className="bg-green-50 border-green-200">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">{success}</AlertDescription>
        </Alert>
      )}

      {/* 错误提示 */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* 操作栏 */}
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">班级列表</h3>
          <p className="text-sm text-slate-600">共 {classes.length} 个班级</p>
        </div>
        <Button onClick={handleCreate} className="bg-blue-600 hover:bg-blue-700">
          <Plus className="w-4 h-4 mr-2" />
          创建班级
        </Button>
      </div>

      {/* 班级列表 */}
      {classes.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Users className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-500">暂无班级数据</p>
            <Button onClick={handleCreate} variant="outline" className="mt-4">
              <Plus className="w-4 h-4 mr-2" />
              创建第一个班级
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {classes.map((cls) => (
            <Card key={cls.id} className="hover:shadow-md transition-shadow">
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h4 className="text-lg font-semibold text-slate-900">{cls.name}</h4>
                      <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                        {cls.code}
                      </Badge>
                    </div>
                    
                    <div className="grid grid-cols-3 gap-4 mt-4">
                      <div className="flex items-center gap-2 text-sm text-slate-600">
                        <Users className="w-4 h-4" />
                        <span>教师: {cls.teacher_name}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-slate-600">
                        <Users className="w-4 h-4" />
                        <span>学生: {cls.student_count} 人</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-slate-600">
                        <Calendar className="w-4 h-4" />
                        <span>{new Date(cls.created_at).toLocaleDateString('zh-CN')}</span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex gap-2 ml-4">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleEdit(cls)}
                    >
                      <Edit className="w-4 h-4 mr-1" />
                      编辑
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDeleteClick(cls)}
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                    >
                      <Trash2 className="w-4 h-4 mr-1" />
                      删除
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* 创建/编辑对话框 */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingClass ? '编辑班级' : '创建班级'}</DialogTitle>
            <DialogDescription>
              {editingClass ? '修改班级信息' : '为教师创建新的班级'}
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="class-name">班级名称 *</Label>
              <Input
                id="class-name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="请输入班级名称"
                disabled={submitting}
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="teacher">指定教师 *</Label>
              <Select
                value={formData.teacher_id}
                onValueChange={(value) => setFormData({ ...formData, teacher_id: value })}
                disabled={submitting || teachers.length === 0}
              >
                <SelectTrigger>
                  <SelectValue placeholder={teachers.length === 0 ? "暂无可用教师" : "请选择教师"} />
                </SelectTrigger>
                <SelectContent>
                  {teachers.length === 0 ? (
                    <div className="p-2 text-sm text-slate-500 text-center">
                      暂无教师用户
                    </div>
                  ) : (
                    teachers.map((teacher) => (
                      <SelectItem key={teacher.id} value={teacher.id}>
                        {teacher.name} ({teacher.email})
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
              {teachers.length === 0 && (
                <p className="text-xs text-red-600">
                  请先在用户管理中创建教师账号
                </p>
              )}
            </div>
          </div>
          
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsDialogOpen(false)}
              disabled={submitting}
            >
              取消
            </Button>
            <Button onClick={handleSubmit} disabled={submitting}>
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  保存中...
                </>
              ) : (
                '保存'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 删除确认对话框 */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>
              您确定要删除班级 "{deletingClass?.name}" 吗？
              <br />
              <span className="text-red-600 font-medium">
                此操作将同时移除该班级的所有学生注册信息，且无法撤销。
              </span>
            </DialogDescription>
          </DialogHeader>
          
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={deleting}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteConfirm}
              disabled={deleting}
            >
              {deleting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  删除中...
                </>
              ) : (
                '确认删除'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ClassManagement;
