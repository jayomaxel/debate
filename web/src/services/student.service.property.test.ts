import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as fc from 'fast-check';
import StudentService, {
  type DebateHistory,
  type FilterHistoryParams,
} from './student.service';
import { api } from '../lib/api';

vi.mock('../lib/api', () => ({
  api: {
    get: vi.fn(),
  },
}));

const safeIdChars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_';
const isoTimestampArbitrary = fc.integer({
  min: Date.parse('2000-01-01T00:00:00.000Z'),
  max: Date.parse('2100-12-31T23:59:59.999Z'),
});
const dateOnlyArbitrary = isoTimestampArbitrary.map((timestamp) =>
  new Date(timestamp).toISOString().split('T')[0]
);

const debateIdArbitrary = fc.oneof(
  fc.uuid(),
  fc.array(fc.constantFrom(...safeIdChars.split('')), { minLength: 8, maxLength: 24 }).map((chars) => `debate-${chars.join('')}`)
);
const limitArbitrary = fc.integer({ min: 1, max: 100 });
const offsetArbitrary = fc.integer({ min: 0, max: 1_000 });
const historyStatusArbitrary = fc.constantFrom('draft', 'published', 'in_progress', 'completed');
const historyRoleArbitrary = fc.constantFrom('debater_1', 'debater_2', 'debater_3', 'debater_4');
const historyStanceArbitrary = fc.constantFrom('positive', 'negative', 'affirmative');

const debateHistoryArbitrary = fc.record({
  list: fc.array(
    fc.record({
      debate_id: debateIdArbitrary,
      topic: fc.string({ minLength: 5, maxLength: 100 }),
      role: historyRoleArbitrary,
      stance: historyStanceArbitrary,
      status: historyStatusArbitrary,
      score: fc.option(fc.integer({ min: 0, max: 100 }), { nil: undefined }),
      created_at: isoTimestampArbitrary.map((timestamp) => new Date(timestamp).toISOString()),
    }),
    { maxLength: 20 }
  ),
  total: fc.integer({ min: 0, max: 1_000 }),
  page: fc.integer({ min: 1, max: 100 }),
  page_size: limitArbitrary,
});

const filterHistoryParamsArbitrary = fc.record(
  {
    status: fc.option(historyStatusArbitrary, { nil: undefined }),
    role: fc.option(historyRoleArbitrary, { nil: undefined }),
    stance: fc.option(fc.constantFrom('affirmative', 'negative'), { nil: undefined }),
    start_date: fc.option(dateOnlyArbitrary, { nil: undefined }),
    end_date: fc.option(dateOnlyArbitrary, { nil: undefined }),
    limit: fc.option(limitArbitrary, { nil: undefined }),
    offset: fc.option(offsetArbitrary, { nil: undefined }),
  },
  { requiredKeys: [] }
);

type MockLink = {
  href: string;
  download: string;
  click: ReturnType<typeof vi.fn>;
};

describe('Student Service - Property-Based Tests', () => {
  let createdLinks: MockLink[] = [];

  beforeEach(() => {
    vi.clearAllMocks();
    createdLinks = [];
    global.URL.createObjectURL = vi.fn(() => 'blob:mock-url') as any;
    global.URL.revokeObjectURL = vi.fn() as any;
    vi.spyOn(document, 'createElement').mockImplementation(() => {
      const link = {
        href: '',
        download: '',
        click: vi.fn(),
      };
      createdLinks.push(link);
      return link as any;
    });
    vi.spyOn(document.body, 'appendChild').mockImplementation((node) => node as any);
    vi.spyOn(document.body, 'removeChild').mockImplementation((node) => node as any);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    createdLinks = [];
  });

  it('exports PDF reports with the current endpoint and filename contract', async () => {
    await fc.assert(
      fc.asyncProperty(debateIdArbitrary, async (debateId) => {
        const blob = new Blob(['pdf'], { type: 'application/pdf' });
        vi.mocked(api.get).mockReset();
        vi.mocked(api.get).mockResolvedValue(blob as never);
        createdLinks = [];

        await StudentService.exportReportPDF(debateId);

        expect(api.get).toHaveBeenCalledWith(`/api/student/reports/${debateId}/export/pdf`, {
          responseType: 'blob',
        });
        expect(createdLinks).toHaveLength(1);
        expect(createdLinks[0].href).toBe('blob:mock-url');
        expect(createdLinks[0].download).toBe(`debate_report_${debateId}.pdf`);
        expect(createdLinks[0].click).toHaveBeenCalled();
        expect(document.body.appendChild).toHaveBeenCalledWith(createdLinks[0]);
        expect(document.body.removeChild).toHaveBeenCalledWith(createdLinks[0]);
        expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
      }),
      { numRuns: 100 }
    );
  });

  it('exports Excel reports with the current endpoint and filename contract', async () => {
    await fc.assert(
      fc.asyncProperty(debateIdArbitrary, async (debateId) => {
        const blob = new Blob(['xlsx'], {
          type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        });
        vi.mocked(api.get).mockReset();
        vi.mocked(api.get).mockResolvedValue(blob as never);
        createdLinks = [];

        await StudentService.exportReportExcel(debateId);

        expect(api.get).toHaveBeenCalledWith(`/api/student/reports/${debateId}/export/excel`, {
          responseType: 'blob',
        });
        expect(createdLinks).toHaveLength(1);
        expect(createdLinks[0].href).toBe('blob:mock-url');
        expect(createdLinks[0].download).toBe(`debate_report_${debateId}.xlsx`);
        expect(createdLinks[0].click).toHaveBeenCalled();
        expect(document.body.appendChild).toHaveBeenCalledWith(createdLinks[0]);
        expect(document.body.removeChild).toHaveBeenCalledWith(createdLinks[0]);
        expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
      }),
      { numRuns: 100 }
    );
  });

  it('forwards getHistory pagination params and returns the API payload unchanged', async () => {
    await fc.assert(
      fc.asyncProperty(limitArbitrary, offsetArbitrary, debateHistoryArbitrary, async (limit, offset, history) => {
        vi.mocked(api.get).mockReset();
        vi.mocked(api.get).mockResolvedValue(history as never);

        const result = await StudentService.getHistory(limit, offset);

        expect(api.get).toHaveBeenCalledWith('/api/student/history', {
          params: { limit, offset },
        });
        expect(result).toEqual(history);
      }),
      { numRuns: 100 }
    );
  });

  it('uses the current default getHistory pagination values', async () => {
    await fc.assert(
      fc.asyncProperty(fc.constant(null), async () => {
        const history: DebateHistory = {
          list: [],
          total: 0,
          page: 1,
          page_size: 20,
        };
        vi.mocked(api.get).mockReset();
        vi.mocked(api.get).mockResolvedValue(history as never);

        const result = await StudentService.getHistory();

        expect(api.get).toHaveBeenCalledWith('/api/student/history', {
          params: { limit: 20, offset: 0 },
        });
        expect(result).toEqual(history);
      }),
      { numRuns: 100 }
    );
  });

  it('passes filterHistory params through as-is', async () => {
    await fc.assert(
      fc.asyncProperty(filterHistoryParamsArbitrary, debateHistoryArbitrary, async (params, history) => {
        vi.mocked(api.get).mockReset();
        vi.mocked(api.get).mockResolvedValue(history as never);

        const result = await StudentService.filterHistory(params as FilterHistoryParams);

        expect(api.get).toHaveBeenCalledWith('/api/student/history/filter', {
          params,
        });
        expect(result).toEqual(history);
      }),
      { numRuns: 100 }
    );
  });

  it('forwards the limit param for getGrowthTrend', async () => {
    await fc.assert(
      fc.asyncProperty(fc.integer({ min: 1, max: 50 }), async (limit) => {
        const trend = { debates: [] };
        vi.mocked(api.get).mockReset();
        vi.mocked(api.get).mockResolvedValue(trend as never);

        const result = await StudentService.getGrowthTrend(limit);

        expect(api.get).toHaveBeenCalledWith('/api/student/analytics/growth', {
          params: { limit },
        });
        expect(result).toEqual(trend);
      }),
      { numRuns: 100 }
    );
  });

  it('uses the current default getGrowthTrend limit', async () => {
    await fc.assert(
      fc.asyncProperty(fc.constant(null), async () => {
        const trend = { debates: [] };
        vi.mocked(api.get).mockReset();
        vi.mocked(api.get).mockResolvedValue(trend as never);

        const result = await StudentService.getGrowthTrend();

        expect(api.get).toHaveBeenCalledWith('/api/student/analytics/growth', {
          params: { limit: 10 },
        });
        expect(result).toEqual(trend);
      }),
      { numRuns: 100 }
    );
  });
});
