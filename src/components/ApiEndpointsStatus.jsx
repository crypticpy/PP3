
import React, { useState, useEffect } from 'react';
import { API_ENDPOINTS, checkAllEndpoints } from '../services/apiEndpointService';

const ApiEndpointsStatus = () => {
  const [endpointStatus, setEndpointStatus] = useState({});
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const checkEndpoints = async () => {
      setIsLoading(true);
      const results = await checkAllEndpoints();
      setEndpointStatus(results);
      setIsLoading(false);
    };

    checkEndpoints();
    
    // Check every 60 seconds
    const interval = setInterval(checkEndpoints, 60000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="api-endpoints-status">
      <h2 className="text-xl font-semibold mb-4">API Endpoints Status</h2>
      
      {isLoading ? (
        <p>Checking API endpoints...</p>
      ) : (
        <div className="endpoint-grid">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-gray-100">
                <th className="text-left p-2 border">Name</th>
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
                  <tr key={endpoint.path} className="border-b">
                    <td className="p-2 border font-medium">{endpoint.name}</td>
                    <td className="p-2 border">{endpoint.path}</td>
                    <td className="p-2 border">{endpoint.method}</td>
                    <td className="p-2 border">
                      <span className={`font-semibold px-2 py-1 rounded ${status.isOnline ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                        {status.isOnline ? 'Online' : 'Offline'} {status.status > 0 && `(${status.status})`}
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
  );
};

export default ApiEndpointsStatus;
