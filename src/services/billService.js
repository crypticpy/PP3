
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
