import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Brain,
  Lightbulb,
  Target,
  TrendingUp,
  MessageSquare,
  Award,
  BookOpen,
  Star,
  ChevronDown,
  ChevronUp,
  Bot
} from 'lucide-react';

interface MentorFeedback {
  id: string;
  type: 'strength' | 'improvement' | 'strategy' | 'highlight';
  title: string;
  content: string;
  specificExamples: string[];
  actionItems: string[];
  priority: 'high' | 'medium' | 'low';
  timestamp: Date;
}

interface AIMentorFeedbackProps {
  feedbacks: MentorFeedback[];
  userName?: string;
  onViewDetails?: (feedback: MentorFeedback) => void;
}

const AIMentorFeedback: React.FC<AIMentorFeedbackProps> = ({
  feedbacks,
  userName = '同学',
  onViewDetails
}) => {
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set(['strength', 'improvement'])
  );

  const toggleCategory = (category: string) => {
    const newExpanded = new Set(expandedCategories);
    if (newExpanded.has(category)) {
      newExpanded.delete(category);
    } else {
      newExpanded.add(category);
    }
    setExpandedCategories(newExpanded);
  };

  const getFeedbackByType = (type: string) => {
    return feedbacks.filter(feedback => feedback.type === type);
  };

  const getSafeCategoryConfig = (type: string) => {
    const configs = {
      'strength': {
        title: '优势亮点',
        icon: <Star className="w-5 h-5 text-emerald-600" />,
        color: 'emerald',
        bgColor: 'bg-emerald-50',
        borderColor: 'border-emerald-300'
      },
      'improvement': {
        title: '改进建议',
        icon: <TrendingUp className="w-5 h-5 text-blue-600" />,
        color: 'blue',
        bgColor: 'bg-blue-50',
        borderColor: 'border-blue-300'
      },
      'strategy': {
        title: '策略指导',
        icon: <Target className="w-5 h-5 text-purple-600" />,
        color: 'purple',
        bgColor: 'bg-purple-50',
        borderColor: 'border-purple-300'
      },
      'highlight': {
        title: '精彩时刻',
        icon: <Award className="w-5 h-5 text-amber-600" />,
        color: 'amber',
        bgColor: 'bg-amber-50',
        borderColor: 'border-amber-300'
      },
      'default': {
        title: '其他反馈',
        icon: <MessageSquare className="w-5 h-5 text-slate-600" />,
        color: 'slate',
        bgColor: 'bg-slate-50',
        borderColor: 'border-slate-300'
      }
    };

    return configs[type as keyof typeof configs] || configs.default;
  };

  
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return 'bg-red-100 text-red-700 border-red-300';
      case 'medium': return 'bg-amber-100 text-amber-700 border-amber-300';
      case 'low': return 'bg-emerald-100 text-emerald-700 border-emerald-300';
      default: return 'bg-slate-100 text-slate-700 border-slate-300';
    }
  };

  const renderFeedbackCard = (feedback: MentorFeedback) => {
    const config = getSafeCategoryConfig(feedback.type);

    return (
      <Card
        key={feedback.id}
        className={`mb-3 ${config.bgColor} ${config.borderColor} border cursor-pointer hover:shadow-md transition-shadow`}
        onClick={() => onViewDetails?.(feedback)}
      >
        <CardContent className="p-4">
          <div className="flex items-start justify-between mb-3">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                {config.icon}
                <h4 className="font-semibold text-slate-900">{feedback.title}</h4>
                <Badge className={getPriorityColor(feedback.priority)} variant="outline">
                  {feedback.priority === 'high' && '重要'}
                  {feedback.priority === 'medium' && '建议'}
                  {feedback.priority === 'low' && '参考'}
                </Badge>
              </div>
              <p className="text-sm text-slate-700 leading-relaxed">
                {feedback.content}
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="text-slate-400 hover:text-slate-600 p-1"
            >
              <ChevronDown className="w-4 h-4" />
            </Button>
          </div>

          {feedback.specificExamples.length > 0 && (
            <div className="mt-3 p-2 bg-white/60 rounded border border-slate-200">
              <div className="text-xs font-medium text-slate-700 mb-1">
                具体例子：
              </div>
              <ul className="text-xs text-slate-600 space-y-1">
                {feedback.specificExamples.slice(0, 2).map((example, index) => (
                  <li key={index} className="flex items-start gap-1">
                    <div className="w-1 h-1 rounded-full bg-slate-400 mt-1.5 flex-shrink-0" />
                    {example}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {feedback.actionItems.length > 0 && (
            <div className="mt-3 p-2 bg-blue-50/60 rounded border border-blue-200">
              <div className="text-xs font-medium text-blue-700 mb-1">
                行动建议：
              </div>
              <ul className="text-xs text-blue-600 space-y-1">
                {feedback.actionItems.slice(0, 2).map((item, index) => (
                  <li key={index} className="flex items-start gap-1">
                    <div className="w-1 h-1 rounded-full bg-blue-400 mt-1.5 flex-shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  const categories = ['strength', 'improvement', 'strategy', 'highlight'];

  return (
    <Card className="bg-white border-slate-200 shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-blue-600" />
            AI导师智能评语
          </div>
          <div className="flex items-center gap-2">
            <Badge className="bg-blue-100 text-blue-700 border-blue-300">
              <Bot className="w-3 h-3 mr-1" />
              智能分析
            </Badge>
            <Badge className="bg-emerald-100 text-emerald-700 border-emerald-300">
              {feedbacks.length} 条反馈
            </Badge>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 开场白 */}
        <div className="p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg border border-blue-200">
          <div className="flex items-start gap-3">
            <Lightbulb className="w-5 h-5 text-blue-600 mt-0.5" />
            <div>
              <h3 className="font-semibold text-slate-900 mb-1">
                给 {userName} 的个性化反馈
              </h3>
              <p className="text-sm text-slate-600">
                基于您在本次辩论中的表现，AI导师为您生成了以下个性化分析报告。
                这些建议将帮助您在未来的辩论中取得更好的成绩。
              </p>
            </div>
          </div>
        </div>

        {/* 分类反馈 */}
        <div className="space-y-4">
          {categories.map(category => {
            const categoryFeedbacks = getFeedbackByType(category);
            const config = getSafeCategoryConfig(category);
            const isExpanded = expandedCategories.has(category);

            if (categoryFeedbacks.length === 0) return null;

            return (
              <div key={category} className={`${config.bgColor} rounded-lg p-4 border border-slate-200`}>
                <div
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => toggleCategory(category)}
                >
                  <div className="flex items-center gap-2">
                    {config.icon}
                    <h4 className="font-semibold text-slate-900">
                      {config.title}
                    </h4>
                    <Badge variant="outline" className="text-xs">
                      {categoryFeedbacks.length}
                    </Badge>
                  </div>
                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-slate-600" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-slate-600" />
                  )}
                </div>

                {isExpanded && (
                  <div className="mt-4 space-y-3">
                    {categoryFeedbacks.map(feedback => renderFeedbackCard(feedback))}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* 学习资源推荐 */}
        <div className="border-t border-slate-200 pt-4">
          <h4 className="font-medium text-slate-900 mb-3 flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-blue-600" />
            推荐学习资源
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <div className="flex items-center gap-2 mb-2">
                <MessageSquare className="w-4 h-4 text-blue-500" />
                <span className="text-sm font-medium text-slate-900">逻辑推理技巧</span>
              </div>
              <p className="text-xs text-slate-600">
                提升您的逻辑分析和论证能力
              </p>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <div className="flex items-center gap-2 mb-2">
                <Target className="w-4 h-4 text-purple-500" />
                <span className="text-sm font-medium text-slate-900">辩论策略课程</span>
              </div>
              <p className="text-xs text-slate-600">
                学习更有效的辩论技巧和策略
              </p>
            </div>
          </div>
        </div>

        {/* 底部操作 */}
        <div className="flex items-center justify-between pt-4 border-t border-slate-200">
          <div className="text-xs text-slate-500">
            AI分析时间：{new Date().toLocaleString('zh-CN')}
          </div>
          <Button
            variant="outline"
            size="sm"
            className="border-blue-300 text-blue-700 hover:bg-blue-50"
          >
            <MessageSquare className="w-4 h-4 mr-2" />
            反馈评语
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default AIMentorFeedback;
