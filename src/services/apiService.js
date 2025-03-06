
/**
 * API Service for PolicyPulse
 * Handles API requests and error handling
 */

const API_URL = process.env.REACT_APP_API_URL || '/api';

class ApiService {
  constructor() {
    this.baseUrl = API_URL;
    console.log('API URL configured as:', this.baseUrl);
  }

  /**
   * General request method that handles common logic
   * @param {string} url - The endpoint URL
   * @param {string} method - HTTP method
   * @param {object} data - Request payload for POST/PUT
   * @returns {Promise<any>} Response data
   */
  async request(url, method = 'GET', data = null) {
    const fullUrl = `${this.baseUrl}${url.startsWith('/') ? url : '/' + url}`;
    
    const options = {
      method,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      }
    };

    if (data) {
      options.body = JSON.stringify(data);
    }

    try {
      console.log(`Requesting ${method} ${url}`);
      const response = await fetch(fullUrl, options);
      
      console.log(`Response from ${url}: Status ${response.status}`);
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API error ${response.status}: ${errorText}`);
      }
      
      // For 204 No Content, return empty object
      if (response.status === 204) {
        return {};
      }
      
      // Parse JSON response
      const result = await response.json();
      return result;
    } catch (error) {
      console.error(`API request failed for ${method} ${url}:`, error);
      throw error;
    }
  }

  /**
   * GET request
   * @param {string} url - Endpoint URL
   * @returns {Promise<any>} Response data
   */
  async get(url) {
    return this.request(url);
  }

  /**
   * POST request
   * @param {string} url - Endpoint URL
   * @param {object} data - Request payload
   * @returns {Promise<any>} Response data
   */
  async post(url, data) {
    return this.request(url, 'POST', data);
  }

  /**
   * PUT request
   * @param {string} url - Endpoint URL
   * @param {object} data - Request payload
   * @returns {Promise<any>} Response data
   */
  async put(url, data) {
    return this.request(url, 'PUT', data);
  }

  /**
   * DELETE request
   * @param {string} url - Endpoint URL
   * @returns {Promise<any>} Response data
   */
  async delete(url) {
    return this.request(url, 'DELETE');
  }

  /**
   * Check the API health
   * @returns {Promise<{status: string, message: string, version: string}>} Health status
   */
  async checkHealth() {
    console.log('Checking API health...');
    try {
      const response = await this.get('/health');
      console.log('API health check successful:', response);
      return response;
    } catch (error) {
      console.error('API health check failed:', error);
      return { status: 'error', message: error.message, version: 'unknown' };
    }
  }
}

// Create and export a singleton instance
const apiService = new ApiService();
export default apiService;
