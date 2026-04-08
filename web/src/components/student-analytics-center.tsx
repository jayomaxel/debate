import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useAuth } from '@/store/auth.context';
import { useToast } from '@/hooks/use-toast';
import StudentService from '@/services/student.service';
import type { StudentAnalytics, DebateHistoryItem, Achievement, ClassComparison } from '@/services/student.service';
import DebateHistoryRecords from '@/components/debate-history-records';
import AbilityRadarChart from '@/components/ability-radar-chart';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  ArrowLeft,
  History,
  TrendingUp,
  Users,
  Trophy,
  Loader2,
  Calendar,
  Target,
  Award,
  Star,
  BarChart3,
  Clock,
  CheckCircle,
  Lock,
  RefreshCw,
  Brain,
  Zap,
  Heart
} from 'lucide-react';

interface StudentAnalyticsCenterProps {
  onBack?: () => void;
  onViewReport?: (debateId: string) => void;
  onViewReplay?: (debateId: string) => void;
}

type MenuTab = 'history' | 'growth' | 'comparison' | 'achievements';

const StudentAnalyticsCenter: React.FC<StudentAnalyticsCenterProps> = ({ onBack, onViewReport, onViewReplay }) => {
  const { user } = useAuth();
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<MenuTab>('history');
  const [loading, setLoading] = useState(true);
  
  // 数据状态
  const [analytics, setAnalytics] = useState<StudentAnalytics | null>(null);
  const [history, setHistory] = useState<DebateHistoryItem[]>([]);
  const [growthTrend, setGrowthTrend] = useState<any[]>([]);
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [comparison, setComparison] = useState<ClassComparison | null>(null);
  const [comparisonMetric, setComparisonMetric] = useState<string>('overall');
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [comparisonNotice, setComparisonNotice] = useState('');
  const [checkingAchievements, setCheckingAchievements] = useState(false);
  const [recentlyUnlockedAchievementIds, setRecentlyUnlockedAchievementIds] = useState<string[]>([]);
  const achievementsAutoCheckedRef = useRef(false);

  const isMissingClassError = (error: any) => {
    const message = String(error?.message || error?.detail || '');
    return message.includes('未加入班级');
  };

  // 加载数据
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);

        const [analyticsResult, historyResult, growthResult, achievementsResult] = await Promise.allSettled([
          StudentService.getAnalytics(),
          StudentService.getHistory(20, 0),
          StudentService.getGrowthTrend(10),
          StudentService.getAchievements()
        ]);

        if (analyticsResult.status === 'fulfilled') {
          setAnalytics(analyticsResult.value);
        } else {
          toast({
            variant: "destructive",
            title: "加载失败",
            description: (analyticsResult.reason as any)?.message || '加载统计数据失败',
          });
        }

        if (historyResult.status === 'fulfilled') {
          setHistory(historyResult.value?.list || []);
        } else {
          toast({
            variant: "destructive",
            title: "加载失败",
            description: (historyResult.reason as any)?.message || '加载历史记录失败',
          });
        }

        if (growthResult.status === 'fulfilled') {
          setGrowthTrend(growthResult.value?.debates || []);
        }

        if (achievementsResult.status === 'fulfilled') {
          setAchievements(achievementsResult.value || []);
        }
      } catch (err: any) {
        console.error('Failed to load analytics data:', err);
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

  const loadComparison = async (metric: string) => {
    try {
      setComparisonLoading(true);
      setComparisonNotice('');
      const data = await StudentService.getClassComparison({ metric, top: 10 });
      setComparison(data);
    } catch (err: any) {
      setComparison(null);
      if (isMissingClassError(err)) {
        setComparisonNotice('您还未加入班级');
        return;
      }
      toast({
        variant: "destructive",
        title: "加载失败",
        description: err?.message || '加载对比数据失败',
      });
    } finally {
      setComparisonLoading(false);
    }
  };

  useEffect(() => {
    loadComparison(comparisonMetric);
  }, [comparisonMetric]);

  const handleCheckAchievements = async () => {
    try {
      setCheckingAchievements(true);
      const result = await StudentService.checkAchievements();
      if (result.count > 0) {
        setRecentlyUnlockedAchievementIds(result.newly_unlocked.map(a => a.id));
        toast({
          title: "解锁成功",
          description: `新解锁 ${result.count} 个成就`,
        });
      } else {
        toast({
          title: "暂无新成就",
          description: "继续加油，下一枚徽章就在不远处",
        });
      }

      const updated = await StudentService.getAchievements();
      setAchievements(updated || []);
      if (result.count > 0) {
        window.setTimeout(() => {
          setRecentlyUnlockedAchievementIds([]);
        }, 1600);
      }
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "检查失败",
        description: err?.message || '检查成就失败',
      });
    } finally {
      setCheckingAchievements(false);
    }
  };

  useEffect(() => {
    if (activeTab !== 'achievements' || achievementsAutoCheckedRef.current) {
      return;
    }

    achievementsAutoCheckedRef.current = true;
    (async () => {
      try {
        setCheckingAchievements(true);
        const result = await StudentService.checkAchievements();
        if (result.count > 0) {
          toast({
            title: "已更新成就",
            description: `自动解锁 ${result.count} 个成就`,
          });
          const updated = await StudentService.getAchievements();
          setAchievements(updated || []);
        }
      } catch (err) {
        console.error('[StudentAnalyticsCenter] Auto check achievements failed:', err);
      } finally {
        setCheckingAchievements(false);
      }
    })();
  }, [activeTab]);

  const menuItems = [
    { id: 'history' as MenuTab, icon: <History className="w-5 h-5" />, label: '历史记录', desc: '查看历史辩论' },
    { id: 'growth' as MenuTab, icon: <TrendingUp className="w-5 h-5" />, label: '成长趋势', desc: '能力发展分析' },
    { id: 'comparison' as MenuTab, icon: <Users className="w-5 h-5" />, label: '对比分析', desc: '表现对比' },
    { id: 'achievements' as MenuTab, icon: <Trophy className="w-5 h-5" />, label: '成就系统', desc: '成就与徽章' },
  ];

  // 渲染历史记录
  const renderHistory = () => {
    return (
      <DebateHistoryRecords
        history={history}
        onSelect={(debateId) => onViewReport?.(debateId)}
        onReplay={(debateId) => onViewReplay?.(debateId)}
      />
    );
  };

  // 渲染成长趋势
  const renderGrowth = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-2xl font-bold text-slate-900">能力成长趋势</h3>
          <p className="text-slate-600 mt-1">追踪您的能力发展轨迹</p>
        </div>
      </div>

      {/* 总体统计 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-2">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <BarChart3 className="w-6 h-6 text-blue-600" />
              </div>
            </div>
            <div className="text-2xl font-bold text-slate-900 mb-1">
              {analytics?.average_score?.toFixed(1) || 0}
            </div>
            <div className="text-sm text-slate-600">平均得分</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-2">
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-green-600" />
              </div>
            </div>
            <div className="text-2xl font-bold text-slate-900 mb-1">
              {analytics?.completed_debates || 0}
            </div>
            <div className="text-sm text-slate-600">完成场次</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-2">
              <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                <Clock className="w-6 h-6 text-purple-600" />
              </div>
            </div>
            <div className="text-2xl font-bold text-slate-900 mb-1">
              {analytics?.total_debates || 0}
            </div>
            <div className="text-sm text-slate-600">总参与场次</div>
          </CardContent>
        </Card>
      </div>

      {/* 成长曲线 */}
      <Card>
        <CardHeader>
          <CardTitle>得分趋势</CardTitle>
        </CardHeader>
        <CardContent>
          {growthTrend.length > 0 ? (
            <div className="space-y-3">
              {growthTrend.map((item, index) => (
                <div key={index} className="flex items-center gap-4">
                  <div className="text-sm text-slate-600 w-24">
                    {new Date(item.date).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })}
                  </div>
                  <div className="flex-1">
                    <div className="h-8 bg-slate-100 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full flex items-center justify-end pr-2"
                        style={{ width: `${item.score}%` }}
                      >
                        <span className="text-xs text-white font-medium">{item.score}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <TrendingUp className="w-16 h-16 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-500">暂无成长数据</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );

  // 渲染对比分析
  const renderComparison = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-2xl font-bold text-slate-900">表现对比分析</h3>
          <p className="text-slate-600 mt-1">与其他学生的表现对比</p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={comparisonMetric} onValueChange={setComparisonMetric}>
            <SelectTrigger className="w-[160px] bg-white">
              <SelectValue placeholder="选择指标" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="overall">综合得分</SelectItem>
              <SelectItem value="logic">逻辑建构力</SelectItem>
              <SelectItem value="argument">AI核心知识运用</SelectItem>
              <SelectItem value="response">批判性思维</SelectItem>
              <SelectItem value="persuasion">语言表达力</SelectItem>
              <SelectItem value="teamwork">AI伦理与科技素养</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            className="bg-white"
            onClick={() => loadComparison(comparisonMetric)}
            disabled={comparisonLoading}
          >
            {comparisonLoading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <RefreshCw className="w-4 h-4 mr-2" />}
            刷新
          </Button>
        </div>
      </div>

      {comparisonLoading ? (
        <Card className="bg-white border-slate-200 shadow-sm">
          <CardContent className="p-12 text-center">
            <Loader2 className="w-10 h-10 text-blue-600 animate-spin mx-auto mb-4" />
            <p className="text-slate-600">加载对比数据中...</p>
          </CardContent>
        </Card>
      ) : comparisonNotice ? (
        <Card className="bg-gradient-to-br from-amber-50 to-orange-50 border-amber-200">
          <CardContent className="p-12 text-center">
            <Users className="w-16 h-16 text-amber-400 mx-auto mb-4" />
            <h4 className="text-xl font-semibold text-slate-900 mb-2">{comparisonNotice}</h4>
            <p className="text-slate-600">
              加入班级后，这里会展示你与班级同学的对比分析与排行榜
            </p>
          </CardContent>
        </Card>
      ) : !comparison || comparison.sample_size === 0 ? (
        <Card className="bg-gradient-to-br from-blue-50 to-purple-50 border-blue-200">
          <CardContent className="p-12 text-center">
            <Users className="w-16 h-16 text-blue-400 mx-auto mb-4" />
            <h4 className="text-xl font-semibold text-slate-900 mb-2">暂无可对比数据</h4>
            <p className="text-slate-600">
              完成更多辩论后，将自动生成与班级同学的对比分析与排行榜
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="bg-white border-slate-200 shadow-sm">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-2">
                  <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                    <Trophy className="w-6 h-6 text-blue-600" />
                  </div>
                </div>
                <div className="text-2xl font-bold text-slate-900 mb-1">
                  {comparison.my?.rank ? `#${comparison.my.rank}` : '-'}
                </div>
                <div className="text-sm text-slate-600">班级排名</div>
                <div className="text-xs text-slate-500 mt-1">{comparison.class_name || '我的班级'}</div>
              </CardContent>
            </Card>

            <Card className="bg-white border-slate-200 shadow-sm">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-2">
                  <div className="w-12 h-12 bg-emerald-100 rounded-lg flex items-center justify-center">
                    <Star className="w-6 h-6 text-emerald-600" />
                  </div>
                </div>
                <div className="text-2xl font-bold text-slate-900 mb-1">
                  {comparison.my?.percentile !== null && comparison.my?.percentile !== undefined ? `${comparison.my.percentile}%` : '-'}
                </div>
                <div className="text-sm text-slate-600">领先百分位</div>
                <div className="text-xs text-slate-500 mt-1">基于班级样本</div>
              </CardContent>
            </Card>

            <Card className="bg-white border-slate-200 shadow-sm">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-2">
                  <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                    <BarChart3 className="w-6 h-6 text-purple-600" />
                  </div>
                </div>
                <div className="text-2xl font-bold text-slate-900 mb-1">
                  {comparison.my?.score?.toFixed(1) || 0}
                </div>
                <div className="text-sm text-slate-600">我的当前指标</div>
                <div className="text-xs text-slate-500 mt-1">可切换指标查看</div>
              </CardContent>
            </Card>

            <Card className="bg-white border-slate-200 shadow-sm">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-2">
                  <div className="w-12 h-12 bg-amber-100 rounded-lg flex items-center justify-center">
                    <Users className="w-6 h-6 text-amber-700" />
                  </div>
                </div>
                <div className="text-2xl font-bold text-slate-900 mb-1">
                  {comparison.class_avg?.score?.toFixed(1) || 0}
                </div>
                <div className="text-sm text-slate-600">班级平均指标</div>
                <div className="text-xs text-slate-500 mt-1">{comparison.sample_size} 人样本</div>
              </CardContent>
            </Card>
          </div>

          <AbilityRadarChart
            title="五维能力对比（我 vs 班级平均）"
            showComparison
            comparisonScores={[
              comparison.class_avg?.ability_scores.logic || 0,
              comparison.class_avg?.ability_scores.argument || 0,
              comparison.class_avg?.ability_scores.response || 0,
              comparison.class_avg?.ability_scores.persuasion || 0,
              comparison.class_avg?.ability_scores.teamwork || 0,
            ]}
            scores={[
              {
                dimension: '逻辑建构力',
                score: comparison.my?.ability_scores.logic || 0,
                icon: <Brain className="w-4 h-4" />,
                description: '观点结构、推理链条与论证严密性',
                color: 'text-blue-600',
              },
              {
                dimension: 'AI核心知识运用',
                score: comparison.my?.ability_scores.argument || 0,
                icon: <Target className="w-4 h-4" />,
                description: 'AI概念、案例与课程知识点的调用能力',
                color: 'text-emerald-600',
              },
              {
                dimension: '批判性思维',
                score: comparison.my?.ability_scores.response || 0,
                icon: <Zap className="w-4 h-4" />,
                description: '识别漏洞、提出质疑与展开反驳的能力',
                color: 'text-amber-600',
              },
              {
                dimension: '语言表达力',
                score: comparison.my?.ability_scores.persuasion || 0,
                icon: <Heart className="w-4 h-4" />,
                description: '表达清晰度、感染力与说服效果',
                color: 'text-rose-600',
              },
              {
                dimension: 'AI伦理与科技素养',
                score: comparison.my?.ability_scores.teamwork || 0,
                icon: <Users className="w-4 h-4" />,
                description: '对技术边界、伦理风险与社会影响的综合判断',
                color: 'text-purple-600',
              }
            ]}
          />

          <Card className="bg-white border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Trophy className="w-5 h-5 text-amber-600" />
                  班级排行榜
                </div>
                <Badge className="bg-slate-100 text-slate-700 border-slate-300">
                  Top {comparison.leaderboard.length}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {comparison.leaderboard.map((item) => {
                  const isMe = item.student_id === user?.id;
                  return (
                    <div
                      key={item.student_id}
                      className={`flex items-center justify-between p-4 rounded-lg border ${
                        isMe ? 'border-blue-300 bg-blue-50' : 'border-slate-200 bg-white'
                      }`}
                    >
                      <div className="flex items-center gap-4">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center font-bold ${
                          item.rank === 1 ? 'bg-amber-100 text-amber-700' :
                          item.rank === 2 ? 'bg-slate-100 text-slate-700' :
                          item.rank === 3 ? 'bg-orange-100 text-orange-700' :
                          'bg-slate-50 text-slate-600'
                        }`}>
                          {item.rank}
                        </div>
                        <div>
                          <div className="font-semibold text-slate-900 flex items-center gap-2">
                            <span>{item.student_name}</span>
                            {isMe && (
                              <Badge className="bg-blue-600 text-white border-blue-600">我</Badge>
                            )}
                          </div>
                          <div className="text-xs text-slate-500">
                            综合均分 {item.overall_score.toFixed(1)}
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-bold text-slate-900">{item.score.toFixed(1)}</div>
                        <div className="text-xs text-slate-500">当前指标</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );

  // 渲染成就系统
  const renderAchievements = () => {
    const unlockedAchievements = achievements.filter(a => a.unlocked);
    const lockedAchievements = achievements.filter(a => !a.unlocked);

    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-2xl font-bold text-slate-900">成就与徽章</h3>
            <p className="text-slate-600 mt-1">收集成就，展示您的辩论实力</p>
          </div>
          <div className="flex items-center gap-3">
            <Badge className="bg-amber-100 text-amber-700 border-amber-300">
              {unlockedAchievements.length} / {achievements.length} 已解锁
            </Badge>
            <Button
              variant="outline"
              className="bg-white"
              onClick={handleCheckAchievements}
              disabled={checkingAchievements}
            >
              {checkingAchievements ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Star className="w-4 h-4 mr-2" />
              )}
              检查新成就
            </Button>
          </div>
        </div>

        {/* 已解锁成就 */}
        {unlockedAchievements.length > 0 && (
          <div>
            <h4 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-600" />
              已解锁成就
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {unlockedAchievements.map((achievement) => {
                const isNewlyUnlocked = recentlyUnlockedAchievementIds.includes(achievement.id);
                return (
                <Card
                  key={achievement.id}
                  className={`relative overflow-hidden border-amber-200 bg-gradient-to-br from-amber-50 via-white to-emerald-50 shadow-sm transition-all hover:shadow-lg hover:-translate-y-0.5 ${
                    isNewlyUnlocked ? 'ring-2 ring-amber-400 shadow-[0_0_30px_rgba(245,158,11,0.35)] animate-in fade-in zoom-in-95 duration-500' : ''
                  }`}
                >
                  {isNewlyUnlocked && (
                    <div className="absolute inset-0 bg-gradient-to-r from-amber-200/20 via-transparent to-emerald-200/20 animate-pulse" />
                  )}
                  <CardContent className="p-6 relative">
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 bg-gradient-to-br from-amber-400 to-orange-500 rounded-full flex items-center justify-center flex-shrink-0 text-white text-xl">
                        {achievement.icon || '🏅'}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-start justify-between gap-3">
                          <h5 className="font-semibold text-slate-900 mb-1">{achievement.name}</h5>
                          <Badge className="bg-emerald-100 text-emerald-700 border-emerald-300">
                            <CheckCircle className="w-3 h-3 mr-1" />
                            已解锁
                          </Badge>
                        </div>
                        <p className="text-sm text-slate-600 mb-2">{achievement.description}</p>
                        {achievement.unlocked_at && (
                          <p className="text-xs text-slate-500">
                            解锁于 {new Date(achievement.unlocked_at).toLocaleDateString('zh-CN')}
                          </p>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )})}
            </div>
          </div>
        )}

        {/* 未解锁成就 */}
        {lockedAchievements.length > 0 && (
          <div>
            <h4 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Lock className="w-5 h-5 text-slate-400" />
              待解锁成就
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {lockedAchievements.map((achievement) => (
                <Card key={achievement.id} className="border-slate-200 bg-slate-50/50 opacity-75">
                  <CardContent className="p-6">
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 bg-slate-200 rounded-full flex items-center justify-center flex-shrink-0 text-slate-500 text-xl">
                        {achievement.icon || '🔒'}
                      </div>
                      <div className="flex-1">
                        <h5 className="font-semibold text-slate-700 mb-1">{achievement.name}</h5>
                        <p className="text-sm text-slate-500 mb-2">{achievement.description}</p>
                        {achievement.progress !== undefined && achievement.target !== undefined && (
                          <div className="mt-2">
                            <div className="flex items-center justify-between text-xs text-slate-600 mb-1">
                              <span>进度</span>
                              <span>{achievement.progress} / {achievement.target}</span>
                            </div>
                            <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                              <div 
                                className="h-full bg-blue-500 rounded-full"
                                style={{ width: `${(achievement.progress / achievement.target) * 100}%` }}
                              />
                            </div>
                          </div>
                        )}
                        {achievement.unlock_hint && (
                          <div className="mt-2 text-xs text-slate-600">
                            {achievement.unlock_hint}
                          </div>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {achievements.length === 0 && (
          <Card>
            <CardContent className="p-12 text-center">
              <Trophy className="w-16 h-16 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-500">暂无成就数据</p>
            </CardContent>
          </Card>
        )}
      </div>
    );
  };

  // 渲染内容区域
  const renderContent = () => {
    switch (activeTab) {
      case 'history':
        return renderHistory();
      case 'growth':
        return renderGrowth();
      case 'comparison':
        return renderComparison();
      case 'achievements':
        return renderAchievements();
      default:
        return null;
    }
  };

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
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={onBack} className="flex items-center gap-2">
              <ArrowLeft className="w-4 h-4" />
              返回
            </Button>
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-slate-900">{user?.name} 的分析中心</h1>
              <p className="text-sm text-slate-600">详细的辩论表现分析和个性化改进建议</p>
            </div>
          </div>
        </div>
      </header>

      {/* 主要内容 */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-12 gap-6">
          {/* 左侧菜单 */}
          <div className="col-span-12 lg:col-span-3">
            <Card className="bg-white border-slate-200 shadow-sm sticky top-6">
              <CardContent className="p-4">
                <div className="space-y-2">
                  {menuItems.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => setActiveTab(item.id)}
                      className={`w-full flex items-start gap-3 p-4 rounded-lg transition-all ${
                        activeTab === item.id
                          ? 'bg-blue-600 text-white shadow-md'
                          : 'hover:bg-slate-50 text-slate-700'
                      }`}
                    >
                      <div className={`flex-shrink-0 ${activeTab === item.id ? 'text-white' : 'text-slate-600'}`}>
                        {item.icon}
                      </div>
                      <div className="text-left">
                        <div className="font-medium">{item.label}</div>
                        <div className={`text-xs ${activeTab === item.id ? 'text-blue-100' : 'text-slate-500'}`}>
                          {item.desc}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>

                <div className="mt-6 pt-6 border-t border-slate-200">
                  <Button 
                    variant="outline" 
                    className="w-full justify-start"
                    onClick={onBack}
                  >
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    收起菜单
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 右侧内容区 */}
          <div className="col-span-12 lg:col-span-9">
            {renderContent()}
          </div>
        </div>
      </div>
    </div>
  );
};

export default StudentAnalyticsCenter;
