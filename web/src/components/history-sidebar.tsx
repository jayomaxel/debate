import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Calendar,
  Trophy,
  Users,
  Bot,
  TrendingUp,
  Search,
  Filter,
  Star,
  Clock,
  Award,
  BookOpen,
  Target,
  ChevronRight,
  Plus,
  FileText
} from 'lucide-react';

interface DebateRecord {
  id: string;
  date: Date;
  topic: string;
  stance: 'positive' | 'negative';
  result: 'win' | 'lose' | 'draw';
  duration: string;
  overallScore: number;
  improvement: number;
  opponentTeam: 'ai' | 'human';
  teamMembers: string[];
  aiOpponents: string[];
  keyMetrics: {
    logicScore: number;
    argumentScore: number;
    responseScore: number;
    persuasionScore: number;
    teamworkScore: number;
  };
  achievements?: string[];
}

interface HistorySidebarProps {
  userType?: 'student' | 'teacher';
  onRecordSelect?: (record: DebateRecord) => void;
  onCreateNewDebate?: () => void;
}

const HistorySidebar: React.FC<HistorySidebarProps> = ({
  userType = 'student',
  onRecordSelect,
  onCreateNewDebate
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterBy, setFilterBy] = useState<'all' | 'win' | 'lose' | 'draw'>('all');
  const [sortBy, setSortBy] = useState<'date' | 'score' | 'improvement'>('date');

  // Mock debate history data
  const debateHistory: DebateRecord[] = [
    {
      id: '1',
      date: new Date('2024-01-15'),
      topic: '人类应不应该与高度拟人化的AI伴侣建立真实的感情羁绊？',
      stance: 'positive',
      result: 'win',
      duration: '28:35',
      overallScore: 82,
      improvement: 5,
      opponentTeam: 'ai',
      teamMembers: ['张三', '李四', '王五'],
      aiOpponents: ['Alpha-Logic', 'Beta-Creative', 'Gamma-Strategic'],
      keyMetrics: {
        logicScore: 85,
        argumentScore: 78,
        responseScore: 92,
        persuasionScore: 73,
        teamworkScore: 88
      },
      achievements: ['首次胜利', '逻辑建构力突出', '快速响应']
    },
    {
      id: '2',
      date: new Date('2024-01-08'),
      topic: '人工智能对教育的影响',
      stance: 'negative',
      result: 'lose',
      duration: '31:20',
      overallScore: 76,
      improvement: -2,
      opponentTeam: 'ai',
      teamMembers: ['张三', '李四', '王五'],
      aiOpponents: ['Edu-Master', 'Think-Tank', 'Logic-Prime'],
      keyMetrics: {
        logicScore: 79,
        argumentScore: 72,
        responseScore: 85,
        persuasionScore: 68,
        teamworkScore: 80
      }
    },
    {
      id: '3',
      date: new Date('2024-01-01'),
      topic: '环保技术：经济发展的新引擎？',
      stance: 'positive',
      result: 'draw',
      duration: '29:45',
      overallScore: 80,
      improvement: 8,
      opponentTeam: 'ai',
      teamMembers: ['张三', '李四', '王五'],
      aiOpponents: ['Green-AI', 'Eco-Logic', 'Sustainability-Bot'],
      keyMetrics: {
        logicScore: 82,
        argumentScore: 80,
        responseScore: 88,
        persuasionScore: 75,
        teamworkScore: 85
      },
      achievements: ['首次参与', '环保意识']
    },
    {
      id: '4',
      date: new Date('2023-12-25'),
      topic: '社交媒体对社会的影响',
      stance: 'negative',
      result: 'win',
      duration: '26:10',
      overallScore: 79,
      improvement: 12,
      opponentTeam: 'ai',
      teamMembers: ['张三', '李四', '王五'],
      aiOpponents: ['Social-Analyst', 'Media-Expert', 'Digital-Psychologist'],
      keyMetrics: {
        logicScore: 78,
        argumentScore: 75,
        responseScore: 90,
        persuasionScore: 70,
        teamworkScore: 82
      }
    }
  ];

  const filterAndSortHistory = (records: DebateRecord[]) => {
    let filtered = records.filter(record => {
      const matchesSearch = record.topic.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesFilter = filterBy === 'all' || record.result === filterBy;
      return matchesSearch && matchesFilter;
    });

    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'score':
          return b.overallScore - a.overallScore;
        case 'improvement':
          return b.improvement - a.improvement;
        case 'date':
        default:
          return b.date.getTime() - a.date.getTime();
      }
    });

    return filtered;
  };

  const getResultConfig = (result: 'win' | 'lose' | 'draw') => {
    switch (result) {
      case 'win':
        return {
          color: 'emerald',
          bgColor: 'bg-emerald-50',
          borderColor: 'border-emerald-300',
          textColor: 'text-emerald-700',
          icon: <Trophy className="w-4 h-4" />,
          label: '胜利'
        };
      case 'lose':
        return {
          color: 'red',
          bgColor: 'bg-red-50',
          borderColor: 'border-red-300',
          textColor: 'text-red-700',
          icon: <Target className="w-4 h-4" />,
          label: '失败'
        };
      case 'draw':
        return {
          color: 'amber',
          bgColor: 'bg-amber-50',
          borderColor: 'border-amber-300',
          textColor: 'text-amber-700',
          icon: <Award className="w-4 h-4" />,
          label: '平局'
        };
    }
  };

  const formatDate = (date: Date) => {
    return date.toLocaleDateString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const filteredHistory = filterAndSortHistory(debateHistory);

  return (
    <div className="w-full max-w-md bg-white border-r border-slate-200 h-full flex flex-col">
      {/* 头部 */}
      <div className="p-6 border-b border-slate-200">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-slate-900">辩论历史</h2>
            <p className="text-sm text-slate-600">
              {userType === 'student' ? '个人' : '全班'} {debateHistory.length} 场记录
            </p>
          </div>
          {userType === 'student' && onCreateNewDebate && (
            <Button
              onClick={onCreateNewDebate}
              size="sm"
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              <Plus className="w-4 h-4 mr-2" />
              新辩论
            </Button>
          )}
        </div>

        {/* 搜索和筛选 */}
        <div className="space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input
              placeholder="搜索辩题..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>

          <div className="flex gap-2">
            <Select value={filterBy} onValueChange={(value: any) => setFilterBy(value)}>
              <SelectTrigger className="flex-1">
                <Filter className="w-4 h-4 mr-2" />
                <SelectValue placeholder="筛选结果" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部</SelectItem>
                <SelectItem value="win">胜利</SelectItem>
                <SelectItem value="lose">失败</SelectItem>
                <SelectItem value="draw">平局</SelectItem>
              </SelectContent>
            </Select>

            <Select value={sortBy} onValueChange={(value: any) => setSortBy(value)}>
              <SelectTrigger className="flex-1">
                <TrendingUp className="w-4 h-4 mr-2" />
                <SelectValue placeholder="排序方式" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="date">按时间</SelectItem>
                <SelectItem value="score">按评分</SelectItem>
                <SelectItem value="improvement">按进步</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* 历史记录列表 */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-3">
          {filteredHistory.map((record) => {
            const resultConfig = getResultConfig(record.result);

            return (
              <Card
                key={record.id}
                className={`cursor-pointer hover:shadow-md transition-shadow ${
                  resultConfig.bgColor
                } ${resultConfig.borderColor} border`}
                onClick={() => onRecordSelect?.(record)}
              >
                <CardContent className="p-4">
                  {/* 头部信息 */}
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <Calendar className="w-4 h-4 text-slate-500" />
                        <span className="text-sm text-slate-600">
                          {formatDate(record.date)}
                        </span>
                      </div>
                      <h3 className="font-semibold text-slate-900 text-sm mb-2">
                        {record.topic}
                      </h3>
                      <div className="flex items-center gap-2">
                        <Badge
                          className={`${resultConfig.textColor} ${resultConfig.bgColor} ${resultConfig.borderColor}`}
                          variant="outline"
                        >
                          {resultConfig.icon}
                          <span className="ml-1">{resultConfig.label}</span>
                        </Badge>
                        <Badge
                          variant="outline"
                          className="text-xs"
                        >
                          {record.stance === 'positive' ? '正方' : '反方'}
                        </Badge>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-bold text-slate-900">
                        {record.overallScore}
                      </div>
                      <div className="text-xs text-slate-600">综合分</div>
                      {record.improvement !== 0 && (
                        <div className={`text-xs font-medium ${
                          record.improvement > 0 ? 'text-emerald-600' : 'text-red-600'
                        }`}>
                          {record.improvement > 0 ? '+' : ''}{record.improvement}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 团队信息 */}
                  <div className="flex items-center justify-between text-xs text-slate-600 mb-2">
                    <div className="flex items-center gap-1">
                      <Users className="w-3 h-3" />
                      <span>我方团队</span>
                    </div>
                    <div className="flex items-center gap-1">
                      {record.opponentTeam === 'ai' ? (
                        <Bot className="w-3 h-3" />
                      ) : (
                        <Users className="w-3 h-3" />
                      )}
                      <span>对手团队</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-white/60 rounded p-1">
                      {record.teamMembers.slice(0, 2).join(', ')}
                      {record.teamMembers.length > 2 && '...'}
                    </div>
                    <div className="bg-white/60 rounded p-1">
                      {record.aiOpponents.slice(0, 2).join(', ')}
                      {record.aiOpponents.length > 2 && '...'}
                    </div>
                  </div>

                  {/* 成就徽章 */}
                  {record.achievements && record.achievements.length > 0 && (
                    <div className="mt-2">
                      <div className="flex items-center gap-1 flex-wrap">
                        {record.achievements.slice(0, 2).map((achievement, index) => (
                          <Badge key={index} className="text-xs bg-amber-100 text-amber-700">
                            <Star className="w-3 h-3 mr-1" />
                            {achievement}
                          </Badge>
                        ))}
                        {record.achievements.length > 2 && (
                          <Badge variant="outline" className="text-xs">
                            +{record.achievements.length - 2}
                          </Badge>
                        )}
                      </div>
                    </div>
                  )}

                  {/* 操作按钮 */}
                  <div className="flex items-center justify-between mt-3 pt-2 border-t border-slate-200/50">
                    <div className="flex items-center gap-1 text-xs text-slate-500">
                      <Clock className="w-3 h-3" />
                      {record.duration}
                    </div>
                    <Button variant="ghost" size="sm" className="p-0 h-auto">
                      <FileText className="w-4 h-4 text-slate-400" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {filteredHistory.length === 0 && (
          <div className="text-center py-8">
            <BookOpen className="w-12 h-12 mx-auto text-slate-300 mb-4" />
            <p className="text-slate-500">暂无符合条件的记录</p>
          </div>
        )}
      </ScrollArea>

      {/* 底部统计 */}
      <div className="p-4 border-t border-slate-200 bg-slate-50">
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="p-2 bg-emerald-50 rounded">
            <div className="text-lg font-bold text-emerald-600">
              {debateHistory.filter(r => r.result === 'win').length}
            </div>
            <div className="text-xs text-slate-600">胜利</div>
          </div>
          <div className="p-2 bg-amber-50 rounded">
            <div className="text-lg font-bold text-amber-600">
              {debateHistory.filter(r => r.result === 'draw').length}
            </div>
            <div className="text-xs text-slate-600">平局</div>
          </div>
          <div className="p-2 bg-red-50 rounded">
            <div className="text-lg font-bold text-red-600">
              {debateHistory.filter(r => r.result === 'lose').length}
            </div>
            <div className="text-xs text-slate-600">失败</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HistorySidebar;
