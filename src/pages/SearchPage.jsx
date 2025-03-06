
import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { searchLegislation } from '../services/api';

const SearchPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const query = searchParams.get('q') || '';
  
  const handleSearch = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const searchQuery = formData.get('query');
    
    setSearchParams({ q: searchQuery });
    
    if (!searchQuery.trim()) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await searchLegislation({ query: searchQuery });
      setResults(response.data);
    } catch (err) {
      console.error('Search error:', err);
      setError('An error occurred while searching. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  React.useEffect(() => {
    if (query) {
      (async () => {
        setLoading(true);
        setError(null);
        try {
          const response = await searchLegislation({ query });
          setResults(response.data);
        } catch (err) {
          console.error('Search error:', err);
          setError('An error occurred while searching. Please try again.');
        } finally {
          setLoading(false);
        }
      })();
    }
  }, []);

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Search Legislation</h1>
      
      <form onSubmit={handleSearch} className="mb-8">
        <div className="flex gap-2">
          <input
            type="text"
            name="query"
            placeholder="Search by keyword, bill number, or topic..."
            className="flex-grow p-2 border border-gray-300 rounded"
            defaultValue={query}
          />
          <button 
            type="submit"
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
            disabled={loading}
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>
      </form>
      
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}
      
      {loading ? (
        <div className="flex justify-center">
          <p>Loading results...</p>
        </div>
      ) : (
        <>
          {results.length > 0 ? (
            <div>
              <h2 className="text-xl font-semibold mb-4">Search Results ({results.length})</h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {results.map((bill) => (
                  <div key={bill.id} className="border rounded shadow p-4">
                    <h3 className="font-medium">{bill.bill_number}</h3>
                    <p className="text-sm text-gray-600">{bill.title}</p>
                    <a 
                      href={`/bills/${bill.id}`}
                      className="text-blue-600 hover:underline text-sm block mt-2"
                    >
                      View Details →
                    </a>
                  </div>
                ))}
              </div>
            </div>
          ) : query ? (
            <div className="text-center py-8">
              <p>No results found for "{query}"</p>
              <p className="text-sm text-gray-600 mt-2">Try using different keywords or check your spelling</p>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
};

export default SearchPage;
