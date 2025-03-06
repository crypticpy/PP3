import React, { useState, useEffect } from 'react';
//Simulating apiEndpointService.js -  This would ideally be a separate file.
const API_ENDPOINTS = [
  { name: 'Health Check', path: '/health', method: 'GET' },
  { name: 'API Root', path: '/', method: 'GET' },
  { name: 'Impact Summary', path: '/dashboard/impact-summary', method: 'GET' },
  { name: 'Recent Activity', path: '/dashboard/recent-activity', method: 'GET' },
  { name: 'Legislation List', path: '/legislation', method: 'GET' },
  { name: 'Legislation Detail', path: '/legislation/1', method: 'GET' },
  { name: 'Legislation Search', path: '/legislation/search', method: 'GET' },
  { name: 'Texas Health Legislation', path: '/texas/health-legislation', method: 'GET' },
  { name: 'Texas Local Government Legislation', path: '/texas/local-govt-legislation', method: 'GET' },
  { name: 'Bills List', path: '/bills/', method: 'GET' },
  { name: 'Bill Detail', path: '/bills/1', method: 'GET' },
  { name: 'Bill Analysis', path: '/bills/1/analysis', method: 'GET' },
  { name: 'States List', path: '/states/', method: 'GET' },
  { name: 'Advanced Search', path: '/search/advanced', method: 'POST' },
  { name: 'User Preferences', path: '/users/test@example.com/preferences', method: 'GET' },
  { name: 'Search History', path: '/users/test@example.com/search', method: 'GET' },
  { name: 'Sync Status', path: '/sync/status', method: 'GET' },
];

const checkAllEndpoints = async () => {
  const results = {};
  for (const endpoint of API_ENDPOINTS) {
    try {
      let response;
      if (endpoint.path === '/legislation/search') {
        response = await fetch(endpoint.path + '?keywords=test'); //Adding parameter for testing
      } else if (endpoint.path === '/legislation/1' || endpoint.path === '/bills/1' || endpoint.path === '/bills/1/analysis') {
          response = await fetch(endpoint.path, { //handling 404 gracefully
            method: endpoint.method,
          });
          if (!response.ok && response.status === 404) {
            results[endpoint.path] = { isOnline: true, status: response.status, message: 'Not Found (Expected if no data)' };
            continue;
          } else if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
      } else {
        response = await fetch(endpoint.path, {
          method: endpoint.method,
        });
      }


      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      results[endpoint.path] = { isOnline: true, status: response.status, message: data.message || 'OK' };
    } catch (error) {
      results[endpoint.path] = { isOnline: false, status: 0, message: error.message };
    }
  }
  return results;
};


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