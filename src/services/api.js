import axios from 'axios';
import { toast } from 'react-toastify';

// Determine the API URL based on the environment
const API_URL = import.meta.env.VITE_API_URL || 
               (window.location.hostname === 'localhost' || window.location.hostname === '0.0.0.0' 
                ? 'http://0.0.0.0:8000' 
                : `${window.location.protocol}//${window.location.hostname}:8000`);

console.log('Using API URL:', API_URL);

// Create axios instance with base URL
const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for authentication
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    const { response } = error;

    if (response) {
      // Handle specific error status codes
      switch (response.status) {
        case 401:
          toast.error('Authentication required. Please log in.');
          // Redirect to login if needed
          break;
        case 403:
          toast.error('You do not have permission to perform this action.');
          break;
        case 404:
          toast.error('Resource not found.');
          break;
        case 500:
          toast.error('Server error. Please try again later.');
          break;
        default:
          if (response.data && response.data.detail) {
            toast.error(response.data.detail);
          } else {
            toast.error('An error occurred. Please try again.');
          }
      }
    } else {
      // Handle network errors
      toast.error('Network error. Please check your connection.');
    }

    return Promise.reject(error);
  }
);

// Authentication API calls
export const login = async (credentials) => {
  try {
    const response = await apiClient.post('/auth/login', credentials);
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const register = async (userData) => {
  try {
    const response = await apiClient.post('/auth/register', userData);
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const logout = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
};

// Legislation API calls
export const fetchLegislation = async (params) => {
  try {
    const response = await apiClient.get('/legislation', { params });
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const fetchLegislationDetails = async (id) => {
  try {
    const response = await apiClient.get(`/legislation/${id}`);
    return response.data;
  } catch (error) {
    throw error;
  }
};

// User preferences and settings
export const updateUserPreferences = async (preferences) => {
  try {
    const response = await apiClient.post('/users/preferences', preferences);
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const fetchUserPreferences = async () => {
  try {
    const response = await apiClient.get('/users/preferences');
    return response.data;
  } catch (error) {
    throw error;
  }
};

// Health check endpoint
export const healthCheck = async () => {
  try {
    const response = await apiClient.get('/health');
    console.log('Health check response:', response.data);
    return response.data;
  } catch (error) {
    console.log('Health check error:', error);
    throw error;
  }
};

export default apiClient;