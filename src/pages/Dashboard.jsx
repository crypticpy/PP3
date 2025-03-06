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
import React, { useEffect, useState } from 'react';
import { getRecentActivity, getImpactSummary } from '../services/api';

const Dashboard = () => {
  const [recentActivity, setRecentActivity] = useState([]);
  const [impactSummary, setImpactSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        const [activityResponse, summaryResponse] = await Promise.all([
          getRecentActivity(),
          getImpactSummary()
        ]);
        
        setRecentActivity(activityResponse.data.activities || []);
        setImpactSummary(summaryResponse.data.summary || {});
      } catch (err) {
        console.error('Error fetching dashboard data:', err);
        setError('Failed to load dashboard data. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-6" role="alert">
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Dashboard</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h2 className="text-xl font-semibold mb-4">Impact Summary</h2>
          {impactSummary ? (
            <div className="space-y-3">
              <div className="flex justify-between">
                <span>Health Bills:</span>
                <span className="font-medium">{impactSummary.healthBillCount || 0}</span>
              </div>
              <div className="flex justify-between">
                <span>Local Govt Bills:</span>
                <span className="font-medium">{impactSummary.localGovtBillCount || 0}</span>
              </div>
              <div className="flex justify-between">
                <span>High Impact Bills:</span>
                <span className="font-medium">{impactSummary.highImpactCount || 0}</span>
              </div>
            </div>
          ) : (
            <p className="text-gray-500">No impact data available</p>
          )}
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h2 className="text-xl font-semibold mb-4">Recent Activity</h2>
          {recentActivity.length > 0 ? (
            <ul className="divide-y divide-gray-200">
              {recentActivity.map((activity, index) => (
                <li key={index} className="py-3">
                  <p className="font-medium">{activity.title || 'Untitled activity'}</p>
                  <p className="text-sm text-gray-600">{activity.description || 'No description'}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {new Date(activity.timestamp).toLocaleString()}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-500">No recent activity</p>
          )}
        </div>
      </div>
      
      <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
        <h2 className="text-lg font-semibold text-blue-700 mb-2">Welcome to the Texas Legislative Tracker</h2>
        <p className="text-blue-600">
          Use the navigation above to browse bills, search for specific legislation, or update your preferences.
        </p>
      </div>
    </div>
  );
};

export default Dashboard;
