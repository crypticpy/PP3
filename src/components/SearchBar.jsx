import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

function SearchBar({ onSearch, initialQuery = '' }) {
  const [query, setQuery] = useState(initialQuery);
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
  const [filters, setFilters] = useState({
    state: '',
    status: '',
    dateFrom: '',
    dateTo: '',
    topic: '',
  });
  
  const navigate = useNavigate();

  const handleSearch = (e) => {
    e.preventDefault();
    
    // Combine query and filters
    const searchParams = {
      q: query,
      ...filters
    };
    
    // Remove empty filters
    Object.keys(searchParams).forEach(key => 
      !searchParams[key] && delete searchParams[key]
    );
    
    if (onSearch) {
      onSearch(searchParams);
    } else {
      // Build query string for URL
      const queryString = new URLSearchParams(searchParams).toString();
      navigate(`/bills?${queryString}`);
    }
  };
  
  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({
      ...prev,
      [name]: value
    }));
  };
  
  const clearFilters = () => {
    setFilters({
      state: '',
      status: '',
      dateFrom: '',
      dateTo: '',
      topic: '',
    });
  };

  return (
    <div className="w-full bg-white rounded-lg shadow-md">
      <form onSubmit={handleSearch} className="p-4">
        <div className="flex flex-col md:flex-row gap-2">
          <div className="flex-grow relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <svg className="h-5 w-5 text-secondary-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
              </svg>
            </div>
            <input
              type="text"
              className="pl-10 w-full py-2 border border-secondary-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="Search bills by keyword, number, or sponsor..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <button 
            type="submit" 
            className="btn btn-primary flex items-center justify-center"
          >
            Search
          </button>
          <button 
            type="button" 
            className="btn btn-secondary flex items-center justify-center"
            onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
          >
            {isAdvancedOpen ? 'Hide Filters' : 'Show Filters'}
            <svg 
              className={`ml-1 h-5 w-5 transform transition-transform ${isAdvancedOpen ? 'rotate-180' : ''}`} 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
        
        {isAdvancedOpen && (
          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pt-4 border-t border-secondary-200">
            <div>
              <label htmlFor="state" className="block text-sm font-medium text-secondary-700 mb-1">
                State
              </label>
              <select
                id="state"
                name="state"
                className="w-full py-2 px-3 border border-secondary-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                value={filters.state}
                onChange={handleFilterChange}
              >
                <option value="">All States</option>
                <option value="AL">Alabama</option>
                <option value="AK">Alaska</option>
                <option value="AZ">Arizona</option>
                <option value="CA">California</option>
                <option value="CO">Colorado</option>
                <option value="NY">New York</option>
                <option value="TX">Texas</option>
                {/* Add more states as needed */}
              </select>
            </div>
            
            <div>
              <label htmlFor="status" className="block text-sm font-medium text-secondary-700 mb-1">
                Status
              </label>
              <select
                id="status"
                name="status"
                className="w-full py-2 px-3 border border-secondary-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                value={filters.status}
                onChange={handleFilterChange}
              >
                <option value="">All Statuses</option>
                <option value="introduced">Introduced</option>
                <option value="in_committee">In Committee</option>
                <option value="passed">Passed</option>
                <option value="enacted">Enacted</option>
                <option value="vetoed">Vetoed</option>
              </select>
            </div>
            
            <div>
              <label htmlFor="topic" className="block text-sm font-medium text-secondary-700 mb-1">
                Topic
              </label>
              <select
                id="topic"
                name="topic"
                className="w-full py-2 px-3 border border-secondary-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                value={filters.topic}
                onChange={handleFilterChange}
              >
                <option value="">All Topics</option>
                <option value="education">Education</option>
                <option value="healthcare">Healthcare</option>
                <option value="environment">Environment</option>
                <option value="taxation">Taxation</option>
                <option value="transportation">Transportation</option>
              </select>
            </div>
            
            <div>
              <label htmlFor="dateFrom" className="block text-sm font-medium text-secondary-700 mb-1">
                From Date
              </label>
              <input
                type="date"
                id="dateFrom"
                name="dateFrom"
                className="w-full py-2 px-3 border border-secondary-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                value={filters.dateFrom}
                onChange={handleFilterChange}
              />
            </div>
            
            <div>
              <label htmlFor="dateTo" className="block text-sm font-medium text-secondary-700 mb-1">
                To Date
              </label>
              <input
                type="date"
                id="dateTo"
                name="dateTo"
                className="w-full py-2 px-3 border border-secondary-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                value={filters.dateTo}
                onChange={handleFilterChange}
              />
            </div>
            
            <div className="flex items-end">
              <button
                type="button"
                className="w-full py-2 px-4 border border-secondary-300 rounded-md text-secondary-700 bg-white hover:bg-secondary-50 focus:outline-none focus:ring-2 focus:ring-primary-500"
                onClick={clearFilters}
              >
                Clear Filters
              </button>
            </div>
          </div>
        )}
      </form>
    </div>
  );
}

export default SearchBar; 