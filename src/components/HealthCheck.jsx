
import React, { useState, useEffect } from 'react';
import apiService from '../services/api';

const HealthCheck = () => {
  const [status, setStatus] = useState('checking');
  const [error, setError] = useState(null);
  const [apiUrl, setApiUrl] = useState('');
  
  useEffect(() => {
    // Get the API URL from environment or config for display purposes
    const displayUrl = import.meta.env.VITE_API_URL || 'http://0.0.0.0:8000';
    setApiUrl(displayUrl);
    
    const checkHealth = async () => {
      try {
        const response = await apiService.healthCheck();
        if (response && response.data) {
          setStatus('online');
        } else {
          setStatus('offline');
          setError('Invalid API response format');
        }
      } catch (err) {
        setStatus('offline');
        setError(err.message || 'Unknown error occurred');
        console.error('Health check error:', err);
      }
    };
    
    checkHealth();
  }, []);
  
  return (
    <div className="health-check p-4 bg-white rounded-lg shadow mb-6">
      <h2 className="text-xl font-semibold mb-2">API Connection Status</h2>
      
      <div className="status-indicator flex items-center mb-3">
        <div
          className={`h-4 w-4 rounded-full mr-2 ${
            status === 'online' ? 'bg-green-500' : 
            status === 'checking' ? 'bg-yellow-400' : 'bg-red-500'
          }`}
        ></div>
        <span className="font-medium">
          {status === 'online' ? 'Connected' : 
           status === 'checking' ? 'Checking Connection...' : 'Connection Error'}
        </span>
      </div>
      
      {error && (
        <div className="error-details mt-2 p-3 bg-red-50 border border-red-200 rounded text-sm">
          <p className="font-bold mb-1">Error Details:</p>
          <p className="text-red-700">{error}</p>
          <p className="mt-2 text-xs">Attempting to connect to: <code className="bg-gray-100 p-1 rounded">{apiUrl}</code></p>
          <p className="mt-2 text-xs">
            If this error persists, please check that:
            <ul className="list-disc ml-4 mt-1">
              <li>The backend server is running</li>
              <li>CORS is properly configured</li>
              <li>The API URL is correct in your environment</li>
            </ul>
          </p>
        </div>
      )}
      
      {status === 'online' && (
        <div className="success-details mt-2 p-3 bg-green-50 border border-green-200 rounded text-sm">
          <p className="text-green-700">Successfully connected to API</p>
          <p className="text-xs mt-1">Connected to: <code className="bg-gray-100 p-1 rounded">{apiUrl}</code></p>
        </div>
      )}
    </div>
  );
};

export default HealthCheck;
