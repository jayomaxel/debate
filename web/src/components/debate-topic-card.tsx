import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { parseDebateDescription } from '@/lib/debate-description';
import type { Debate } from '@/services/student.service';
import {
  TrendingUp,
  DollarSign,
  Shield,
  Clock,
  Users,
  BookOpen,
  ChevronDown,
  ChevronUp,
  FileText,
  Lightbulb
} from 'lucide-react';

interface DebateTopic {
  title: string;
  subtitle: string;
  description: string;
  knowledgePoints: string[];
  duration: string;
  participants: number;
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  background: {
    overview: string;
    keyPoints: string[];
    resources: Array<{
      title: string;
      type: 'article' | 'video' | 'document';
      url: string;
    }>;
  };
}

interface DebateTopicCardProps {
  debate?: Debate | null;
}

const DebateTopicCard: React.FC<DebateTopicCardProps> = ({ debate }) => {
  const [showBackground, setShowBackground] = useState(false);
  const descriptionMeta = parseDebateDescription(debate?.description);

  const debateTopic: DebateTopic = debate
    ? {
        title: debate.topic,
        subtitle: '',
        description: descriptionMeta.roundsInfo || descriptionMeta.raw || '请围绕该辩题准备论据与反驳点。',
        knowledgePoints: descriptionMeta.knowledgePoints,
        duration: `${debate.duration}分钟`,
        participants: debate.participant_count ?? 4,
        difficulty: 'intermediate',
        background: {
          overview: descriptionMeta.knowledgePointsText
            ? `建议围绕以下支撑知识点准备论据与反驳：${descriptionMeta.knowledgePointsText}`
            : descriptionMeta.raw && !descriptionMeta.hasStructuredMeta
              ? descriptionMeta.raw
              : '建议在辩论前熟悉背景资料，准备支持观点的论据和例子。',
          keyPoints: [
            '明确正反方核心立场与论点边界',
            '准备数据、案例、类比等证据链',
            '预判对方可能攻击点并准备反驳',
            '总结提炼价值主张与政策建议（如适用）'
          ],
          resources: []
        }
      }
    : {
        title: '人类应不应该与高度拟人化的AI伴侣建立真实的感情羁绊？',
        subtitle: 'Should humans form genuine emotional bonds with highly anthropomorphic AI companions?',
        description: '探讨AI伴侣在情感陪伴、心理支持、伦理风险与社会关系中的角色边界',
        knowledgePoints: ['情感计算', '自然语言处理(NLP)', '人机交互心理学', 'AI伦理'],
        duration: '30分钟',
        participants: 4,
        difficulty: 'intermediate',
        background: {
          overview: '高度拟人化AI伴侣正在从聊天工具走向长期陪伴对象。围绕情感依附、替代关系、隐私风险与人机边界的讨论，正在成为AI社会应用中的核心议题。',
          keyPoints: [
            '情感计算与拟人化设计会显著提升用户依恋感和信任感',
            'AI伴侣可能提供陪伴、倾听与情绪支持，但也可能带来情感替代风险',
            '长期互动会涉及隐私数据、心理依赖和价值观塑造等伦理问题',
            '需要从AI伦理、人机关系与社会影响三个层面进行综合评估',
            '讨论焦点不只是“能不能做”，还包括“应不应该鼓励形成真实羁绊”'
          ],
          resources: [
            {
              title: '情感计算与AI伴侣研究综述',
              type: 'document',
              url: '#'
            },
            {
              title: '人机关系与数字陪伴伦理分析',
              type: 'article',
              url: '#'
            },
            {
              title: 'AI伴侣产品中的隐私与心理风险',
              type: 'video',
              url: '#'
            }
          ]
        }
      };

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'beginner':
        return 'bg-emerald-100 text-emerald-700 border-emerald-300';
      case 'intermediate':
        return 'bg-amber-100 text-amber-700 border-amber-300';
      case 'advanced':
        return 'bg-red-100 text-red-700 border-red-300';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-300';
    }
  };

  const getDifficultyLabel = (difficulty: string) => {
    switch (difficulty) {
      case 'beginner':
        return '入门级';
      case 'intermediate':
        return '中级';
      case 'advanced':
        return '高级';
      default:
        return '未知';
    }
  };

  const getResourceIcon = (type: string) => {
    switch (type) {
      case 'document':
        return <FileText className="w-4 h-4" />;
      case 'video':
        return <div className="w-4 h-4 bg-red-500 rounded-sm flex items-center justify-center text-white text-xs">▶</div>;
      case 'article':
        return <BookOpen className="w-4 h-4" />;
      default:
        return <FileText className="w-4 h-4" />;
    }
  };

  return (
    <Card className="bg-gradient-to-br from-blue-50 to-purple-50 border-blue-200 shadow-lg overflow-hidden">
      {/* 顶部渐变背景 */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white p-6">
        <div className="flex items-center gap-2 mb-2">
          <TrendingUp className="w-6 h-6" />
          <Badge className="bg-white/20 text-white border-white/30">
            {debate ? '本场辩题' : '今日辩题'}
          </Badge>
        </div>
        <CardTitle className="text-2xl font-bold mb-2 text-white">
          {debateTopic.title}
        </CardTitle>
        <p className="text-blue-100 text-sm mb-1">{debateTopic.subtitle}</p>
        <p className="text-white/90 text-sm">{debateTopic.description}</p>
      </div>

      <CardContent className="p-6 space-y-4">
        {/* 辩论信息 */}
        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center gap-2 text-slate-700">
            <Clock className="w-4 h-4 text-blue-600" />
            <span className="text-sm">时长: {debateTopic.duration}</span>
          </div>
          <div className="flex items-center gap-2 text-slate-700">
            <Users className="w-4 h-4 text-blue-600" />
            <span className="text-sm">参与者: {debateTopic.participants}人</span>
          </div>
        </div>

        {/* 难度标签 */}
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-600">难度等级:</span>
          <Badge className={getDifficultyColor(debateTopic.difficulty)} variant="outline">
            <Shield className="w-3 h-3 mr-1" />
            {getDifficultyLabel(debateTopic.difficulty)}
          </Badge>
        </div>

        {debateTopic.knowledgePoints.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <BookOpen className="w-4 h-4 text-blue-600" />
              <span>支撑知识点</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {debateTopic.knowledgePoints.map((point, index) => (
                <Badge
                  key={`${point}-${index}`}
                  variant="outline"
                  className="bg-blue-50 text-blue-700 border-blue-200"
                >
                  {point}
                </Badge>
              ))}
            </div>
          </div>
        )}

        <Separator />

        {/* 背景资料展开/收起 */}
        <div>
          <Button
            variant="ghost"
            onClick={() => setShowBackground(!showBackground)}
            className="w-full justify-between p-3 h-auto text-left hover:bg-blue-50"
          >
            <div className="flex items-center gap-2">
              <Lightbulb className="w-4 h-4 text-blue-600" />
              <span className="font-medium text-slate-900">背景资料</span>
            </div>
            {showBackground ? (
              <ChevronUp className="w-4 h-4 text-slate-600" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-600" />
            )}
          </Button>

          {showBackground && (
            <div className="mt-4 p-4 bg-white rounded-lg border border-slate-200 space-y-4">
              {/* 概述 */}
              <div>
                <h4 className="font-medium text-slate-900 mb-2">概述</h4>
                <p className="text-sm text-slate-600 leading-relaxed">
                  {debateTopic.background.overview}
                </p>
              </div>

              {/* 关键点 */}
              <div>
                <h4 className="font-medium text-slate-900 mb-2">关键论点</h4>
                <ul className="space-y-2">
                  {debateTopic.background.keyPoints.map((point, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm text-slate-600">
                      <div className="w-1.5 h-1.5 bg-blue-600 rounded-full mt-1.5 flex-shrink-0" />
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* 学习资源 */}
              <div>
                <h4 className="font-medium text-slate-900 mb-2">推荐学习资源</h4>
                <div className="space-y-2">
                  {debateTopic.background.resources.map((resource, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-3 p-2 hover:bg-blue-50 rounded cursor-pointer transition-colors"
                    >
                      <div className="text-blue-600">
                        {getResourceIcon(resource.type)}
                      </div>
                      <span className="text-sm text-slate-700 flex-1">{resource.title}</span>
                      <Badge variant="outline" className="text-xs">
                        {resource.type === 'document' && '文档'}
                        {resource.type === 'video' && '视频'}
                        {resource.type === 'article' && '文章'}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 快速提示 */}
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
          <div className="flex items-start gap-2">
            <Lightbulb className="w-4 h-4 text-amber-600 mt-0.5" />
            <div className="text-sm">
              <p className="font-medium text-amber-900 mb-1">辩论提示</p>
              <p className="text-amber-700">
                建议在辩论前熟悉背景资料，准备支持您观点的论据和例子。记住，良好的辩论不仅是表达观点，更要倾听对手并有效回应。
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default DebateTopicCard;
