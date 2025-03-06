
import axios from 'axios';

// Get the API base URL from environment variables or default
const API_URL = import.meta.env.VITE_API_URL || 'http://0.0.0.0:8000';

// Create axios instance with base configuration
const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000, // 10 seconds timeout
});

// API service object with all endpoint methods
const apiService = {
  // Health check
  healthCheck: async () => {
    try {
      const response = await apiClient.get('/health');
      return response;
    } catch (error) {
      console.error('Health check failed:', error);
      throw error;
    }
  },
  
  // Legislation endpoints
  getLegislation: (id) => apiClient.get(`/api/legislation/${id}`),
  searchLegislation: (params) => apiClient.get('/api/legislation/search', { params }),
  getRelevantLegislation: (type, minScore, limit) => 
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

export default apiService;
export { apiService, billService };
