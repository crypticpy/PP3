import React, { useState, useEffect } from 'react';
import { getRecentActivity, getImpactSummary } from '../services/api';

function Dashboard() {
  const [recentActivity, setRecentActivity] = useState([]);
  const [impactSummary, setImpactSummary] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setIsLoading(true);

        // Fetch dashboard data
        const [activityResponse, summaryResponse] = await Promise.allSettled([
          getRecentActivity(),
          getImpactSummary()
        ]);

        if (activityResponse.status === 'fulfilled') {
          setRecentActivity(activityResponse.value.data?.activities || []);
        }

        if (summaryResponse.status === 'fulfilled') {
          setImpactSummary(summaryResponse.value.data || {});
        }
      } catch (err) {
        setError('Failed to load dashboard data. Please try again later.');
        console.error('Error fetching dashboard data:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

      {error && (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-6" role="alert">
          <p>{error}</p>
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center items-center h-64">
          <p className="text-gray-500">Loading dashboard data...</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-primary-700 mb-2">Bills Tracked</h3>
              <p className="text-3xl font-bold">{impactSummary.bills_tracked || 0}</p>
            </div>

            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-primary-700 mb-2">Recent Updates</h3>
              <p className="text-3xl font-bold">{recentActivity.length || 0}</p>
            </div>

            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-primary-700 mb-2">States Monitored</h3>
              <p className="text-3xl font-bold">{impactSummary.states_monitored || 1}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-xl font-bold mb-4 text-primary-700">Recent Activity</h2>
              <div className="space-y-4">
                {recentActivity.length > 0 ? (
                  recentActivity.map((activity, index) => (
                    <div key={index} className="border-b pb-3">
                      <p className="font-medium">{activity.title || 'Activity Update'}</p>
                      <p className="text-sm text-gray-600">{activity.description}</p>
                      <p className="text-xs text-gray-500 mt-1">{activity.timestamp}</p>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-gray-600">No recent activity to display.</p>
                )}
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-xl font-bold mb-4 text-primary-700">Important Bills</h2>
              <div className="space-y-4">
                {impactSummary.important_bills && impactSummary.important_bills.length > 0 ? (
                  impactSummary.important_bills.map((bill, index) => (
                    <div key={index} className="border-b pb-3">
                      <p className="font-medium">{bill.bill_number}: {bill.title}</p>
                      <p className="text-sm text-gray-600">{bill.status}</p>
                      <a 
                        href={`/bills/${bill.id}`}
                        className="text-blue-600 hover:underline text-sm"
                      >
                        View Details
                      </a>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-gray-600">No important bills to display.</p>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default Dashboard;