
import React, { useState, useEffect } from 'react';

function App() {
  const [apiStatus, setApiStatus] = useState('checking');
  
  useEffect(() => {
    // Simple health check to verify backend connection
    fetch('/api/health')
      .then(response => {
        if (response.ok) {
          setApiStatus('online');
        } else {
          setApiStatus('offline');
        }
      })
      .catch(error => {
        console.error('Health check failed:', error);
        setApiStatus('offline');
      });
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <h1>Texas Legislative Tracker</h1>
        <p>Hello World! This is our new frontend.</p>
        <div className="api-status">
          <p>API Status: 
            <span className={apiStatus === 'online' ? 'status-online' : 'status-offline'}>
              {apiStatus === 'checking' ? 'Checking...' : apiStatus}
            </span>
          </p>
        </div>
      </header>
    </div>
  );
}

export default App;
