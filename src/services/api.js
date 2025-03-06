
import axios from 'axios';

// Get the API base URL from environment variables or use the backend port from run.py
const API_URL = import.meta.env.VITE_API_URL || 'http://0.0.0.0:8001';

// Create axios instance with base configuration
const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
});

// Add request interceptor for logging and debugging
apiClient.interceptors.request.use(
  config => {
    console.log(`API Request: ${config.method.toUpperCase()} ${config.baseURL}${config.url}`);
    return config;
  },
  error => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// API service methods
const apiService = {
  // Health check endpoint for system status
  healthCheck: () => apiClient.get('/health'),

  // Legislation endpoints
  getLegislation: (id) => apiClient.get(`/api/legislation/${id}`),
  searchLegislation: (params) => apiClient.get('/api/legislation/search', { params }),
  getRecentLegislation: () => apiClient.get('/api/legislation/recent'),
  getTrendingLegislation: () => apiClient.get('/api/legislation/trending'),
  getRelevantLegislation: (type = 'health', minScore = 50, limit = 10) => 
    apiClient.get('/api/legislation/relevant', { params: { type, min_score: minScore, limit } }),

  // Analysis endpoints
  getAnalysis: (id) => apiClient.get(`/api/legislation/${id}/analysis`),
  triggerAnalysis: (id, options) => apiClient.post(`/api/legislation/${id}/analysis`, options),

  // Dashboard data
  getDashboardStats: () => apiClient.get('/api/dashboard/stats')
};

export default apiService;
