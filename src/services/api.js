import axios from 'axios';

// Create API configuration with proper base URL
const API_URL = window.location.hostname === 'localhost' ? 
  'http://localhost:8000' : 
  `${window.location.protocol}//${window.location.host}/api`;

// Create an axios instance with appropriate config
const api = axios.create({
  baseURL: API_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
});

// Add request interceptor for handling auth tokens if needed
api.interceptors.request.use(
  (config) => {
    // You can add auth token logic here if needed
    return config;
  },
  (error) => {
    console.error('API request error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for common error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API response error:', error.response || error);

    // Handle specific error status codes
    if (error.response) {
      switch (error.response.status) {
        case 401:
          // Handle unauthorized
          break;
        case 404:
          // Handle not found
          break;
        case 500:
          // Handle server error
          break;
        default:
          // Handle other errors
          break;
      }
    }

    return Promise.reject(error);
  }
);

// Export API methods
const apiService = {
  // Legislation methods
  getLegislation: (limit = 50, offset = 0) => 
    api.get(`/legislation?limit=${limit}&offset=${offset}`),

  getLegislationDetail: (id) => 
    api.get(`/legislation/${id}`),

  searchLegislation: (keywords) => 
    api.get(`/legislation/search?keywords=${encodeURIComponent(keywords)}`),

  // Analysis methods
  analyzeLegislation: (id, options = {}) => 
    api.post(`/legislation/${id}/analysis`, options),

  getAnalysisHistory: (id) => 
    api.get(`/legislation/${id}/analysis/history`),

  // Texas-specific methods
  getTexasHealthLegislation: (params = {}) => 
    api.get('/texas/health-legislation', { params }),

  getTexasLocalGovtLegislation: (params = {}) => 
    api.get('/texas/local-govt-legislation', { params }),

  // Health check
  healthCheck: () => api.get('/health')
};


// Export the billService for components that specifically need it
export const billService = {
  getAllBills: apiService.getLegislation, // Adjusted to use the new getLegislation
  getBillDetails: apiService.getLegislationDetail, // Adjusted to use the new getLegislationDetail
  searchBills: (params) => apiService.searchLegislation(params.keywords), // Adjusted to use the new searchLegislation
  getBillAnalysis: apiService.analyzeLegislation, // Adjusted to use the new analyzeLegislation
};

export default apiService;