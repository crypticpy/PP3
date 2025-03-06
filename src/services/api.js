import axios from 'axios';

// Get the API URL from environment or use a default
const API_URL = import.meta.env.VITE_API_URL || '/api';

// Create an axios instance with the base URL
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  },
  timeout: 10000 // 10 seconds timeout
});

// Health check endpoint
export const healthCheck = () => {
  return api.get('/health');
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