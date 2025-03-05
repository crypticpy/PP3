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