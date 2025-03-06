
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
