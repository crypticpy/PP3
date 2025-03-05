/**
 * API service for interacting with the backend
 */

// Base URL for API requests
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || '/api';

/**
 * Generic fetch wrapper with error handling
 * 
 * @param {string} endpoint - API endpoint to call
 * @param {Object} options - Fetch options
 * @returns {Promise<any>} - Response data
 */
async function fetchApi(endpoint, options = {}) {
  try {
    const url = `${API_BASE_URL}${endpoint}`;
    
    // Set default headers
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };
    
    const response = await fetch(url, {
      ...options,
      headers,
    });
    
    // Handle non-2xx responses
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `API error: ${response.status} ${response.statusText}`);
    }
    
    // Parse JSON response
    return await response.json();
  } catch (error) {
    console.error(`API request failed: ${error.message}`, error);
    throw error;
  }
}

/**
 * Get a list of bills with optional filtering
 * 
 * @param {Object} params - Query parameters
 * @param {string} params.state - Filter by state
 * @param {string} params.keyword - Search by keyword
 * @param {number} params.limit - Maximum number of bills to return
 * @param {number} params.offset - Number of bills to skip
 * @returns {Promise<Array>} - List of bills
 */
export async function getBills(params = {}) {
  // Build query string from params
  const queryParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      queryParams.append(key, value);
    }
  });
  
  const queryString = queryParams.toString();
  const endpoint = `/bills/${queryString ? `?${queryString}` : ''}`;
  
  return fetchApi(endpoint);
}

/**
 * Get detailed information about a specific bill
 * 
 * @param {number} billId - Bill ID
 * @returns {Promise<Object>} - Bill details
 */
export async function getBillDetails(billId) {
  return fetchApi(`/bills/${billId}`);
}

/**
 * Get AI analysis for a specific bill
 * 
 * @param {number} billId - Bill ID
 * @returns {Promise<Object>} - Analysis results
 */
export async function getBillAnalysis(billId) {
  return fetchApi(`/bills/${billId}/analysis`);
}

/**
 * Get a list of available states
 * 
 * @returns {Promise<Array<string>>} - List of state codes
 */
export async function getStates() {
  return fetchApi('/states/');
}

/**
 * Refresh bill data from LegiScan API
 * 
 * @param {string} state - Optional state to refresh
 * @returns {Promise<Object>} - Refresh result
 */
export async function refreshData(state = null) {
  const queryParams = state ? `?state=${state}` : '';
  return fetchApi(`/refresh/${queryParams}`, { method: 'POST' });
}

// Export all functions as a single object
const apiService = {
  getBills,
  getBillDetails,
  getBillAnalysis,
  getStates,
  refreshData,
};

export default apiService; 