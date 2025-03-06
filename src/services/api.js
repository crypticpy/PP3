
import axios from 'axios';

// Get API URL from environment or default to /api
const API_URL = import.meta.env.VITE_API_URL || '/api';
console.log('API URL configured as:', API_URL);

// Create axios instance with base configuration
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
});

// Add request/response interceptors for better debugging
api.interceptors.request.use(
  config => {
    // Only log non-HMR requests to avoid console noise
    if (!config.url.includes('__vite') && !config.url.includes('@vite')) {
      console.log(`Requesting ${config.method.toUpperCase()} ${config.url}`);
    }
    return config;
  },
  error => {
    // Don't log HMR-related errors
    if (!error.config || (!error.config.url.includes('__vite') && !error.config.url.includes('@vite'))) {
      console.error('Request error:', error.message);
    }
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  response => {
    // Only log non-HMR responses
    if (!response.config.url.includes('__vite') && !response.config.url.includes('@vite')) {
      console.log(`Response from ${response.config.url}: Status ${response.status}`);
    }
    return response;
  },
  error => {
    // Skip logging for HMR-related errors or aborted requests
    if (error.code === 'ERR_CANCELED' || 
        error.message === 'canceled' || 
        (error.config && (error.config.url.includes('__vite') || error.config.url.includes('@vite')))) {
      return Promise.reject(error);
    }

    // Get the request URL that failed
    const url = error.config ? error.config.url : 'unknown endpoint';

    if (error.response) {
      // The request was made and the server responded with a status code
      // that falls out of the range of 2xx
      console.error(`API Error (${url}): ${error.response.status} - ${error.message}`);
    } else if (error.request) {
      // The request was made but no response was received
      console.error(`API Network Error (${url}): No response received`);
    } else {
      // Something happened in setting up the request that triggered an Error
      console.error(`API Error (${url}): ${error.message}`);
    }
    return Promise.reject(error);
  }
);

// API health check
export const healthCheck = async () => {
  return await api.get('/health');
};

// Texas legislation endpoints
export const getTexasHealthLegislation = async (params = {}) => {
  return await api.get('/texas/health-legislation', { params });
};

export const getTexasLocalGovtLegislation = async (params = {}) => {
  return await api.get('/texas/local-govt-legislation', { params });
};

// General legislation endpoints
export const getLegislation = async (params = {}) => {
  return await api.get('/legislation', { params });
};

export const getLegislationById = async (legId) => {
  return await api.get(`/legislation/${legId}`);
};

export const searchLegislation = async (params = {}) => {
  return await api.get('/legislation/search', { params });
};

// Analysis endpoints
export const analyzeLegislation = async (legId, data = {}) => {
  return await api.post(`/legislation/${legId}/analysis`, data);
};

export const getAnalysisHistory = async (legId) => {
  return await api.get(`/legislation/${legId}/analysis/history`);
};

// Dashboard endpoints
export const getRecentActivity = async () => {
  return await api.get('/dashboard/recent-activity');
};

export const getImpactSummary = async () => {
  return await api.get('/dashboard/impact-summary');
};

// Sync status endpoint
export const getSyncStatus = async () => {
  return await api.get('/sync/status');
};

export default api;
