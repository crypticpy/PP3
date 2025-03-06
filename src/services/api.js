import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  }
});

// Add response interceptor for better error handling
api.interceptors.response.use(
  response => response,
  error => {
    console.error('API Error:', error.message);
    return Promise.reject(error);
  }
);

export const healthCheck = async () => {
  try {
    return await api.get('/health');
  } catch (error) {
    console.error('Health check error:', error);
    throw error;
  }
};

// Bill-related endpoints
export const fetchBills = (params) => {
  return api.get('/bills', { params });
};

export const fetchBillDetails = (billId) => {
  return api.get(`/bills/${billId}`);
};

// Analysis endpoints
export const fetchAnalysis = (billId) => {
  return api.get(`/analysis/${billId}`);
};

export const fetchKeywords = () => {
  return api.get('/analysis/keywords');
};

// Authentication endpoints
export const login = (credentials) => {
  return api.post('/auth/login', credentials);
};

export const signup = (userData) => {
  return api.post('/auth/signup', userData);
};

// User preference endpoints
export const getUserPreferences = () => {
  return api.get('/user/preferences');
};

export const updateUserPreferences = (preferences) => {
  return api.post('/user/preferences', preferences);
};

// Notifications endpoints
export const getNotifications = () => {
  return api.get('/notifications');
};

export const markNotificationRead = (notificationId) => {
  return api.put(`/notifications/${notificationId}/read`);
};

export default api;