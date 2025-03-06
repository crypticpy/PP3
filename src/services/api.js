
import axios from 'axios';

// Get the API base URL from environment variables or use the backend port from run.py
const API_URL = import.meta.env.VITE_API_URL || 'http://0.0.0.0:8002';

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

// Health check function
const healthCheck = async () => {
  try {
    const response = await apiClient.get('/health');
    return response;
  } catch (error) {
    console.error('Health check failed:', error);
    throw error;
  }
};

// Bill service functions
const billService = {
  // Get all bills
  getBills: async () => {
    try {
      const response = await apiClient.get('/api/legislation');
      return response.data;
    } catch (error) {
      console.error('Error fetching bills:', error);
      throw error;
    }
  },
  
  // Get a specific bill by ID
  getBillById: async (id) => {
    try {
      const response = await apiClient.get(`/api/legislation/${id}`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching bill ${id}:`, error);
      throw error;
    }
  },
  
  // Get bill analysis
  getBillAnalysis: async (id) => {
    try {
      const response = await apiClient.get(`/api/legislation/${id}/analysis`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching analysis for bill ${id}:`, error);
      throw error;
    }
  }
};

// Export all services
export { 
  apiClient,
  healthCheck,
  billService
};

export default {
  healthCheck,
  billService
};
