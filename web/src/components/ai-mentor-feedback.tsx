import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { formatStudentDateTime } from '@/lib/student-display';
import {
  Brain,
  Lightbulb,
  Target,
  TrendingUp,
  MessageSquare,
  Award,
  Star,
  ChevronDown,
  ChevronUp,
  Bot,
} from 'lucide-react';

interface MentorFeedback {
  id: string;
  type: 'strength' | 'improvement' | 'strategy' | 'highlight';
  title: string;
  content: string;
  specificExamples: string[];
  actionItems: string[];
  priority: 'high' | 'medium' | 'low';
  timestamp?: Date | null;
}

interface AIMentorFeedbackProps {
  feedbacks: MentorFeedback[];
  userName?: string;
  onViewDetails?: (feedback: MentorFeedback) => void;
  studentMode?: boolean;
}

const themeCard = (studentMode: boolean) =>
  studentMode
    ? 'rounded-[16px] border border-[#d7ccbf] bg-white/88 shadow-[0_14px_34px_rgba(58,42,28,0.07)]'
    : 'bg-white border-slate-200 shadow-sm';

const AIMentorFeedback: React.FC<AIMentorFeedbackProps> = ({
  feedbacks,
  userName = '同学',
  onViewDetails,
  studentMode = false,
}) => {
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set(['strength', 'improvement'])
  );
  const latestTimestamp = feedbacks.reduce<Date | null>((latest, feedback) => {
    if (!(feedback.timestamp instanceof Date) || Number.isNaN(feedback.timestamp.getTime())) {
      return latest;
    }

    if (!latest || feedback.timestamp.getTime() > latest.getTime()) {
      return feedback.timestamp;
    }

    return latest;
  }, null);
  const formattedTimestamp = formatStudentDateTime(latestTimestamp);

  const toggleCategory = (category: string) => {
    const next = new Set(expandedCategories);
    if (next.has(category)) {
      next.delete(category);
    } else {
      next.add(category);
    }
    setExpandedCategories(next);
  };

  const getFeedbackByType = (type: string) =>
    feedbacks.filter((feedback) => feedback.type === type);

  const getSafeCategoryConfig = (type: string) => {
    const configs = {
      strength: {
        title: '优势亮点',
        icon: <Star className="h-5 w-5 text-slate-700" />,
        tone: 'student-card-soft-blue',
      },
      improvement: {
        title: '改进建议',
        icon: <TrendingUp className="h-5 w-5 text-slate-700" />,
        tone: 'student-card-soft-peach',
      },
      strategy: {
        title: '策略指导',
        icon: <Target className="h-5 w-5 text-slate-700" />,
        tone: 'student-card-soft-lavender',
      },
      highlight: {
        title: '精彩时刻',
        icon: <Award className="h-5 w-5 text-slate-700" />,
        tone: 'student-card-muted',
      },
      default: {
        title: '其他反馈',
        icon: <MessageSquare className="h-5 w-5 text-slate-700" />,
        tone: 'student-card-muted',
      },
    } as const;

    return configs[type as keyof typeof configs] || configs.default;
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high':
        return 'bg-red-100 text-red-700 border-red-300';
      case 'medium':
        return 'bg-amber-100 text-amber-700 border-amber-300';
      case 'low':
        return 'bg-emerald-100 text-emerald-700 border-emerald-300';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-300';
    }
  };

  const renderFeedbackCard = (feedback: MentorFeedback) => {
    const config = getSafeCategoryConfig(feedback.type);

    return (
      <div
        key={feedback.id}
        className={`${config.tone} cursor-pointer p-4 transition-colors duration-150 hover:border-[#b8a891] hover:bg-white/84`}
        onClick={() => onViewDetails?.(feedback)}
      >
        <div className="mb-3 flex items-start justify-between">
          <div className="flex-1">
            <div className="mb-2 flex items-center gap-2">
              {config.icon}
              <h4 className="font-semibold text-slate-900">{feedback.title}</h4>
              <Badge className={getPriorityColor(feedback.priority)} variant="outline">
                {feedback.priority === 'high' && '重要'}
                {feedback.priority === 'medium' && '建议'}
                {feedback.priority === 'low' && '参考'}
              </Badge>
            </div>
            <p className="text-sm leading-7 text-slate-700">{feedback.content}</p>
          </div>
          <Button variant="ghost" size="sm" className="h-auto p-1 text-slate-400">
            <ChevronDown className="h-4 w-4" />
          </Button>
        </div>

        {feedback.specificExamples.length > 0 ? (
          <div className="student-card-muted mt-3 p-3">
            <div className="mb-1 text-xs font-medium text-slate-700">具体例子</div>
            <ul className="space-y-1 text-xs text-slate-600">
              {feedback.specificExamples.slice(0, 2).map((example, index) => (
                <li key={index} className="flex items-start gap-1">
                  <div className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-slate-400" />
                  {example}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {feedback.actionItems.length > 0 ? (
          <div className="student-card-muted mt-3 p-3">
            <div className="mb-1 text-xs font-medium text-slate-700">行动建议</div>
            <ul className="space-y-1 text-xs text-slate-600">
              {feedback.actionItems.slice(0, 2).map((item, index) => (
                <li key={index} className="flex items-start gap-1">
                  <div className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-slate-400" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    );
  };

  const categories = ['strength', 'improvement', 'strategy', 'highlight'];

  return (
    <Card className={themeCard(studentMode)}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-slate-700" />
            AI 导师智能评语
          </div>
          <div className="flex items-center gap-2">
            <Badge className="student-pill">
              <Bot className="mr-1 h-3 w-3" />
              智能分析
            </Badge>
            <Badge className="student-pill">{feedbacks.length} 条反馈</Badge>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="student-card-soft-blue p-4">
          <div className="flex items-start gap-3">
            <Lightbulb className="mt-1 h-5 w-5 text-slate-700" />
            <div>
              <h3 className="font-semibold text-slate-900">
                给 {userName} 的个性化反馈
              </h3>
              <p className="mt-2 text-sm leading-7 text-slate-600">
                基于你在本次辩论中的表现，AI 导师为你生成了以下个性化分析与建议，帮助你在下一场辩论中更有方向地进步。
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          {categories.map((category) => {
            const categoryFeedbacks = getFeedbackByType(category);
            const config = getSafeCategoryConfig(category);
            const isExpanded = expandedCategories.has(category);

            if (categoryFeedbacks.length === 0) return null;

            return (
              <div key={category} className={`${config.tone} p-4`}>
                <div
                  className="flex cursor-pointer items-center justify-between"
                  onClick={() => toggleCategory(category)}
                >
                  <div className="flex items-center gap-2">
                    {config.icon}
                    <h4 className="font-semibold text-slate-900">{config.title}</h4>
                    <Badge className="student-pill">{categoryFeedbacks.length}</Badge>
                  </div>
                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4 text-slate-600" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-slate-600" />
                  )}
                </div>

                {isExpanded ? (
                  <div className="mt-4 space-y-3">
                    {categoryFeedbacks.map((feedback) => renderFeedbackCard(feedback))}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>

        <div
          className={`flex items-center border-t border-black/5 pt-4 ${
            formattedTimestamp ? 'justify-between' : 'justify-end'
          }`}
        >
          {formattedTimestamp ? (
            <div className="text-xs text-slate-500">
              AI 分析时间：{formattedTimestamp}
            </div>
          ) : null}
          <Button variant="outline" size="sm" className="student-light-button h-auto px-4 py-2">
            <MessageSquare className="mr-2 h-4 w-4" />
            反馈评语
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default AIMentorFeedback;
