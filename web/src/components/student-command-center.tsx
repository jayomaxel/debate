import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useAuth } from '@/store/auth.context';
import { useToast } from '@/hooks/use-toast';
import StudentService from '@/services/student.service';
import UserProfile from '@/components/user-profile';
import DebateHistoryRecords from '@/components/debate-history-records';
import type { StudentAnalytics, DebateHistoryItem, Debate, KBDocument } from '@/services/student.service';
import {
  User,
  Trophy,
  Target,
  TrendingUp,
  Clock,
  BookOpen,
  ArrowRight,
  Star,
  Award,
  Sparkles,
  Rocket,
  Shield,
  Brain,
  ExternalLink,
  Search,
  Loader2,
  Settings,
  Bot
} from 'lucide-react';
// import PreparationAssistant from '@/components/student/preparation-assistant';

interface StudentStats {
  totalMatches: number;
  winRate: number;
  mvpCount: number;
  averageScore: number;
  currentStreak: number;
  bestStreak: number;
}

const formatDuration = (seconds?: number) => {
  const totalSeconds = Math.max(0, Math.floor(Number(seconds || 0)));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;
  if (hours > 0) {
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }
  return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
};

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  });
};

const getFileTypeConfig = (fileType: string) => {
  const type = fileType.toLowerCase();
  if (type.includes('pdf')) {
    return { name: 'PDF 文档', color: 'red', icon: <BookOpen className="w-4 h-4" /> };
  } else if (type.includes('word') || type.includes('docx') || type.includes('doc')) {
    return { name: 'Word 文档', color: 'blue', icon: <BookOpen className="w-4 h-4" /> };
  } else if (type.includes('text') || type.includes('plain')) {
    return { name: '文本文件', color: 'gray', icon: <BookOpen className="w-4 h-4" /> };
  } else {
    return { name: '未知格式', color: 'gray', icon: <BookOpen className="w-4 h-4" /> };
  }
};

interface StudentCommandCenterProps {
  studentName?: string;
  classCode?: string;
  onJoinClass?: (debate: Debate) => void;
  onToWaitingRoom?: () => void;
  onViewReport?: (matchId: string) => void;
  onViewReplay?: (debateId: string) => void;
  onLogout?: () => void;
  onNavigateToAnalytics?: () => void;
  onNavigateToPreparation?: () => void;
  defaultShowProfile?: boolean;
  defaultProfileTab?: 'info' | 'password' | 'ability';
}

const StudentCommandCenter: React.FC<StudentCommandCenterProps> = ({
  studentName: propStudentName,
  classCode = '',
  onJoinClass,
  onToWaitingRoom,
  onViewReport,
  onViewReplay,
  onLogout,
  onNavigateToAnalytics,
  onNavigateToPreparation,
  defaultShowProfile = false,
  defaultProfileTab = 'info',
}) => {
  const { user } = useAuth();
  const { toast } = useToast();
  const [inputClassCode, setInputClassCode] = useState('');
  const [showProfile, setShowProfile] = useState(!!defaultShowProfile);
  // Removed showPreparationAssistant as we now use navigation
  const [searchTerm, setSearchTerm] = useState('');
  // const [filterCategory, setFilterCategory] = useState<string>('all'); // 暂时移除分类筛选，后续可加回
  
  // API数据状态
  const [analytics, setAnalytics] = useState<StudentAnalytics | null>(null);
  const [history, setHistory] = useState<DebateHistoryItem[]>([]);
  const [kbDocuments, setKbDocuments] = useState<KBDocument[]>([]);
  const [loading, setLoading] = useState(true);
  
  const studentName = propStudentName || user?.name || '学生';

  // 从API数据计算统计信息
  const studentStats: StudentStats = {
    totalMatches: analytics?.total_debates || 0,
    winRate: analytics ? Math.round((analytics.completed_debates / Math.max(analytics.total_debates, 1)) * 100) : 0,
    mvpCount: 0, // 暂时没有MVP数据
    averageScore: analytics?.average_score || 0,
    currentStreak: 0, // 暂时没有连胜数据
    bestStreak: 0
  };

  // 加载数据
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);

        // 并行加载所有数据
        const [analyticsData, historyData, kbData] = await Promise.all([
          StudentService.getAnalytics(),
          StudentService.getHistory(20, 0),
          StudentService.getKBDocuments(1, 100) // 获取前100个文档
        ]);

        setAnalytics(analyticsData);
        setHistory(historyData?.list || []);
        setKbDocuments(kbData?.documents || []);
      } catch (err: any) {
        console.error('Failed to load student data:', err);
        toast({
          variant: "destructive",
          title: "加载失败",
          description: err.message || '加载数据失败',
        });
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  const handleJoinClass = async () => {
    if (inputClassCode.length === 6) {
      try {
        const debate = await StudentService.joinDebate({ invitation_code: inputClassCode });
        onJoinClass?.(debate);
        onToWaitingRoom?.();
      } catch (err: any) {
        toast({
          variant: "destructive",
          title: "加入失败",
          description: err.message || '加入课堂失败',
        });
      }
    }
  };

  const getResultConfig = (result: 'win' | 'lose' | 'draw') => {
    switch (result) {
      case 'win':
        return { color: 'emerald', bgColor: 'bg-emerald-100', textColor: 'text-emerald-700', label: '胜利' };
      case 'lose':
        return { color: 'red', bgColor: 'bg-red-100', textColor: 'text-red-700', label: '失败' };
      case 'draw':
        return { color: 'amber', bgColor: 'bg-amber-100', textColor: 'text-amber-700', label: '平局' };
    }
  };

  const filteredDocuments = kbDocuments.filter(doc => {
    const matchesSearch = doc.filename.toLowerCase().includes(searchTerm.toLowerCase());
    // const matchesCategory = filterCategory === 'all' || resource.category === filterCategory;
    return matchesSearch;
  });

  // 加载状态
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-slate-50 to-purple-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-slate-600">加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-slate-50 to-purple-50">
      {/* 顶部导航 */}
      <header className="bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <User className="w-6 h-6 text-blue-600" />
                <h1 className="text-xl font-bold text-slate-900">
                  欢迎，{studentName} 👋
                </h1>
              </div>
              <Badge className="bg-blue-100 text-blue-700 border-blue-300">
                <Star className="w-3 h-3 mr-1" />
                等级 Lv.{Math.floor(studentStats.totalMatches / 5) + 1}
              </Badge>
            </div>

            <div className="flex items-center gap-3">
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => onNavigateToPreparation?.()}
                className="flex items-center gap-2"
              >
                <Bot className="w-4 h-4" />
                备战辅助
              </Button>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => onNavigateToAnalytics?.()}
                className="flex items-center gap-2"
              >
                <TrendingUp className="w-4 h-4" />
                分析中心
              </Button>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => setShowProfile((prev) => !prev)}
                className="flex items-center gap-2"
              >
                <Settings className="w-4 h-4" />
                {showProfile ? '控制中心' : '个人中心'}
              </Button>
              <Button variant="ghost" size="sm" onClick={onLogout}>
                退出登录
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* 主要内容区域 */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* 如果显示个人中心，则渲染个人中心组件 */}
        {showProfile ? (
          <div>
            <Button 
              variant="ghost" 
              onClick={() => setShowProfile(false)}
              className="mb-4"
            >
              ← 返回控制台
            </Button>
            {user && <UserProfile user={user} initialTab={defaultProfileTab} onUpdate={() => setShowProfile(false)} />}
          </div>
        ) : (
          <>
        {/* 顶部欢迎与行动区 */}
        <div className="mb-8">
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-slate-900 mb-2">
              准备好迎接今天的挑战了吗？ 🚀
            </h2>
            <p className="text-lg text-slate-600">
              今天的辩题：AI伴侣与人类情感羁绊
            </p>
          </div>

          {/* 核心行动卡片 */}
          <Card className="bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-lg mb-6">
            <CardContent className="p-8">
              <div className="text-center">
                <div className="flex items-center justify-center gap-3 mb-6">
                  <Rocket className="w-8 h-8" />
                  <h3 className="text-2xl font-bold">加入课堂</h3>
                </div>

                <div className="max-w-md mx-auto space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      请输入 6 位课堂邀请码
                    </label>
                    <Input
                      value={inputClassCode}
                      onChange={(e) => setInputClassCode(e.target.value)}
                      placeholder="例如: ABC123"
                      maxLength={6}
                      className="text-center text-lg font-mono bg-white/20 border-white/30 text-white placeholder-white/60"
                    />
                  </div>

                  <Button
                    onClick={handleJoinClass}
                    disabled={inputClassCode.length !== 6}
                    size="lg"
                    className="w-full bg-white text-blue-600 hover:bg-blue-50 font-semibold"
                  >
                    进入候场区
                    <ArrowRight className="w-5 h-5 ml-2" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 个人数据概览 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="bg-white border-slate-200 shadow-sm">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-2">
                  <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                    <Target className="w-6 h-6 text-blue-600" />
                  </div>
                  <Trophy className="w-5 h-5 text-blue-500" />
                </div>
                <div className="text-2xl font-bold text-slate-900 mb-1">
                  {studentStats.totalMatches} 场
                </div>
                <div className="text-sm text-slate-600">总场次</div>
              </CardContent>
            </Card>

            <Card className="bg-white border-slate-200 shadow-sm">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-2">
                  <div className="w-12 h-12 bg-emerald-100 rounded-lg flex items-center justify-center">
                    <Award className="w-6 h-6 text-emerald-600" />
                  </div>
                  <TrendingUp className="w-5 h-5 text-emerald-500" />
                </div>
                <div className="text-2xl font-bold text-slate-900 mb-1">
                  {studentStats.winRate}%
                </div>
                <div className="text-sm text-slate-600">胜率</div>
              </CardContent>
            </Card>

            <Card className="bg-white border-slate-200 shadow-sm">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-2">
                  <div className="w-12 h-12 bg-amber-100 rounded-lg flex items-center justify-center">
                    <Star className="w-6 h-6 text-amber-600" />
                  </div>
                  <Sparkles className="w-5 h-5 text-amber-500" />
                </div>
                <div className="text-2xl font-bold text-slate-900 mb-1">
                  {studentStats.mvpCount} 次
                </div>
                <div className="text-sm text-slate-600">MVP次数</div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* 历史战绩列表 (全宽) */}
        <div className="mb-8">
          <DebateHistoryRecords
            history={history}
            limit={4}
            showAllButton={true}
            onSelect={(debateId) => onViewReport?.(debateId)}
            onReplay={(debateId) => onViewReplay?.(debateId)}
          />
        </div>

        {/* 底部：课程知识库 */}
        <Card className="bg-white border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-blue-600" />
              课程知识库
              <Badge variant="outline" className="ml-auto">
                {kbDocuments.length} 篇文档
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* 搜索和筛选 */}
            <div className="flex items-center gap-4 mb-6">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
                <Input
                  placeholder="搜索文档..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>

              {/* 
              <select
                value={filterCategory}
                onChange={(e) => setFilterCategory(e.target.value)}
                className="px-3 py-2 border border-slate-300 rounded-lg bg-white text-sm"
              >
                <option value="all">全部分类</option>
                <option value="policy">政策法规</option>
                <option value="technical">技术解析</option>
                <option value="debate">辩论技巧</option>
                <option value="strategy">策略思维</option>
              </select>
              */}
            </div>

            {/* 资源列表 */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredDocuments.map((doc) => {
                const fileTypeConfig = getFileTypeConfig(doc.file_type);
                
                return (
                  <div
                    key={doc.id}
                    className="p-4 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer transition-colors"
                    onClick={() => console.log('打开文档:', doc.filename)}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <div className="p-1 rounded bg-slate-100">
                          {fileTypeConfig.icon}
                        </div>
                        <span className="text-xs text-slate-600">{fileTypeConfig.name}</span>
                      </div>
                      <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                        {formatDate(doc.uploaded_at)}
                      </Badge>
                    </div>

                    <h4 className="font-medium text-slate-900 mb-2 truncate" title={doc.filename}>
                      {doc.filename}
                    </h4>

                    {/* 
                    <p className="text-sm text-slate-600 mb-3 line-clamp-2">
                      {resource.description}
                    </p>
                    */}
                    
                    <div className="flex items-center justify-between text-xs text-slate-500 mt-4">
                      <span>📦 {formatFileSize(doc.file_size)}</span>
                      <ExternalLink className="w-3 h-3" />
                    </div>
                  </div>
                );
              })}
            </div>

            {filteredDocuments.length === 0 && (
              <div className="text-center py-12">
                <BookOpen className="w-12 h-12 mx-auto text-slate-300 mb-4" />
                <p className="text-slate-500">未找到相关文档</p>
              </div>
            )}
          </CardContent>
        </Card>
          </>
        )}
      </div>

      {/* 备战辅助对话框已移除，改为全页导航 */}
    </div>
  );
};

export default StudentCommandCenter;
