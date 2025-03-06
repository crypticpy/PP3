
import React, { useState, useEffect } from 'react';

const Dashboard = () => {
  const [loading, setLoading] = useState(true);
  const [recentBills, setRecentBills] = useState([]);
  const [keyTerms, setKeyTerms] = useState([]);
  const [impactSummary, setImpactSummary] = useState(null);

  useEffect(() => {
    // Simulating loading of dashboard data
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        // These would be replaced with actual API calls
        // Placeholder data for now
        setRecentBills([
          { id: 1, title: "H.R. 1234 - Healthcare Reform Act", jurisdiction: "U.S. Congress", date: "2023-06-15", progress: 60 },
          { id: 2, title: "S. 567 - Education Funding Amendment", jurisdiction: "U.S. Congress", date: "2023-06-10", progress: 30 },
          { id: 3, title: "H.B. 789 - Texas Infrastructure Bill", jurisdiction: "Texas", date: "2023-06-05", progress: 85 },
          { id: 4, title: "S.B. 321 - Energy Regulation Reform", jurisdiction: "Texas", date: "2023-06-01", progress: 45 }
        ]);
        
        setKeyTerms([
          { text: "healthcare", value: 35 },
          { text: "education", value: 28 },
          { text: "infrastructure", value: 25 },
          { text: "energy", value: 22 },
          { text: "reform", value: 20 },
          { text: "tax", value: 18 },
          { text: "budget", value: 16 },
          { text: "regulation", value: 14 }
        ]);
        
        setImpactSummary({
          healthcare: 28,
          education: 23,
          infrastructure: 18,
          energy: 16,
          economy: 15
        });
        
        setLoading(false);
      } catch (error) {
        console.error("Error fetching dashboard data:", error);
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-8">Policy Analysis Dashboard</h1>
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">Policy Analysis Dashboard</h1>
      
      <div className="grid md:grid-cols-2 gap-6 mb-10">
        {/* Recent Legislative Activity */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4">Recent Legislative Activity</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Title
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Jurisdiction
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Date
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Progress
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {recentBills.map(bill => (
                  <tr key={bill.id}>
                    <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-blue-600 hover:text-blue-800">
                      <a href={`/bills/${bill.id}`}>{bill.title}</a>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                      {bill.jurisdiction}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                      {bill.date}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                      <div className="w-full bg-gray-200 rounded-full h-2.5">
                        <div 
                          className="bg-blue-600 h-2.5 rounded-full" 
                          style={{ width: `${bill.progress}%` }}
                        ></div>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        
        {/* Key Terms Analysis */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4">Key Terms Analysis</h2>
          <div className="flex flex-wrap gap-2 justify-center p-4">
            {keyTerms.map((term, index) => (
              <span 
                key={index} 
                className="inline-block px-3 py-1 rounded-full bg-blue-100 text-blue-800"
                style={{ 
                  fontSize: `${Math.max(0.8, term.value / 10)}rem`,
                  opacity: Math.max(0.5, term.value / 40) 
                }}
              >
                {term.text}
              </span>
            ))}
          </div>
        </div>
      </div>
      
      {/* Legislative Impact Analysis */}
      <div className="bg-white rounded-lg shadow p-6 mb-10">
        <h2 className="text-xl font-bold mb-4">Legislative Impact Analysis</h2>
        <div className="grid grid-cols-5 gap-4 text-center">
          {Object.entries(impactSummary).map(([area, value], index) => (
            <div key={index} className="flex flex-col items-center">
              <div className="w-full bg-gray-200 rounded-full h-24 flex flex-col justify-end">
                <div 
                  className="bg-blue-600 rounded-t-full w-full" 
                  style={{ height: `${value * 3}%` }}
                ></div>
              </div>
              <span className="mt-2 text-sm text-gray-700 capitalize">{area}</span>
            </div>
          ))}
        </div>
      </div>
      
      {/* Bill Timeline */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold mb-4">Legislative Timeline</h2>
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute h-full w-1 bg-gray-200 left-1/2 transform -translate-x-1/2"></div>
          
          {/* Timeline events */}
          <div className="space-y-12 relative py-4">
            {/* Sample timeline events */}
            <TimelineEvent 
              date="Jun 15, 2023" 
              title="H.R. 1234 - Healthcare Reform Act"
              description="Introduced in House"
              isLeft={true}
            />
            <TimelineEvent 
              date="Jun 10, 2023" 
              title="S. 567 - Education Funding Amendment"
              description="Referred to Committee"
              isLeft={false}
            />
            <TimelineEvent 
              date="Jun 5, 2023" 
              title="H.B. 789 - Texas Infrastructure Bill"
              description="Passed Committee Vote"
              isLeft={true}
            />
            <TimelineEvent 
              date="Jun 1, 2023" 
              title="S.B. 321 - Energy Regulation Reform"
              description="Introduced in Senate"
              isLeft={false}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

const TimelineEvent = ({ date, title, description, isLeft }) => {
  return (
    <div className={`flex items-center ${isLeft ? 'flex-row' : 'flex-row-reverse'}`}>
      <div className={`w-5/12 ${isLeft ? 'text-right pr-8' : 'text-left pl-8'}`}>
        <div className="text-sm text-gray-500">{date}</div>
        <div className="font-medium">{title}</div>
        <div className="text-sm text-gray-600">{description}</div>
      </div>
      <div className="w-2/12 flex justify-center">
        <div className="w-4 h-4 rounded-full bg-blue-500 z-10"></div>
      </div>
      <div className="w-5/12"></div>
    </div>
  );
};

export default Dashboard;
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import apiService from '../services/apiService';
import AnalysisSummary from './analysis/AnalysisSummary';
import RecentActivity from './RecentActivity';
import StatusIndicator from './StatusIndicator';

const Dashboard = () => {
  const [impactSummary, setImpactSummary] = useState(null);
  const [recentActivity, setRecentActivity] = useState([]);
  const [statusData, setStatusData] = useState({ status: 'checking' });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDashboardData = async () => {
      setLoading(true);
      try {
        // Check API health
        const healthResponse = await apiService.get('/health');
        setStatusData(healthResponse);

        // Try to fetch impact summary
        try {
          const summaryResponse = await apiService.get('/dashboard/impact-summary');
          setImpactSummary(summaryResponse);
        } catch (summaryError) {
          console.warn('Impact summary endpoint not available:', summaryError);
        }

        // Try to fetch recent activity
        try {
          const activityResponse = await apiService.get('/dashboard/recent-activity');
          if (activityResponse && activityResponse.recent_legislation) {
            setRecentActivity(activityResponse.recent_legislation);
          }
        } catch (activityError) {
          console.warn('Recent activity endpoint not available:', activityError);
          
          // Fallback: try to get recent bills from legislation endpoint
          try {
            const legislationResponse = await apiService.get('/legislation?limit=5');
            if (legislationResponse && legislationResponse.items) {
              setRecentActivity(legislationResponse.items);
            }
          } catch (legError) {
            console.error('Failed to fetch recent legislation:', legError);
          }
        }
      } catch (err) {
        console.error('Error fetching dashboard data:', err);
        setError('Failed to load dashboard data. Please try again later.');
        setStatusData({ status: 'error', message: 'API unavailable' });
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="h-32 bg-gray-200 rounded mb-4"></div>
          <div className="h-64 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6 flex justify-between items-center">
        <h1 className="text-3xl font-bold">PolicyPulse Dashboard</h1>
        <StatusIndicator status={statusData.status} message={statusData.message} />
      </div>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6">
          <p>{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="lg:col-span-2 bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Legislative Impact Overview</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-blue-50 rounded-lg p-4">
              <h3 className="text-lg font-medium text-blue-800 mb-2">Public Health</h3>
              <p className="text-sm mb-2">
                Recent legislation with significant public health impacts
              </p>
              <div className="flex justify-between items-center">
                <span className="text-3xl font-bold text-blue-800">
                  {impactSummary?.public_health_count || '?'}
                </span>
                <Link to="/legislation?impact=public_health" className="text-blue-600 hover:underline text-sm">
                  View all
                </Link>
              </div>
            </div>
            <div className="bg-green-50 rounded-lg p-4">
              <h3 className="text-lg font-medium text-green-800 mb-2">Local Government</h3>
              <p className="text-sm mb-2">
                Recent legislation with significant local government impacts
              </p>
              <div className="flex justify-between items-center">
                <span className="text-3xl font-bold text-green-800">
                  {impactSummary?.local_govt_count || '?'}
                </span>
                <Link to="/legislation?impact=local_gov" className="text-green-600 hover:underline text-sm">
                  View all
                </Link>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">API Status</h2>
          <div className="space-y-4">
            <div className="flex items-center">
              <div className={`w-3 h-3 rounded-full mr-2 ${
                statusData.status === 'ok' ? 'bg-green-500' : 'bg-red-500'
              }`}></div>
              <span>API Status: {statusData.status === 'ok' ? 'Online' : 'Offline'}</span>
            </div>
            <div className="text-sm text-gray-600">
              <p>Version: {statusData.version || 'Unknown'}</p>
              <p>Message: {statusData.message || 'No information available'}</p>
            </div>
            <Link to="/status" className="inline-block mt-2 text-blue-600 hover:underline">
              View detailed status
            </Link>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-lg shadow p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">Recent Legislation</h2>
            <Link to="/legislation" className="text-blue-600 hover:underline text-sm">
              View all
            </Link>
          </div>
          {recentActivity.length > 0 ? (
            <div className="divide-y divide-gray-200">
              {recentActivity.map((item, index) => (
                <div key={index} className="py-3">
                  <div className="flex justify-between">
                    <Link to={`/legislation/${item.id}`} className="font-medium text-blue-600 hover:underline">
                      {item.bill_number}
                    </Link>
                    <span className="text-sm text-gray-500">
                      {new Date(item.updated_at || item.bill_last_action_date).toLocaleDateString()}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 truncate">{item.title}</p>
                  <div className="mt-1 flex space-x-2">
                    {item.bill_status && (
                      <span className="px-2 py-1 bg-gray-100 text-gray-800 text-xs rounded-full">
                        {item.bill_status}
                      </span>
                    )}
                    {item.govt_type && (
                      <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                        {item.govt_type}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500">No recent legislation found.</p>
          )}
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Analysis Overview</h2>
          <AnalysisSummary />
          <div className="mt-4">
            <Link to="/bills" className="text-blue-600 hover:underline">
              Browse all analyzed bills
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
