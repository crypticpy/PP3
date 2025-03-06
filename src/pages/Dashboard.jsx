import React from 'react';

function Dashboard() {
  return (
    <div>
      <h1 className="mb-6">Dashboard</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        <div className="card bg-white shadow-md">
          <h3 className="text-primary-700 mb-2">Bills Tracked</h3>
          <p className="text-3xl font-bold">124</p>
        </div>
        
        <div className="card bg-white shadow-md">
          <h3 className="text-primary-700 mb-2">Recent Updates</h3>
          <p className="text-3xl font-bold">18</p>
        </div>
        
        <div className="card bg-white shadow-md">
          <h3 className="text-primary-700 mb-2">States Monitored</h3>
          <p className="text-3xl font-bold">12</p>
        </div>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card bg-white shadow-md">
          <h2 className="text-xl font-bold mb-4 text-primary-700">Recent Activity</h2>
          <div className="space-y-4">
            <p className="text-sm text-secondary-600">No recent activity to display.</p>
          </div>
        </div>
        
        <div className="card bg-white shadow-md">
          <h2 className="text-xl font-bold mb-4 text-primary-700">Important Bills</h2>
          <div className="space-y-4">
            <p className="text-sm text-secondary-600">No important bills to display.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard; 