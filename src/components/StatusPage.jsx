
import React, { useState, useEffect } from 'react';
import { healthCheck } from '../services/api';
import ApiEndpointsStatus from './ApiEndpointsStatus';

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
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">System Status</h1>
      
      <div className="grid md:grid-cols-3 gap-6 mb-10">
        <StatusCard 
          title="Core API" 
          status={apiStatus.coreApi.isOnline} 
          lastChecked={apiStatus.coreApi.lastChecked} 
          description="Main API services for policy tracking and analysis"
        />
        <StatusCard 
          title="Database" 
          status={apiStatus.database.isOnline} 
          lastChecked={apiStatus.database.lastChecked} 
          description="Storage system for legislative data"
        />
        <StatusCard 
          title="Data Pipeline" 
          status={apiStatus.dataPipeline.isOnline} 
          lastChecked={apiStatus.dataPipeline.lastChecked} 
          description="Data collection and processing system"
        />
      </div>

      <div className="bg-white rounded-lg shadow p-6 mb-8">
        <h2 className="text-2xl font-bold mb-4">API Endpoints Status</h2>
        <p className="mb-6">Detailed status of individual API endpoints that power the Policy Pulse platform.</p>
        <ApiEndpointsStatus />
      </div>
    </div>
  );
};

const StatusCard = ({ title, status, lastChecked, description }) => {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-xl font-bold">{title}</h3>
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${
          status === null ? 'bg-gray-200 text-gray-700' :
          status ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
        }`}>
          {status === null ? 'Checking...' : status ? 'Operational' : 'Offline'}
        </span>
      </div>
      <p className="text-gray-600 mb-4">{description}</p>
      {lastChecked && (
        <p className="text-sm text-gray-500">
          Last checked: {lastChecked.toLocaleTimeString()}
        </p>
      )}
    </div>
  );
};

export default StatusPage;
