import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { billService } from '../services/api';
import AnalysisDashboard from '../components/analysis/AnalysisDashboard';
import VisualizationDashboard from '../components/visualizations/VisualizationDashboard';

function BillDetail() {
  const { billId } = useParams();
  const [bill, setBill] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [similarBills, setSimilarBills] = useState([]);
  
  useEffect(() => {
    const fetchBill = async () => {
      try {
        setLoading(true);
        const data = await billService.getBillById(billId);
        setBill(data);
        
        // Fetch similar bills if available
        if (data && data.similarBills) {
          const similarBillsData = await Promise.all(
            data.similarBills.map(id => billService.getBillById(id))
          );
          setSimilarBills(similarBillsData.filter(Boolean));
        }
      } catch (err) {
        setError('Failed to load bill details. Please try again later.');
        console.error('Error fetching bill:', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchBill();
  }, [billId]);
  
  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-600"></div>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="bg-red-50 border-l-4 border-red-500 p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <p className="text-sm text-red-700">
              {error}
            </p>
          </div>
        </div>
      </div>
    );
  }
  
  // Fallback for development/testing
  const mockBill = {
    id: billId,
    title: "HB 1234",
    description: "An act relating to education funding",
    state: "CA",
    status: "In Committee",
    introduced: "2023-01-15",
    introduced_date: "2023-01-15", // Added for visualization components
    lastAction: "Referred to Education Committee",
    sponsors: ["John Smith", "Jane Doe"],
    text: "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam auctor, nisl eget ultricies tincidunt, nisl nisl aliquam nisl, eget ultricies nisl nisl eget nisl.",
    progress: 45, // Added for visualization components
    history: [
      { date: "2023-01-15", action: "Introduced", chamber: "House", importance: "major" },
      { date: "2023-01-20", action: "Referred to Committee", chamber: "House", importance: "normal" },
      { date: "2023-02-10", action: "Committee Hearing", chamber: "House", importance: "normal" },
      { date: "2023-03-05", action: "Committee Vote", chamber: "House", importance: "major" },
      { date: "2023-03-15", action: "Floor Vote Scheduled", chamber: "House", importance: "normal" }
    ],
    analysis: {
      summary: "This bill would increase funding for public education by 5% over the next fiscal year.",
      keyProvisions: [
        "Increases education budget by 5%",
        "Allocates additional funds for teacher salaries",
        "Establishes new grant program for technology"
      ],
      potentialImpacts: [
        "Improved educational outcomes",
        "Reduced class sizes",
        "Increased teacher retention"
      ],
      sentiment: {
        score: 0.65,
        explanation: "The bill is generally viewed positively by education advocates and has bipartisan support."
      },
      topics: [
        { name: "Education", score: 0.95 },
        { name: "Budget", score: 0.82 },
        { name: "Teachers", score: 0.75 },
        { name: "Technology", score: 0.60 },
        { name: "School Infrastructure", score: 0.45 }
      ],
      stakeholders: [
        { name: "Teachers", type: "advocacy", impact: "positive", reason: "Increased salaries and resources", influence: 8 },
        { name: "Students", type: "public", impact: "positive", reason: "Improved educational resources", influence: 5 },
        { name: "School Districts", type: "government", impact: "positive", reason: "Additional funding", influence: 9 },
        { name: "Taxpayers", type: "public", impact: "negative", reason: "Potential tax implications", influence: 6 },
        { name: "Education Technology Companies", type: "industry", impact: "positive", reason: "New grant opportunities", influence: 7 }
      ],
      stakeholderRelationships: [
        { source: "Teachers", target: "Students", strength: 5 },
        { source: "School Districts", target: "Teachers", strength: 7 },
        { source: "School Districts", target: "Students", strength: 6 },
        { source: "Taxpayers", target: "School Districts", strength: 4 },
        { source: "Education Technology Companies", target: "School Districts", strength: 3 },
        { source: "Education Technology Companies", target: "Teachers", strength: 2 }
      ],
      keyTerms: [
        { term: "education", relevance: 0.95 },
        { term: "funding", relevance: 0.90 },
        { term: "teachers", relevance: 0.85 },
        { term: "schools", relevance: 0.80 },
        { term: "budget", relevance: 0.75 },
        { term: "grants", relevance: 0.70 },
        { term: "technology", relevance: 0.65 },
        { term: "students", relevance: 0.60 },
        { term: "classrooms", relevance: 0.55 },
        { term: "resources", relevance: 0.50 }
      ],
      support: 65,
      opposition: 35
    }
  };
  
  // Mock similar bills for development/testing
  const mockSimilarBills = [
    {
      id: "SB5678",
      title: "SB 5678 - Education Technology Grant Program",
      status: "Passed",
      introduced_date: "2022-03-10",
      progress: 100,
      analysis: { support: 75, opposition: 25 }
    },
    {
      id: "HB7890",
      title: "HB 7890 - Teacher Salary Increase Act",
      status: "In Committee",
      introduced_date: "2023-02-05",
      progress: 30,
      analysis: { support: 60, opposition: 40 }
    },
    {
      id: "SB1234",
      title: "SB 1234 - School Infrastructure Improvement",
      status: "Introduced",
      introduced_date: "2023-01-20",
      progress: 15,
      analysis: { support: 55, opposition: 45 }
    }
  ];
  
  // Use actual bill data if available, otherwise use mock data
  const displayBill = bill || mockBill;
  const displaySimilarBills = similarBills.length ? similarBills : mockSimilarBills;

  return (
    <div>
      {/* Breadcrumb navigation */}
      <nav className="mb-4">
        <ol className="flex text-sm text-secondary-500">
          <li className="flex items-center">
            <Link to="/" className="hover:text-primary-600">Dashboard</Link>
            <svg className="h-4 w-4 mx-2" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
            </svg>
          </li>
          <li className="flex items-center">
            <Link to="/bills" className="hover:text-primary-600">Bills</Link>
            <svg className="h-4 w-4 mx-2" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
            </svg>
          </li>
          <li className="text-secondary-700 font-medium">{displayBill.title}</li>
        </ol>
      </nav>
      
      <div className="mb-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-primary-700">{displayBill.title}</h1>
            <p className="text-lg text-secondary-600">{displayBill.description}</p>
          </div>
          <div className="mt-4 md:mt-0 flex space-x-2">
            <button className="btn btn-secondary flex items-center">
              <svg className="h-5 w-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
              </svg>
              Save
            </button>
            <button className="btn btn-secondary flex items-center">
              <svg className="h-5 w-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
              Export
            </button>
          </div>
        </div>
        
        <div className="mt-4 inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-secondary-100 text-secondary-800">
          <span className="mr-1">Status:</span>
          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold 
            ${displayBill.status === 'Passed' ? 'bg-green-100 text-green-800' : 
              displayBill.status === 'In Committee' ? 'bg-yellow-100 text-yellow-800' : 
              displayBill.status === 'Introduced' ? 'bg-blue-100 text-blue-800' : 
              'bg-secondary-100 text-secondary-800'}`}>
            {displayBill.status}
          </span>
        </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="card bg-white shadow-md">
          <h3 className="text-primary-700 mb-2">State</h3>
          <p>{displayBill.state}</p>
        </div>
        
        <div className="card bg-white shadow-md">
          <h3 className="text-primary-700 mb-2">Introduced</h3>
          <p>{displayBill.introduced}</p>
        </div>
        
        <div className="card bg-white shadow-md">
          <h3 className="text-primary-700 mb-2">Last Action</h3>
          <p>{displayBill.lastAction}</p>
        </div>
      </div>
      
      <div className="grid grid-cols-1 gap-6 mb-8">
        <div className="card bg-white shadow-md">
          <h2 className="text-xl font-bold mb-4 text-primary-700">Sponsors</h2>
          <div className="flex flex-wrap gap-2">
            {displayBill.sponsors.map((sponsor, index) => (
              <span 
                key={index} 
                className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-primary-100 text-primary-800"
              >
                {sponsor}
              </span>
            ))}
          </div>
        </div>
        
        <div className="card bg-white shadow-md">
          <h2 className="text-xl font-bold mb-4 text-primary-700">Bill Text</h2>
          <div className="bg-secondary-50 p-4 rounded">
            <p className="whitespace-pre-line">{displayBill.text}</p>
          </div>
        </div>
      </div>
      
      <div className="mb-8">
        <h2 className="text-xl font-bold mb-4 text-primary-700">AI Analysis</h2>
        <AnalysisDashboard analysis={displayBill.analysis} />
      </div>
      
      {/* Add the Visualization Dashboard */}
      <div className="mb-8">
        <VisualizationDashboard 
          bill={displayBill} 
          analysis={displayBill.analysis} 
          similarBills={displaySimilarBills} 
        />
      </div>
    </div>
  );
}

export default BillDetail; 