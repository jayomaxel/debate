/**
 * Property-Based Tests for Student Service
 * 
 * Feature: frontend-backend-integration
 * Tests Properties 14 and 17 from the design document
 * 
 * **Validates: Requirements 9.5, 10.3**
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as fc from 'fast-check';
import StudentService, {
  type DebateHistory,
  type FilterHistoryParams,
} from './student.service';
import { api } from '../lib/api';

// Mock dependencies
vi.mock('../lib/api', () => ({
  api: {
    get: vi.fn(),
  },
}));

// ==================== Arbitraries (Generators) ====================

/**
 * Generator for valid debate IDs
 */
const debateIdArbitrary = fc.oneof(
  fc.uuid(),
  fc.string({ minLength: 10, maxLength: 30 }).map(s => `debate-${s}`)
);

/**
 * Generator for pagination limit (1-100)
 */
const limitArbitrary = fc.integer({ min: 1, max: 100 });

/**
 * Generator for pagination offset (0-1000)
 */
const offsetArbitrary = fc.integer({ min: 0, max: 1000 });

/**
 * Generator for file extensions
 */
const fileExtensionArbitrary = fc.constantFrom('pdf', 'xlsx');

/**
 * Generator for debate history response
 */
const debateHistoryArbitrary = fc.record({
  list: fc.array(
    fc.record({
      debate_id: debateIdArbitrary,
      topic: fc.string({ minLength: 5, maxLength: 100 }),
      role: fc.constantFrom('一辩', '二辩', '三辩', '四辩'),
      stance: fc.constantFrom('affirmative' as const, 'negative' as const),
      status: fc.constantFrom('draft', 'published', 'in_progress', 'completed'),
      score: fc.option(fc.integer({ min: 0, max: 100 }), { nil: undefined }),
      created_at: fc.date().map(d => d.toISOString()),
    }),
    { minLength: 0, maxLength: 20 }
  ),
  total: fc.integer({ min: 0, max: 1000 }),
  page: fc.integer({ min: 1, max: 100 }),
  page_size: fc.integer({ min: 1, max: 100 }),
});

/**
 * Generator for filter history parameters
 */
const filterHistoryParamsArbitrary = fc.record({
  status: fc.option(fc.constantFrom('draft', 'published', 'in_progress', 'completed'), { nil: undefined }),
  role: fc.option(fc.constantFrom('一辩', '二辩', '三辩', '四辩'), { nil: undefined }),
  stance: fc.option(fc.constantFrom('affirmative', 'negative'), { nil: undefined }),
  start_date: fc.option(fc.date().map(d => d.toISOString().split('T')[0]), { nil: undefined }),
  end_date: fc.option(fc.date().map(d => d.toISOString().split('T')[0]), { nil: undefined }),
  limit: fc.option(limitArbitrary, { nil: undefined }),
  offset: fc.option(offsetArbitrary, { nil: undefined }),
});

describe('Student Service - Property-Based Tests', () => {
  let createdLinks: any[] = [];

  beforeEach(() => {
    vi.clearAllMocks();
    createdLinks = [];
    
    // Mock DOM APIs for file download tests
    global.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
    global.URL.revokeObjectURL = vi.fn();
    
    // Mock document.createElement to return a new mock link each time and track it
    vi.spyOn(document, 'createElement').mockImplementation(() => {
      const mockLink = {
        href: '',
        download: '',
        click: vi.fn(),
      };
      createdLinks.push(mockLink);
      return mockLink as any;
    });
    vi.spyOn(document.body, 'appendChild').mockImplementation((node) => node as any);
    vi.spyOn(document.body, 'removeChild').mockImplementation((node) => node as any);
  });

  afterEach(() => {
    vi.clearAllMocks();
    createdLinks = [];
  });

  describe('Property 14: File Download Filename', () => {
    /**
     * **Validates: Requirements 9.5**
     * 
     * Property: For any file download operation (PDF or Excel), the system should set
     * a descriptive filename in the format `{type}_report_{debate_id}.{extension}`.
     * 
     * Feature: frontend-backend-integration, Property 14: File Download Filename
     */
    it('should set correct filename format for PDF downloads for any debate ID', () => {
      fc.assert(
        fc.property(debateIdArbitrary, async (debateId) => {
          // Arrange: Mock blob response
          const mockBlob = new Blob(['mock pdf content'], { type: 'application/pdf' });
          vi.mocked(api.get).mockResolvedValue(mockBlob as any);

          // Clear previous links
          createdLinks = [];

          // Act: Export PDF report
          await StudentService.exportReportPDF(debateId);

          // Assert: Filename should follow the pattern debate_report_{debate_id}.pdf
          expect(createdLinks).toHaveLength(1);
          expect(createdLinks[0].download).toBe(`debate_report_${debateId}.pdf`);
        }),
        { numRuns: 100 }
      );
    });

    it('should set correct filename format for Excel downloads for any debate ID', () => {
      fc.assert(
        fc.property(debateIdArbitrary, async (debateId) => {
          // Arrange: Mock blob response
          const mockBlob = new Blob(['mock excel content'], { 
            type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
          });
          vi.mocked(api.get).mockResolvedValue(mockBlob as any);

          // Clear previous links
          createdLinks = [];

          // Act: Export Excel report
          await StudentService.exportReportExcel(debateId);

          // Assert: Filename should follow the pattern debate_report_{debate_id}.xlsx
          expect(createdLinks).toHaveLength(1);
          expect(createdLinks[0].download).toBe(`debate_report_${debateId}.xlsx`);
        }),
        { numRuns: 100 }
      );
    });

    it('should use correct file extension for PDF downloads', () => {
      fc.assert(
        fc.property(debateIdArbitrary, async (debateId) => {
          // Arrange: Mock blob response
          const mockBlob = new Blob(['mock pdf content'], { type: 'application/pdf' });
          vi.mocked(api.get).mockResolvedValue(mockBlob as any);

          // Clear previous links
          createdLinks = [];

          // Act: Export PDF report
          await StudentService.exportReportPDF(debateId);

          // Assert: Filename should end with .pdf
          expect(createdLinks).toHaveLength(1);
          expect(createdLinks[0].download).toMatch(/\.pdf$/);
        }),
        { numRuns: 100 }
      );
    });

    it('should use correct file extension for Excel downloads', () => {
      fc.assert(
        fc.property(debateIdArbitrary, async (debateId) => {
          // Arrange: Mock blob response
          const mockBlob = new Blob(['mock excel content'], { 
            type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
          });
          vi.mocked(api.get).mockResolvedValue(mockBlob as any);

          // Clear previous links
          createdLinks = [];

          // Act: Export Excel report
          await StudentService.exportReportExcel(debateId);

          // Assert: Filename should end with .xlsx
          expect(createdLinks).toHaveLength(1);
          expect(createdLinks[0].download).toMatch(/\.xlsx$/);
        }),
        { numRuns: 100 }
      );
    });

    it('should include debate_id in filename for any valid debate ID', () => {
      fc.assert(
        fc.property(debateIdArbitrary, fileExtensionArbitrary, async (debateId, extension) => {
          // Arrange: Mock blob response
          const mockBlob = new Blob(['mock content'], { type: 'application/octet-stream' });
          vi.mocked(api.get).mockResolvedValue(mockBlob as any);

          // Clear previous links
          createdLinks = [];

          // Act: Export report based on extension
          if (extension === 'pdf') {
            await StudentService.exportReportPDF(debateId);
          } else {
            await StudentService.exportReportExcel(debateId);
          }

          // Assert: Filename should contain the debate_id
          expect(createdLinks).toHaveLength(1);
          expect(createdLinks[0].download).toContain(debateId);
        }),
        { numRuns: 100 }
      );
    });

    it('should create download link with blob URL for any file download', () => {
      fc.assert(
        fc.property(debateIdArbitrary, fileExtensionArbitrary, async (debateId, extension) => {
          // Arrange: Mock blob response
          const mockBlob = new Blob(['mock content'], { type: 'application/octet-stream' });
          vi.mocked(api.get).mockResolvedValue(mockBlob as any);

          // Clear previous links
          createdLinks = [];

          // Act: Export report based on extension
          if (extension === 'pdf') {
            await StudentService.exportReportPDF(debateId);
          } else {
            await StudentService.exportReportExcel(debateId);
          }

          // Assert: Should create object URL and set it as href
          expect(global.URL.createObjectURL).toHaveBeenCalledWith(mockBlob);
          expect(createdLinks).toHaveLength(1);
          expect(createdLinks[0].href).toBe('blob:mock-url');
        }),
        { numRuns: 100 }
      );
    });

    it('should trigger download and cleanup for any file download', () => {
      fc.assert(
        fc.property(debateIdArbitrary, fileExtensionArbitrary, async (debateId, extension) => {
          // Arrange: Mock blob response
          const mockBlob = new Blob(['mock content'], { type: 'application/octet-stream' });
          vi.mocked(api.get).mockResolvedValue(mockBlob as any);

          // Clear previous links
          createdLinks = [];

          // Act: Export report based on extension
          if (extension === 'pdf') {
            await StudentService.exportReportPDF(debateId);
          } else {
            await StudentService.exportReportExcel(debateId);
          }

          // Assert: Should trigger click, append/remove from DOM, and revoke URL
          expect(createdLinks).toHaveLength(1);
          expect(createdLinks[0].click).toHaveBeenCalled();
          expect(document.body.appendChild).toHaveBeenCalledWith(createdLinks[0]);
          expect(document.body.removeChild).toHaveBeenCalledWith(createdLinks[0]);
          expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
        }),
        { numRuns: 100 }
      );
    });

    it('should call correct API endpoint for PDF downloads', () => {
      fc.assert(
        fc.property(debateIdArbitrary, async (debateId) => {
          // Arrange: Mock blob response
          const mockBlob = new Blob(['mock pdf content'], { type: 'application/pdf' });
          vi.mocked(api.get).mockResolvedValue(mockBlob as any);

          // Clear previous links
          createdLinks = [];

          // Act: Export PDF report
          await StudentService.exportReportPDF(debateId);

          // Assert: Should call the correct API endpoint
          expect(api.get).toHaveBeenCalledWith(
            `/api/student/reports/${debateId}/export/pdf`,
            { responseType: 'blob' }
          );
        }),
        { numRuns: 100 }
      );
    });

    it('should call correct API endpoint for Excel downloads', () => {
      fc.assert(
        fc.property(debateIdArbitrary, async (debateId) => {
          // Arrange: Mock blob response
          const mockBlob = new Blob(['mock excel content'], { 
            type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
          });
          vi.mocked(api.get).mockResolvedValue(mockBlob as any);

          // Clear previous links
          createdLinks = [];

          // Act: Export Excel report
          await StudentService.exportReportExcel(debateId);

          // Assert: Should call the correct API endpoint
          expect(api.get).toHaveBeenCalledWith(
            `/api/student/reports/${debateId}/export/excel`,
            { responseType: 'blob' }
          );
        }),
        { numRuns: 100 }
      );
    });

    it('should handle special characters in debate ID for filename', () => {
      fc.assert(
        fc.property(
          fc.string({ minLength: 5, maxLength: 30 }),
          async (debateId) => {
            // Arrange: Mock blob response
            const mockBlob = new Blob(['mock content'], { type: 'application/pdf' });
            vi.mocked(api.get).mockResolvedValue(mockBlob as any);

            // Clear previous links
            createdLinks = [];

            // Act: Export PDF report
            await StudentService.exportReportPDF(debateId);

            // Assert: Filename should include the debate_id as-is
            expect(createdLinks).toHaveLength(1);
            expect(createdLinks[0].download).toBe(`debate_report_${debateId}.pdf`);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should maintain filename format consistency across multiple downloads', () => {
      fc.assert(
        fc.property(
          fc.array(debateIdArbitrary, { minLength: 2, maxLength: 5 }),
          async (debateIds) => {
            // Arrange: Mock blob response
            const mockBlob = new Blob(['mock content'], { type: 'application/pdf' });
            
            const filenames: string[] = [];

            // Act: Export multiple reports
            for (const debateId of debateIds) {
              vi.mocked(api.get).mockResolvedValue(mockBlob as any);
              createdLinks = []; // Clear for each iteration
              
              await StudentService.exportReportPDF(debateId);
              
              expect(createdLinks).toHaveLength(1);
              filenames.push(createdLinks[0].download);
            }

            // Assert: All filenames should follow the same pattern
            for (let i = 0; i < debateIds.length; i++) {
              expect(filenames[i]).toBe(`debate_report_${debateIds[i]}.pdf`);
              expect(filenames[i]).toMatch(/^debate_report_.+\.pdf$/);
            }
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  describe('Property 17: Pagination Support', () => {
    /**
     * **Validates: Requirements 10.3**
     * 
     * Property: For any list API endpoint supporting pagination, the service method
     * should accept limit and offset parameters and return paginated results with total count.
     * 
     * Feature: frontend-backend-integration, Property 17: Pagination Support
     */
    it('should accept limit and offset parameters for getHistory', () => {
      fc.assert(
        fc.property(limitArbitrary, offsetArbitrary, async (limit, offset) => {
          // Arrange: Mock history response
          const mockHistory: DebateHistory = {
            list: [],
            total: 100,
            page: Math.floor(offset / limit) + 1,
            page_size: limit,
          };
          vi.mocked(api.get).mockResolvedValue(mockHistory);

          // Act: Get history with pagination
          await StudentService.getHistory(limit, offset);

          // Assert: Should call API with correct pagination parameters
          expect(api.get).toHaveBeenCalledWith('/api/student/history', {
            params: { limit, offset },
          });
        }),
        { numRuns: 100 }
      );
    });

    it('should return paginated results with total count for any pagination params', () => {
      fc.assert(
        fc.property(limitArbitrary, offsetArbitrary, debateHistoryArbitrary, async (limit, offset, mockHistory) => {
          // Arrange: Mock history response with pagination info
          vi.mocked(api.get).mockResolvedValue(mockHistory);

          // Act: Get history with pagination
          const result = await StudentService.getHistory(limit, offset);

          // Assert: Result should have pagination metadata
          expect(result).toHaveProperty('list');
          expect(result).toHaveProperty('total');
          expect(result).toHaveProperty('page');
          expect(result).toHaveProperty('page_size');
          expect(Array.isArray(result.list)).toBe(true);
          expect(typeof result.total).toBe('number');
        }),
        { numRuns: 100 }
      );
    });

    it('should handle limit parameter in filterHistory', () => {
      fc.assert(
        fc.property(filterHistoryParamsArbitrary, async (params) => {
          // Arrange: Mock history response
          const mockHistory: DebateHistory = {
            list: [],
            total: 50,
            page: 1,
            page_size: params.limit || 20,
          };
          vi.mocked(api.get).mockResolvedValue(mockHistory);

          // Act: Filter history with pagination
          await StudentService.filterHistory(params);

          // Assert: Should call API with filter params including limit
          expect(api.get).toHaveBeenCalledWith('/api/student/history/filter', {
            params,
          });
        }),
        { numRuns: 100 }
      );
    });

    it('should handle offset parameter in filterHistory', () => {
      fc.assert(
        fc.property(filterHistoryParamsArbitrary, async (params) => {
          // Arrange: Mock history response
          const mockHistory: DebateHistory = {
            list: [],
            total: 50,
            page: 1,
            page_size: params.limit || 20,
          };
          vi.mocked(api.get).mockResolvedValue(mockHistory);

          // Act: Filter history with pagination
          await StudentService.filterHistory(params);

          // Assert: Should call API with filter params including offset
          expect(api.get).toHaveBeenCalledWith('/api/student/history/filter', {
            params,
          });
        }),
        { numRuns: 100 }
      );
    });

    it('should use default pagination when no parameters provided', () => {
      fc.assert(
        fc.property(fc.constant(null), async () => {
          // Arrange: Mock history response
          const mockHistory: DebateHistory = {
            list: [],
            total: 100,
            page: 1,
            page_size: 20,
          };
          vi.mocked(api.get).mockResolvedValue(mockHistory);

          // Act: Get history without parameters (using defaults)
          await StudentService.getHistory();

          // Assert: Should use default limit=20, offset=0
          expect(api.get).toHaveBeenCalledWith('/api/student/history', {
            params: { limit: 20, offset: 0 },
          });
        }),
        { numRuns: 100 }
      );
    });

    it('should return correct total count for any pagination request', () => {
      fc.assert(
        fc.property(
          limitArbitrary,
          offsetArbitrary,
          fc.integer({ min: 0, max: 1000 }),
          async (limit, offset, totalCount) => {
            // Arrange: Mock history response with specific total
            const mockHistory: DebateHistory = {
              list: [],
              total: totalCount,
              page: Math.floor(offset / limit) + 1,
              page_size: limit,
            };
            vi.mocked(api.get).mockResolvedValue(mockHistory);

            // Act: Get history with pagination
            const result = await StudentService.getHistory(limit, offset);

            // Assert: Total count should match the response
            expect(result.total).toBe(totalCount);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should handle pagination with empty results', () => {
      fc.assert(
        fc.property(limitArbitrary, offsetArbitrary, async (limit, offset) => {
          // Arrange: Mock empty history response
          const mockHistory: DebateHistory = {
            list: [],
            total: 0,
            page: 1,
            page_size: limit,
          };
          vi.mocked(api.get).mockResolvedValue(mockHistory);

          // Act: Get history with pagination
          const result = await StudentService.getHistory(limit, offset);

          // Assert: Should return empty list with total=0
          expect(result.list).toHaveLength(0);
          expect(result.total).toBe(0);
        }),
        { numRuns: 100 }
      );
    });

    it('should handle pagination when offset exceeds total count', () => {
      fc.assert(
        fc.property(
          limitArbitrary,
          fc.integer({ min: 100, max: 1000 }),
          fc.integer({ min: 0, max: 50 }),
          async (limit, offset, totalCount) => {
            // Arrange: Mock history response where offset > total
            const mockHistory: DebateHistory = {
              list: [],
              total: totalCount,
              page: Math.floor(offset / limit) + 1,
              page_size: limit,
            };
            vi.mocked(api.get).mockResolvedValue(mockHistory);

            // Act: Get history with offset beyond total
            const result = await StudentService.getHistory(limit, offset);

            // Assert: Should return empty list but preserve total count
            expect(result.list).toHaveLength(0);
            expect(result.total).toBe(totalCount);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should calculate correct page number from offset and limit', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 1, max: 50 }),
          fc.integer({ min: 0, max: 10 }),
          async (limit, pageNumber) => {
            // Arrange: Calculate offset from page number
            const offset = pageNumber * limit;
            const mockHistory: DebateHistory = {
              list: [],
              total: 500,
              page: pageNumber + 1, // Page numbers are 1-indexed
              page_size: limit,
            };
            vi.mocked(api.get).mockResolvedValue(mockHistory);

            // Act: Get history with calculated offset
            const result = await StudentService.getHistory(limit, offset);

            // Assert: Page number should match expected value
            expect(result.page).toBe(pageNumber + 1);
            expect(result.page_size).toBe(limit);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should preserve page_size in response for any limit value', () => {
      fc.assert(
        fc.property(limitArbitrary, offsetArbitrary, async (limit, offset) => {
          // Arrange: Mock history response
          const mockHistory: DebateHistory = {
            list: [],
            total: 100,
            page: Math.floor(offset / limit) + 1,
            page_size: limit,
          };
          vi.mocked(api.get).mockResolvedValue(mockHistory);

          // Act: Get history with pagination
          const result = await StudentService.getHistory(limit, offset);

          // Assert: page_size should match the limit parameter
          expect(result.page_size).toBe(limit);
        }),
        { numRuns: 100 }
      );
    });

    it('should support pagination with filter parameters', () => {
      fc.assert(
        fc.property(
          fc.record({
            status: fc.option(fc.constantFrom('completed', 'in_progress'), { nil: undefined }),
            limit: limitArbitrary,
            offset: offsetArbitrary,
          }),
          async (params) => {
            // Arrange: Mock filtered history response
            const mockHistory: DebateHistory = {
              list: [],
              total: 30,
              page: Math.floor(params.offset / params.limit) + 1,
              page_size: params.limit,
            };
            vi.mocked(api.get).mockResolvedValue(mockHistory);

            // Act: Filter history with pagination
            await StudentService.filterHistory(params);

            // Assert: Should call API with both filter and pagination params
            expect(api.get).toHaveBeenCalledWith('/api/student/history/filter', {
              params,
            });
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should handle getGrowthTrend with limit parameter', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 1, max: 50 }),
          async (limit) => {
            // Arrange: Mock growth trend response
            const mockTrend = {
              debates: [],
            };
            vi.mocked(api.get).mockResolvedValue(mockTrend);

            // Act: Get growth trend with limit
            await StudentService.getGrowthTrend(limit);

            // Assert: Should call API with limit parameter
            expect(api.get).toHaveBeenCalledWith('/api/student/analytics/growth', {
              params: { limit },
            });
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should use default limit for getGrowthTrend when not specified', () => {
      fc.assert(
        fc.property(fc.constant(null), async () => {
          // Arrange: Mock growth trend response
          const mockTrend = {
            debates: [],
          };
          vi.mocked(api.get).mockResolvedValue(mockTrend);

          // Act: Get growth trend without limit (using default)
          await StudentService.getGrowthTrend();

          // Assert: Should use default limit=10
          expect(api.get).toHaveBeenCalledWith('/api/student/analytics/growth', {
            params: { limit: 10 },
          });
        }),
        { numRuns: 100 }
      );
    });

    it('should maintain pagination consistency across multiple requests', () => {
      fc.assert(
        fc.property(
          fc.array(
            fc.tuple(limitArbitrary, offsetArbitrary),
            { minLength: 2, maxLength: 5 }
          ),
          async (paginationParams) => {
            // Act: Make multiple paginated requests
            for (const [limit, offset] of paginationParams) {
              const mockHistory: DebateHistory = {
                list: [],
                total: 100,
                page: Math.floor(offset / limit) + 1,
                page_size: limit,
              };
              vi.mocked(api.get).mockResolvedValue(mockHistory);
              
              const result = await StudentService.getHistory(limit, offset);

              // Assert: Each request should have correct pagination params
              expect(api.get).toHaveBeenCalledWith('/api/student/history', {
                params: { limit, offset },
              });
              expect(result.page_size).toBe(limit);
            }
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should handle boundary values for limit parameter', () => {
      fc.assert(
        fc.property(
          fc.constantFrom(1, 100),
          fc.integer({ min: 0, max: 100 }),
          async (limit, offset) => {
            // Arrange: Mock history response
            const mockHistory: DebateHistory = {
              list: [],
              total: 100,
              page: Math.floor(offset / limit) + 1,
              page_size: limit,
            };
            vi.mocked(api.get).mockResolvedValue(mockHistory);

            // Act: Get history with boundary limit values
            const result = await StudentService.getHistory(limit, offset);

            // Assert: Should handle boundary values correctly
            expect(result.page_size).toBe(limit);
            expect(api.get).toHaveBeenCalledWith('/api/student/history', {
              params: { limit, offset },
            });
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should handle zero offset correctly', () => {
      fc.assert(
        fc.property(limitArbitrary, async (limit) => {
          // Arrange: Mock history response for first page
          const mockHistory: DebateHistory = {
            list: [],
            total: 100,
            page: 1,
            page_size: limit,
          };
          vi.mocked(api.get).mockResolvedValue(mockHistory);

          // Act: Get history with offset=0 (first page)
          const result = await StudentService.getHistory(limit, 0);

          // Assert: Should return first page
          expect(result.page).toBe(1);
          expect(api.get).toHaveBeenCalledWith('/api/student/history', {
            params: { limit, offset: 0 },
          });
        }),
        { numRuns: 100 }
      );
    });
  });
});
