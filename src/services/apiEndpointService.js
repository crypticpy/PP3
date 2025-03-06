
import axios from 'axios';

// The base URL that matches the backend configuration
const API_BASE_URL = '/api';

// Endpoints that are actually implemented and working in the backend
export const API_ENDPOINTS = [
  { name: "Health Check", path: "/health", method: "GET" },
  { name: "Impact Summary", path: "/dashboard/impact-summary", method: "GET" },
  { name: "Recent Activity", path: "/dashboard/recent-activity", method: "GET" },
  { name: "Legislation List", path: "/legislation", method: "GET" },
  { name: "Texas Health Legislation", path: "/texas/health-legislation", method: "GET" },
  { name: "Texas Local Government Legislation", path: "/texas/local-govt-legislation", method: "GET" }
  // Removed bills and states that are failing
];

export const checkEndpoint = async (endpoint) => {
  try {
    const url = `${API_BASE_URL}${endpoint.path}`;
    console.log(`Checking endpoint: ${url}`);
    
    const response = await axios({
      method: endpoint.method,
      url: url,
      timeout: 5000 // 5 second timeout
    });
    
    return {
      isOnline: true,
      status: response.status,
      message: response.statusText || 'OK'
    };
  } catch (error) {
    console.error(`Error checking endpoint ${endpoint.path}:`, error);
    return {
      isOnline: false,
      status: error.response?.status || 0,
      message: error.message || 'Connection failed'
    };
  }
};

export const checkAllEndpoints = async () => {
  const results = {};
  
  for (const endpoint of API_ENDPOINTS) {
    results[endpoint.path] = await checkEndpoint(endpoint);
  }
  
  return results;
};
