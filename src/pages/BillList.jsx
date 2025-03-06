import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { getLegislation, searchLegislation } from '../services/api';

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

          const response = await searchLegislation(searchParams);
          setBills(response.data?.results || []);
        } else {
          // Otherwise fetch all bills
          const response = await getLegislation();
          setBills(response.data?.results || []);
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

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Texas Legislation</h1>

      {error && (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-6" role="alert">
          <p>{error}</p>
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center items-center h-64">
          <p className="text-gray-500">Loading bills...</p>
        </div>
      ) : bills.length > 0 ? (
        <div className="grid grid-cols-1 gap-4">
          {bills.map((bill) => (
            <div key={bill.id} className="bg-white rounded-lg shadow-md p-4">
              <h2 className="text-xl font-semibold mb-2">{bill.title || bill.bill_number}</h2>
              <p className="text-gray-600 mb-2">
                <span className="font-medium">{bill.bill_number}</span> - {bill.status || 'Status unknown'}
              </p>
              <p className="text-sm text-gray-500 mb-4">
                {bill.summary ? bill.summary.substring(0, 200) + '...' : 'No summary available.'}
              </p>
              <div className="flex justify-end">
                <a 
                  href={`/bills/${bill.id}`} 
                  className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-md text-sm"
                >
                  View Details
                </a>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-gray-100 rounded-lg p-6 text-center">
          <p className="text-gray-600">No bills found matching your criteria.</p>
        </div>
      )}
    </div>
  );
}

export default BillList;