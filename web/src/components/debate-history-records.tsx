import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { DebateHistoryItem } from '@/services/student.service';
import { formatDebateRole } from '@/lib/student-display';
import { ArrowRight, Clock, FileText, Play } from 'lucide-react';

interface DebateHistoryRecordsProps {
  history: DebateHistoryItem[];
  limit?: number;
  title?: string;
  showAllButton?: boolean;
  onClickAll?: () => void;
  onSelect: (debateId: string) => void;
  onReplay?: (debateId: string) => void;
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

const getResultConfig = (result: 'win' | 'lose' | 'draw') => {
  switch (result) {
    case 'win':
      return { className: 'student-card-soft-blue', label: '胜利' };
    case 'lose':
      return { className: 'student-card-soft-peach', label: '失利' };
    case 'draw':
      return { className: 'student-card-soft-lavender', label: '平局' };
  }
};

const resolveResult = (item: DebateHistoryItem): 'win' | 'lose' | 'draw' => {
  const normalizedOutcome = String((item as any).outcome || '').toLowerCase();
  if (normalizedOutcome === 'win') return 'win';
  if (normalizedOutcome === 'lose') return 'lose';
  if (normalizedOutcome === 'draw' || normalizedOutcome === 'tie') return 'draw';

  const score = typeof item.score === 'number' ? item.score : Number(item.score || 0);
  if (score >= 80) return 'win';
  if (score >= 60) return 'draw';
  return 'lose';
};

const DebateHistoryRecords: React.FC<DebateHistoryRecordsProps> = ({
  history,
  limit,
  title = '历史辩论记录',
  showAllButton = false,
  onClickAll,
  onSelect,
  onReplay,
}) => {
  const completedHistory = (history || []).filter((item) => item.status === 'completed');
  const items =
    typeof limit === 'number' ? completedHistory.slice(0, limit) : completedHistory;

  return (
    <Card className="rounded-[16px] border border-[#d7ccbf] bg-white/88 shadow-[0_14px_34px_rgba(58,42,28,0.07)]">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-slate-900">
            <Clock className="h-5 w-5 text-slate-700" />
            {title}
          </div>
          {showAllButton ? (
            <Button
              variant="outline"
              size="sm"
              className="student-light-button h-auto px-4 py-2 text-xs"
              onClick={onClickAll}
            >
              查看全部
              <ArrowRight className="ml-1 h-3 w-3" />
            </Button>
          ) : null}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="student-dashed-card py-10 text-center text-sm text-slate-500">
            暂无已完成的辩论记录
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => {
              const resultConfig = getResultConfig(resolveResult(item));
              const date = item.created_at
                ? new Date(item.created_at).toLocaleDateString('zh-CN', {
                    month: '2-digit',
                    day: '2-digit',
                  })
                : '--/--';
              const score = typeof item.score === 'number' ? item.score : Number(item.score || 0);
              const duration = formatDuration((item as any).duration_seconds);

              return (
                <div
                  key={item.debate_id}
                  className={`${resultConfig.className} cursor-pointer p-4 transition-colors duration-150 hover:border-[#b8a891] hover:bg-white/84`}
                  onClick={() => onSelect(item.debate_id)}
                >
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-slate-900">{date}</span>
                        <span className="text-sm text-slate-500">·</span>
                        <span className="text-sm font-medium text-slate-700">
                          {item.topic}
                        </span>
                      </div>
                      <div className="mt-2 text-xs text-slate-600">
                        {formatDebateRole(item.role)} · {duration}
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <div className="text-[1.4rem] font-semibold tracking-[-0.03em] text-slate-900">
                          {score}
                        </div>
                        <Badge className="student-pill">{resultConfig.label}</Badge>
                      </div>

                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="student-light-button h-auto px-3 py-2 text-xs"
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelect(item.debate_id);
                          }}
                        >
                          <FileText className="mr-1 h-4 w-4" />
                          报告
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="student-light-button h-auto px-3 py-2 text-xs"
                          onClick={(e) => {
                            e.stopPropagation();
                            onReplay?.(item.debate_id);
                          }}
                          disabled={!onReplay}
                        >
                          <Play className="mr-1 h-4 w-4" />
                          回放
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default DebateHistoryRecords;
