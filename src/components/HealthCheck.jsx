
import React, { useState, useEffect } from 'react';
import api from '../services/api';

const HealthCheck = () => {
  const [status, setStatus] = useState('Loading...');
  const [error, setError] = useState(null);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await api.healthCheck();
        setStatus(`API is ${response.data.status}: ${response.data.message}`);
      } catch (err) {
        console.error('Health check failed:', err);
        setError(`Failed to connect to API: ${err.message}`);
        setStatus('Error');
      }
    };

    checkHealth();
  }, []);

  return (
    <div className="p-4 m-4 border rounded bg-white">
      <h2 className="text-xl font-bold mb-2">API Health Status</h2>
      {error ? (
        <div className="text-red-600">
          <p>{error}</p>
          <p className="mt-2 text-sm">
            Please check your network connection and API configuration.
          </p>
        </div>
      ) : (
        <div className="text-green-600">{status}</div>
      )}
    </div>
  );
};

export default HealthCheck;
