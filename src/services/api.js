/**
 * API service for interacting with the backend
 */

import axios from 'axios';

// Base URL for API requests
const API_BASE_URL = '/api';

// Create axios instance with common config
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Handle response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle global error cases here
    const { response } = error;

    if (response && response.status === 401) {
      // Handle unauthorized access
      console.error('Unauthorized access');
      // Could redirect to login page if needed
    }

    return Promise.reject(error);
  }
);

/**
 * API Services for all endpoints
 */
const apiService = {
  // Health Check
  checkHealth: () => apiClient.get('/health'),

  // Bills / Legislation
  getBills: (params) => apiClient.get('/bills/', { params }),
  getBillDetails: (billId) => apiClient.get(`/bills/${billId}`),
  getBillAnalysis: (billId) => apiClient.get(`/bills/${billId}/analysis`),

  // Search Functionality
  searchBills: (query, filters) => apiClient.post('/search/advanced', { query, filters }),

  // Texas Specific Endpoints
  getTexasHealthLegislation: (params) => apiClient.get('/texas/health-legislation', { params }),
  getTexasLocalGovtLegislation: (params) => apiClient.get('/texas/local-govt-legislation', { params }),

  // Dashboard Analytics
  getImpactSummary: (params) => apiClient.get('/dashboard/impact-summary', { params }),
  getRecentActivity: (params) => apiClient.get('/dashboard/recent-activity', { params }),

  // User Preferences
  getUserPreferences: (email) => apiClient.get(`/users/${email}/preferences`),
  updateUserPreferences: (email, prefsData) => apiClient.post(`/users/${email}/preferences`, prefsData),

  // Search History
  getSearchHistory: (email) => apiClient.get(`/users/${email}/search`),
  addSearchHistory: (email, searchData) => apiClient.post(`/users/${email}/search`, searchData),

  // Analysis
  requestAnalysis: (legId, options) => apiClient.post(`/legislation/${legId}/analysis`, options),
  getAnalysisHistory: (legId) => apiClient.get(`/legislation/${legId}/analysis/history`),

  // Priority Management
  updatePriority: (legId, priorityData) => apiClient.post(`/legislation/${legId}/priority`, priorityData),

  // Sync Operations
  getSyncStatus: () => apiClient.get('/sync/status'),
  triggerSync: (force = false) => apiClient.post('/sync/trigger', { force }),

  // General utility methods
  getStates: () => apiClient.get('/states/'),
  refreshData: (state = null) => apiClient.post('/refresh/', { state }),
};

// Export the billService for components that specifically need it
export const billService = {
  getAllBills: apiService.getBills,
  getBillDetails: apiService.getBillDetails,
  searchBills: (params) => apiService.getBills(params),
  getBillAnalysis: apiService.getBillAnalysis,
};

export default apiService;