import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Search,
  Filter,
  Users,
  Calendar,
  TrendingUp,
  Award,
  BarChart3,
  Download,
  Eye,
  EyeOff,
  RefreshCw,
  Settings,
  FileText,
  Star,
  Clock,
  Target,
  Brain,
  Zap,
  Heart,
  UserPlus,
  ChevronDown,
  X
} from 'lucide-react';

interface Student {
  id: string;
  name: string;
  classCode: string;
  email: string;
  totalDebates: number;
  averageScore: number;
  improvement: number;
  active: boolean;
  lastDebate: Date;
}

interface FilterOptions {
  searchTerm: string;
  classes: string[];
  scoreRange: [number, number];
  debateCount: [number, number];
  improvementRange: [number, number];
  activeStudents: boolean;
  dateRange: 'week' | 'month' | 'semester' | 'year' | 'all';
  sortBy: 'name' | 'score' | 'improvement' | 'debates' | 'lastActive';
  sortOrder: 'asc' | 'desc';
}

interface TeacherSearchFilterProps {
  students: Student[];
  onFilterChange?: (filters: FilterOptions) => void;
  onStudentSelect?: (studentIds: string[]) => void;
  selectedStudents?: string[];
  enableBatchActions?: boolean;
}

const TeacherSearchFilter: React.FC<TeacherSearchFilterProps> = ({
  students,
  onFilterChange,
  onStudentSelect,
  selectedStudents = [],
  enableBatchActions = true
}) => {
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [filters, setFilters] = useState<FilterOptions>({
    searchTerm: '',
    classes: [],
    scoreRange: [0, 100],
    debateCount: [0, 50],
    improvementRange: [-20, 50],
    activeStudents: true,
    dateRange: 'all',
    sortBy: 'name',
    sortOrder: 'asc'
  });

  const [selectedStudentIds, setSelectedStudentIds] = useState<string[]>(selectedStudents);

  // Extract unique class codes
  const classCodes = [...new Set(students.map(student => student.classCode))];

  const updateFilters = (newFilters: Partial<FilterOptions>) => {
    const updatedFilters = { ...filters, ...newFilters };
    setFilters(updatedFilters);
    onFilterChange?.(updatedFilters);
  };

  const handleStudentSelection = (studentId: string, checked: boolean) => {
    const newSelection = checked
      ? [...selectedStudentIds, studentId]
      : selectedStudentIds.filter(id => id !== studentId);

    setSelectedStudentIds(newSelection);
    onStudentSelect?.(newSelection);
  };

  const handleSelectAll = (checked: boolean) => {
    const filteredStudentIds = getFilteredStudents().map(student => student.id);
    const newSelection = checked ? filteredStudentIds : [];

    setSelectedStudentIds(newSelection);
    onStudentSelect?.(newSelection);
  };

  const getFilteredStudents = () => {
    return students.filter(student => {
      // Search term filter
      if (filters.searchTerm && !student.name.toLowerCase().includes(filters.searchTerm.toLowerCase()) &&
          !student.email.toLowerCase().includes(filters.searchTerm.toLowerCase())) {
        return false;
      }

      // Class filter
      if (filters.classes.length > 0 && !filters.classes.includes(student.classCode)) {
        return false;
      }

      // Score range filter
      if (student.averageScore < filters.scoreRange[0] || student.averageScore > filters.scoreRange[1]) {
        return false;
      }

      // Debate count filter
      if (student.totalDebates < filters.debateCount[0] || student.totalDebates > filters.debateCount[1]) {
        return false;
      }

      // Improvement range filter
      if (student.improvement < filters.improvementRange[0] || student.improvement > filters.improvementRange[1]) {
        return false;
      }

      // Active students filter
      if (filters.activeStudents && !student.active) {
        return false;
      }

      return true;
    }).sort((a, b) => {
      const { sortBy, sortOrder } = filters;
      let aValue: any;
      let bValue: any;

      switch (sortBy) {
        case 'name':
          aValue = a.name;
          bValue = b.name;
          break;
        case 'score':
          aValue = a.averageScore;
          bValue = b.averageScore;
          break;
        case 'improvement':
          aValue = a.improvement;
          bValue = b.improvement;
          break;
        case 'debates':
          aValue = a.totalDebates;
          bValue = b.totalDebates;
          break;
        case 'lastActive':
          aValue = a.lastDebate.getTime();
          bValue = b.lastDebate.getTime();
          break;
        default:
          aValue = a.name;
          bValue = b.name;
      }

      if (typeof aValue === 'string') {
        return sortOrder === 'asc'
          ? aValue.localeCompare(bValue)
          : bValue.localeCompare(aValue);
      } else {
        return sortOrder === 'asc' ? aValue - bValue : bValue - aValue;
      }
    });
  };

  const filteredStudents = getFilteredStudents();

  const getScoreColor = (score: number) => {
    if (score >= 85) return 'text-emerald-600';
    if (score >= 75) return 'text-blue-600';
    if (score >= 65) return 'text-amber-600';
    return 'text-red-600';
  };

  const getImprovementColor = (improvement: number) => {
    if (improvement > 5) return 'text-emerald-600';
    if (improvement > 0) return 'text-blue-600';
    if (improvement < -5) return 'text-red-600';
    return 'text-slate-600';
  };

  const formatDate = (date: Date) => {
    const daysDiff = Math.floor((new Date().getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

    if (daysDiff === 0) return '今天';
    if (daysDiff === 1) return '昨天';
    if (daysDiff < 7) return `${daysDiff}天前`;
    if (daysDiff < 30) return `${Math.floor(daysDiff / 7)}周前`;
    if (daysDiff < 365) return `${Math.floor(daysDiff / 30)}个月前`;
    return `${Math.floor(daysDiff / 365)}年前`;
  };

  return (
    <div className="space-y-4">
      {/* 搜索和基础筛选 */}
      <Card className="bg-white border-slate-200 shadow-sm">
        <CardContent className="p-4">
          <div className="flex items-center gap-4 mb-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                placeholder="搜索学生姓名或邮箱..."
                value={filters.searchTerm}
                onChange={(e) => updateFilters({ searchTerm: e.target.value })}
                className="pl-10"
              />
            </div>

            <Select value={filters.sortBy} onValueChange={(value: any) => updateFilters({ sortBy: value })}>
              <SelectTrigger className="w-40">
                <BarChart3 className="w-4 h-4 mr-2" />
                <SelectValue placeholder="排序方式" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="name">姓名</SelectItem>
                <SelectItem value="score">平均分</SelectItem>
                <SelectItem value="improvement">进步幅度</SelectItem>
                <SelectItem value="debates">辩论次数</SelectItem>
                <SelectItem value="lastActive">最后活跃</SelectItem>
              </SelectContent>
            </Select>

            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
            >
              <Filter className="w-4 h-4 mr-2" />
              高级筛选
              {showAdvancedFilters ? (
                <ChevronDown className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4 rotate-180" />
              )}
            </Button>
          </div>

          {/* 快速统计 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4 text-sm text-slate-600">
              <span>找到 {filteredStudents.length} 名学生</span>
              <span>共 {students.length} 名学生</span>
              {selectedStudentIds.length > 0 && (
                <Badge className="bg-blue-100 text-blue-700">
                  已选择 {selectedStudentIds.length} 人
                </Badge>
              )}
            </div>

            {enableBatchActions && selectedStudentIds.length > 0 && (
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm">
                  <FileText className="w-4 h-4 mr-2" />
                  批量报告
                </Button>
                <Button variant="outline" size="sm">
                  <Download className="w-4 h-4 mr-2" />
                  导出数据
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedStudentIds([])}
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 高级筛选 */}
      {showAdvancedFilters && (
        <Card className="bg-white border-slate-200 shadow-sm">
          <CardContent className="p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* 班级筛选 */}
              <div>
                <label className="text-sm font-medium text-slate-700 mb-2 block">班级</label>
                <div className="space-y-2">
                  {classCodes.map(classCode => (
                    <div key={classCode} className="flex items-center space-x-2">
                      <Checkbox
                        id={`class-${classCode}`}
                        checked={filters.classes.includes(classCode)}
                        onCheckedChange={(checked) => {
                          const newClasses = checked
                            ? [...filters.classes, classCode]
                            : filters.classes.filter(c => c !== classCode);
                          updateFilters({ classes: newClasses });
                        }}
                      />
                      <label htmlFor={`class-${classCode}`} className="text-sm text-slate-700">
                        {classCode}
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {/* 分数范围 */}
              <div>
                <label className="text-sm font-medium text-slate-700 mb-2 block">平均分范围</label>
                <div className="space-y-2">
                  <Input
                    type="number"
                    placeholder="最低分"
                    value={filters.scoreRange[0]}
                    onChange={(e) => updateFilters({
                      scoreRange: [parseInt(e.target.value) || 0, filters.scoreRange[1]]
                    })}
                  />
                  <Input
                    type="number"
                    placeholder="最高分"
                    value={filters.scoreRange[1]}
                    onChange={(e) => updateFilters({
                      scoreRange: [filters.scoreRange[0], parseInt(e.target.value) || 100]
                    })}
                  />
                </div>
              </div>

              {/* 辩论次数范围 */}
              <div>
                <label className="text-sm font-medium text-slate-700 mb-2 block">辩论次数范围</label>
                <div className="space-y-2">
                  <Input
                    type="number"
                    placeholder="最少场次"
                    value={filters.debateCount[0]}
                    onChange={(e) => updateFilters({
                      debateCount: [parseInt(e.target.value) || 0, filters.debateCount[1]]
                    })}
                  />
                  <Input
                    type="number"
                    placeholder="最多场次"
                    value={filters.debateCount[1]}
                    onChange={(e) => updateFilters({
                      debateCount: [filters.debateCount[0], parseInt(e.target.value) || 50]
                    })}
                  />
                </div>
              </div>

              {/* 活跃状态 */}
              <div>
                <label className="text-sm font-medium text-slate-700 mb-2 block">学生状态</label>
                <div className="space-y-2">
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="active-students"
                      checked={filters.activeStudents}
                      onCheckedChange={(checked) => updateFilters({ activeStudents: !!checked })}
                    />
                    <label htmlFor="active-students" className="text-sm text-slate-700">
                      只显示活跃学生
                    </label>
                  </div>
                </div>
              </div>

              {/* 时间范围 */}
              <div>
                <label className="text-sm font-medium text-slate-700 mb-2 block">时间范围</label>
                <Select value={filters.dateRange} onValueChange={(value: any) => updateFilters({ dateRange: value })}>
                  <SelectTrigger>
                    <Calendar className="w-4 h-4 mr-2" />
                    <SelectValue placeholder="选择时间范围" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="week">最近一周</SelectItem>
                    <SelectItem value="month">最近一个月</SelectItem>
                    <SelectItem value="semester">本学期</SelectItem>
                    <SelectItem value="year">本年度</SelectItem>
                    <SelectItem value="all">全部时间</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* 清除筛选 */}
            <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-200">
              <div className="text-sm text-slate-600">
                当前筛选条件：
                <span className="font-medium">
                  {filters.classes.length > 0 && `${filters.classes.length}个班级 `}
                  {filters.searchTerm && '关键词搜索 '}
                  {filters.scoreRange[0] > 0 || filters.scoreRange[1] < 100 ? '分数范围 ' : ''}
                  {filters.activeStudents && '活跃学生 '}
                </span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setFilters({
                    searchTerm: '',
                    classes: [],
                    scoreRange: [0, 100],
                    debateCount: [0, 50],
                    improvementRange: [-20, 50],
                    activeStudents: true,
                    dateRange: 'all',
                    sortBy: 'name',
                    sortOrder: 'asc'
                  });
                }}
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                清除筛选
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 学生列表 */}
      <Card className="bg-white border-slate-200 shadow-sm">
        <CardContent className="p-4">
          {enableBatchActions && (
            <div className="flex items-center space-x-2 mb-4 pb-4 border-b border-slate-200">
              <Checkbox
                id="select-all"
                checked={selectedStudentIds.length === filteredStudents.length && filteredStudents.length > 0}
                onCheckedChange={handleSelectAll}
              />
              <label htmlFor="select-all" className="text-sm font-medium text-slate-700">
                全选
              </label>
            </div>
          )}

          <div className="space-y-3">
            {filteredStudents.map((student) => (
              <div
                key={student.id}
                className={`p-4 rounded-lg border ${
                  selectedStudentIds.includes(student.id)
                    ? 'border-blue-300 bg-blue-50'
                    : 'border-slate-200 bg-white'
                } hover:shadow-md transition-shadow`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 flex-1">
                    {enableBatchActions && (
                      <Checkbox
                        checked={selectedStudentIds.includes(student.id)}
                        onCheckedChange={(checked) => handleStudentSelection(student.id, !!checked)}
                      />
                    )}

                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold text-slate-900">{student.name}</h3>
                        <Badge variant="outline" className="text-xs">
                          {student.classCode}
                        </Badge>
                        {student.active && (
                          <Badge className="bg-emerald-100 text-emerald-700 text-xs">
                            活跃
                          </Badge>
                        )}
                      </div>
                      <div className="text-sm text-slate-600">{student.email}</div>
                    </div>
                  </div>

                  <div className="grid grid-cols-4 gap-4 text-center">
                    <div>
                      <div className={`text-lg font-bold ${getScoreColor(student.averageScore)}`}>
                        {student.averageScore}
                      </div>
                      <div className="text-xs text-slate-600">平均分</div>
                    </div>
                    <div>
                      <div className={`text-lg font-bold ${getImprovementColor(student.improvement)}`}>
                        {student.improvement > 0 ? '+' : ''}{student.improvement}
                      </div>
                      <div className="text-xs text-slate-600">进步</div>
                    </div>
                    <div>
                      <div className="text-lg font-bold text-slate-900">
                        {student.totalDebates}
                      </div>
                      <div className="text-xs text-slate-600">辩论次数</div>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-slate-700">
                        {formatDate(student.lastDebate)}
                      </div>
                      <div className="text-xs text-slate-600">最后活跃</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 ml-4">
                    <Button variant="outline" size="sm">
                      <Eye className="w-4 h-4 mr-2" />
                      查看详情
                    </Button>
                    <Button variant="outline" size="sm">
                      <FileText className="w-4 h-4 mr-2" />
                      报告
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {filteredStudents.length === 0 && (
            <div className="text-center py-12">
              <Users className="w-12 h-12 mx-auto text-slate-300 mb-4" />
              <p className="text-slate-500">未找到符合条件的学生</p>
              <Button
                variant="outline"
                className="mt-4"
                onClick={() => {
                  setFilters({
                    searchTerm: '',
                    classes: [],
                    scoreRange: [0, 100],
                    debateCount: [0, 50],
                    improvementRange: [-20, 50],
                    activeStudents: true,
                    dateRange: 'all',
                    sortBy: 'name',
                    sortOrder: 'asc'
                  });
                }}
              >
                清除所有筛选条件
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default TeacherSearchFilter;