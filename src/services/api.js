import axios from 'axios';

// Get API URL from environment variables
const API_URL = import.meta.env.VITE_API_URL || 'http://0.0.0.0:8000';

// Create a configured axios instance
const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 10000, // 10 seconds timeout
});

// API service object with methods for different endpoints
const apiService = {
  // Health check
  healthCheck: async () => {
    try {
      return await apiClient.get('/health');
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
  getAnalysis: (id) => apiClient.get(`/api/legislation/${id}/analysis`),
  triggerAnalysis: (id, options) => apiClient.post(`/api/legislation/${id}/analysis`, options),

  // Dashboard data
  getDashboardStats: () => apiClient.get('/api/dashboard/stats')
};

// Legacy service - can be removed if not used elsewhere
const billService = {
  getBill: (id) => apiClient.get(`/bills/${id}`)
};

export { apiService, billService };
export default apiService;