import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import TeachingSummaryPanel from './teaching-summary-panel';

describe('TeachingSummaryPanel', () => {
  it('renders teacher review data and opens an available speech anchor', () => {
    const onAnchorClick = vi.fn();
    render(
      <TeachingSummaryPanel
        loading={false}
        onAnchorClick={onAnchorClick}
        summary={{
          debate_id: 'debate-1',
          common_issues: [
            { title: '证据链不完整', detail: '结论缺少来源支撑' },
          ],
          turning_points: [
            {
              speech_id: 'speech-1',
              anchor_id: 'anchor-1',
              speaker_name: '正方三辩',
              reason: '完成关键反驳',
            },
          ],
          next_training_focus: [
            { focus: '影响比较', reason: '明确双方代价差异' },
          ],
        }}
      />
    );

    expect(screen.getByText('证据链不完整')).toBeInTheDocument();
    expect(screen.getByText('影响比较')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /正方三辩/ }));
    expect(onAnchorClick).toHaveBeenCalledWith('anchor-1');
  });
});
