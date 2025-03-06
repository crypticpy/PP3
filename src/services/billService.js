
import api, { 
  getLegislation,
  getLegislationById,
  searchLegislation,
  getTexasHealthLegislation,
  getTexasLocalGovtLegislation,
  analyzeLegislation
} from './api';

// Bill retrieval functions
export const getAllBills = async () => {
  const response = await getLegislation();
  return response.data;
};

export const getBillById = async (id) => {
  const response = await getLegislationById(id);
  return response.data;
};

export const searchBills = async (params) => {
  const response = await searchLegislation(params);
  return response.data;
};

export const getHealthBills = async () => {
  const response = await getTexasHealthLegislation();
  return response.data;
};

export const getLocalGovBills = async () => {
  const response = await getTexasLocalGovtLegislation();
  return response.data;
};

// Bill analysis functions
export const requestBillAnalysis = async (billId, options = {}) => {
  const response = await analyzeLegislation(billId, options);
  return response.data;
};

export default {
  getAllBills,
  getBillById,
  searchBills,
  getHealthBills,
  getLocalGovBills,
  requestBillAnalysis
};
import api from './api';

/**
 * Service for bill-related operations
 */
export const billService = {
  /**
   * Get a single bill by ID
   * @param {string} billId - The ID of the bill to retrieve
   * @returns {Promise} - Promise resolving to bill data
   */
  getBillById: async (billId) => {
    try {
      const response = await api.get(`/legislation/${billId}`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching bill ${billId}:`, error);
      throw error;
    }
  },
  
  /**
   * Get bill analysis by ID
   * @param {string} billId - The ID of the bill
   * @returns {Promise} - Promise resolving to bill analysis data
   */
  getBillAnalysis: async (billId) => {
    try {
      const response = await api.get(`/legislation/${billId}/analysis`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching analysis for bill ${billId}:`, error);
      throw error;
    }
  },
  
  /**
   * Get bill history by ID
   * @param {string} billId - The ID of the bill
   * @returns {Promise} - Promise resolving to bill history data
   */
  getBillHistory: async (billId) => {
    try {
      const response = await api.get(`/legislation/${billId}/history`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching history for bill ${billId}:`, error);
      throw error;
    }
  },
  
  /**
   * Request an analysis for a bill
   * @param {string} billId - The ID of the bill to analyze
   * @param {Object} options - Analysis options
   * @returns {Promise} - Promise resolving to analysis result
   */
  requestAnalysis: async (billId, options = {}) => {
    try {
      const response = await api.post(`/legislation/${billId}/analysis`, options);
      return response.data;
    } catch (error) {
      console.error(`Error requesting analysis for bill ${billId}:`, error);
      throw error;
    }
  }
};
