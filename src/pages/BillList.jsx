import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { billService } from '../services/api';
import SearchBar from '../components/SearchBar';
import BillSearchResults from '../components/BillSearchResults';

function BillList() {
  const location = useLocation();
  const [bills, setBills] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Parse query parameters from URL
  const queryParams = new URLSearchParams(location.search);
  const initialQuery = queryParams.get('q') || '';
  
  useEffect(() => {
    const fetchBills = async () => {
      try {
        setIsLoading(true);
        
        // If we have query parameters, use search endpoint
        if (location.search) {
          const searchParams = {};
          for (const [key, value] of queryParams.entries()) {
            searchParams[key] = value;
          }
          
          const data = await billService.searchBills(searchParams);
          setBills(data);
        } else {
          // Otherwise fetch all bills
          const data = await billService.getAllBills();
          setBills(data);
        }
      } catch (err) {
        setError('Failed to load bills. Please try again later.');
        console.error('Error fetching bills:', err);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchBills();
  }, [location.search]);
  
  const handleSearch = async (searchParams) => {
    try {
      setIsLoading(true);
      const data = await billService.searchBills(searchParams);
      setBills(data);
    } catch (err) {
      setError('Search failed. Please try again later.');
      console.error('Error searching bills:', err);
    } finally {
      setIsLoading(false);
    }
  };
  
  // Mock data for development/testing
  const mockBills = [
    { id: 1, title: "HB 1234", description: "An act relating to education funding", state: "CA", status: "In Committee" },
    { id: 2, title: "SB 5678", description: "An act relating to healthcare reform", state: "NY", status: "Passed" },
    { id: 3, title: "HB 9012", description: "An act relating to transportation infrastructure", state: "TX", status: "Introduced" },
    { id: 4, title: "SB 3456", description: "An act relating to environmental protection", state: "WA", status: "In Committee" },
    { id: 5, title: "HB 7890", description: "An act relating to criminal justice reform", state: "IL", status: "Passed" },
  ];
  
  // Use actual bills if available, otherwise use mock data
  const displayBills = bills.length > 0 ? bills : mockBills;

  return (
    <div>
      <div className="mb-6">
        <h1 className="mb-4">Bills</h1>
        <SearchBar onSearch={handleSearch} initialQuery={initialQuery} />
      </div>
      
      <BillSearchResults 
        bills={displayBills} 
        isLoading={isLoading} 
        error={error} 
      />
    </div>
  );
}

export default BillList; 
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getTexasHealthLegislation, getTexasLocalGovtLegislation } from '../services/api';

const BillList = () => {
  const [bills, setBills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [billType, setBillType] = useState('health'); // 'health' or 'localGovt'
  
  useEffect(() => {
    const fetchBills = async () => {
      setLoading(true);
      try {
        const response = billType === 'health' 
          ? await getTexasHealthLegislation()
          : await getTexasLocalGovtLegislation();
        
        setBills(response.data.items || []);
        setError(null);
      } catch (err) {
        console.error('Error fetching bills:', err);
        setError('Failed to load legislation data. Please try again later.');
        setBills([]);
      } finally {
        setLoading(false);
      }
    };

    fetchBills();
  }, [billType]);

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Texas Legislation</h1>
      
      <div className="mb-6">
        <div className="flex space-x-4 mb-4">
          <button
            onClick={() => setBillType('health')}
            className={`px-4 py-2 rounded-md ${
              billType === 'health' 
                ? 'bg-blue-600 text-white' 
                : 'bg-gray-200 text-gray-800 hover:bg-gray-300'
            }`}
          >
            Public Health Bills
          </button>
          <button
            onClick={() => setBillType('localGovt')}
            className={`px-4 py-2 rounded-md ${
              billType === 'localGovt' 
                ? 'bg-blue-600 text-white' 
                : 'bg-gray-200 text-gray-800 hover:bg-gray-300'
            }`}
          >
            Local Government Bills
          </button>
        </div>
      </div>
      
      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      ) : error ? (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4" role="alert">
          <p>{error}</p>
        </div>
      ) : bills.length === 0 ? (
        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4">
          <p className="text-yellow-700">No bills found. Try changing your filter or check back later.</p>
        </div>
      ) : (
        <div className="bg-white shadow-md rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Bill Number</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Introduced</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Relevance</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {bills.map((bill) => (
                <tr key={bill.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Link to={`/bills/${bill.id}`} className="text-blue-600 hover:text-blue-800 font-medium">
                      {bill.bill_number}
                    </Link>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm text-gray-900">{bill.title}</div>
                    {bill.description && (
                      <div className="text-xs text-gray-500 mt-1 truncate max-w-md">
                        {bill.description}
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      bill.status === 'PASSED' ? 'bg-green-100 text-green-800' :
                      bill.status === 'FAILED' ? 'bg-red-100 text-red-800' :
                      'bg-yellow-100 text-yellow-800'
                    }`}>
                      {bill.status || 'Unknown'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {bill.introduced_date ? new Date(bill.introduced_date).toLocaleDateString() : 'N/A'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="w-full bg-gray-200 rounded-full h-2.5">
                        <div 
                          className="bg-blue-600 h-2.5 rounded-full" 
                          style={{ width: `${billType === 'health' ? bill.health_relevance * 10 : bill.local_govt_relevance * 10}%` }}
                        ></div>
                      </div>
                      <span className="ml-2 text-xs text-gray-600">
                        {billType === 'health' ? bill.health_relevance : bill.local_govt_relevance}/10
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default BillList;
