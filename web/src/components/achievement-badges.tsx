import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import {
  Trophy,
  Star,
  Award,
  Target,
  Brain,
  Zap,
  Heart,
  Users,
  TrendingUp,
  Calendar,
  Flame,
  Crown,
  Shield,
  Swords,
  Gem,
  Lock,
  Unlock,
  CheckCircle,
  Clock,
  BarChart3,
  Gift,
  BookOpen,
  MessageSquare,
  ChevronRight,
  Sparkles,
  Medal
} from 'lucide-react';

interface Achievement {
  id: string;
  name: string;
  description: string;
  category: 'beginner' | 'performance' | 'consistency' | 'growth' | 'special' | 'teamwork';
  icon: React.ReactNode;
  rarity: 'common' | 'rare' | 'epic' | 'legendary';
  unlocked: boolean;
  unlockedDate?: Date;
  progress: number; // 0-100
  maxProgress: number;
  currentProgress: number;
  requirements: string[];
  reward: {
    points: number;
    title?: string;
    badge: string;
  };
  metadata?: {
    totalDebates?: number;
    averageScore?: number;
    winStreak?: number;
    improvementRate?: number;
  };
}

interface StudentStats {
  totalDebates: number;
  wins: number;
  losses: number;
  draws: number;
  averageScore: number;
  currentStreak: number;
  bestStreak: number;
  totalImprovement: number;
  lastDebateDate?: Date;
  activeDays: number;
}

interface AchievementBadgesProps {
  studentStats: StudentStats;
  studentName?: string;
  showLocked?: boolean;
  compact?: boolean;
}

const AchievementBadges: React.FC<AchievementBadgesProps> = ({
  studentStats,
  studentName = '学生',
  showLocked = true,
  compact = false
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedAchievement, setSelectedAchievement] = useState<Achievement | null>(null);

  // Generate achievements based on student stats
  const generateAchievements = (): Achievement[] => [
    // Beginner achievements
    {
      id: 'first_debate',
      name: '初出茅庐',
      description: '完成第一场辩论',
      category: 'beginner',
      icon: <Target className="w-6 h-6" />,
      rarity: 'common',
      unlocked: studentStats.totalDebates >= 1,
      unlockedDate: studentStats.totalDebates >= 1 ? new Date() : undefined,
      progress: Math.min(studentStats.totalDebates, 1),
      maxProgress: 1,
      currentProgress: studentStats.totalDebates,
      requirements: ['完成1场辩论'],
      reward: { points: 10, badge: '新手' }
    },
    {
      id: 'five_debates',
      name: '渐入佳境',
      description: '完成5场辩论',
      category: 'beginner',
      icon: <Star className="w-6 h-6" />,
      rarity: 'common',
      unlocked: studentStats.totalDebates >= 5,
      unlockedDate: studentStats.totalDebates >= 5 ? new Date() : undefined,
      progress: Math.min(studentStats.totalDebates, 5),
      maxProgress: 5,
      currentProgress: studentStats.totalDebates,
      requirements: ['完成5场辩论'],
      reward: { points: 25, badge: '辩论新手' }
    },

    // Performance achievements
    {
      id: 'perfect_score',
      name: '完美表现',
      description: '单场辩论获得90分以上',
      category: 'performance',
      icon: <Trophy className="w-6 h-6" />,
      rarity: 'epic',
      unlocked: studentStats.averageScore >= 90,
      progress: Math.min(studentStats.averageScore, 100),
      maxProgress: 90,
      currentProgress: studentStats.averageScore,
      requirements: ['单场辩论得分≥90分'],
      reward: { points: 100, badge: '优秀辩手', title: '精英' }
    },
    {
      id: 'excellent_debater',
      name: '优秀辩手',
      description: '平均得分达到85分',
      category: 'performance',
      icon: <Award className="w-6 h-6" />,
      rarity: 'rare',
      unlocked: studentStats.averageScore >= 85,
      progress: Math.min(studentStats.averageScore, 100),
      maxProgress: 85,
      currentProgress: studentStats.averageScore,
      requirements: ['平均得分≥85分'],
      reward: { points: 75, badge: '熟练辩手' }
    },
    {
      id: 'quick_responder',
      name: '反应如神',
      description: '批判性思维得分达到95分',
      category: 'performance',
      icon: <Zap className="w-6 h-6" />,
      rarity: 'rare',
      unlocked: false, // This would need specific per-debate data
      progress: 0,
      maxProgress: 95,
      currentProgress: 0,
      requirements: ['批判性思维得分≥95分'],
      reward: { points: 60, badge: '快速思考者' }
    },

    // Consistency achievements
    {
      id: 'weekly_warrior',
      name: '每周战士',
      description: '连续4周参与辩论',
      category: 'consistency',
      icon: <Calendar className="w-6 h-6" />,
      rarity: 'rare',
      unlocked: studentStats.activeDays >= 28,
      progress: studentStats.activeDays,
      maxProgress: 28,
      currentProgress: studentStats.activeDays,
      requirements: ['连续4周（每周至少1场辩论）'],
      reward: { points: 50, badge: '坚持者' }
    },
    {
      id: 'consistency_king',
      name: ' consistency之王',
      description: '连续参与20场辩论',
      category: 'consistency',
      icon: <Flame className="w-6 h-6" />,
      rarity: 'epic',
      unlocked: studentStats.currentStreak >= 20,
      progress: studentStats.currentStreak,
      maxProgress: 20,
      currentProgress: studentStats.currentStreak,
      requirements: ['连续参与20场辩论'],
      reward: { points: 120, badge: ' consistency大师', title: '坚持大师' }
    },

    // Growth achievements
    {
      id: 'rapid_improvement',
      name: '快速进步',
      description: '10场辩论内提升20分',
      category: 'growth',
      icon: <TrendingUp className="w-6 h-6" />,
      rarity: 'rare',
      unlocked: studentStats.totalImprovement >= 20,
      progress: Math.max(0, Math.min(studentStats.totalImprovement, 20)),
      maxProgress: 20,
      currentProgress: Math.max(0, studentStats.totalImprovement),
      requirements: ['10场辩论内总分提升≥20分'],
      reward: { points: 65, badge: '进步之星' }
    },
    {
      id: 'transformation',
      name: '脱胎换骨',
      description: '从及格到优秀的蜕变',
      category: 'growth',
      icon: <Sparkles className="w-6 h-6" />,
      rarity: 'legendary',
      unlocked: studentStats.totalImprovement >= 30,
      progress: Math.max(0, Math.min(studentStats.totalImprovement, 30)),
      maxProgress: 30,
      currentProgress: Math.max(0, studentStats.totalImprovement),
      requirements: ['总分提升≥30分'],
      reward: { points: 200, badge: '蜕变者', title: '进阶大师' }
    },

    // Teamwork achievements
    {
      id: 'team_player',
      name: '团队伙伴',
      description: 'AI伦理与科技素养得分达到90分',
      category: 'teamwork',
      icon: <Users className="w-6 h-6" />,
      rarity: 'rare',
      unlocked: false, // This would need specific per-debate data
      progress: 0,
      maxProgress: 90,
      currentProgress: 0,
      requirements: ['AI伦理与科技素养得分≥90分'],
      reward: { points: 55, badge: '团队核心' }
    },
    {
      id: 'leadership',
      name: '领导力',
      description: '作为队长带领团队获胜5次',
      category: 'teamwork',
      icon: <Crown className="w-6 h-6" />,
      rarity: 'epic',
      unlocked: false, // This would need captain data
      progress: 0,
      maxProgress: 5,
      currentProgress: 0,
      requirements: ['作为队长获胜5次'],
      reward: { points: 90, badge: '领袖', title: '队长' }
    },

    // Special achievements
    {
      id: 'comeback_king',
      name: '逆转之王',
      description: '在劣势情况下完成逆转获胜',
      category: 'special',
      icon: <Swords className="w-6 h-6" />,
      rarity: 'legendary',
      unlocked: false, // This would need comeback data
      progress: 0,
      maxProgress: 1,
      currentProgress: 0,
      requirements: ['劣势情况下逆转获胜'],
      reward: { points: 150, badge: '逆转者', title: '逆袭王' }
    },
    {
      id: 'perfect_record',
      name: '完美记录',
      description: '连续5场辩论获胜',
      category: 'special',
      icon: <Crown className="w-6 h-6" />,
      rarity: 'epic',
      unlocked: studentStats.bestStreak >= 5,
      progress: studentStats.bestStreak,
      maxProgress: 5,
      currentProgress: studentStats.bestStreak,
      requirements: ['连续5场辩论获胜'],
      reward: { points: 110, badge: '连胜者', title: '连胜大师' }
    },
    {
      id: 'debate_master',
      name: '辩论大师',
      description: '完成100场辩论',
      category: 'special',
      icon: <Gem className="w-6 h-6" />,
      rarity: 'legendary',
      unlocked: studentStats.totalDebates >= 100,
      progress: Math.min(studentStats.totalDebates, 100),
      maxProgress: 100,
      currentProgress: studentStats.totalDebates,
      requirements: ['完成100场辩论'],
      reward: { points: 500, badge: '大师', title: '辩论宗师' }
    }
  ];

  const achievements = generateAchievements();

  const categories = [
    { id: 'all', name: '全部', icon: <Star className="w-4 h-4" /> },
    { id: 'beginner', name: '新手', icon: <Target className="w-4 h-4" /> },
    { id: 'performance', name: '表现', icon: <Trophy className="w-4 h-4" /> },
    { id: 'consistency', name: '坚持', icon: <Calendar className="w-4 h-4" /> },
    { id: 'growth', name: '成长', icon: <TrendingUp className="w-4 h-4" /> },
    { id: 'teamwork', name: '团队', icon: <Users className="w-4 h-4" /> },
    { id: 'special', name: '特殊', icon: <Gem className="w-4 h-4" /> }
  ];

  const rarityConfig = {
    common: {
      color: 'bg-slate-100 text-slate-700 border-slate-300',
      borderColor: 'border-slate-300',
      textColor: 'text-slate-700',
      name: '普通'
    },
    rare: {
      color: 'bg-blue-100 text-blue-700 border-blue-300',
      borderColor: 'border-blue-300',
      textColor: 'text-blue-700',
      name: '稀有'
    },
    epic: {
      color: 'bg-purple-100 text-purple-700 border-purple-300',
      borderColor: 'border-purple-300',
      textColor: 'text-purple-700',
      name: '史诗'
    },
    legendary: {
      color: 'bg-amber-100 text-amber-700 border-amber-300',
      borderColor: 'border-amber-300',
      textColor: 'text-amber-700',
      name: '传奇'
    }
  };

  const filteredAchievements = selectedCategory === 'all'
    ? achievements
    : achievements.filter(a => a.category === selectedCategory);

  const unlockedAchievements = achievements.filter(a => a.unlocked);
  const totalPoints = unlockedAchievements.reduce((sum, a) => sum + a.reward.points, 0);

  const getProgressPercentage = (achievement: Achievement) => {
    return Math.min((achievement.currentProgress / achievement.maxProgress) * 100, 100);
  };

  if (compact) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-slate-900">成就徽章</h3>
          <Badge className="bg-blue-100 text-blue-700">
            {unlockedAchievements.length}/{achievements.length}
          </Badge>
        </div>

        <div className="grid grid-cols-4 md:grid-cols-6 gap-3">
          {achievements.slice(0, 12).map((achievement) => (
            <div
              key={achievement.id}
              className={`relative p-3 rounded-lg border-2 transition-all cursor-pointer hover:shadow-md ${
                achievement.unlocked
                  ? `${rarityConfig[achievement.rarity].color} ${rarityConfig[achievement.rarity].borderColor}`
                  : 'bg-slate-50 border-slate-200 opacity-60'
              }`}
              onClick={() => setSelectedAchievement(achievement)}
            >
              <div className={`text-center ${achievement.unlocked ? '' : 'grayscale'}`}>
                <div className="text-lg mb-1">{achievement.icon}</div>
                <div className="text-xs text-slate-600 font-medium truncate">
                  {achievement.name}
                </div>
              </div>
              {!achievement.unlocked && (
                <Lock className="absolute top-1 right-1 w-3 h-3 text-slate-400" />
              )}
              {achievement.unlocked && (
                <CheckCircle className="absolute top-1 right-1 w-3 h-3 text-emerald-600" />
              )}
            </div>
          ))}
        </div>

        <div className="text-center">
          <Button variant="outline" size="sm" onClick={() => setSelectedAchievement(null)}>
            查看全部成就 ({achievements.length})
          </Button>
        </div>
      </div>
    );
  }

  return (
    <Card className="bg-white border-slate-200 shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Medal className="w-5 h-5 text-amber-600" />
            {studentName} 的成就徽章
          </div>
          <div className="flex items-center gap-2">
            <Badge className="bg-amber-100 text-amber-700 border-amber-300">
              <Trophy className="w-3 h-3 mr-1" />
              {totalPoints} 积分
            </Badge>
            <Badge className="bg-blue-100 text-blue-700 border-blue-300">
              <Star className="w-3 h-3 mr-1" />
              {unlockedAchievements.length}/{achievements.length}
            </Badge>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* 统计概览 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center p-3 bg-emerald-50 rounded-lg">
            <div className="text-2xl font-bold text-emerald-600">
              {unlockedAchievements.length}
            </div>
            <div className="text-xs text-slate-600">已解锁</div>
          </div>
          <div className="text-center p-3 bg-amber-50 rounded-lg">
            <div className="text-2xl font-bold text-amber-600">
              {totalPoints}
            </div>
            <div className="text-xs text-slate-600">成就积分</div>
          </div>
          <div className="text-center p-3 bg-purple-50 rounded-lg">
            <div className="text-2xl font-bold text-purple-600">
              {achievements.filter(a => a.rarity === 'legendary' && a.unlocked).length}
            </div>
            <div className="text-xs text-slate-600">传奇成就</div>
          </div>
          <div className="text-center p-3 bg-blue-50 rounded-lg">
            <div className="text-2xl font-bold text-blue-600">
              {Math.round((unlockedAchievements.length / achievements.length) * 100)}%
            </div>
            <div className="text-xs text-slate-600">完成度</div>
          </div>
        </div>

        {/* 分类筛选 */}
        <div className="flex items-center gap-2 flex-wrap">
          {categories.map((category) => (
            <Button
              key={category.id}
              variant={selectedCategory === category.id ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedCategory(category.id)}
              className="flex items-center gap-2"
            >
              {category.icon}
              {category.name}
              <Badge variant="outline" className="text-xs">
                {category.id === 'all'
                  ? achievements.length
                  : achievements.filter(a => a.category === category.id).length
                }
              </Badge>
            </Button>
          ))}
        </div>

        {/* 成就列表 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredAchievements
            .filter(achievement => showLocked || achievement.unlocked)
            .map((achievement) => {
              const config = rarityConfig[achievement.rarity];
              const progressPercentage = getProgressPercentage(achievement);

              return (
                <Card
                  key={achievement.id}
                  className={`cursor-pointer transition-all hover:shadow-md ${
                    achievement.unlocked
                      ? config.color + ' ' + config.borderColor
                      : 'bg-slate-50 border-slate-200'
                  } border-2`}
                  onClick={() => setSelectedAchievement(achievement)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg ${
                          achievement.unlocked ? config.color : 'bg-slate-100'
                        }`}>
                          {achievement.unlocked ? (
                            <div className={config.textColor}>{achievement.icon}</div>
                          ) : (
                            <div className="text-slate-400">{achievement.icon}</div>
                          )}
                        </div>
                        <div className="flex-1">
                          <h3 className={`font-semibold ${
                            achievement.unlocked ? config.textColor : 'text-slate-700'
                          }`}>
                            {achievement.name}
                          </h3>
                          <p className={`text-sm ${
                            achievement.unlocked ? 'text-slate-600' : 'text-slate-500'
                          }`}>
                            {achievement.description}
                          </p>
                        </div>
                      </div>

                      <div className="flex flex-col items-end gap-1">
                        <Badge className={config.color} variant="outline">
                          {config.name}
                        </Badge>
                        {achievement.unlocked ? (
                          <CheckCircle className="w-4 h-4 text-emerald-600" />
                        ) : (
                          <Lock className="w-4 h-4 text-slate-400" />
                        )}
                      </div>
                    </div>

                    {/* 进度条 */}
                    {!achievement.unlocked && achievement.maxProgress > 1 && (
                      <div className="space-y-2">
                        <div className="flex justify-between text-xs text-slate-600">
                          <span>进度</span>
                          <span>{achievement.currentProgress}/{achievement.maxProgress}</span>
                        </div>
                        <Progress
                          value={progressPercentage}
                          className="h-2"
                        />
                      </div>
                    )}

                    {/* 奖励信息 */}
                    <div className="mt-3 flex items-center justify-between">
                      <div className="text-xs text-slate-600">
                        <Gift className="w-3 h-3 inline mr-1" />
                        {achievement.reward.points} 积分
                      </div>
                      {achievement.reward.title && (
                        <Badge variant="outline" className="text-xs">
                          {achievement.reward.title}
                        </Badge>
                      )}
                    </div>

                    {/* 解锁时间 */}
                    {achievement.unlocked && achievement.unlockedDate && (
                      <div className="mt-2 text-xs text-slate-500">
                        <Calendar className="w-3 h-3 inline mr-1" />
                        解锁于 {achievement.unlockedDate.toLocaleDateString('zh-CN')}
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
        </div>

        {/* 成就详情弹窗 */}
        {selectedAchievement && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <Card className="max-w-md w-full">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {selectedAchievement.icon}
                    {selectedAchievement.name}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedAchievement(null)}
                  >
                    ×
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-slate-700">{selectedAchievement.description}</p>

                <div className="space-y-2">
                  <h4 className="font-medium text-slate-900">完成条件：</h4>
                  <ul className="text-sm text-slate-600 space-y-1">
                    {selectedAchievement.requirements.map((req, index) => (
                      <li key={index} className="flex items-center gap-2">
                        {selectedAchievement.unlocked ? (
                          <CheckCircle className="w-4 h-4 text-emerald-600" />
                        ) : (
                          <div className="w-4 h-4 border border-slate-300 rounded-full" />
                        )}
                        {req}
                      </li>
                    ))}
                  </ul>
                </div>

                {!selectedAchievement.unlocked && (
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>进度</span>
                      <span>{selectedAchievement.currentProgress}/{selectedAchievement.maxProgress}</span>
                    </div>
                    <Progress
                      value={getProgressPercentage(selectedAchievement)}
                      className="h-3"
                    />
                  </div>
                )}

                <div className="border-t border-slate-200 pt-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium text-slate-900">奖励</div>
                      <div className="text-sm text-slate-600">
                        {selectedAchievement.reward.points} 积分
                      </div>
                    </div>
                    <Badge className={rarityConfig[selectedAchievement.rarity].color}>
                      {rarityConfig[selectedAchievement.rarity].name}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default AchievementBadges;
