
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import './index.css';
import { healthCheck } from './services/api';
import LandingPage from './components/LandingPage';
import StatusPage from './components/StatusPage';
import ApiEndpointsStatus from './components/ApiEndpointsStatus';
import Dashboard from './components/Dashboard';
import BillsPage from './components/BillsPage';

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
    <Router>
      <div className="App">
        <header className="App-header">
          <div className="container mx-auto flex justify-between items-center px-4">
            <Link to="/" className="text-white no-underline">
              <h1 className="text-xl md:text-2xl font-bold">
                <span className="text-purple-300">Policy</span>Pulse
              </h1>
            </Link>
            <nav className="flex space-x-4">
              <Link to="/" className="text-white hover:text-blue-200 transition px-3 py-2">Home</Link>
              <Link to="/dashboard" className="text-white hover:text-blue-200 transition px-3 py-2">Dashboard</Link>
              <Link to="/bills" className="text-white hover:text-blue-200 transition px-3 py-2">Bills</Link>
              <Link to="/status" className="text-white hover:text-blue-200 transition px-3 py-2">Status</Link>
            </nav>
          </div>
          <div className="api-status mt-2 mx-4">
            <p>
              {apiStatus.isChecking ? 'Checking API status...' : (
                <>
                  SYSTEM STATUS 
                  <span className={apiStatus.isOnline ? 'status-online' : 'status-offline'}>
                    {apiStatus.isOnline ? 'OPERATIONAL' : 'OFFLINE'}
                  </span>
                </>
              )}
            </p>
          </div>
        </header>
        
        <main className="App-content">
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/status" element={<StatusPage />} />
            <Route path="/dashboard" element={
              apiStatus.isOnline ? <Dashboard /> : (
                <div className="mt-8 p-4 bg-red-50 rounded-lg shadow border border-red-200">
                  <h2 className="text-2xl font-bold mb-4">Dashboard - API Offline</h2>
                  <p className="text-red-600 mb-4">The API is currently offline. Please try again later.</p>
                </div>
              )
            } />
            <Route path="/bills" element={
              apiStatus.isOnline ? <BillsPage /> : (
                <div className="mt-8 p-4 bg-red-50 rounded-lg shadow border border-red-200">
                  <h2 className="text-2xl font-bold mb-4">Bills - API Offline</h2>
                  <p className="text-red-600 mb-4">The API is currently offline. Please try again later.</p>
                </div>
              )
            } />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
