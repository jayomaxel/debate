import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { ToastAction } from "@/components/ui/toast";
import { useToast } from '@/hooks/use-toast';
import UserProfile from './user-profile';
import { useAuth } from '@/store/auth.context';
import TeacherService from '@/services/teacher.service';
import type { Class, Student, CreateDebateParams, TeacherDebate, DebateGroupingItem } from '@/services/teacher.service';
import {
  Plus,
  Upload,
  Users,
  Clock,
  CheckCircle,
  FileSpreadsheet,
  Play,
  History,
  Settings,
  BarChart3,
  TrendingUp,
  Calendar,
  MessageSquare,
  Award,
  Loader2,
  AlertCircle,
  User as UserIcon,
  Pencil,
  X,
  BrainCircuit,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

interface DebateConfig {
  topic: string;
  duration: string;
  rounds: string;
  class_id: string;
}

interface TeacherDashboardProps {
  onLogout: () => void;
  onNavigate: (page: 'debate' | 'analytics' | 'debate-report' | 'debate-replay', debateId?: string) => void;
}

const TeacherDashboard: React.FC<TeacherDashboardProps> = ({ onLogout, onNavigate }) => {
  const { user } = useAuth();
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState('new');
  const [students, setStudents] = useState<Student[]>([]);
  const [classes, setClasses] = useState<Class[]>([]);
  const [debates, setDebates] = useState<TeacherDebate[]>([]);
  const [selectedClass, setSelectedClass] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [selectedStudentIds, setSelectedStudentIds] = useState<string[]>([]);
  const [editingDebateId, setEditingDebateId] = useState<string | null>(null);
  const [groupingOpenByDebateId, setGroupingOpenByDebateId] = useState<Record<string, boolean>>({});
  const [groupingLoadingByDebateId, setGroupingLoadingByDebateId] = useState<Record<string, boolean>>({});
  const [debateDetailsById, setDebateDetailsById] = useState<Record<string, TeacherDebate>>({});

  const [debateConfig, setDebateConfig] = useState<DebateConfig>({
    topic: '稳定币的未来监管与发展',
    duration: '30',
    rounds: '3',
    class_id: ''
  });

  // 加载数据
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);

        const [classesData, debatesData] = await Promise.all([
          TeacherService.getClasses(),
          TeacherService.getDebates()
        ]);

        setClasses(classesData);
        setDebates(debatesData);

        // 如果有班级，默认选择第一个
        if (classesData.length > 0) {
          setSelectedClass(classesData[0].id);
          setDebateConfig(prev => ({ ...prev, class_id: classesData[0].id }));

          // 加载该班级的学生
          const studentsData = await TeacherService.getStudents(classesData[0].id);
          setStudents(studentsData);
        }
      } catch (err: any) {
        console.error('Failed to load teacher data:', err);
        setError(err.message || '加载数据失败');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  // 当选择的班级改变时，加载该班级的学生
  useEffect(() => {
    if (selectedClass) {
      const loadStudents = async () => {
        try {
          const studentsData = await TeacherService.getStudents(selectedClass);
          setStudents(studentsData);
        } catch (err: any) {
          console.error('Failed to load students:', err);
          setError(err.message || '加载学生列表失败');
        }
      };
      loadStudents();
    }
  }, [selectedClass]);

  const stats = {
    activeDebates: debates.filter(d => d.status === 'in_progress').length,
    completedDebates: debates.filter(d => d.status === 'completed').length,
    totalStudents: students.length,
    todayDebates: debates.filter(d => {
      const today = new Date().toDateString();
      return new Date(d.created_at).toDateString() === today;
    }).length
  };

  const menuItems = [
    { id: 'new', label: '新建辩论', icon: Plus },
    { id: 'history', label: '历史记录', icon: History },
    { id: 'students', label: '学生管理', icon: Users },
    { id: 'analytics', label: '数据分析', icon: BarChart3 },
    { id: 'profile', label: '个人中心', icon: UserIcon }
  ];

  const handleStudentToggle = (studentId: string) => {
    setSelectedStudentIds(prev => {
      if (prev.includes(studentId)) {
        return prev.filter(id => id !== studentId);
      } else {
        if (prev.length >= 4) {
          setError("最多只能选择4名辩手");
          return prev;
        }
        setError(null);
        return [...prev, studentId];
      }
    });
  };

  const handleEditDebate = async (debate: TeacherDebate) => {
    console.log('Editing debate (initial):', debate);

    // Set basic info first for immediate feedback
    setEditingDebateId(debate.id);
    setActiveTab('new');
    setError(null);

    try {
        // Fetch latest details to ensure we have student_ids
        const debateDetails = await TeacherService.getDebate(debate.id);
        console.log('Editing debate (fetched):', debateDetails);

        // Extract rounds from description "X轮辩论"
        let rounds = '3';
        if (debateDetails.description) {
          const match = debateDetails.description.match(/(\d+)轮/);
          if (match) {
            rounds = match[1];
          }
        }

        setDebateConfig({
          topic: debateDetails.topic,
          duration: debateDetails.duration.toString(),
          rounds: rounds,
          class_id: debateDetails.class_id || selectedClass
        });

        if (debateDetails.class_id) {
            setSelectedClass(debateDetails.class_id);
        }

        setSelectedStudentIds(debateDetails.student_ids || []);

    } catch (err) {
        console.error("Failed to fetch debate details:", err);
        setError("获取辩论详情失败，请刷新重试");
        // Fallback to existing data
        let rounds = '3';
        if (debate.description) {
          const match = debate.description.match(/(\d+)轮/);
          if (match) {
            rounds = match[1];
          }
        }
        setDebateConfig({
          topic: debate.topic,
          duration: debate.duration.toString(),
          rounds: rounds,
          class_id: debate.class_id || selectedClass
        });
        if (debate.class_id) setSelectedClass(debate.class_id);
        setSelectedStudentIds(debate.student_ids || []);
    }
  };

  const handleCancelEdit = () => {
    setDebateConfig({
        topic: '',
        duration: '30',
        rounds: '3',
        class_id: selectedClass
      });
      setSelectedStudentIds([]);
      setEditingDebateId(null);
      setError(null);
  };

  const roleLabel: Record<DebateGroupingItem['role'], string> = {
    debater_1: '一辩',
    debater_2: '二辩',
    debater_3: '三辩',
    debater_4: '四辩'
  };

  const ensureDebateDetailsLoaded = async (debateId: string) => {
    if (debateDetailsById[debateId]?.grouping) return;
    if (groupingLoadingByDebateId[debateId]) return;

    setGroupingLoadingByDebateId(prev => ({ ...prev, [debateId]: true }));
    try {
      const details = await TeacherService.getDebate(debateId);
      setDebateDetailsById(prev => ({ ...prev, [debateId]: details }));
    } catch (err: any) {
      toast({
        variant: 'destructive',
        title: '加载分组失败',
        description: err?.message || '请稍后重试',
        duration: 3000,
      });
    } finally {
      setGroupingLoadingByDebateId(prev => ({ ...prev, [debateId]: false }));
    }
  };

  const setGroupingOpen = (debateId: string, open: boolean) => {
    setGroupingOpenByDebateId(prev => ({ ...prev, [debateId]: open }));
    if (open) {
      ensureDebateDetailsLoaded(debateId);
    }
  };

  const handleCreateDebate = async () => {
    if (!debateConfig.class_id) {
      setError('请选择班级');
      return;
    }

    if (selectedStudentIds.length === 0) {
      setError('请至少选择一名学生参与辩论');
      return;
    }

    try {
      setSubmitting(true);
      setError(null);

      const params: CreateDebateParams = {
        class_id: debateConfig.class_id,
        topic: debateConfig.topic,
        duration: parseInt(debateConfig.duration),
        description: `${debateConfig.rounds}轮辩论`,
        student_ids: selectedStudentIds
      };

      if (editingDebateId) {
         const updatedDebate = await TeacherService.updateDebate(editingDebateId, params);
         setDebates(prev => prev.map(d => d.id === editingDebateId ? updatedDebate : d));
         setDebateDetailsById(prev => ({ ...prev, [editingDebateId]: updatedDebate }));
         toast({
            variant: "success",
            title: "辩论更新成功",
            description: "辩论信息已保存",
            duration: 3000,
         });
      } else {
         const newDebate = await TeacherService.createDebate(params);
         setDebates(prev => [newDebate, ...prev]);
         setDebateDetailsById(prev => ({ ...prev, [newDebate.id]: newDebate }));
         toast({
            variant: "success",
            title: "辩论创建成功",
            description: `邀请码：${newDebate.invitation_code}（已智能分组）`,
            duration: 5000,
            action: (
              <ToastAction
                altText="查看分组"
                onClick={() => {
                  setActiveTab('history');
                  setGroupingOpen(newDebate.id, true);
                }}
              >
                查看分组
              </ToastAction>
            ),
         });
      }

      // 重置表单
      setDebateConfig({
        topic: '',
        duration: '30',
        rounds: '3',
        class_id: selectedClass
      });
      setSelectedStudentIds([]);
      setEditingDebateId(null);

      setError(null);
    } catch (err: any) {
      console.error('Failed to save debate:', err);
      setError(err.message || '保存失败');
    } finally {
      setSubmitting(false);
    }
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

      <div className="flex h-screen">
        {/* 侧边栏 */}
        <div className="w-64 bg-white border-r border-slate-200 shadow-lg relative">
          <div className="p-6 border-b border-slate-200">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-blue-700 rounded-lg flex items-center justify-center">
                <BrainCircuit className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-slate-900">碳硅之辩</h1>
                <p className="text-xs text-slate-500">人机思辨平台 · 教师控制台</p>
              </div>
            </div>
          </div>

          <nav className="p-4">
            {menuItems.map((item) => {
              const IconComponent = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 mb-1 ${
                    activeTab === item.id
                      ? 'bg-blue-100 text-blue-700 border-l-4 border-blue-600'
                      : 'hover:bg-slate-100 text-slate-700'
                  }`}
                >
                  <IconComponent className="w-5 h-5" />
                  <span className="font-medium">{item.label}</span>
                </button>
              );
            })}
          </nav>

          {/* 侧边栏底部 - 登出按钮 */}
          <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-slate-200">
            <button
              onClick={onLogout}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 hover:bg-red-50 text-red-600 hover:text-red-700"
            >
              <Settings className="w-5 h-5" />
              <span className="font-medium">退出登录</span>
            </button>
          </div>
        </div>

        {/* 主内容区 */}
        <div className="flex-1 overflow-auto">
          <div className="p-8">
            {/* 页面标题和状态看板 */}
            <div className="mb-8">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h1 className="text-3xl font-bold text-slate-900 mb-2">
                    教师控制台
                  </h1>
                  <p className="text-slate-600">管理辩论任务，监控学生进度</p>
                </div>
                <div className="flex gap-2">
                  <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                    <Users className="w-4 h-4 mr-1" />
                    {stats.totalStudents} 学生
                  </Badge>
                  <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200">
                    <Play className="w-4 h-4 mr-1" />
                    {stats.activeDebates} 进行中
                  </Badge>
                </div>
              </div>

              {/* 统计卡片 */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-blue-700">进行中辩论</p>
                        <p className="text-2xl font-bold text-blue-900">{stats.activeDebates}</p>
                      </div>
                      <Play className="w-8 h-8 text-blue-600 opacity-50" />
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-gradient-to-br from-emerald-50 to-emerald-100 border-emerald-200">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-emerald-700">已完成辩论</p>
                        <p className="text-2xl font-bold text-emerald-900">{stats.completedDebates}</p>
                      </div>
                      <CheckCircle className="w-8 h-8 text-emerald-600 opacity-50" />
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-amber-700">今日辩论</p>
                        <p className="text-2xl font-bold text-amber-900">{stats.todayDebates}</p>
                      </div>
                      <Calendar className="w-8 h-8 text-amber-600 opacity-50" />
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-purple-700">参与学生</p>
                        <p className="text-2xl font-bold text-purple-900">{stats.totalStudents}</p>
                      </div>
                      <Users className="w-8 h-8 text-purple-600 opacity-50" />
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>

            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsContent value="new" className="space-y-6">
                {/* 新建辩论表单 */}
                <Card className="bg-white border-slate-200 shadow-sm">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-slate-900">
                      <Plus className="w-5 h-5 text-blue-600" />
                      创建新辩论
                    </CardTitle>
                    <CardDescription>
                      配置辩论参数并导入学生名单
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {/* 班级选择 */}
                    <div className="space-y-2">
                      <Label className="text-slate-700 font-medium">选择班级</Label>
                      <Select
                        value={debateConfig.class_id}
                        onValueChange={(value) => {
                          setDebateConfig({ ...debateConfig, class_id: value });
                          setSelectedClass(value);
                        }}
                      >
                        <SelectTrigger className="border-slate-300 focus:border-blue-500 focus:ring-blue-500">
                          <SelectValue placeholder="请选择班级" />
                        </SelectTrigger>
                        <SelectContent>
                          {classes.map(cls => (
                            <SelectItem key={cls.id} value={cls.id}>
                              {cls.name} ({cls.code})
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    {/* 辩论主题 */}
                    <div className="space-y-2">
                      <Label htmlFor="topic" className="text-slate-700 font-medium">
                        辩论主题
                      </Label>
                      <Textarea
                        id="topic"
                        value={debateConfig.topic}
                        onChange={(e) => setDebateConfig({ ...debateConfig, topic: e.target.value })}
                        className="min-h-[80px] border-slate-300 focus:border-blue-500 focus:ring-blue-500"
                        placeholder="输入辩论主题..."
                      />
                    </div>

                    {/* 赛制设置 */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label className="text-slate-700 font-medium">辩论时长</Label>
                        <Select
                          value={debateConfig.duration}
                          onValueChange={(value) => setDebateConfig({ ...debateConfig, duration: value })}
                        >
                          <SelectTrigger className="border-slate-300 focus:border-blue-500 focus:ring-blue-500">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="15">15分钟</SelectItem>
                            <SelectItem value="30">30分钟</SelectItem>
                            <SelectItem value="45">45分钟</SelectItem>
                            <SelectItem value="60">60分钟</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-2">
                        <Label className="text-slate-700 font-medium">发言轮次</Label>
                        <Select
                          value={debateConfig.rounds}
                          onValueChange={(value) => setDebateConfig({ ...debateConfig, rounds: value })}
                        >
                          <SelectTrigger className="border-slate-300 focus:border-blue-500 focus:ring-blue-500">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="2">2轮</SelectItem>
                            <SelectItem value="3">3轮</SelectItem>
                            <SelectItem value="4">4轮</SelectItem>
                            <SelectItem value="5">5轮</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <Separator />

                    {/* 学生选择 */}
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <Label className="text-slate-700 font-medium">
                          选择辩手 ({selectedStudentIds.length}/4)
                        </Label>
                        <Users className="w-4 h-4 text-slate-500" />
                      </div>

                      {students.length === 0 ? (
                        <div className="text-center py-8 bg-slate-50 rounded-lg border border-slate-200 border-dashed">
                          <p className="text-slate-500">当前班级暂无学生</p>
                        </div>
                      ) : (
                        <Card className="bg-slate-50 border-slate-200">
                          <CardContent className="p-0">
                            <div className="max-h-60 overflow-y-auto divide-y divide-slate-200">
                              {students.map((student) => (
                                <div
                                  key={student.id}
                                  className={`flex items-center justify-between p-3 hover:bg-slate-100 transition-colors cursor-pointer ${
                                    selectedStudentIds.includes(student.id) ? 'bg-blue-50 hover:bg-blue-100' : ''
                                  }`}
                                  onClick={() => handleStudentToggle(student.id)}
                                >
                                  <div className="flex items-center gap-3">
                                    <Checkbox
                                      checked={selectedStudentIds.includes(student.id)}
                                      onCheckedChange={() => handleStudentToggle(student.id)}
                                    />
                                    <div className="w-8 h-8 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-sm font-medium">
                                      {student.name.charAt(0)}
                                    </div>
                                    <div>
                                      <p className="font-medium text-slate-900 text-sm">{student.name}</p>
                                      <p className="text-xs text-slate-500">{student.email || student.account}</p>
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </CardContent>
                        </Card>
                      )}
                    </div>

                    {/* 发布按钮 */}
                    <div className="flex justify-end gap-3 pt-4">
                      {editingDebateId ? (
                          <Button variant="outline" className="border-slate-300 text-slate-700" onClick={handleCancelEdit}>
                              <X className="w-4 h-4 mr-2" />
                              取消编辑
                          </Button>
                      ) : (
                        <Button variant="outline" className="border-slate-300 text-slate-700">
                          保存草稿
                        </Button>
                      )}
                      <Button
                        onClick={handleCreateDebate}
                        disabled={submitting || !debateConfig.class_id}
                        className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white px-8"
                      >
                        {submitting ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            {editingDebateId ? '保存中...' : '智能分组中...'}
                          </>
                        ) : (
                          <>
                            {editingDebateId ? (
                                <>
                                    <Pencil className="w-4 h-4 mr-2" />
                                    保存修改
                                </>
                            ) : (
                                <>
                                    <Play className="w-4 h-4 mr-2" />
                                    发布辩论任务
                                </>
                            )}
                          </>
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="history">
                <Card>
                  <CardHeader>
                    <CardTitle>历史记录</CardTitle>
                    <CardDescription>查看过去的辩论记录</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {debates.length === 0 ? (
                      <p className="text-slate-500 text-center py-8">暂无历史记录</p>
                    ) : (
                      <div className="space-y-3">
                        {debates.map(debate => (
                          <Collapsible
                            key={debate.id}
                            open={!!groupingOpenByDebateId[debate.id]}
                            onOpenChange={(open) => setGroupingOpen(debate.id, open)}
                          >
                            <div className="p-4 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors">
                              <div className="flex items-center justify-between">
                                <div>
                                  <h4 className="font-medium text-slate-900">{debate.topic}</h4>
                                  <p className="text-sm text-slate-600">
                                    {new Date(debate.created_at).toLocaleDateString('zh-CN')} • {debate.duration}分钟
                                  </p>
                                </div>
                                <div className="flex items-center gap-3">
                                  <Badge className={
                                    debate.status === 'completed' ? 'bg-emerald-100 text-emerald-700' :
                                    debate.status === 'in_progress' ? 'bg-blue-100 text-blue-700' :
                                    'bg-slate-100 text-slate-700'
                                  }>
                                    {debate.status === 'completed' ? '已完成' :
                                     debate.status === 'in_progress' ? '进行中' :
                                     debate.status === 'published' ? '已发布' : '草稿'}
                                  </Badge>
                                  <div className="flex gap-2">
                                      <CollapsibleTrigger asChild>
                                        <Button
                                          variant="outline"
                                          size="sm"
                                          className="h-8 px-2"
                                        >
                                          {groupingOpenByDebateId[debate.id] ? (
                                            <ChevronUp className="w-4 h-4 mr-1" />
                                          ) : (
                                            <ChevronDown className="w-4 h-4 mr-1" />
                                          )}
                                          智能分组
                                        </Button>
                                      </CollapsibleTrigger>
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => handleEditDebate(debate)}
                                        className="h-8 px-2"
                                      >
                                        <Pencil className="w-4 h-4 mr-1" />
                                        编辑
                                      </Button>
                                      {/*<Button
                                        size="sm"
                                        className="h-8 px-3 bg-blue-600 hover:bg-blue-700 text-white"
                                        onClick={() => {
                                          onNavigate('debate', debate.id);
                                        }}
                                      >
                                        进入
                                      </Button> */}
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        className="h-8 px-2"
                                        disabled={debate.status !== 'completed'}
                                        onClick={() => onNavigate('debate-report', debate.id)}
                                      >
                                        报告
                                      </Button>
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        className="h-8 px-2"
                                        disabled={debate.status !== 'completed'}
                                        onClick={() => onNavigate('debate-replay', debate.id)}
                                      >
                                        回放
                                      </Button>
                                  </div>
                                </div>
                              </div>
                              {debate.invitation_code && (
                                <div className="mt-2 text-sm text-slate-600">
                                  邀请码: <span className="font-mono font-bold">{debate.invitation_code}</span>
                                </div>
                              )}
                              <CollapsibleContent>
                                <div className="mt-3 border-t border-slate-200 pt-3">
                                  {groupingLoadingByDebateId[debate.id] ? (
                                    <div className="flex items-center text-sm text-slate-600">
                                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                      正在生成分组信息...
                                    </div>
                                  ) : (
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                      {(debateDetailsById[debate.id]?.grouping || debate.grouping || []).map((item) => (
                                        <div
                                          key={`${debate.id}-${item.user_id}`}
                                          className="flex items-center justify-between p-3 bg-white rounded-lg border border-slate-200"
                                        >
                                          <div className="flex items-center gap-3">
                                            <div className="w-9 h-9 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center font-medium">
                                              {(item.name || ' ').charAt(0) || '?'}
                                            </div>
                                            <div>
                                              <div className="flex items-center gap-2">
                                                <Badge variant="outline" className="bg-slate-50 text-slate-700 border-slate-200">
                                                  {roleLabel[item.role]}
                                                </Badge>
                                                <span className="font-medium text-slate-900">
                                                  {item.name || item.user_id.slice(0, 8)}
                                                </span>
                                              </div>
                                            </div>
                                          </div>
                                          <Badge className="bg-blue-50 text-blue-700 border-blue-200">
                                            {item.role_reason || '—'}
                                          </Badge>
                                        </div>
                                      ))}
                                      {((debateDetailsById[debate.id]?.grouping || debate.grouping || []).length === 0) && (
                                        <div className="text-sm text-slate-500">暂无分组信息</div>
                                      )}
                                    </div>
                                  )}
                                </div>
                              </CollapsibleContent>
                            </div>
                          </Collapsible>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="students">
                <Card>
                  <CardHeader>
                    <CardTitle>学生管理</CardTitle>
                    {/* <CardDescription>管理参与辩论的学生</CardDescription> */}
                  </CardHeader>
                  <CardContent>
                    {students.length === 0 ? (
                      <p className="text-slate-500 text-center py-8">暂无学生数据</p>
                    ) : (
                      <div className="space-y-2">
                        {students.map(student => (
                          <div key={student.id} className="flex items-center justify-between p-3 border border-slate-200 rounded-lg">
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center font-medium">
                                {student.name.charAt(0)}
                              </div>
                              <div>
                                <p className="font-medium text-slate-900">{student.name}</p>
                                <p className="text-sm text-slate-600">{student.email || student.account}</p>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="analytics">
                <Card>
                  <CardHeader>
                    <CardTitle>数据分析</CardTitle>
                    <CardDescription>查看辩论数据统计</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <p className="text-slate-500 text-center py-8">暂无分析数据</p>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="profile">
                {user && <UserProfile user={user} onUpdate={() => {}} />}
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TeacherDashboard;
