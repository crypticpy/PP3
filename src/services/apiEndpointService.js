import axios from 'axios';

// The base URL that matches the backend configuration
const API_BASE_URL = '/api';

// Complete list of endpoints from app/api.py
export const API_ENDPOINTS = [
  // Basic endpoints
  { name: "Health Check", path: "/health", method: "GET" },
  { name: "API Root", path: "/", method: "GET" },

  // Dashboard endpoints
  { name: "Impact Summary", path: "/dashboard/impact-summary", method: "GET" },
  { name: "Recent Activity", path: "/dashboard/recent-activity", method: "GET" },

  // Legislation endpoints
  { name: "Legislation List", path: "/legislation", method: "GET" },
  { name: "Legislation Detail", path: "/legislation/1", method: "GET" },
  { name: "Legislation Search", path: "/legislation/search", method: "GET", params: { keywords: "test" } },

  // Texas-specific endpoints
  { name: "Texas Health Legislation", path: "/texas/health-legislation", method: "GET" },
  { name: "Texas Local Government Legislation", path: "/texas/local-govt-legislation", method: "GET" },

  // Bills endpoints
  { name: "Bills List", path: "/bills/", method: "GET" },
  { name: "Bill Detail", path: "/bills/1", method: "GET" },
  { name: "Bill Analysis", path: "/bills/1/analysis", method: "GET" },

  // States endpoint
  { name: "States List", path: "/states/", method: "GET" },

  // Search endpoint
  { name: "Advanced Search", path: "/search/advanced", method: "POST" },

  // User endpoints
  { name: "User Preferences", path: "/users/test@example.com/preferences", method: "GET" },
  { name: "Search History", path: "/users/test@example.com/search", method: "GET" },

  // Sync endpoints
  { name: "Sync Status", path: "/sync/status", method: "GET" },
];

export const checkEndpoint = async (endpoint) => {
    const url = `${API_BASE_URL}${endpoint.path}`;
    console.log(`Checking endpoint: ${url}`);

    try {
        const response = await axios({
            method: endpoint.method,
            url: url,
            timeout: 5000, // 5 second timeout
            // Don't throw error on non-2xx responses for monitoring
            validateStatus: function (status) {
                return true; // Always return true so we can see the actual status
            },
            // For POST requests, send data if provided
            data: endpoint.method === 'POST' ? (endpoint.data || {}) : undefined,
            // For GET requests, send params if provided
            params: endpoint.method === 'GET' ? endpoint.params : undefined
        });

        // Check if status is in expected status codes (if provided)
        const isExpectedStatus = endpoint.expectedStatus 
            ? endpoint.expectedStatus.includes(response.status)
            : (response.status >= 200 && response.status < 300);

        // Consider any response a success for monitoring purposes if it's expected
        return {
            isOnline: true,
            status: response.status,
            message: response.statusText || (isExpectedStatus ? 'OK' : 'Responded with error'),
            isExpected: isExpectedStatus
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