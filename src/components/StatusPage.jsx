
import React, { useState, useEffect } from 'react';
import { API_ENDPOINTS, checkAllEndpoints } from '../services/apiEndpointService';
import { healthCheck } from '../services/api';

const StatusPage = () => {
  const [endpointStatus, setEndpointStatus] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [apiStatus, setApiStatus] = useState({
    isChecking: true,
    isOnline: false,
    message: 'Checking API status...',
    lastChecked: null
  });

  useEffect(() => {
    const checkApiHealth = async () => {
      try {
        const response = await healthCheck();
        setApiStatus({
          isChecking: false,
          isOnline: true,
          message: response.data.message || 'API is online',
          lastChecked: new Date()
        });
      } catch (error) {
        setApiStatus({
          isChecking: false,
          isOnline: false,
          message: 'API is offline or unreachable',
          lastChecked: new Date()
        });
      }
    };

    const checkEndpoints = async () => {
      setIsLoading(true);
      const results = await checkAllEndpoints();
      setEndpointStatus(results);
      setIsLoading(false);
    };

    checkApiHealth();
    checkEndpoints();

    // Check every 60 seconds
    const intervalHealth = setInterval(checkApiHealth, 60000);
    const intervalEndpoints = setInterval(checkEndpoints, 60000);
    
    return () => {
      clearInterval(intervalHealth);
      clearInterval(intervalEndpoints);
    };
  }, []);

  return (
    <div className="status-page bg-white rounded-lg shadow-md p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-4">PolicyPulse API Status</h1>
        
        <div className="api-overall-status p-4 rounded-lg mb-6 border-l-4 border-blue-500 bg-blue-50">
          <div className="flex items-center mb-2">
            <div className={`h-4 w-4 rounded-full mr-2 ${apiStatus.isOnline ? 'bg-green-500' : apiStatus.isChecking ? 'bg-yellow-400' : 'bg-red-500'}`}></div>
            <h2 className="text-xl font-semibold">System Status: {apiStatus.isOnline ? 'Operational' : 'Service Disruption'}</h2>
          </div>
          <p className="text-gray-700">{apiStatus.message}</p>
          {apiStatus.lastChecked && (
            <p className="text-sm text-gray-500 mt-1">Last checked: {apiStatus.lastChecked.toLocaleString()}</p>
          )}
        </div>
      </div>

      <div className="endpoints-status">
        <h2 className="text-xl font-semibold mb-4">API Endpoints Status</h2>
        
        {isLoading ? (
          <div className="animate-pulse p-4 bg-gray-100 rounded-lg">
            <p>Checking API endpoints...</p>
          </div>
        ) : (
          <div className="endpoint-grid overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-100">
                  <th className="text-left p-2 border">Service</th>
                  <th className="text-left p-2 border">Endpoint</th>
                  <th className="text-left p-2 border">Method</th>
                  <th className="text-left p-2 border">Status</th>
                  <th className="text-left p-2 border">Message</th>
                </tr>
              </thead>
              <tbody>
                {API_ENDPOINTS.map((endpoint) => {
                  const status = endpointStatus[endpoint.path] || { 
                    isOnline: false, 
                    status: 0, 
                    message: 'Not checked yet' 
                  };
                  
                  return (
                    <tr key={endpoint.path} className="border-b hover:bg-gray-50">
                      <td className="p-2 border font-medium">{endpoint.name}</td>
                      <td className="p-2 border font-mono text-sm">{endpoint.path}</td>
                      <td className="p-2 border">{endpoint.method}</td>
                      <td className="p-2 border">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          status.isOnline ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                        }`}>
                          {status.isOnline ? 'Operational' : 'Degraded'} {status.status > 0 && `(${status.status})`}
                        </span>
                      </td>
                      <td className="p-2 border">
                        {status.isOnline ? (
                          <span className="text-gray-700">{status.message}</span>
                        ) : (
                          <span className="text-red-600">{status.message || 'Could not connect to endpoint'}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default StatusPage;
