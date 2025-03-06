import axios from 'axios';

// Define the API URL from environment or use fallback
const API_URL = import.meta.env.VITE_API_URL || 'http://0.0.0.0:8002';

// Create axios instance with base URL
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Health check endpoint
const healthCheck = async () => {
  try {
    const response = await api.get('/health');
    return response;
  } catch (error) {
    console.error('Health check failed:', error);
    throw error;
  }
};

// Bill related API calls
const fetchBills = async (params = {}) => {
  try {
    const response = await api.get('/bills', { params });
    return response.data;
  } catch (error) {
    console.error('Error fetching bills:', error);
    throw error;
  }
};

const fetchBillDetails = async (billId) => {
  try {
    const response = await api.get(`/bills/${billId}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching bill ${billId} details:`, error);
    throw error;
  }
};

// Impact analysis API calls
const fetchImpactSummary = async (params = {}) => {
  try {
    const response = await api.get('/analysis/impact-summary', { params });
    return response.data;
  } catch (error) {
    console.error('Error fetching impact summary:', error);
    throw error;
  }
};

// Export all API functions
export {
  healthCheck,
  fetchBills,
  fetchBillDetails,
  fetchImpactSummary,
};

export default {
  healthCheck,
  fetchBills,
  fetchBillDetails,
  fetchImpactSummary,
};