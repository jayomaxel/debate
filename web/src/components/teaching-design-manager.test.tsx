import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TeachingDesignManager from './teaching-design-manager';
import TeacherService from '@/services/teacher.service';

vi.mock('@/services/teacher.service', () => ({
  default: {
    getCurrentTeachingDesign: vi.fn(),
    listTeachingDesignVersions: vi.fn(),
    getTeachingDesignVersion: vi.fn(),
    activateTeachingDesignVersion: vi.fn(),
    correctTeachingDesignVersion: vi.fn(),
    uploadTeachingDesign: vi.fn(),
    saveTeachingDesign: vi.fn(),
  },
}));

describe('TeachingDesignManager', () => {
  beforeEach(() => {
    vi.mocked(TeacherService.getCurrentTeachingDesign).mockResolvedValue(null);
    vi.mocked(TeacherService.listTeachingDesignVersions).mockResolvedValue([]);
  });

  it('shows the independent teaching design entry and empty state', async () => {
    render(
      <TeachingDesignManager
        classes={[{ id: 'class-1', name: '一班', code: 'C1', teacher_id: 't1', student_count: 0, created_at: '' }]}
      />
    );
    expect(screen.getByText('教学设计中心')).toBeInTheDocument();
    expect(await screen.findByText(/当前班级还没有教学设计/)).toBeInTheDocument();
  });
});
