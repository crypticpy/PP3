
import React, { useState, useEffect } from 'react';
import { healthCheck } from '../services/api';

const HealthCheck = () => {
  const [status, setStatus] = useState('checking');
  const [error, setError] = useState(null);
  const [apiUrl, setApiUrl] = useState('');

  useEffect(() => {
    // Get the API URL from environment or config for display purposes
    const displayUrl = import.meta.env.VITE_API_URL || 'http://0.0.0.0:8002';
    setApiUrl(displayUrl);

    const checkHealth = async () => {
      try {
        const response = await healthCheck();
        if (response && response.status === 200) {
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

      {status === 'online' ? (
        <p className="text-green-600">Connected to API at: {apiUrl}</p>
      ) : (
        <div className="error-details mt-2">
          <p className="text-red-600">Cannot connect to API at: {apiUrl}</p>
          {error && <p className="text-red-500 text-sm mt-1">Error: {error}</p>}
          <p className="text-sm mt-2">
            Please ensure the backend server is running and accessible.
          </p>
        </div>
      )}
    </div>
  );
};

export default HealthCheck;
