import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { DebateHistoryItem } from '@/services/student.service';
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
      return { bgColor: 'bg-emerald-100', textColor: 'text-emerald-700', label: '胜利' };
    case 'lose':
      return { bgColor: 'bg-red-100', textColor: 'text-red-700', label: '失败' };
    case 'draw':
      return { bgColor: 'bg-amber-100', textColor: 'text-amber-700', label: '平局' };
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
  const completedHistory = (history || []).filter(item => item.status === 'completed');
  const items = typeof limit === 'number' ? completedHistory.slice(0, limit) : completedHistory;

  return (
    <Card className="bg-white border-slate-200 shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-blue-600" />
            {title}
          </div>
          {showAllButton && (
            <Button variant="outline" size="sm" className="text-xs" onClick={onClickAll}>
              查看全部
              <ArrowRight className="w-3 h-3 ml-1" />
            </Button>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="text-center text-sm text-slate-500 py-10">暂无已完成的辩论记录</div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => {
              const resultConfig = getResultConfig(resolveResult(item));
              const date = item.created_at
                ? new Date(item.created_at).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
                : '--/--';
              const score = typeof item.score === 'number' ? item.score : Number(item.score || 0);
              const duration = formatDuration((item as any).duration_seconds);

              return (
                <div
                  key={item.debate_id}
                  className="flex items-center justify-between p-4 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer transition-colors"
                  onClick={() => onSelect(item.debate_id)}
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-slate-900">{date}</span>
                      <span className="text-sm text-slate-600">|</span>
                      <span className="text-sm text-slate-700 font-medium">{item.topic}</span>
                    </div>
                    <div className="text-xs text-slate-600">
                      {item.role} • {duration}
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <div className="text-lg font-bold text-slate-900">{score}</div>
                      <Badge className={resultConfig.bgColor + ' ' + resultConfig.textColor + ' border-0'}>
                        {resultConfig.label}
                      </Badge>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 px-2 text-xs"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelect(item.debate_id);
                        }}
                      >
                        <FileText className="w-4 h-4 mr-1" />
                        报告
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 px-2 text-xs"
                        onClick={(e) => {
                          e.stopPropagation();
                          onReplay?.(item.debate_id);
                        }}
                        disabled={!onReplay}
                      >
                        <Play className="w-4 h-4 mr-1" />
                        回放
                      </Button>
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
