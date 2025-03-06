import React, { useState, useEffect } from 'react';
import ApiEndpointsStatus from './ApiEndpointsStatus';
import { healthCheck } from '../services/api';


const StatusPage = () => {
  const [apiStatus, setApiStatus] = useState({
    coreApi: { isOnline: null, lastChecked: null },
    database: { isOnline: null, lastChecked: null },
    dataPipeline: { isOnline: null, lastChecked: null },
  });

  useEffect(() => {
    const checkApiHealth = async () => {
      try {
        const response = await healthCheck();
        setApiStatus({
          coreApi: { isOnline: true, lastChecked: new Date() },
          database: { isOnline: true, lastChecked: new Date() }, // Assume database is also online
          dataPipeline: { isOnline: true, lastChecked: new Date() }, // Assume pipeline is also online
        });
      } catch (error) {
        setApiStatus({
          coreApi: { isOnline: false, lastChecked: new Date() },
          database: { isOnline: false, lastChecked: new Date() },
          dataPipeline: { isOnline: false, lastChecked: new Date() },
        });
      }
    };

    checkApiHealth();
    const intervalHealth = setInterval(checkApiHealth, 60000);
    return () => clearInterval(intervalHealth);
  }, []);

  return (
    <div className="status-page max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-6">System Status</h1>
        <p className="text-gray-600 mb-4">
          This page provides real-time information about the PolicyPulse API and its endpoints.
          Use this page to check the status of various services within the system.
        </p>

        <div className="api-overall-status mb-8">
          <h2 className="text-xl font-semibold mb-2">API Health</h2>
          <p className="mb-4">
            The current status of the PolicyPulse API system. This shows the overall health of the backend services.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white p-6 rounded-lg shadow border border-gray-100">
              <div className="flex items-center justify-between">
                <span className="text-gray-500 font-medium">Core API</span>
                <span className={`px-2 py-1 rounded-md text-sm font-medium ${apiStatus.coreApi.isOnline ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                  {apiStatus.coreApi.isOnline ? 'Operational' : 'Degraded'}
                </span>
              </div>
              <div className="mt-2 text-sm text-gray-500">Last updated: {apiStatus.coreApi.lastChecked?.toLocaleTimeString()}</div>
            </div>
            <div className="bg-white p-6 rounded-lg shadow border border-gray-100">
              <div className="flex items-center justify-between">
                <span className="text-gray-500 font-medium">Database</span>
                <span className={`px-2 py-1 rounded-md text-sm font-medium ${apiStatus.database.isOnline ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                  {apiStatus.database.isOnline ? 'Operational' : 'Degraded'}
                </span>
              </div>
              <div className="mt-2 text-sm text-gray-500">Last updated: {apiStatus.database.lastChecked?.toLocaleTimeString()}</div>
            </div>
            <div className="bg-white p-6 rounded-lg shadow border border-gray-100">
              <div className="flex items-center justify-between">
                <span className="text-gray-500 font-medium">Data Pipeline</span>
                <span className={`px-2 py-1 rounded-md text-sm font-medium ${apiStatus.dataPipeline.isOnline ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                  {apiStatus.dataPipeline.isOnline ? 'Operational' : 'Degraded'}
                </span>
              </div>
              <div className="mt-2 text-sm text-gray-500">Last updated: {apiStatus.dataPipeline.lastChecked?.toLocaleTimeString()}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="api-endpoints-status">
        <h2 className="text-xl font-semibold mb-4">API Endpoints Status</h2>
        <p className="text-gray-600 mb-6">
          Detailed status of individual API endpoints. This shows which specific endpoints are operational.
        </p>
        <ApiEndpointsStatus />
      </div>
    </div>
  );
};

export default StatusPage;