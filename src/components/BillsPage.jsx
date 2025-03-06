
import React, { useState, useEffect } from 'react';

const BillsPage = () => {
  const [loading, setLoading] = useState(true);
  const [bills, setBills] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState({
    jurisdiction: 'all',
    status: 'all',
    dateRange: 'all'
  });

  useEffect(() => {
    // Simulating loading of bills data
    const fetchBills = async () => {
      try {
        setLoading(true);
        // This would be replaced with actual API calls
        // Placeholder data for now
        setBills([
          { 
            id: 1, 
            title: "H.R. 1234 - Healthcare Reform Act", 
            jurisdiction: "U.S. Congress", 
            status: "In Committee",
            date: "2023-06-15", 
            summary: "A bill to reform healthcare provisions across federal agencies and programs.",
            sponsor: "Rep. John Smith",
            type: "House Bill"
          },
          { 
            id: 2, 
            title: "S. 567 - Education Funding Amendment", 
            jurisdiction: "U.S. Congress", 
            status: "Introduced",
            date: "2023-06-10", 
            summary: "A bill to amend education funding allocations for public schools.",
            sponsor: "Sen. Jane Doe",
            type: "Senate Bill"
          },
          { 
            id: 3, 
            title: "H.B. 789 - Texas Infrastructure Bill", 
            jurisdiction: "Texas", 
            status: "Passed Committee",
            date: "2023-06-05", 
            summary: "A bill to fund infrastructure improvements across the state of Texas.",
            sponsor: "Rep. Robert Johnson",
            type: "House Bill"
          },
          { 
            id: 4, 
            title: "S.B. 321 - Energy Regulation Reform", 
            jurisdiction: "Texas", 
            status: "Introduced",
            date: "2023-06-01", 
            summary: "A bill to reform energy regulations and promote renewable energy sources.",
            sponsor: "Sen. Maria Rodriguez",
            type: "Senate Bill"
          },
          { 
            id: 5, 
            title: "H.R. 987 - Federal Budget Amendments", 
            jurisdiction: "U.S. Congress", 
            status: "Floor Vote Scheduled",
            date: "2023-05-25", 
            summary: "A bill to amend the federal budget for the upcoming fiscal year.",
            sponsor: "Rep. William Taylor",
            type: "House Bill"
          }
        ]);
        
        setLoading(false);
      } catch (error) {
        console.error("Error fetching bills data:", error);
        setLoading(false);
      }
    };

    fetchBills();
  }, []);

  // Filter bills based on search and filters
  const filteredBills = bills.filter(bill => {
    // Apply search term filter
    if (searchTerm && !bill.title.toLowerCase().includes(searchTerm.toLowerCase()) && 
        !bill.summary.toLowerCase().includes(searchTerm.toLowerCase())) {
      return false;
    }
    
    // Apply jurisdiction filter
    if (filters.jurisdiction !== 'all' && bill.jurisdiction !== filters.jurisdiction) {
      return false;
    }
    
    // Apply status filter
    if (filters.status !== 'all' && bill.status !== filters.status) {
      return false;
    }
    
    // Apply date filter - simplified for demo
    if (filters.dateRange === 'lastWeek') {
      const lastWeek = new Date();
      lastWeek.setDate(lastWeek.getDate() - 7);
      if (new Date(bill.date) < lastWeek) {
        return false;
      }
    } else if (filters.dateRange === 'lastMonth') {
      const lastMonth = new Date();
      lastMonth.setMonth(lastMonth.getMonth() - 1);
      if (new Date(bill.date) < lastMonth) {
        return false;
      }
    }
    
    return true;
  });

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-8">Legislation Tracking</h1>
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">Legislation Tracking</h1>
      
      {/* Search and Filters */}
      <div className="bg-white rounded-lg shadow p-6 mb-8">
        <div className="flex flex-col md:flex-row gap-4 mb-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search bills by title or content..."
              className="w-full p-2 border border-gray-300 rounded-md"
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <select 
              className="p-2 border border-gray-300 rounded-md"
              value={filters.jurisdiction}
              onChange={e => setFilters({...filters, jurisdiction: e.target.value})}
            >
              <option value="all">All Jurisdictions</option>
              <option value="U.S. Congress">U.S. Congress</option>
              <option value="Texas">Texas</option>
            </select>
            <select 
              className="p-2 border border-gray-300 rounded-md"
              value={filters.status}
              onChange={e => setFilters({...filters, status: e.target.value})}
            >
              <option value="all">All Statuses</option>
              <option value="Introduced">Introduced</option>
              <option value="In Committee">In Committee</option>
              <option value="Passed Committee">Passed Committee</option>
              <option value="Floor Vote Scheduled">Floor Vote Scheduled</option>
            </select>
            <select 
              className="p-2 border border-gray-300 rounded-md"
              value={filters.dateRange}
              onChange={e => setFilters({...filters, dateRange: e.target.value})}
            >
              <option value="all">All Dates</option>
              <option value="lastWeek">Last Week</option>
              <option value="lastMonth">Last Month</option>
            </select>
          </div>
        </div>
        <div className="text-sm text-gray-500">
          Showing {filteredBills.length} of {bills.length} bills
        </div>
      </div>
      
      {/* Bills List */}
      <div className="space-y-4">
        {filteredBills.length > 0 ? (
          filteredBills.map(bill => (
            <div key={bill.id} className="bg-white rounded-lg shadow p-6 transition hover:shadow-md">
              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start mb-4">
                <h3 className="text-xl font-bold text-blue-600 hover:text-blue-800">
                  <a href={`/bills/${bill.id}`}>{bill.title}</a>
                </h3>
                <div className="flex items-center mt-2 sm:mt-0">
                  <span className="px-3 py-1 rounded-full bg-blue-100 text-blue-800 text-sm">
                    {bill.jurisdiction}
                  </span>
                  <span className="ml-2 px-3 py-1 rounded-full bg-gray-100 text-gray-800 text-sm">
                    {bill.status}
                  </span>
                </div>
              </div>
              <p className="text-gray-600 mb-4">{bill.summary}</p>
              <div className="flex flex-wrap gap-y-2 text-sm text-gray-500">
                <div className="w-full sm:w-1/3">
                  <span className="font-medium">Type:</span> {bill.type}
                </div>
                <div className="w-full sm:w-1/3">
                  <span className="font-medium">Sponsor:</span> {bill.sponsor}
                </div>
                <div className="w-full sm:w-1/3">
                  <span className="font-medium">Date Introduced:</span> {bill.date}
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="bg-gray-50 rounded-lg p-8 text-center">
            <p className="text-gray-500">No bills found matching your search criteria.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default BillsPage;
