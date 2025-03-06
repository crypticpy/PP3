
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getRecentActivity, getImpactSummary } from '../services/api';

function Dashboard() {
  const [recentBills, setRecentBills] = useState([]);
  const [impactSummary, setImpactSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        // Fetch recent bills with analysis
        const recentActivityResponse = await getRecentActivity();
        setRecentBills(recentActivityResponse.data.bills || []);
        
        // Fetch impact summary data
        const impactSummaryResponse = await getImpactSummary();
        setImpactSummary(impactSummaryResponse.data || null);
        
        setLoading(false);
      } catch (err) {
        console.error('Error fetching dashboard data:', err);
        setError('Failed to load dashboard data. Please try again later.');
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  // Helper function to get a badge color based on bill level
  const getBillLevelBadge = (level) => {
    const levelMap = {
      'presidential': 'bg-purple-100 text-purple-800',
      'congressional': 'bg-blue-100 text-blue-800',
      'state': 'bg-green-100 text-green-800',
      'local': 'bg-yellow-100 text-yellow-800',
      'default': 'bg-gray-100 text-gray-800'
    };
    return levelMap[level?.toLowerCase()] || levelMap.default;
  };

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Hero Section */}
      <section className="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-xl shadow-lg mb-10 p-8 text-white">
        <h1 className="text-4xl font-bold mb-4">PolicyPulse</h1>
        <p className="text-xl mb-6">
          Presidential, Congressional and State policy tracker that uses AI to analyze the impact of new policy in a way that helps leaders plan and adapt quickly.
        </p>
        <div className="flex flex-wrap gap-4">
          <Link to="/bills" className="px-6 py-3 bg-white text-blue-700 font-medium rounded-lg hover:bg-blue-50 transition-colors">
            Browse Legislation
          </Link>
          <a href="#recent-analysis" className="px-6 py-3 bg-blue-500 text-white font-medium rounded-lg hover:bg-blue-600 transition-colors">
            View Recent Analysis
          </a>
        </div>
      </section>

      {/* Main Dashboard Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Recent Bills Section */}
        <div className="lg:col-span-2">
          <h2 id="recent-analysis" className="text-2xl font-bold mb-4">Latest Analyzed Bills</h2>
          
          {loading ? (
            <div className="animate-pulse space-y-4">
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="bg-gray-100 rounded-lg p-4">
                  <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
                  <div className="h-3 bg-gray-200 rounded w-1/2"></div>
                </div>
              ))}
            </div>
          ) : error ? (
            <div className="bg-red-50 text-red-800 p-4 rounded-lg">{error}</div>
          ) : (
            <div className="space-y-4">
              {recentBills.length === 0 ? (
                <p>No recent bills available.</p>
              ) : (
                recentBills.map(bill => (
                  <Link 
                    key={bill.id} 
                    to={`/bills/${bill.id}`}
                    className="block bg-white rounded-lg shadow-md p-4 hover:shadow-lg transition-shadow border border-gray-100"
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <span className={`inline-block px-2 py-1 text-xs font-semibold rounded-full mb-2 ${getBillLevelBadge(bill.level)}`}>
                          {bill.level || 'Unknown'}
                        </span>
                        <h3 className="text-lg font-semibold mb-1">{bill.title}</h3>
                        <p className="text-sm text-gray-600 mb-2">
                          {bill.number} • {new Date(bill.lastAction?.date || bill.date).toLocaleDateString()}
                        </p>
                        <p className="text-sm line-clamp-2">{bill.description || bill.summary || 'No description available'}</p>
                      </div>
                      {bill.analysis?.impactScore && (
                        <div className="ml-4 flex-shrink-0">
                          <div className="flex items-center justify-center h-14 w-14 rounded-full bg-gray-50 border-2 border-blue-500">
                            <span className="text-lg font-bold text-blue-700">{bill.analysis.impactScore}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  </Link>
                ))
              )}
            </div>
          )}
        </div>

        {/* Impact Analysis Section */}
        <div>
          <h2 className="text-2xl font-bold mb-4">Impact Analysis</h2>
          
          {loading ? (
            <div className="animate-pulse space-y-4">
              <div className="h-40 bg-gray-100 rounded-lg"></div>
              <div className="h-40 bg-gray-100 rounded-lg"></div>
            </div>
          ) : error ? (
            <div className="bg-red-50 text-red-800 p-4 rounded-lg">{error}</div>
          ) : (
            <>
              {/* Policy Distribution Card */}
              <div className="bg-white rounded-lg shadow-md p-4 mb-6">
                <h3 className="text-lg font-semibold mb-3">Policy Distribution</h3>
                {impactSummary?.policyDistribution ? (
                  <div className="space-y-2">
                    {Object.entries(impactSummary.policyDistribution).map(([level, count]) => (
                      <div key={level} className="flex items-center">
                        <span className={`inline-block w-20 px-2 py-1 text-xs font-semibold rounded-full ${getBillLevelBadge(level)}`}>
                          {level}
                        </span>
                        <div className="flex-1 mx-2 bg-gray-200 rounded-full h-2.5">
                          <div 
                            className="bg-blue-600 h-2.5 rounded-full" 
                            style={{ width: `${(count / Math.max(...Object.values(impactSummary.policyDistribution))) * 100}%` }}
                          ></div>
                        </div>
                        <span className="text-sm font-medium">{count}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500">No distribution data available</p>
                )}
              </div>

              {/* Top Impact Areas Card */}
              <div className="bg-white rounded-lg shadow-md p-4 mb-6">
                <h3 className="text-lg font-semibold mb-3">Top Impact Areas</h3>
                {impactSummary?.topImpactAreas ? (
                  <div className="space-y-2">
                    {impactSummary.topImpactAreas.map((area, index) => (
                      <div key={index} className="flex items-center">
                        <span className="text-sm font-medium w-1/3">{area.name}</span>
                        <div className="flex-1 mx-2 bg-gray-200 rounded-full h-2.5">
                          <div 
                            className="bg-green-500 h-2.5 rounded-full" 
                            style={{ width: `${area.score}%` }}
                          ></div>
                        </div>
                        <span className="text-sm font-medium">{area.score}%</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500">No impact area data available</p>
                )}
              </div>

              {/* High Impact Bills Card */}
              <div className="bg-white rounded-lg shadow-md p-4">
                <h3 className="text-lg font-semibold mb-3">High Impact Bills</h3>
                {impactSummary?.highImpactBills ? (
                  <ul className="divide-y divide-gray-200">
                    {impactSummary.highImpactBills.map((bill) => (
                      <li key={bill.id} className="py-2">
                        <Link to={`/bills/${bill.id}`} className="hover:text-blue-600">
                          <div className="flex justify-between">
                            <span className="text-sm font-medium">{bill.number}</span>
                            <span className="text-sm bg-blue-100 text-blue-800 px-2 rounded-full">{bill.impactScore}</span>
                          </div>
                          <p className="text-xs text-gray-500 truncate">{bill.title}</p>
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-gray-500">No high impact bills available</p>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
