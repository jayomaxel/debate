import React, { useEffect, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { DebateConfigMeta, TopicCandidateContract } from '@/lib/frontend-contracts';
import TeacherService from '@/services/teacher.service';
import { Lightbulb, Loader2, RefreshCw } from 'lucide-react';

interface TopicRecommendationPanelProps {
  classId: string;
  onSelect: (topic: string, config: DebateConfigMeta) => void;
}

const TopicRecommendationPanel: React.FC<TopicRecommendationPanelProps> = ({
  classId,
  onSelect,
}) => {
  const [designId, setDesignId] = useState<string | null>(null);
  const [chapterFocus, setChapterFocus] = useState('');
  const [trainingFocus, setTrainingFocus] = useState('');
  const [classroomScene, setClassroomScene] = useState('');
  const [candidates, setCandidates] = useState<TopicCandidateContract[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setCandidates([]);
    setRunId(null);
    if (!classId) {
      setDesignId(null);
      return;
    }
    TeacherService.getCurrentTeachingDesign(classId)
      .then((value) => setDesignId(value?.id || null))
      .catch(() => setDesignId(null));
  }, [classId]);

  const generate = async (regenerate = false) => {
    if (!classId || !designId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await TeacherService.generateTopicRecommendations(classId, {
        teaching_design_version_id: designId,
        mode: 'teaching',
        preferred_count: 4,
        regenerate_from_run_id: regenerate ? runId || undefined : undefined,
        activity_focus: {
          chapter_focus: chapterFocus || undefined,
          training_focus: trainingFocus || undefined,
          classroom_scene: classroomScene || undefined,
        },
      });
      setCandidates(result.candidates || []);
      setRunId(result.run_id);
      if (!result.candidates?.length) setError(result.warnings?.[0] || '没有生成可用辩题');
    } catch (err: any) {
      setError(err?.message || '候选辩题生成失败，手动填写仍可继续');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className='space-y-4 rounded-lg border border-blue-100 bg-blue-50/40 p-4'>
      <div className='flex flex-wrap items-center justify-between gap-3'>
        <div>
          <div className='flex items-center gap-2 font-medium text-slate-900'><Lightbulb className='h-4 w-4 text-blue-600' />教学设计与辩题推荐</div>
          <p className='mt-1 text-sm text-slate-500'>{designId ? '已读取当前班级教学设计' : '当前班级没有教学设计，仍可手动填写辩题'}</p>
        </div>
        <Button type='button' variant='outline' disabled={!designId || loading} onClick={() => void generate(Boolean(runId))}>
          {loading ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : runId ? <RefreshCw className='mr-2 h-4 w-4' /> : null}
          {runId ? '重新生成' : '生成候选辩题'}
        </Button>
      </div>
      <div className='grid gap-3 md:grid-cols-3'>
        <div className='space-y-1'><Label>章节重点</Label><Input value={chapterFocus} onChange={(event) => setChapterFocus(event.target.value)} /></div>
        <div className='space-y-1'><Label>训练目标</Label><Input value={trainingFocus} onChange={(event) => setTrainingFocus(event.target.value)} /></div>
        <div className='space-y-1'><Label>课堂场景</Label><Input value={classroomScene} onChange={(event) => setClassroomScene(event.target.value)} /></div>
      </div>
      {error && <Alert><AlertDescription>{error}</AlertDescription></Alert>}
      {candidates.length > 0 && (
        <div className='grid gap-3 lg:grid-cols-2'>
          {candidates.map((candidate) => (
            <Card key={candidate.candidate_id} className='border-slate-200'>
              <CardContent className='space-y-3 p-4'>
                <div className='font-medium text-slate-900'>{candidate.topic_text}</div>
                <div className='flex flex-wrap gap-1'>
                  {candidate.mapped_knowledge_points.map((item) => <Badge key={item} variant='secondary'>{item}</Badge>)}
                  {candidate.difficulty_level && <Badge variant='outline'>{candidate.difficulty_level}</Badge>}
                </div>
                <p className='text-sm text-slate-600'>{candidate.debatability_reason || candidate.recommendation_reason}</p>
                <Button type='button' size='sm' onClick={() => onSelect(candidate.topic_text, {
                  teaching_design_version_id: designId || undefined,
                  topic_recommendation_run_id: runId || undefined,
                  selected_topic_candidate_id: candidate.candidate_id,
                  topic_source: 'ai_recommended',
                  activity_focus: {
                    chapter_focus: chapterFocus || undefined,
                    training_focus: trainingFocus || undefined,
                    classroom_scene: classroomScene || undefined,
                  },
                })}>选用此辩题</Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default TopicRecommendationPanel;
