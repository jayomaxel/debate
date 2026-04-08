/**
 * Unit Tests for Student Service
 * 
 * Feature: frontend-backend-integration
 * Tests student service methods for all API endpoints
 * 
 * **Validates: Requirements 3.1-3.15**
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import StudentService, {
  type StudentProfile,
  type UpdateProfileParams,
  type AssessmentParams,
  type AssessmentResult,
  type Debate,
  type JoinDebateParams,
  type DebateHistory,
  type FilterHistoryParams,
  type DebateDetails,
  type StudentAnalytics,
  type GrowthTrend,
  type Achievement,
  type DebateReport,
} from './student.service';
import { api } from '../lib/api';

// Mock dependencies
vi.mock('../lib/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

describe('Student Service - Unit Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // ==================== 个人信息测试 ====================

  describe('getProfile()', () => {
    /**
     * Test: getProfile() should call GET /api/student/profile
     * **Validates: Requirements 3.1**
     */
    it('should call GET /api/student/profile', async () => {
      // Arrange
      const mockProfile: StudentProfile = {
        id: 'student-123',
        name: 'Test Student',
        email: 'student@example.com',
        phone: '13800138000',
        student_id: 'S2024001',
        avatar: 'https://example.com/avatar.jpg',
        created_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(api.get).mockResolvedValue(mockProfile);

      // Act
      const result = await StudentService.getProfile();

      // Assert
      expect(api.get).toHaveBeenCalledWith('/api/student/profile');
      expect(api.get).toHaveBeenCalledTimes(1);
      expect(result).toEqual(mockProfile);
    });

    it('should throw error when profile fetch fails', async () => {
      // Arrange
      const mockError = new Error('Failed to fetch profile');
      vi.mocked(api.get).mockRejectedValue(mockError);

      // Act & Assert
      await expect(StudentService.getProfile()).rejects.toThrow('Failed to fetch profile');
      expect(api.get).toHaveBeenCalledWith('/api/student/profile');
    });

    it('should handle profile with minimal fields', async () => {
      // Arrange
      const mockProfile: StudentProfile = {
        id: 'student-456',
        name: 'Minimal Student',
        email: '',
        created_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(api.get).mockResolvedValue(mockProfile);

      // Act
      const result = await StudentService.getProfile();

      // Assert
      expect(result).toEqual(mockProfile);
      expect(result.phone).toBeUndefined();
      expect(result.student_id).toBeUndefined();
    });
  });

  describe('updateProfile()', () => {
    /**
     * Test: updateProfile() should call PUT /api/student/profile
     * **Validates: Requirements 3.2**
     */
    it('should call PUT /api/student/profile with correct parameters', async () => {
      // Arrange
      const params: UpdateProfileParams = {
        name: 'Updated Name',
        email: 'updated@example.com',
        phone: '13900139000',
        student_id: 'S2024002',
      };

      const mockUpdatedProfile: StudentProfile = {
        id: 'student-123',
        name: 'Updated Name',
        email: 'updated@example.com',
        phone: '13900139000',
        student_id: 'S2024002',
        created_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(api.put).mockResolvedValue(mockUpdatedProfile);

      // Act
      const result = await StudentService.updateProfile(params);

      // Assert
      expect(api.put).toHaveBeenCalledWith('/api/student/profile', params);
      expect(api.put).toHaveBeenCalledTimes(1);
      expect(result).toEqual(mockUpdatedProfile);
    });

    it('should handle partial profile updates', async () => {
      // Arrange - only update name
      const params: UpdateProfileParams = {
        name: 'New Name Only',
      };

      const mockUpdatedProfile: StudentProfile = {
        id: 'student-123',
        name: 'New Name Only',
        email: 'old@example.com',
        created_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(api.put).mockResolvedValue(mockUpdatedProfile);

      // Act
      const result = await StudentService.updateProfile(params);

      // Assert
      expect(api.put).toHaveBeenCalledWith('/api/student/profile', params);
      expect(result.name).toBe('New Name Only');
    });

    it('should throw error when profile update fails', async () => {
      // Arrange
      const params: UpdateProfileParams = {
        email: 'invalid-email',
      };

      const mockError = new Error('Invalid email format');
      vi.mocked(api.put).mockRejectedValue(mockError);

      // Act & Assert
      await expect(StudentService.updateProfile(params)).rejects.toThrow('Invalid email format');
      expect(api.put).toHaveBeenCalledWith('/api/student/profile', params);
    });
  });

  // ==================== 能力评估测试 ====================

  describe('submitAssessment()', () => {
    /**
     * Test: submitAssessment() should call POST /api/student/assessment
     * **Validates: Requirements 3.3**
     */
    it('should call POST /api/student/assessment with correct parameters', async () => {
      // Arrange
      const params: AssessmentParams = {
        personality_type: 'INTJ',
        expression_willingness: 80,
        logical_thinking: 90,
        stablecoin_knowledge: 70,
        financial_knowledge: 60,
        critical_thinking: 85,
      };

      const mockResult: AssessmentResult = {
        personality_type: 'INTJ',
        expression_willingness: 80,
        logical_thinking: 90,
        stablecoin_knowledge: 70,
        financial_knowledge: 60,
        critical_thinking: 85,
        recommended_role: '一辩',
        role_description: '适合担任一辩，逻辑思维强',
        created_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(api.post).mockResolvedValue(mockResult);

      // Act
      const result = await StudentService.submitAssessment(params);

      // Assert
      expect(api.post).toHaveBeenCalledWith('/api/student/assessment', params);
      expect(api.post).toHaveBeenCalledTimes(1);
      expect(result).toEqual(mockResult);
    });

    it('should handle assessment without personality type', async () => {
      // Arrange
      const params: AssessmentParams = {
        expression_willingness: 50,
        logical_thinking: 70,
        stablecoin_knowledge: 50,
        financial_knowledge: 50,
        critical_thinking: 50,
      };

      const mockResult: AssessmentResult = {
        expression_willingness: 50,
        logical_thinking: 70,
        stablecoin_knowledge: 50,
        financial_knowledge: 50,
        critical_thinking: 50,
        recommended_role: '三辩',
        role_description: '适合担任三辩',
        created_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(api.post).mockResolvedValue(mockResult);

      // Act
      const result = await StudentService.submitAssessment(params);

      // Assert
      expect(result.personality_type).toBeUndefined();
      expect(result.recommended_role).toBe('三辩');
    });

    it('should throw error when assessment submission fails', async () => {
      // Arrange
      const params: AssessmentParams = {
        expression_willingness: 101, // Invalid value
        logical_thinking: 90,
        stablecoin_knowledge: 50,
        financial_knowledge: 50,
        critical_thinking: 50,
      };

      const mockError = new Error('Invalid assessment values');
      vi.mocked(api.post).mockRejectedValue(mockError);

      // Act & Assert
      await expect(StudentService.submitAssessment(params)).rejects.toThrow('Invalid assessment values');
    });
  });

  describe('getAssessment()', () => {
    /**
     * Test: getAssessment() should call GET /api/student/assessment
     * **Validates: Requirements 3.4**
     */
    it('should call GET /api/student/assessment and return result', async () => {
      // Arrange
      const mockResult: AssessmentResult = {
        personality_type: 'ENFP',
        expression_willingness: 90,
        logical_thinking: 70,
        stablecoin_knowledge: 60,
        financial_knowledge: 50,
        critical_thinking: 80,
        recommended_role: '四辩',
        role_description: '适合担任四辩，表达能力强',
        created_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(api.get).mockResolvedValue(mockResult);

      // Act
      const result = await StudentService.getAssessment();

      // Assert
      expect(api.get).toHaveBeenCalledWith('/api/student/assessment');
      expect(api.get).toHaveBeenCalledTimes(1);
      expect(result).toEqual(mockResult);
    });

    it('should return null when no assessment exists', async () => {
      // Arrange
      vi.mocked(api.get).mockResolvedValue(null);

      // Act
      const result = await StudentService.getAssessment();

      // Assert
      expect(result).toBeNull();
    });

    it('should throw error when assessment fetch fails', async () => {
      // Arrange
      const mockError = new Error('Failed to fetch assessment');
      vi.mocked(api.get).mockRejectedValue(mockError);

      // Act & Assert
      await expect(StudentService.getAssessment()).rejects.toThrow('Failed to fetch assessment');
    });
  });

  // ==================== 辩论参与测试 ====================

  describe('getAvailableDebates()', () => {
    /**
     * Test: getAvailableDebates() should call GET /api/student/debates
     * **Validates: Requirements 3.5**
     */
    it('should call GET /api/student/debates and return debate list', async () => {
      // Arrange
      const mockDebates: Debate[] = [
        {
          id: 'debate-1',
          topic: '人工智能是否会取代人类工作',
          description: '讨论AI对就业市场的影响',
          duration: 60,
          status: 'published',
          invitation_code: 'ABC123',
          created_at: '2024-01-01T00:00:00Z',
        },
        {
          id: 'debate-2',
          topic: '远程工作是否应该成为常态',
          duration: 45,
          status: 'published',
          invitation_code: 'DEF456',
          created_at: '2024-01-02T00:00:00Z',
        },
      ];

      vi.mocked(api.get).mockResolvedValue(mockDebates);

      // Act
      const result = await StudentService.getAvailableDebates();

      // Assert
      expect(api.get).toHaveBeenCalledWith('/api/student/debates');
      expect(api.get).toHaveBeenCalledTimes(1);
      expect(result).toEqual(mockDebates);
      expect(result).toHaveLength(2);
    });

    it('should return empty array when no debates available', async () => {
      // Arrange
      vi.mocked(api.get).mockResolvedValue([]);

      // Act
      const result = await StudentService.getAvailableDebates({ force: true });

      // Assert
      expect(result).toEqual([]);
      expect(result).toHaveLength(0);
    });

    it('should throw error when fetching debates fails', async () => {
      // Arrange
      const mockError = new Error('Failed to fetch debates');
      vi.mocked(api.get).mockRejectedValue(mockError);

      // Act & Assert
      await expect(StudentService.getAvailableDebates({ force: true })).rejects.toThrow('Failed to fetch debates');
    });
  });

  describe('joinDebate()', () => {
    /**
     * Test: joinDebate() should call POST /api/student/debates/join
     * **Validates: Requirements 3.6**
     */
    it('should call POST /api/student/debates/join with invitation code', async () => {
      // Arrange
      const params: JoinDebateParams = {
        invitation_code: 'ABC123',
      };

      const mockResponse = {
        id: 'debate-123',
        topic: 'Test Debate',
        duration: 45,
        status: 'published',
        invitation_code: 'ABC123',
        created_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      // Act
      const result = await StudentService.joinDebate(params);

      // Assert
      expect(api.post).toHaveBeenCalledWith('/api/student/debates/join', params);
      expect(api.post).toHaveBeenCalledTimes(1);
      expect(result).toEqual(mockResponse);
      expect(result.id).toBe('debate-123');
    });

    it('should throw error when invitation code is invalid', async () => {
      // Arrange
      const params: JoinDebateParams = {
        invitation_code: 'INVALID',
      };

      const mockError = new Error('Invalid invitation code');
      vi.mocked(api.post).mockRejectedValue(mockError);

      // Act & Assert
      await expect(StudentService.joinDebate(params)).rejects.toThrow('Invalid invitation code');
      expect(api.post).toHaveBeenCalledWith('/api/student/debates/join', params);
    });

    it('should throw error when debate is full', async () => {
      // Arrange
      const params: JoinDebateParams = {
        invitation_code: 'FULL123',
      };

      const mockError = new Error('Debate is full');
      vi.mocked(api.post).mockRejectedValue(mockError);

      // Act & Assert
      await expect(StudentService.joinDebate(params)).rejects.toThrow('Debate is full');
    });
  });

  // ==================== 历史记录测试 ====================

  describe('getHistory()', () => {
    /**
     * Test: getHistory() should call GET /api/student/history with pagination
     * **Validates: Requirements 3.7**
     */
    it('should call GET /api/student/history with default pagination', async () => {
      // Arrange
      const mockHistory: DebateHistory = {
        list: [
          {
            debate_id: 'debate-1',
            topic: 'AI辩论',
            role: '一辩',
            stance: 'affirmative',
            status: 'completed',
            score: 85,
            created_at: '2024-01-01T00:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      };

      vi.mocked(api.get).mockResolvedValue(mockHistory);

      // Act
      const result = await StudentService.getHistory();

      // Assert
      expect(api.get).toHaveBeenCalledWith('/api/student/history', {
        params: { limit: 20, offset: 0 },
      });
      expect(result).toEqual(mockHistory);
    });

    it('should call GET /api/student/history with custom pagination', async () => {
      // Arrange
      const mockHistory: DebateHistory = {
        list: [],
        total: 50,
        page: 3,
        page_size: 10,
      };

      vi.mocked(api.get).mockResolvedValue(mockHistory);

      // Act
      const result = await StudentService.getHistory(10, 20);

      // Assert
      expect(api.get).toHaveBeenCalledWith('/api/student/history', {
        params: { limit: 10, offset: 20 },
      });
      expect(result.page).toBe(3);
      expect(result.page_size).toBe(10);
    });

    it('should return empty list when no history exists', async () => {
      // Arrange
      const mockHistory: DebateHistory = {
        list: [],
        total: 0,
        page: 1,
        page_size: 20,
      };

      vi.mocked(api.get).mockResolvedValue(mockHistory);

      // Act
      const result = await StudentService.getHistory();

      // Assert
      expect(result.list).toHaveLength(0);
      expect(result.total).toBe(0);
    });

    it('should throw error when history fetch fails', async () => {
      // Arrange
      const mockError = new Error('Failed to fetch history');
      vi.mocked(api.get).mockRejectedValue(mockError);

      // Act & Assert
      await expect(StudentService.getHistory()).rejects.toThrow('Failed to fetch history');
    });
  });

  describe('filterHistory()', () => {
    /**
     * Test: filterHistory() should call GET /api/student/history/filter with filter params
     * **Validates: Requirements 3.8**
     */
    it('should call GET /api/student/history/filter with all filter parameters', async () => {
      // Arrange
      const params: FilterHistoryParams = {
        status: 'completed',
        role: '一辩',
        stance: 'affirmative',
        start_date: '2024-01-01',
        end_date: '2024-12-31',
        limit: 10,
        offset: 0,
      };

      const mockHistory: DebateHistory = {
        list: [
          {
            debate_id: 'debate-1',
            topic: 'Filtered Debate',
            role: '一辩',
            stance: 'affirmative',
            status: 'completed',
            score: 90,
            created_at: '2024-06-01T00:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 10,
      };

      vi.mocked(api.get).mockResolvedValue(mockHistory);

      // Act
      const result = await StudentService.filterHistory(params);

      // Assert
      expect(api.get).toHaveBeenCalledWith('/api/student/history/filter', {
        params,
      });
      expect(result).toEqual(mockHistory);
    });

    it('should handle partial filter parameters', async () => {
      // Arrange
      const params: FilterHistoryParams = {
        status: 'completed',
      };

      const mockHistory: DebateHistory = {
        list: [],
        total: 0,
        page: 1,
        page_size: 20,
      };

      vi.mocked(api.get).mockResolvedValue(mockHistory);

      // Act
      const result = await StudentService.filterHistory(params);

      // Assert
      expect(api.get).toHaveBeenCalledWith('/api/student/history/filter', {
        params,
      });
    });

    it('should filter by stance only', async () => {
      // Arrange
      const params: FilterHistoryParams = {
        stance: 'negative',
      };

      const mockHistory: DebateHistory = {
        list: [
          {
            debate_id: 'debate-2',
            topic: 'Negative Stance Debate',
            role: '二辩',
            stance: 'negative',
            status: 'completed',
            score: 88,
            created_at: '2024-02-01T00:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      };

      vi.mocked(api.get).mockResolvedValue(mockHistory);

      // Act
      const result = await StudentService.filterHistory(params);

      // Assert
      expect(result.list[0].stance).toBe('negative');
    });

    it('should throw error when filter fails', async () => {
      // Arrange
      const params: FilterHistoryParams = {
        start_date: 'invalid-date',
      };

      const mockError = new Error('Invalid date format');
      vi.mocked(api.get).mockRejectedValue(mockError);

      // Act & Assert
      await expect(StudentService.filterHistory(params)).rejects.toThrow('Invalid date format');
    });
  });

  describe('getDebateDetails()', () => {
    /**
     * Test: getDebateDetails() should call GET /api/student/history/{debate_id}
     * **Validates: Requirements 3.9**
     */
    it('should call GET /api/student/history/{debate_id} with correct debate ID', async () => {
      // Arrange
      const debateId = 'debate-123';
      const mockDetails: DebateDetails = {
        debate: {
          id: 'debate-123',
          topic: 'AI Ethics',
          description: 'Discussion on AI ethics',
          duration: 60,
          status: 'completed',
          invitation_code: 'ABC123',
          created_at: '2024-01-01T00:00:00Z',
        },
        participation: {
          role: '一辩',
          stance: 'affirmative',
          score: 92,
        },
        speeches: [
          {
            id: 'speech-1',
            debate_id: 'debate-123',
            user_id: 'user-1',
            content: 'Opening statement',
            duration: 180,
            phase: 'opening',
            created_at: '2024-01-01T10:00:00Z',
          },
        ],
        scores: [
          {
            id: 'score-1',
            debate_id: 'debate-123',
            user_id: 'user-1',
            logic: 9,
            expression: 9,
            rebuttal: 8,
            teamwork: 9,
            knowledge: 10,
            total: 92,
            feedback: 'Excellent performance',
            created_at: '2024-01-01T11:00:00Z',
          },
        ],
      };

      vi.mocked(api.get).mockResolvedValue(mockDetails);

      // Act
      const result = await StudentService.getDebateDetails(debateId);

      // Assert
      expect(api.get).toHaveBeenCalledWith(`/api/student/history/${debateId}`);
      expect(api.get).toHaveBeenCalledTimes(1);
      expect(result).toEqual(mockDetails);
      expect(result.debate.id).toBe(debateId);
    });

    it('should throw error when debate not found', async () => {
      // Arrange
      const debateId = 'non-existent';
      const mockError = new Error('Debate not found');
      vi.mocked(api.get).mockRejectedValue(mockError);

      // Act & Assert
      await expect(StudentService.getDebateDetails(debateId)).rejects.toThrow('Debate not found');
      expect(api.get).toHaveBeenCalledWith(`/api/student/history/${debateId}`);
    });

    it('should handle debate details with multiple speeches', async () => {
      // Arrange
      const debateId = 'debate-456';
      const mockDetails: DebateDetails = {
        debate: {
          id: 'debate-456',
          topic: 'Climate Change',
          duration: 90,
          status: 'completed',
          invitation_code: 'XYZ789',
          created_at: '2024-02-01T00:00:00Z',
        },
        participation: {
          role: '二辩',
          stance: 'negative',
          score: 85,
        },
        speeches: [
          {
            id: 'speech-1',
            debate_id: 'debate-456',
            user_id: 'user-1',
            content: 'First speech',
            duration: 120,
            phase: 'opening',
            created_at: '2024-02-01T10:00:00Z',
          },
          {
            id: 'speech-2',
            debate_id: 'debate-456',
            user_id: 'user-1',
            content: 'Rebuttal speech',
            duration: 90,
            phase: 'rebuttal',
            created_at: '2024-02-01T10:05:00Z',
          },
        ],
        scores: [],
      };

      vi.mocked(api.get).mockResolvedValue(mockDetails);

      // Act
      const result = await StudentService.getDebateDetails(debateId);

      // Assert
      expect(result.speeches).toHaveLength(2);
      expect(result.speeches[0].phase).toBe('opening');
      expect(result.speeches[1].phase).toBe('rebuttal');
    });
  });

  // ==================== 数据分析测试 ====================

  describe('getAnalytics()', () => {
    /**
     * Test: getAnalytics() should call GET /api/student/analytics
     * **Validates: Requirements 3.10**
     */
    it('should call GET /api/student/analytics and return analytics data', async () => {
      // Arrange
      const mockAnalytics: StudentAnalytics = {
        total_debates: 10,
        completed_debates: 8,
        average_score: 87.5,
        ability_scores: {
          logic: 8.5,
          expression: 9.0,
          rebuttal: 8.0,
          teamwork: 8.5,
          knowledge: 9.0,
        },
        speech_stats: {
          total_speeches: 25,
          average_duration: 150,
        },
        role_distribution: {
          '一辩': 3,
          '二辩': 2,
          '三辩': 2,
          '四辩': 1,
        },
      };

      vi.mocked(api.get).mockResolvedValue(mockAnalytics);

      // Act
      const result = await StudentService.getAnalytics();

      // Assert
      expect(api.get).toHaveBeenCalledWith('/api/student/analytics');
      expect(api.get).toHaveBeenCalledTimes(1);
      expect(result).toEqual(mockAnalytics);
      expect(result.average_score).toBe(87.5);
    });

    it('should handle analytics with zero debates', async () => {
      // Arrange
      const mockAnalytics: StudentAnalytics = {
        total_debates: 0,
        completed_debates: 0,
        average_score: 0,
        ability_scores: {
          logic: 0,
          expression: 0,
          rebuttal: 0,
          teamwork: 0,
          knowledge: 0,
        },
        speech_stats: {
          total_speeches: 0,
          average_duration: 0,
        },
        role_distribution: {},
      };

      vi.mocked(api.get).mockResolvedValue(mockAnalytics);

      // Act
      const result = await StudentService.getAnalytics();

      // Assert
      expect(result.total_debates).toBe(0);
      expect(result.completed_debates).toBe(0);
      expect(Object.keys(result.role_distribution)).toHaveLength(0);
    });

    it('should throw error when analytics fetch fails', async () => {
      // Arrange
      const mockError = new Error('Failed to fetch analytics');
      vi.mocked(api.get).mockRejectedValue(mockError);

      // Act & Assert
      await expect(StudentService.getAnalytics()).rejects.toThrow('Failed to fetch analytics');
    });
  });

  describe('getGrowthTrend()', () => {
    /**
     * Test: getGrowthTrend() should call GET /api/student/analytics/growth
     * **Validates: Requirements 3.11**
     */
    it('should call GET /api/student/analytics/growth with default limit', async () => {
      // Arrange
      const mockTrend: GrowthTrend = {
        debates: [
          {
            debate_id: 'debate-1',
            topic: 'First Debate',
            date: '2024-01-01',
            score: 80,
            ability_scores: {
              logic: 8,
              expression: 8,
              rebuttal: 7,
              teamwork: 8,
              knowledge: 9,
            },
          },
          {
            debate_id: 'debate-2',
            topic: 'Second Debate',
            date: '2024-02-01',
            score: 85,
            ability_scores: {
              logic: 8.5,
              expression: 8.5,
              rebuttal: 8,
              teamwork: 8.5,
              knowledge: 9,
            },
          },
        ],
      };

      vi.mocked(api.get).mockResolvedValue(mockTrend);

      // Act
      const result = await StudentService.getGrowthTrend();

      // Assert
      expect(api.get).toHaveBeenCalledWith('/api/student/analytics/growth', {
        params: { limit: 10 },
      });
      expect(result).toEqual(mockTrend);
      expect(result.debates).toHaveLength(2);
    });

    it('should call GET /api/student/analytics/growth with custom limit', async () => {
      // Arrange
      const mockTrend: GrowthTrend = {
        debates: [],
      };

      vi.mocked(api.get).mockResolvedValue(mockTrend);

      // Act
      const result = await StudentService.getGrowthTrend(5);

      // Assert
      expect(api.get).toHaveBeenCalledWith('/api/student/analytics/growth', {
        params: { limit: 5 },
      });
    });

    it('should show score improvement over time', async () => {
      // Arrange
      const mockTrend: GrowthTrend = {
        debates: [
          {
            debate_id: 'debate-1',
            topic: 'Debate 1',
            date: '2024-01-01',
            score: 70,
            ability_scores: {
              logic: 7,
              expression: 7,
              rebuttal: 7,
              teamwork: 7,
              knowledge: 7,
            },
          },
          {
            debate_id: 'debate-2',
            topic: 'Debate 2',
            date: '2024-02-01',
            score: 90,
            ability_scores: {
              logic: 9,
              expression: 9,
              rebuttal: 9,
              teamwork: 9,
              knowledge: 9,
            },
          },
        ],
      };

      vi.mocked(api.get).mockResolvedValue(mockTrend);

      // Act
      const result = await StudentService.getGrowthTrend();

      // Assert
      expect(result.debates[0].score).toBeLessThan(result.debates[1].score);
      expect(result.debates[1].score).toBe(90);
    });

    it('should throw error when growth trend fetch fails', async () => {
      // Arrange
      const mockError = new Error('Failed to fetch growth trend');
      vi.mocked(api.get).mockRejectedValue(mockError);

      // Act & Assert
      await expect(StudentService.getGrowthTrend()).rejects.toThrow('Failed to fetch growth trend');
    });
  });

  // ==================== 成就系统测试 ====================

  describe('getAchievements()', () => {
    /**
     * Test: getAchievements() should call GET /api/student/achievements
     * **Validates: Requirements 3.12**
     */
    it('should call GET /api/student/achievements and return achievement list', async () => {
      // Arrange
      const mockAchievements: Achievement[] = [
        {
          id: 'achievement-1',
          name: '首次辩论',
          description: '完成第一场辩论',
          category: 'milestone',
          icon: '🎯',
          unlocked: true,
          unlocked_at: '2024-01-01T00:00:00Z',
        },
        {
          id: 'achievement-2',
          name: '逻辑大师',
          description: '逻辑评分达到9分以上',
          category: 'ability',
          icon: '🧠',
          unlocked: false,
          progress: 75,
          unlock_hint: '还需要在1场辩论中获得9分以上的逻辑评分',
        },
      ];

      vi.mocked(api.get).mockResolvedValue(mockAchievements);

      // Act
      const result = await StudentService.getAchievements();

      // Assert
      expect(api.get).toHaveBeenCalledWith('/api/student/achievements/v2');
      expect(api.get).toHaveBeenCalledTimes(1);
      expect(result).toEqual(mockAchievements);
      expect(result).toHaveLength(2);
    });

    it('should handle achievements with different categories', async () => {
      // Arrange
      const mockAchievements: Achievement[] = [
        {
          id: 'achievement-1',
          name: 'Milestone Achievement',
          description: 'Complete 10 debates',
          category: 'milestone',
          icon: '🏆',
          unlocked: true,
          unlocked_at: '2024-01-01T00:00:00Z',
        },
        {
          id: 'achievement-2',
          name: 'Performance Achievement',
          description: 'Score above 90',
          category: 'performance',
          icon: '⭐',
          unlocked: false,
        },
        {
          id: 'achievement-3',
          name: 'Ability Achievement',
          description: 'Master all abilities',
          category: 'ability',
          icon: '💪',
          unlocked: false,
        },
      ];

      vi.mocked(api.get).mockResolvedValue(mockAchievements);

      // Act
      const result = await StudentService.getAchievements();

      // Assert
      expect(result.filter(a => a.category === 'milestone')).toHaveLength(1);
      expect(result.filter(a => a.category === 'performance')).toHaveLength(1);
      expect(result.filter(a => a.category === 'ability')).toHaveLength(1);
    });

    it('should return empty array when no achievements exist', async () => {
      // Arrange
      vi.mocked(api.get).mockResolvedValue([]);

      // Act
      const result = await StudentService.getAchievements();

      // Assert
      expect(result).toEqual([]);
      expect(result).toHaveLength(0);
    });

    it('should throw error when achievements fetch fails', async () => {
      // Arrange
      const mockError = new Error('Failed to fetch achievements');
      vi.mocked(api.get).mockRejectedValue(mockError);

      // Act & Assert
      await expect(StudentService.getAchievements()).rejects.toThrow('Failed to fetch achievements');
    });
  });

  describe('checkAchievements()', () => {
    /**
     * Test: checkAchievements() should call POST /api/student/achievements/check
     * **Validates: Requirements 3.12**
     */
    it('should call POST /api/student/achievements/check and return newly unlocked achievements', async () => {
      // Arrange
      const mockResponse = {
        newly_unlocked: [
          {
            id: 'achievement-3',
            name: '连胜三场',
            description: '连续赢得三场辩论',
            category: 'performance' as const,
            icon: '🔥',
            unlocked: true,
            unlocked_at: '2024-01-15T00:00:00Z',
          },
        ],
        count: 1,
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      // Act
      const result = await StudentService.checkAchievements();

      // Assert
      expect(api.post).toHaveBeenCalledWith('/api/student/achievements/check/v2');
      expect(api.post).toHaveBeenCalledTimes(1);
      expect(result).toEqual(mockResponse);
      expect(result.count).toBe(1);
      expect(result.newly_unlocked).toHaveLength(1);
    });

    it('should return empty array when no new achievements unlocked', async () => {
      // Arrange
      const mockResponse = {
        newly_unlocked: [],
        count: 0,
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      // Act
      const result = await StudentService.checkAchievements();

      // Assert
      expect(result.newly_unlocked).toHaveLength(0);
      expect(result.count).toBe(0);
    });

    it('should handle multiple newly unlocked achievements', async () => {
      // Arrange
      const mockResponse = {
        newly_unlocked: [
          {
            id: 'achievement-4',
            name: 'Achievement 1',
            description: 'Description 1',
            category: 'milestone' as const,
            icon: '🎯',
            unlocked: true,
            unlocked_at: '2024-01-15T00:00:00Z',
          },
          {
            id: 'achievement-5',
            name: 'Achievement 2',
            description: 'Description 2',
            category: 'performance' as const,
            icon: '⭐',
            unlocked: true,
            unlocked_at: '2024-01-15T00:00:00Z',
          },
        ],
        count: 2,
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      // Act
      const result = await StudentService.checkAchievements();

      // Assert
      expect(result.count).toBe(2);
      expect(result.newly_unlocked).toHaveLength(2);
    });

    it('should throw error when check achievements fails', async () => {
      // Arrange
      const mockError = new Error('Failed to check achievements');
      vi.mocked(api.post).mockRejectedValue(mockError);

      // Act & Assert
      await expect(StudentService.checkAchievements()).rejects.toThrow('Failed to check achievements');
    });
  });

  // ==================== 报告查看测试 ====================

  describe('getReport()', () => {
    /**
     * Test: getReport() should call GET /api/student/reports/{debate_id}
     * **Validates: Requirements 3.13**
     */
    it('should call GET /api/student/reports/{debate_id} with correct debate ID', async () => {
      // Arrange
      const debateId = 'debate-123';
      const mockReport: DebateReport = {
        debate_id: 'debate-123',
        student_id: 'student-456',
        topic: 'AI Ethics',
        role: '一辩',
        stance: 'affirmative',
        final_score: 92,
        ability_scores: {
          logic: 9,
          expression: 9,
          rebuttal: 9,
          teamwork: 9,
          knowledge: 10,
        },
        speeches: [
          {
            id: 'speech-1',
            debate_id: 'debate-123',
            user_id: 'student-456',
            content: 'Opening statement',
            duration: 180,
            phase: 'opening',
            created_at: '2024-01-01T10:00:00Z',
          },
        ],
        feedback: 'Excellent performance with strong logical arguments',
        generated_at: '2024-01-01T12:00:00Z',
      };

      vi.mocked(api.get).mockResolvedValue(mockReport);

      // Act
      const result = await StudentService.getReport(debateId);

      // Assert
      expect(api.get).toHaveBeenCalledWith(`/api/student/reports/${debateId}`);
      expect(api.get).toHaveBeenCalledTimes(1);
      expect(result).toEqual(mockReport);
      expect(result.debate_id).toBe(debateId);
    });

    it('should throw error when report not found', async () => {
      // Arrange
      const debateId = 'non-existent';
      const mockError = new Error('Report not found');
      vi.mocked(api.get).mockRejectedValue(mockError);

      // Act & Assert
      await expect(StudentService.getReport(debateId)).rejects.toThrow('Report not found');
      expect(api.get).toHaveBeenCalledWith(`/api/student/reports/${debateId}`);
    });

    it('should handle report with multiple speeches', async () => {
      // Arrange
      const debateId = 'debate-789';
      const mockReport: DebateReport = {
        debate_id: 'debate-789',
        student_id: 'student-123',
        topic: 'Climate Change',
        role: '二辩',
        stance: 'negative',
        final_score: 88,
        ability_scores: {
          logic: 9,
          expression: 8,
          rebuttal: 9,
          teamwork: 9,
          knowledge: 9,
        },
        speeches: [
          {
            id: 'speech-1',
            debate_id: 'debate-789',
            user_id: 'student-123',
            content: 'First speech',
            duration: 120,
            phase: 'opening',
            created_at: '2024-02-01T10:00:00Z',
          },
          {
            id: 'speech-2',
            debate_id: 'debate-789',
            user_id: 'student-123',
            content: 'Rebuttal speech',
            duration: 90,
            phase: 'rebuttal',
            created_at: '2024-02-01T10:05:00Z',
          },
          {
            id: 'speech-3',
            debate_id: 'debate-789',
            user_id: 'student-123',
            content: 'Closing speech',
            duration: 60,
            phase: 'closing',
            created_at: '2024-02-01T10:10:00Z',
          },
        ],
        feedback: 'Good performance with room for improvement',
        generated_at: '2024-02-01T11:00:00Z',
      };

      vi.mocked(api.get).mockResolvedValue(mockReport);

      // Act
      const result = await StudentService.getReport(debateId);

      // Assert
      expect(result.speeches).toHaveLength(3);
      expect(result.speeches[0].phase).toBe('opening');
      expect(result.speeches[2].phase).toBe('closing');
    });
  });

  describe('exportReportPDF()', () => {
    /**
     * Test: exportReportPDF() should download PDF file
     * **Validates: Requirements 3.14, 9.3, 9.5**
     */
    it('should call GET /api/student/reports/{debate_id}/export/pdf and trigger download', async () => {
      // Arrange
      const debateId = 'debate-123';
      const mockBlob = new Blob(['PDF content'], { type: 'application/pdf' });

      vi.mocked(api.get).mockResolvedValue(mockBlob);

      // Mock DOM methods
      const createObjectURLMock = vi.fn().mockReturnValue('blob:mock-url');
      const revokeObjectURLMock = vi.fn();
      global.URL.createObjectURL = createObjectURLMock;
      global.URL.revokeObjectURL = revokeObjectURLMock;

      const appendChildMock = vi.fn();
      const removeChildMock = vi.fn();
      const clickMock = vi.fn();

      const linkElement = {
        href: '',
        download: '',
        click: clickMock,
      };

      vi.spyOn(document, 'createElement').mockReturnValue(linkElement as any);
      vi.spyOn(document.body, 'appendChild').mockImplementation(appendChildMock);
      vi.spyOn(document.body, 'removeChild').mockImplementation(removeChildMock);

      // Act
      await StudentService.exportReportPDF(debateId);

      // Assert
      expect(api.get).toHaveBeenCalledWith(`/api/student/reports/${debateId}/export/pdf`, {
        responseType: 'blob',
      });
      expect(createObjectURLMock).toHaveBeenCalledWith(mockBlob);
      expect(linkElement.download).toBe(`debate_report_${debateId}.pdf`);
      expect(clickMock).toHaveBeenCalled();
      expect(appendChildMock).toHaveBeenCalled();
      expect(removeChildMock).toHaveBeenCalled();
      expect(revokeObjectURLMock).toHaveBeenCalledWith('blob:mock-url');
    });

    it('should throw error when PDF export fails', async () => {
      // Arrange
      const debateId = 'debate-456';
      const mockError = new Error('Failed to export PDF');
      vi.mocked(api.get).mockRejectedValue(mockError);

      // Act & Assert
      await expect(StudentService.exportReportPDF(debateId)).rejects.toThrow('Failed to export PDF');
      expect(api.get).toHaveBeenCalledWith(`/api/student/reports/${debateId}/export/pdf`, {
        responseType: 'blob',
      });
    });

    it('should use correct filename format for PDF', async () => {
      // Arrange
      const debateId = 'debate-special-123';
      const mockBlob = new Blob(['PDF content'], { type: 'application/pdf' });

      vi.mocked(api.get).mockResolvedValue(mockBlob);

      const createObjectURLMock = vi.fn().mockReturnValue('blob:mock-url');
      const revokeObjectURLMock = vi.fn();
      global.URL.createObjectURL = createObjectURLMock;
      global.URL.revokeObjectURL = revokeObjectURLMock;

      const linkElement = {
        href: '',
        download: '',
        click: vi.fn(),
      };

      vi.spyOn(document, 'createElement').mockReturnValue(linkElement as any);
      vi.spyOn(document.body, 'appendChild').mockImplementation(vi.fn());
      vi.spyOn(document.body, 'removeChild').mockImplementation(vi.fn());

      // Act
      await StudentService.exportReportPDF(debateId);

      // Assert - verify filename format
      expect(linkElement.download).toBe(`debate_report_${debateId}.pdf`);
    });
  });

  describe('exportReportExcel()', () => {
    /**
     * Test: exportReportExcel() should download Excel file
     * **Validates: Requirements 3.15, 9.4, 9.5**
     */
    it('should call GET /api/student/reports/{debate_id}/export/excel and trigger download', async () => {
      // Arrange
      const debateId = 'debate-123';
      const mockBlob = new Blob(['Excel content'], { 
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
      });

      vi.mocked(api.get).mockResolvedValue(mockBlob);

      // Mock DOM methods
      const createObjectURLMock = vi.fn().mockReturnValue('blob:mock-url');
      const revokeObjectURLMock = vi.fn();
      global.URL.createObjectURL = createObjectURLMock;
      global.URL.revokeObjectURL = revokeObjectURLMock;

      const appendChildMock = vi.fn();
      const removeChildMock = vi.fn();
      const clickMock = vi.fn();

      const linkElement = {
        href: '',
        download: '',
        click: clickMock,
      };

      vi.spyOn(document, 'createElement').mockReturnValue(linkElement as any);
      vi.spyOn(document.body, 'appendChild').mockImplementation(appendChildMock);
      vi.spyOn(document.body, 'removeChild').mockImplementation(removeChildMock);

      // Act
      await StudentService.exportReportExcel(debateId);

      // Assert
      expect(api.get).toHaveBeenCalledWith(`/api/student/reports/${debateId}/export/excel`, {
        responseType: 'blob',
      });
      expect(createObjectURLMock).toHaveBeenCalledWith(mockBlob);
      expect(linkElement.download).toBe(`debate_report_${debateId}.xlsx`);
      expect(clickMock).toHaveBeenCalled();
      expect(appendChildMock).toHaveBeenCalled();
      expect(removeChildMock).toHaveBeenCalled();
      expect(revokeObjectURLMock).toHaveBeenCalledWith('blob:mock-url');
    });

    it('should throw error when Excel export fails', async () => {
      // Arrange
      const debateId = 'debate-789';
      const mockError = new Error('Failed to export Excel');
      vi.mocked(api.get).mockRejectedValue(mockError);

      // Act & Assert
      await expect(StudentService.exportReportExcel(debateId)).rejects.toThrow('Failed to export Excel');
      expect(api.get).toHaveBeenCalledWith(`/api/student/reports/${debateId}/export/excel`, {
        responseType: 'blob',
      });
    });

    it('should use correct filename format for Excel', async () => {
      // Arrange
      const debateId = 'debate-excel-456';
      const mockBlob = new Blob(['Excel content'], { 
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
      });

      vi.mocked(api.get).mockResolvedValue(mockBlob);

      const createObjectURLMock = vi.fn().mockReturnValue('blob:mock-url');
      const revokeObjectURLMock = vi.fn();
      global.URL.createObjectURL = createObjectURLMock;
      global.URL.revokeObjectURL = revokeObjectURLMock;

      const linkElement = {
        href: '',
        download: '',
        click: vi.fn(),
      };

      vi.spyOn(document, 'createElement').mockReturnValue(linkElement as any);
      vi.spyOn(document.body, 'appendChild').mockImplementation(vi.fn());
      vi.spyOn(document.body, 'removeChild').mockImplementation(vi.fn());

      // Act
      await StudentService.exportReportExcel(debateId);

      // Assert - verify filename format
      expect(linkElement.download).toBe(`debate_report_${debateId}.xlsx`);
    });
  });

  // ==================== Integration scenarios ====================

  describe('Integration scenarios', () => {
    it('should handle complete student workflow: profile -> assessment -> join debate', async () => {
      // Arrange & Act - Get Profile
      const mockProfile: StudentProfile = {
        id: 'student-123',
        name: 'Test Student',
        email: 'student@example.com',
        created_at: '2024-01-01T00:00:00Z',
      };
      vi.mocked(api.get).mockResolvedValueOnce(mockProfile);
      const profile = await StudentService.getProfile();

      // Assert - Profile
      expect(profile).toEqual(mockProfile);

      // Arrange & Act - Submit Assessment
      const assessmentParams: AssessmentParams = {
        expression_willingness: 80,
        logical_thinking: 90,
        stablecoin_knowledge: 70,
        financial_knowledge: 60,
        critical_thinking: 85,
      };
      const mockAssessment: AssessmentResult = {
        expression_willingness: 80,
        logical_thinking: 90,
        stablecoin_knowledge: 70,
        financial_knowledge: 60,
        critical_thinking: 85,
        recommended_role: '一辩',
        role_description: '适合担任一辩',
        created_at: '2024-01-02T00:00:00Z',
      };
      vi.mocked(api.post).mockResolvedValueOnce(mockAssessment);
      const assessment = await StudentService.submitAssessment(assessmentParams);

      // Assert - Assessment
      expect(assessment.recommended_role).toBe('一辩');

      // Arrange & Act - Join Debate
      const joinParams: JoinDebateParams = {
        invitation_code: 'ABC123',
      };
      vi.mocked(api.post).mockResolvedValueOnce({
        id: 'debate-123',
        topic: 'Test Debate',
        duration: 45,
        status: 'published',
        invitation_code: 'ABC123',
        created_at: '2024-01-01T00:00:00Z',
        is_joined: true,
      });
      const joinResult = await StudentService.joinDebate(joinParams);

      // Assert - Join Debate
      expect(joinResult.id).toBe('debate-123');
    });

    it('should handle complete analytics workflow: get analytics -> get growth trend -> get achievements', async () => {
      // Arrange & Act - Get Analytics
      const mockAnalytics: StudentAnalytics = {
        total_debates: 10,
        completed_debates: 8,
        average_score: 87.5,
        ability_scores: {
          logic: 8.5,
          expression: 9.0,
          rebuttal: 8.0,
          teamwork: 8.5,
          knowledge: 9.0,
        },
        speech_stats: {
          total_speeches: 25,
          average_duration: 150,
        },
        role_distribution: {
          '一辩': 3,
        },
      };
      vi.mocked(api.get).mockResolvedValueOnce(mockAnalytics);
      const analytics = await StudentService.getAnalytics();

      // Assert - Analytics
      expect(analytics.total_debates).toBe(10);

      // Arrange & Act - Get Growth Trend
      const mockTrend: GrowthTrend = {
        debates: [
          {
            debate_id: 'debate-1',
            topic: 'Topic 1',
            date: '2024-01-01',
            score: 80,
            ability_scores: {
              logic: 8,
              expression: 8,
              rebuttal: 7,
              teamwork: 8,
              knowledge: 9,
            },
          },
        ],
      };
      vi.mocked(api.get).mockResolvedValueOnce(mockTrend);
      const trend = await StudentService.getGrowthTrend();

      // Assert - Growth Trend
      expect(trend.debates).toHaveLength(1);

      // Arrange & Act - Get Achievements
      const mockAchievements: Achievement[] = [
        {
          id: 'achievement-1',
          name: 'First Debate',
          description: 'Complete first debate',
          category: 'milestone',
          icon: '🎯',
          unlocked: true,
          unlocked_at: '2024-01-01T00:00:00Z',
        },
      ];
      vi.mocked(api.get).mockResolvedValueOnce(mockAchievements);
      const achievements = await StudentService.getAchievements();

      // Assert - Achievements
      expect(achievements).toHaveLength(1);
      expect(achievements[0].unlocked).toBe(true);
    });

    it('should handle complete report workflow: get history -> get details -> get report -> export', async () => {
      // Arrange & Act - Get History
      const mockHistory: DebateHistory = {
        list: [
          {
            debate_id: 'debate-123',
            topic: 'AI Ethics',
            role: '一辩',
            stance: 'affirmative',
            status: 'completed',
            score: 92,
            created_at: '2024-01-01T00:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      };
      vi.mocked(api.get).mockResolvedValueOnce(mockHistory);
      const history = await StudentService.getHistory();

      // Assert - History
      expect(history.list).toHaveLength(1);

      const debateId = history.list[0].debate_id;

      // Arrange & Act - Get Details
      const mockDetails: DebateDetails = {
        debate: {
          id: debateId,
          topic: 'AI Ethics',
          duration: 60,
          status: 'completed',
          invitation_code: 'ABC123',
          created_at: '2024-01-01T00:00:00Z',
        },
        participation: {
          role: '一辩',
          stance: 'affirmative',
          score: 92,
        },
        speeches: [],
        scores: [],
      };
      vi.mocked(api.get).mockResolvedValueOnce(mockDetails);
      const details = await StudentService.getDebateDetails(debateId);

      // Assert - Details
      expect(details.debate.id).toBe(debateId);

      // Arrange & Act - Get Report
      const mockReport: DebateReport = {
        debate_id: debateId,
        student_id: 'student-123',
        topic: 'AI Ethics',
        role: '一辩',
        stance: 'affirmative',
        final_score: 92,
        ability_scores: {
          logic: 9,
          expression: 9,
          rebuttal: 9,
          teamwork: 9,
          knowledge: 10,
        },
        speeches: [],
        feedback: 'Excellent',
        generated_at: '2024-01-01T12:00:00Z',
      };
      vi.mocked(api.get).mockResolvedValueOnce(mockReport);
      const report = await StudentService.getReport(debateId);

      // Assert - Report
      expect(report.final_score).toBe(92);
    });
  });

  describe('knowledge base timestamps', () => {
    it('should normalize KB conversation timestamps without timezone suffix', async () => {
      vi.mocked(api.get).mockResolvedValue({
        conversations: [
          {
            id: 'conv-001',
            question: '问题',
            answer: '回答',
            sources: [],
            created_at: '2026-04-07T01:00:00',
          },
        ],
        count: 1,
      });

      const result = await StudentService.getKBConversationHistory('session-001');

      expect(api.get).toHaveBeenCalledWith('/api/student/kb/conversations/session-001', {
        params: { limit: 20 },
      });
      expect(result[0].created_at).toBe('2026-04-07T01:00:00Z');
    });

    it('should normalize KB session timestamps without changing timezone-aware values', async () => {
      vi.mocked(api.get).mockResolvedValue([
        {
          session_id: 'session-001',
          title: '新会话',
          updated_at: '2026-04-07T01:13:18',
        },
        {
          session_id: 'session-002',
          title: '旧会话',
          updated_at: '2026-04-07T01:13:18+08:00',
        },
      ]);

      const result = await StudentService.getKBSessions();

      expect(api.get).toHaveBeenCalledWith('/api/student/kb/sessions');
      expect(result[0].updated_at).toBe('2026-04-07T01:13:18Z');
      expect(result[1].updated_at).toBe('2026-04-07T01:13:18+08:00');
    });
  });
});
