import api, {
  getLegislation,
  getLegislationById,
  searchLegislation,
  analyzeLegislation,
  getAnalysisHistory
} from './api';

/**
 * Service module for bill-related operations
 */

/**
 * Fetches bills based on provided filters
 * @param {Object} filters - Filter parameters
 * @returns {Promise<Array>} List of bills
 */
export const fetchBills = async (filters = {}) => {
  try {
    const response = await getLegislation(filters);
    return response.data.bills || [];
  } catch (error) {
    console.error('Error fetching bills:', error);
    throw error;
  }
};

/**
 * Fetches a single bill by ID
 * @param {string} billId - The bill ID
 * @returns {Promise<Object>} Bill details
 */
export const fetchBillById = async (billId) => {
  try {
    const response = await getLegislationById(billId);
    return response.data.bill || null;
  } catch (error) {
    console.error(`Error fetching bill ${billId}:`, error);
    throw error;
  }
};

/**
 * Searches for bills based on query
 * @param {string} query - Search query
 * @param {Object} filters - Additional filters
 * @returns {Promise<Array>} Search results
 */
export const searchBills = async (query, filters = {}) => {
  try {
    const response = await searchLegislation({ 
      query, 
      ...filters 
    });
    return response.data.results || [];
  } catch (error) {
    console.error('Error searching bills:', error);
    throw error;
  }
};

/**
 * Requests analysis for a bill
 * @param {string} billId - The bill ID
 * @param {Object} options - Analysis options
 * @returns {Promise<Object>} Analysis result
 */
export const requestBillAnalysis = async (billId, options = {}) => {
  try {
    const response = await analyzeLegislation(billId, options);
    return response.data.analysis || null;
  } catch (error) {
    console.error(`Error analyzing bill ${billId}:`, error);
    throw error;
  }
};

/**
 * Fetches analysis history for a bill
 * @param {string} billId - The bill ID
 * @returns {Promise<Array>} Analysis history
 */
export const fetchAnalysisHistory = async (billId) => {
  try {
    const response = await getAnalysisHistory(billId);
    return response.data.history || [];
  } catch (error) {
    console.error(`Error fetching analysis history for bill ${billId}:`, error);
    throw error;
  }
};