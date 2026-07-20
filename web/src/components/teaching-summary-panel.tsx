import React from 'react';
import { Loader2, Target } from 'lucide-react';
import type { TeachingSummaryResult } from '@/services/teacher.service';

interface TeachingSummaryPanelProps {
  summary: TeachingSummaryResult | null;
  loading?: boolean;
  onAnchorClick: (anchorId: string) => void;
}

const TeachingSummaryPanel: React.FC<TeachingSummaryPanelProps> = ({
  summary,
  loading = false,
  onAnchorClick,
}) => (
  <div
    className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
    aria-busy={loading}
  >
    <div className="mb-3 flex items-center justify-between gap-3">
      <div className="flex items-center gap-2 text-base font-semibold text-slate-900">
        <Target className="h-5 w-5 text-slate-600" />
        教师复盘摘要
      </div>
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin text-slate-500" />
      ) : null}
    </div>

    <div className="grid gap-4 md:grid-cols-3" aria-live="polite">
      <div>
        <div className="mb-2 text-sm font-medium text-slate-700">共性问题</div>
        <div className="space-y-2">
          {(summary?.common_issues || []).slice(0, 3).map((item, index) => (
            <div
              key={`${item.type || 'issue'}-${index}`}
              className="rounded-md bg-slate-50 p-3 text-sm text-slate-600"
            >
              <div className="font-medium text-slate-800">
                {item.title || item.type || '待关注项'}
              </div>
              {item.detail ? <div className="mt-1">{item.detail}</div> : null}
            </div>
          ))}
          {!summary?.common_issues?.length ? (
            <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-500">
              暂无明显共性问题
            </div>
          ) : null}
        </div>
      </div>

      <div>
        <div className="mb-2 text-sm font-medium text-slate-700">
          高价值片段
        </div>
        <div className="space-y-2">
          {(summary?.turning_points || []).slice(0, 3).map((item, index) => (
            <button
              key={`${item.speech_id || 'turn'}-${index}`}
              type="button"
              disabled={!item.anchor_id}
              onClick={() => item.anchor_id && onAnchorClick(item.anchor_id)}
              className="block w-full rounded-md bg-slate-50 p-3 text-left text-sm text-slate-600 transition hover:bg-slate-100 disabled:cursor-default disabled:hover:bg-slate-50"
            >
              <div className="font-medium text-slate-800">
                {item.speaker_name || '发言片段'}
                {item.overall_score ? ` · ${item.overall_score}` : ''}
              </div>
              {item.reason ? <div className="mt-1">{item.reason}</div> : null}
            </button>
          ))}
          {!summary?.turning_points?.length ? (
            <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-500">
              暂无可定位片段
            </div>
          ) : null}
        </div>
      </div>

      <div>
        <div className="mb-2 text-sm font-medium text-slate-700">后续训练</div>
        <div className="space-y-2">
          {(summary?.next_training_focus || [])
            .slice(0, 3)
            .map((item, index) => (
              <div
                key={`${item.focus || 'focus'}-${index}`}
                className="rounded-md bg-slate-50 p-3 text-sm text-slate-600"
              >
                <div className="font-medium text-slate-800">
                  {item.focus || '训练重点'}
                </div>
                {item.reason ? <div className="mt-1">{item.reason}</div> : null}
              </div>
            ))}
          {!summary?.next_training_focus?.length ? (
            <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-500">
              暂无训练建议
            </div>
          ) : null}
        </div>
      </div>
    </div>
  </div>
);

export default TeachingSummaryPanel;
