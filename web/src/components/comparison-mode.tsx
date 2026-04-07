import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  GitCompare,
  Users,
  Bot,
  Calendar,
  Trophy,
  Target,
  TrendingUp,
  TrendingDown,
  Minus,
  Brain,
  Zap,
  Heart,
  Users as UserGroup,
  BarChart3,
  FileText,
  Download,
  Settings,
  Eye,
  Split,
  Maximize2
} from 'lucide-react';

interface DebatePerformance {
  id: string;
  date: Date;
  topic: string;
  stance: 'positive' | 'negative';
  result: 'win' | 'lose' | 'draw';
  duration: string;
  overallScore: number;
  keyMetrics: {
    logicScore: number;
    argumentScore: number;
    responseScore: number;
    persuasionScore: number;
    teamworkScore: number;
  };
  speakingTime: number;
  teamMembers: string[];
  opponentTeam: 'ai' | 'human';
  opponents: string[];
  improvement?: number;
}

interface ComparisonItem {
  type: 'debate' | 'student' | 'class';
  name: string;
  data: DebatePerformance[];
  color: string;
}

interface ComparisonModeProps {
  availableDebates: DebatePerformance[];
  availableStudents?: string[];
  availableClasses?: string[];
  onCompare?: (item1: ComparisonItem, item2: ComparisonItem) => void;
}

const ComparisonMode: React.FC<ComparisonModeProps> = ({
  availableDebates,
  availableStudents = ['张三', '李四', '王五', '赵六'],
  availableClasses = ['CS101', 'CS102', 'CS201'],
  onCompare
}) => {
  const [selectedItem1, setSelectedItem1] = useState<string>('');
  const [selectedItem2, setSelectedItem2] = useState<string>('');
  const [comparisonType, setComparisonType] = useState<'debate' | 'student' | 'class'>('debate');
  const [viewMode, setViewMode] = useState<'split' | 'stacked'>('split');

  const comparisonColors = {
    blue: '#3b82f6',
    purple: '#8b5cf6',
    green: '#10b981',
    amber: '#f59e0b',
    red: '#ef4444'
  };

  const formatPercentage = (value: number) => {
    return `${value > 0 ? '+' : ''}${value}%`;
  };

  const calculateDifference = (value1: number, value2: number) => {
    return value1 - value2;
  };

  const calculatePercentChange = (value1: number, value2: number) => {
    if (value2 === 0) return value1 > 0 ? 100 : 0;
    return ((value1 - value2) / value2) * 100;
  };

  const getDifferenceColor = (diff: number) => {
    if (diff > 0) return 'text-emerald-600';
    if (diff < 0) return 'text-red-600';
    return 'text-slate-600';
  };

  const getDifferenceIcon = (diff: number) => {
    if (diff > 0) return <TrendingUp className="w-4 h-4" />;
    if (diff < 0) return <TrendingDown className="w-4 h-4" />;
    return <Minus className="w-4 h-4" />;
  };

  const renderComparisonGrid = (item1: ComparisonItem, item2: ComparisonItem) => {
    const avgScore1 = item1.data.reduce((sum, d) => sum + d.overallScore, 0) / item1.data.length;
    const avgScore2 = item2.data.reduce((sum, d) => sum + d.overallScore, 0) / item2.data.length;

    const avgMetrics1 = {
      logic: item1.data.reduce((sum, d) => sum + d.keyMetrics.logicScore, 0) / item1.data.length,
      argument: item1.data.reduce((sum, d) => sum + d.keyMetrics.argumentScore, 0) / item1.data.length,
      response: item1.data.reduce((sum, d) => sum + d.keyMetrics.responseScore, 0) / item1.data.length,
      persuasion: item1.data.reduce((sum, d) => sum + d.keyMetrics.persuasionScore, 0) / item1.data.length,
      teamwork: item1.data.reduce((sum, d) => sum + d.keyMetrics.teamworkScore, 0) / item1.data.length
    };

    const avgMetrics2 = {
      logic: item2.data.reduce((sum, d) => sum + d.keyMetrics.logicScore, 0) / item2.data.length,
      argument: item2.data.reduce((sum, d) => sum + d.keyMetrics.argumentScore, 0) / item2.data.length,
      response: item2.data.reduce((sum, d) => sum + d.keyMetrics.responseScore, 0) / item2.data.length,
      persuasion: item2.data.reduce((sum, d) => sum + d.keyMetrics.persuasionScore, 0) / item2.data.length,
      teamwork: item2.data.reduce((sum, d) => sum + d.keyMetrics.teamworkScore, 0) / item2.data.length
    };

    const metrics = [
      { key: 'logic', name: '逻辑建构力', icon: <Brain className="w-4 h-4" /> },
      { key: 'argument', name: 'AI核心知识运用', icon: <Target className="w-4 h-4" /> },
      { key: 'response', name: '批判性思维', icon: <Zap className="w-4 h-4" /> },
      { key: 'persuasion', name: '语言表达力', icon: <Heart className="w-4 h-4" /> },
      { key: 'teamwork', name: 'AI伦理与科技素养', icon: <UserGroup className="w-4 h-4" /> }
    ];

    return (
      <div className="space-y-6">
        {/* 总体对比 */}
        <div className="grid grid-cols-3 gap-6">
          <Card className="text-center">
            <CardContent className="p-6">
              <h3 className="font-semibold text-slate-700 mb-4">{item1.name}</h3>
              <div className="text-3xl font-bold" style={{ color: item1.color }}>
                {avgScore1.toFixed(1)}
              </div>
              <div className="text-sm text-slate-600">综合评分</div>
              <div className="text-xs text-slate-500 mt-2">{item1.data.length} 场辩论</div>
            </CardContent>
          </Card>

          <Card className="text-center">
            <CardContent className="p-6">
              <h3 className="font-semibold text-slate-700 mb-4">对比结果</h3>
              <div className={`text-3xl font-bold flex items-center justify-center gap-2 ${getDifferenceColor(avgScore1 - avgScore2)}`}>
                {getDifferenceIcon(avgScore1 - avgScore2)}
                {Math.abs(avgScore1 - avgScore2).toFixed(1)}
              </div>
              <div className="text-sm text-slate-600">评分差异</div>
              <div className="text-xs text-slate-500 mt-2">
                {formatPercentage(calculatePercentChange(avgScore1, avgScore2))}
              </div>
            </CardContent>
          </Card>

          <Card className="text-center">
            <CardContent className="p-6">
              <h3 className="font-semibold text-slate-700 mb-4">{item2.name}</h3>
              <div className="text-3xl font-bold" style={{ color: item2.color }}>
                {avgScore2.toFixed(1)}
              </div>
              <div className="text-sm text-slate-600">综合评分</div>
              <div className="text-xs text-slate-500 mt-2">{item2.data.length} 场辩论</div>
            </CardContent>
          </Card>
        </div>

        {/* 能力维度对比 */}
        <div className="space-y-4">
          <h3 className="font-semibold text-slate-900 flex items-center gap-2">
            <BarChart3 className="w-5 h-5" />
            能力维度对比分析
          </h3>

          {metrics.map((metric) => {
            const value1 = avgMetrics1[metric.key as keyof typeof avgMetrics1];
            const value2 = avgMetrics2[metric.key as keyof typeof avgMetrics2];
            const difference = value1 - value2;
            const percentChange = calculatePercentChange(value1, value2);

            return (
              <div key={metric.key} className="bg-slate-50 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    {metric.icon}
                    <span className="font-medium text-slate-900">{metric.name}</span>
                  </div>
                  <div className={`flex items-center gap-2 ${getDifferenceColor(difference)}`}>
                    {getDifferenceIcon(difference)}
                    <span className="font-medium">{Math.abs(difference).toFixed(1)}</span>
                    <span className="text-sm">({formatPercentage(percentChange)})</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-slate-600">{item1.name}</span>
                      <span className="font-medium" style={{ color: item1.color }}>
                        {value1.toFixed(1)}
                      </span>
                    </div>
                    <div className="w-full bg-slate-200 rounded-full h-2">
                      <div
                        className="h-2 rounded-full transition-all"
                        style={{
                          width: `${value1}%`,
                          backgroundColor: item1.color
                        }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-slate-600">{item2.name}</span>
                      <span className="font-medium" style={{ color: item2.color }}>
                        {value2.toFixed(1)}
                      </span>
                    </div>
                    <div className="w-full bg-slate-200 rounded-full h-2">
                      <div
                        className="h-2 rounded-full transition-all"
                        style={{
                          width: `${value2}%`,
                          backgroundColor: item2.color
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* 详细数据表格 */}
        <div>
          <h3 className="font-semibold text-slate-900 flex items-center gap-2 mb-4">
            <FileText className="w-5 h-5" />
            详细数据对比
          </h3>

          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="text-left p-3 font-medium text-slate-900">指标</th>
                  <th className="text-center p-3 font-medium text-slate-900">{item1.name}</th>
                  <th className="text-center p-3 font-medium text-slate-900">{item2.name}</th>
                  <th className="text-center p-3 font-medium text-slate-900">差异</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-slate-100">
                  <td className="p-3 text-slate-700">综合评分</td>
                  <td className="p-3 text-center" style={{ color: item1.color }}>
                    {avgScore1.toFixed(1)}
                  </td>
                  <td className="p-3 text-center" style={{ color: item2.color }}>
                    {avgScore2.toFixed(1)}
                  </td>
                  <td className={`p-3 text-center ${getDifferenceColor(avgScore1 - avgScore2)}`}>
                    {formatPercentage(calculatePercentChange(avgScore1, avgScore2))}
                  </td>
                </tr>

                {metrics.map((metric) => {
                  const value1 = avgMetrics1[metric.key as keyof typeof avgMetrics1];
                  const value2 = avgMetrics2[metric.key as keyof typeof avgMetrics2];
                  const difference = value1 - value2;

                  return (
                    <tr key={metric.key} className="border-b border-slate-100">
                      <td className="p-3 text-slate-700 flex items-center gap-2">
                        {metric.icon}
                        {metric.name}
                      </td>
                      <td className="p-3 text-center" style={{ color: item1.color }}>
                        {value1.toFixed(1)}
                      </td>
                      <td className="p-3 text-center" style={{ color: item2.color }}>
                        {value2.toFixed(1)}
                      </td>
                      <td className={`p-3 text-center ${getDifferenceColor(difference)}`}>
                        {formatPercentage(calculatePercentChange(value1, value2))}
                      </td>
                    </tr>
                  );
                })}

                <tr className="bg-slate-50">
                  <td className="p-3 font-medium text-slate-900">辩论场次</td>
                  <td className="p-3 text-center font-medium">{item1.data.length}</td>
                  <td className="p-3 text-center font-medium">{item2.data.length}</td>
                  <td className="p-3 text-center">
                    <Badge variant="outline">
                      {item1.data.length - item2.data.length > 0 ? '+' : ''}
                      {item1.data.length - item2.data.length}
                    </Badge>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* 操作按钮 */}
        <div className="flex items-center justify-center gap-4 pt-4 border-t border-slate-200">
          <Button variant="outline">
            <Download className="w-4 h-4 mr-2" />
            导出对比报告
          </Button>
          <Button
            onClick={() => onCompare?.(item1, item2)}
            className="bg-blue-600 hover:bg-blue-700 text-white"
          >
            <FileText className="w-4 h-4 mr-2" />
            生成详细分析
          </Button>
        </div>
      </div>
    );
  };

  const mockDebatesForComparison: DebatePerformance[] = [
    // 这里可以添加更多模拟数据
  ];

  const getComparisonItems = (): ComparisonItem[] => {
    if (comparisonType === 'debate') {
      return availableDebates.slice(0, 6).map((debate, index) => ({
        type: 'debate',
        name: `辩论: ${debate.topic.substring(0, 10)}...`,
        data: [debate],
        color: Object.values(comparisonColors)[index % Object.keys(comparisonColors).length]
      }));
    }

    if (comparisonType === 'student') {
      return availableStudents.map((student, index) => ({
        type: 'student',
        name: `学生: ${student}`,
        data: availableDebates.filter(d => d.teamMembers.includes(student)) || mockDebatesForComparison,
        color: Object.values(comparisonColors)[index % Object.keys(comparisonColors).length]
      }));
    }

    if (comparisonType === 'class') {
      return availableClasses.map((className, index) => ({
        type: 'class',
        name: `班级: ${className}`,
        data: mockDebatesForComparison,
        color: Object.values(comparisonColors)[index % Object.keys(comparisonColors).length]
      }));
    }

    return [];
  };

  const comparisonItems = getComparisonItems();
  const item1 = comparisonItems.find(item => item.name === selectedItem1);
  const item2 = comparisonItems.find(item => item.name === selectedItem2);

  return (
    <Card className="bg-white border-slate-200 shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitCompare className="w-5 h-5 text-blue-600" />
            对比模式
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setViewMode(viewMode === 'split' ? 'stacked' : 'split')}
            >
              {viewMode === 'split' ? (
                <Maximize2 className="w-4 h-4" />
              ) : (
                <Split className="w-4 h-4" />
              )}
              {viewMode === 'split' ? '堆叠视图' : '对比视图'}
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* 对比类型选择 */}
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium text-slate-700">对比类型:</span>
          <div className="flex items-center gap-2">
            {[
              { value: 'debate', label: '辩论场次', icon: <Target className="w-4 h-4" /> },
              { value: 'student', label: '学生表现', icon: <Users className="w-4 h-4" /> },
              { value: 'class', label: '班级对比', icon: <UserGroup className="w-4 h-4" /> }
            ].map((type) => (
              <Button
                key={type.value}
                variant={comparisonType === type.value ? 'default' : 'outline'}
                size="sm"
                onClick={() => {
                  setComparisonType(type.value as any);
                  setSelectedItem1('');
                  setSelectedItem2('');
                }}
                className="flex items-center gap-2"
              >
                {type.icon}
                {type.label}
              </Button>
            ))}
          </div>
        </div>

        {/* 对比项目选择 */}
        <div className="grid grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              选择对比项目 1
            </label>
            <Select value={selectedItem1} onValueChange={setSelectedItem1}>
              <SelectTrigger>
                <SelectValue placeholder={`选择${comparisonType === 'debate' ? '辩论' : comparisonType === 'student' ? '学生' : '班级'}`} />
              </SelectTrigger>
              <SelectContent>
                {comparisonItems.map((item) => (
                  <SelectItem key={item.name} value={item.name}>
                    <div className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: item.color }}
                      />
                      {item.name}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              选择对比项目 2
            </label>
            <Select value={selectedItem2} onValueChange={setSelectedItem2}>
              <SelectTrigger>
                <SelectValue placeholder={`选择${comparisonType === 'debate' ? '辩论' : comparisonType === 'student' ? '学生' : '班级'}`} />
              </SelectTrigger>
              <SelectContent>
                {comparisonItems
                  .filter(item => item.name !== selectedItem1)
                  .map((item) => (
                    <SelectItem key={item.name} value={item.name}>
                      <div className="flex items-center gap-2">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: item.color }}
                        />
                        {item.name}
                      </div>
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* 对比结果展示 */}
        {item1 && item2 && (
          <div className="border-t border-slate-200 pt-6">
            {renderComparisonGrid(item1, item2)}
          </div>
        )}

        {/* 选择提示 */}
        {!item1 || !item2 && (
          <div className="text-center py-12">
            <GitCompare className="w-16 h-16 mx-auto text-slate-300 mb-4" />
            <h3 className="text-lg font-semibold text-slate-700 mb-2">选择对比项目</h3>
            <p className="text-slate-500 max-w-md mx-auto">
              请选择两个{comparisonType === 'debate' ? '辩论场次' : comparisonType === 'student' ? '学生' : '班级'}
              进行详细对比分析
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ComparisonMode;
