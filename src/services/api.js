
// API service for handling all backend requests
const API_URL = '/api';

/**
 * Check the health/status of the API
 * @returns {Promise<Object>} Response data with message
 */
export const checkApiHealth = async () => {
  try {
    const response = await fetch(`${API_URL}/`);
    
    if (!response.ok) {
      throw new Error(`API responded with status: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('API health check failed:', error);
    throw error;
  }
};

/**
 * Get a list of bills with optional filters
 * @param {Object} filters - Optional filters for the query
 * @returns {Promise<Array>} Array of bill objects
 */
export const getBills = async (filters = {}) => {
  try {
    // Build query string from filters
    const queryParams = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, value);
      }
    });
    
    const queryString = queryParams.toString();
    const endpoint = `${API_URL}/bills${queryString ? `?${queryString}` : ''}`;
    
    const response = await fetch(endpoint);
    
    if (!response.ok) {
      throw new Error(`Failed to fetch bills: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error fetching bills:', error);
    throw error;
  }
};

/**
 * Get detailed information about a specific bill
 * @param {string|number} billId - ID of the bill to retrieve
 * @returns {Promise<Object>} Bill data
 */
export const getBillDetails = async (billId) => {
  try {
    const response = await fetch(`${API_URL}/bills/${billId}`);
    
    if (!response.ok) {
      throw new Error(`Failed to fetch bill details: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error(`Error fetching bill ${billId}:`, error);
    throw error;
  }
};

/**
 * Get analysis for a specific bill
 * @param {string|number} billId - ID of the bill
 * @returns {Promise<Object>} Analysis data
 */
export const getBillAnalysis = async (billId) => {
  try {
    const response = await fetch(`${API_URL}/analysis/${billId}`);
    
    if (!response.ok) {
      throw new Error(`Failed to fetch analysis: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error(`Error fetching analysis for bill ${billId}:`, error);
    throw error;
  }
};

export default {
  checkApiHealth,
  getBills,
  getBillDetails,
  getBillAnalysis
};
