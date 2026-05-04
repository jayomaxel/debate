import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PreparationAssistantPage from './preparation-assistant-page';
import StudentService from '@/services/student.service';

const toastMock = vi.fn();

vi.mock('@/services/student.service', () => ({
  default: {
    getKBSessions: vi.fn(),
    getKBConversationHistory: vi.fn(),
    getKBDocuments: vi.fn(),
    downloadKBDocument: vi.fn(),
  },
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: toastMock,
  }),
}));

vi.mock('@/store/auth.context', () => ({
  useAuth: () => ({
    user: {
      id: 'student-001',
      name: '测试学生',
    },
  }),
}));

const createSseResponse = (events: unknown[]) => {
  const encoder = new TextEncoder();

  return {
    ok: true,
    body: new ReadableStream({
      start(controller) {
        events.forEach((event) => {
          controller.enqueue(
            encoder.encode(`data: ${JSON.stringify(event)}\n\n`)
          );
        });
        controller.close();
      },
    }),
  } as Response;
};

describe('PreparationAssistantPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('access_token', 'test-token');
    vi.stubGlobal('fetch', vi.fn());
    (StudentService.getKBDocuments as any).mockResolvedValue({
      documents: [],
      total: 0,
      page: 1,
      page_size: 50,
      total_pages: 0,
    });
  });

  it('loads the latest saved session on entry', async () => {
    (StudentService.getKBSessions as any).mockResolvedValue([
      {
        session_id: 'session-1',
        title: '最近会话',
        updated_at: '2026-04-07T01:00:00.000Z',
      },
    ]);
    (StudentService.getKBConversationHistory as any).mockResolvedValue([
      {
        id: 'conv-1',
        question: '历史问题',
        answer: '历史回答',
        sources: [],
        created_at: '2026-04-07T01:00:00.000Z',
      },
    ]);

    render(<PreparationAssistantPage onBack={vi.fn()} />);

    await waitFor(() => {
      expect(StudentService.getKBConversationHistory).toHaveBeenCalledWith(
        'session-1'
      );
    });
    await waitFor(() => {
      expect(StudentService.getKBDocuments).toHaveBeenCalledWith(1, 50);
    });

    await waitFor(() => {
      expect(screen.getByText('历史问题')).toBeInTheDocument();
    });
    expect(screen.getByText('历史回答')).toBeInTheDocument();
  });

  it('keeps the optimistic message visible while a brand-new session is streaming', async () => {
    (StudentService.getKBSessions as any)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        {
          session_id: 'session-new',
          title: '新会话',
          updated_at: '2026-04-07T01:13:18.000Z',
        },
      ]);
    (StudentService.getKBConversationHistory as any).mockResolvedValue([]);
    (fetch as any).mockResolvedValue(
      createSseResponse([
        { type: 'sources', data: [] },
        { type: 'answer', content: '这是回答' },
        { type: 'done', id: 'conv-new' },
      ])
    );

    const { container } = render(
      <PreparationAssistantPage onBack={vi.fn()} />
    );

    const textarea = container.querySelector('textarea');
    expect(textarea).not.toBeNull();

    fireEvent.change(textarea!, { target: { value: '这是新问题' } });
    fireEvent.keyDown(textarea!, { key: 'Enter', shiftKey: false });

    await waitFor(() => {
      expect(screen.getByText('这是新问题')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('这是回答')).toBeInTheDocument();
    });

    expect(StudentService.getKBConversationHistory).not.toHaveBeenCalled();
  });

  it('renders knowledge-base documents and supports downloading them', async () => {
    (StudentService.getKBSessions as any).mockResolvedValue([]);
    (StudentService.getKBConversationHistory as any).mockResolvedValue([]);
    (StudentService.getKBDocuments as any).mockResolvedValue({
      documents: [
        {
          id: 'doc-001',
          filename: 'AI辩题资料.pdf',
          file_type: 'pdf',
          file_size: 204800,
          upload_status: 'processed',
          uploaded_by: 'teacher-001',
          uploaded_at: '2026-05-03T00:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      page_size: 50,
      total_pages: 1,
    });

    render(<PreparationAssistantPage onBack={vi.fn()} />);

    expect(await screen.findByText('AI辩题资料.pdf')).toBeInTheDocument();

    const downloadButtons = screen.getAllByRole('button');
    fireEvent.click(downloadButtons[downloadButtons.length - 1]);

    await waitFor(() => {
      expect(StudentService.downloadKBDocument).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 'doc-001',
        })
      );
    });
  });
});
