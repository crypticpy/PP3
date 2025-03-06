
import React, { useState, useEffect } from 'react';
import { checkApiHealth } from '../services/api';

function HealthCheck() {
  const [status, setStatus] = useState({ loading: true, error: null, message: '' });

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await checkApiHealth();
        setStatus({
          loading: false,
          error: null,
          message: response.message
        });
      } catch (error) {
        setStatus({
          loading: false,
          error: true,
          message: error.message || 'Failed to connect to API'
        });
      }
    };

    checkHealth();
  }, []);

  if (status.loading) {
    return <div className="p-2 border-l-4 border-blue-500 bg-blue-50 text-blue-700">Checking API connection...</div>;
  }

  if (status.error) {
    return <div className="p-2 border-l-4 border-red-500 bg-red-50 text-red-700">API Error: {status.message}</div>;
  }

  return (
    <div className="p-2 border-l-4 border-green-500 bg-green-50 text-green-700">
      API Status: {status.message}
    </div>
  );
}

export default HealthCheck;
