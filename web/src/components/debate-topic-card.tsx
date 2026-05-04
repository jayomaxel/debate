import React, { useState } from 'react';
import { Card, CardContent, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { parseDebateDescription } from '@/lib/debate-description';
import type { Debate } from '@/services/student.service';
import {
  BookOpen,
  ChevronDown,
  ChevronUp,
  Clock,
  FileText,
  Lightbulb,
  TrendingUp,
  Users,
} from 'lucide-react';

interface DebateTopicCardProps {
  debate?: Debate | null;
}

const DebateTopicCard: React.FC<DebateTopicCardProps> = ({ debate }) => {
  const [showBackground, setShowBackground] = useState(false);
  const descriptionMeta = parseDebateDescription(debate?.description);

  if (!debate) {
    return (
      <Card className="overflow-hidden rounded-[16px] border border-[#d7ccbf] bg-white/88 shadow-[0_14px_34px_rgba(58,42,28,0.07)]">
        <div className="bg-[#171717] p-5 text-white">
          <div className="mb-2 flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            <Badge className="border-white/20 bg-white/10 text-white">
              辩题信息
            </Badge>
          </div>
          <CardTitle className="mb-2 text-xl font-semibold text-white">
            暂无辩题信息
          </CardTitle>
        </div>
      </Card>
    );
  }

  const metrics = [
    debate.duration > 0
      ? {
          key: 'duration',
          icon: <Clock className="h-4 w-4 text-slate-700" />,
          label: '时长',
          value: `${debate.duration} 分钟`,
        }
      : null,
    typeof debate.participant_count === 'number' && debate.participant_count > 0
      ? {
          key: 'participants',
          icon: <Users className="h-4 w-4 text-slate-700" />,
          label: '参与者',
          value: `${debate.participant_count} 人`,
        }
      : null,
    descriptionMeta.roundsInfo
      ? {
          key: 'rounds',
          icon: <FileText className="h-4 w-4 text-slate-700" />,
          label: '轮次',
          value: descriptionMeta.roundsInfo.replace(/^发言轮次：/, ''),
        }
      : null,
  ].filter(Boolean) as Array<{
    key: string;
    icon: React.ReactNode;
    label: string;
    value: string;
  }>;

  const hasOverview = Boolean(descriptionMeta.raw);
  const hasKnowledgePoints = descriptionMeta.knowledgePoints.length > 0;
  const hasBackground = hasOverview || hasKnowledgePoints;

  return (
    <Card className="overflow-hidden rounded-[16px] border border-[#d7ccbf] bg-white/88 shadow-[0_14px_34px_rgba(58,42,28,0.07)]">
      <div className="bg-[#171717] p-5 text-white">
        <div className="mb-2 flex items-center gap-2">
          <TrendingUp className="h-5 w-5" />
          <Badge className="border-white/20 bg-white/10 text-white">
            本场辩题
          </Badge>
        </div>
        <CardTitle className="mb-2 text-xl font-semibold text-white">
          {debate.topic}
        </CardTitle>
        {descriptionMeta.roundsInfo ? (
          <p className="text-sm text-white/80">{descriptionMeta.roundsInfo}</p>
        ) : null}
      </div>

      <CardContent className="space-y-4 p-5">
        {metrics.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {metrics.map((item) => (
              <div key={item.key} className="student-card-muted p-3.5">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-slate-500">
                  {item.icon}
                  <span>{item.label}</span>
                </div>
                <div className="mt-2 text-sm font-medium text-slate-900">
                  {item.value}
                </div>
              </div>
            ))}
          </div>
        ) : null}

        {hasKnowledgePoints ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <BookOpen className="h-4 w-4 text-slate-700" />
              <span>支撑知识点</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {descriptionMeta.knowledgePoints.map((point, index) => (
                <Badge
                  key={`${point}-${index}`}
                  className="student-pill"
                  variant="outline"
                >
                  {point}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}

        {hasBackground ? (
          <>
            <Separator />
            <div>
              <Button
                variant="ghost"
                onClick={() => setShowBackground(!showBackground)}
                className="h-auto w-full justify-between rounded-[10px] p-3 text-left hover:bg-[#f7f2ea]"
              >
                <div className="flex items-center gap-2">
                  <Lightbulb className="h-4 w-4 text-slate-700" />
                  <span className="font-medium text-slate-900">背景资料</span>
                </div>
                {showBackground ? (
                  <ChevronUp className="h-4 w-4 text-slate-600" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-slate-600" />
                )}
              </Button>

              {showBackground ? (
                <div className="student-card-muted mt-3 space-y-4 p-4">
                  {hasOverview ? (
                    <div>
                      <h4 className="mb-2 font-medium text-slate-900">概述</h4>
                      <p className="text-sm leading-7 text-slate-600">
                        {descriptionMeta.raw}
                      </p>
                    </div>
                  ) : null}

                  {hasKnowledgePoints ? (
                    <div>
                      <h4 className="mb-2 font-medium text-slate-900">知识点</h4>
                      <ul className="space-y-2">
                        {descriptionMeta.knowledgePoints.map((point, index) => (
                          <li
                            key={`${point}-${index}`}
                            className="flex items-start gap-2 text-sm text-slate-600"
                          >
                            <div className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-slate-700" />
                            <span>{point}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          </>
        ) : null}
      </CardContent>
    </Card>
  );
};

export default DebateTopicCard;
