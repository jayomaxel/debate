import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import SkillsRadar, {
  DEFAULT_SKILLS_EMPTY_STATE_MESSAGE,
  createEditableDefaultSkills,
  createEmptySkills,
  mergeAssessmentIntoSkills,
} from './skills-radar';

describe('SkillsRadar', () => {
  it('uses null values instead of hardcoded default scores', () => {
    expect(createEditableDefaultSkills().map((skill) => skill.value)).toEqual([
      null,
      null,
      null,
      null,
      null,
    ]);
  });

  it('shows an empty state when all skill values are null', () => {
    render(<SkillsRadar skills={createEmptySkills()} />);

    expect(screen.getByText(DEFAULT_SKILLS_EMPTY_STATE_MESSAGE)).toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('renders read-only progress values when assessment data exists', () => {
    const skills = mergeAssessmentIntoSkills(createEmptySkills(), {
      expression_willingness: 66,
      logical_thinking: 72,
      stablecoin_knowledge: 58,
      financial_knowledge: 88,
      critical_thinking: 79,
      recommended_role: '一辩',
      role_description: '推荐测试角色',
    });

    render(<SkillsRadar skills={skills} />);

    expect(screen.getByText('88%')).toBeInTheDocument();
    expect(screen.getByText('58%')).toBeInTheDocument();
    expect(screen.getAllByRole('progressbar')).toHaveLength(5);
    expect(screen.queryByText(DEFAULT_SKILLS_EMPTY_STATE_MESSAGE)).not.toBeInTheDocument();
  });
});
