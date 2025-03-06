import axios from 'axios';

// Get the API base URL from environment variables or default to the backend
const API_URL = import.meta.env.VITE_API_URL || 'http://0.0.0.0:8000';

// Create axios instance with base configuration
const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000, // 10 seconds timeout
});

// Health check service
const apiService = {
  healthCheck: async () => {
    try {
      const response = await apiClient.get('/');
      return { status: 'online', data: response.data };
    } catch (error) {
      console.error('Health check failed:', error);
      throw error;
    }
  },
  // Legislation endpoints
  getLegislation: (id) => apiClient.get(`/api/legislation/${id}`),
  searchLegislation: (params) => apiClient.get('/api/legislation/search', { params }),
  getTrendingLegislation: () => apiClient.get('/api/legislation/trending'),
  getRecentLegislation: () => apiClient.get('/api/legislation/recent'),
  getRelevantLegislation: (type = 'health', minScore = 50, limit = 10) =>
    apiClient.get('/api/legislation/relevant', { params: { type, min_score: minScore, limit } }),

  // Analysis endpoints
  getLegislationAnalysis: (id) => apiClient.get(`/api/analysis/${id}`),
  requestAnalysis: (id) => apiClient.post(`/api/analysis/request/${id}`),

  // User preferences
  getUserPreferences: () => apiClient.get('/api/user/preferences'),
  updateUserPreferences: (preferences) => apiClient.post('/api/user/preferences', preferences),

  // Notifications
  getNotifications: () => apiClient.get('/api/notifications'),
  markNotificationRead: (id) => apiClient.post(`/api/notifications/${id}/read`),
  markAllNotificationsRead: () => apiClient.post('/api/notifications/read-all'),

  // Dashboard data
  getDashboardStats: () => apiClient.get('/api/dashboard/stats'),

  // Mock data for development (will fall back to these if API calls fail)
  getMockLegislation: () => {
    console.warn('Using mock legislation data');
    return Promise.resolve({
      data: {
        results: [
          {
            id: 1,
            bill_number: 'HB 123',
            title: 'Public Health Emergency Response Act',
            description: 'An act relating to public health emergency response procedures',
            status: 'In Committee',
            last_updated: '2024-02-15',
            relevance_score: 85
          },
          // Additional mock items...
        ]
      }
    });
  },

  getMockAnalysis: () => {
    console.warn('Using mock analysis data');
    return Promise.resolve({
      data: {
        legislation_id: 1,
        summary: 'This bill establishes new protocols for public health emergencies.',
        key_points: [
          { point: 'Establishes emergency response protocols', impact_type: 'positive' },
          { point: 'Requires county health departments to develop plans', impact_type: 'neutral' },
          { point: 'Allocates funding for emergency supplies', impact_type: 'positive' }
        ],
        // Additional mock data...
      }
    });
  }
};

// Bill service for bill-related API calls
const billService = {
  getAllBills: async (params = {}) => {
    try {
      const response = await apiClient.get('/api/bills', { params });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch bills:', error);
      throw error;
    }
  },

  getBillById: async (billId) => {
    try {
      const response = await apiClient.get(`/api/bills/${billId}`);
      return response.data;
    } catch (error) {
      console.error(`Failed to fetch bill ${billId}:`, error);
      throw error;
    }
  },

  getBillAnalysis: async (billId) => {
    try {
      const response = await apiClient.get(`/api/bills/${billId}/analysis`);
      return response.data;
    } catch (error) {
      console.error(`Failed to fetch analysis for bill ${billId}:`, error);
      throw error;
    }
  }
};

export { apiService, billService };