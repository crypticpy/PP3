
import React, { useState, useEffect } from 'react';
import './index.css';
import { healthCheck } from './services/api';
import ApiEndpointsStatus from './components/ApiEndpointsStatus';

function App() {
  const [apiStatus, setApiStatus] = useState({
    isChecking: true,
    isOnline: false,
    message: 'Checking API status...'
  });

  useEffect(() => {
    const checkApiHealth = async () => {
      try {
        console.log('Checking API health...');
        const response = await healthCheck();
        console.log('API health check successful:', response.data);
        setApiStatus({
          isChecking: false,
          isOnline: true,
          message: response.data.message || 'API is online'
        });
      } catch (error) {
        console.error('API health check failed:', error);
        setApiStatus({
          isChecking: false,
          isOnline: false,
          message: 'API is offline or unreachable'
        });
      }
    };

    checkApiHealth();
    // Set interval to check every 30 seconds
    const interval = setInterval(checkApiHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <h1>Texas Legislative Tracker</h1>
        <div className="api-status">
          <p>
            {apiStatus.isChecking ? 'Checking API status...' : (
              <>
                API Status: 
                <span className={apiStatus.isOnline ? 'status-online' : 'status-offline'}>
                  {apiStatus.isOnline ? 'Online' : 'Offline'}
                </span>
              </>
            )}
          </p>
          <p>{apiStatus.message}</p>
        </div>
      </header>
      
      <main className="App-content">
        {apiStatus.isOnline && 
          <div className="mt-8 p-4 bg-white rounded-lg shadow">
            <h2 className="text-2xl font-bold mb-4">API Dashboard</h2>
            <p className="mb-4">Welcome to the Texas Legislative Tracker. Below you can see the status of all API endpoints.</p>
            <ApiEndpointsStatus />
          </div>
        }
      </main>
    </div>
  );
}

export default App;
