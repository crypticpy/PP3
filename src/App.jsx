import React, { useState, useEffect } from 'react';
import HealthCheck from './components/HealthCheck';

function App() {
  return (
    <div className="App">
      <header className="App-header p-6 bg-gray-100 min-h-screen">
        <h1 className="text-3xl font-bold mb-4">Texas Legislative Tracker</h1>
        <p className="mb-6">Hello World! This is our new frontend.</p>

        <HealthCheck />

        <div className="mt-8">
          <h2 className="text-xl font-semibold mb-4">Getting Started</h2>
          <p>
            Once the API is connected, you'll be able to browse and track Texas legislation
            relevant to public health and local governments.
          </p>
        </div>
      </header>
    </div>
  );
}

export default App;