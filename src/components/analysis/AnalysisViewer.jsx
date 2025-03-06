
import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import apiService from '../../services/apiService';

const AnalysisViewer = ({ legislationId }) => {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [analysisHistory, setAnalysisHistory] = useState([]);

  useEffect(() => {
    if (!legislationId) return;
    
    const fetchAnalysisData = async () => {
      setLoading(true);
      try {
        // First get the legislation details which includes the latest analysis
        const legislationResponse = await apiService.get(`/legislation/${legislationId}`);
        
        if (legislationResponse && legislationResponse.latest_analysis) {
          setAnalysis(legislationResponse.latest_analysis);
        } else {
          // If no analysis in legislation details, try to fetch it directly
          try {
            const analysisResponse = await apiService.get(`/legislation/${legislationId}/analysis/history`);
            if (analysisResponse && analysisResponse.analyses && analysisResponse.analyses.length > 0) {
              // Get the most recent analysis from history
              setAnalysis(analysisResponse.analyses[analysisResponse.analyses.length - 1]);
              setAnalysisHistory(analysisResponse.analyses);
            }
          } catch (historyError) {
            console.error("Error fetching analysis history:", historyError);
          }
        }
      } catch (err) {
        console.error("Error fetching analysis:", err);
        setError("Failed to load analysis data. Please try again later.");
      } finally {
        setLoading(false);
      }
    };

    fetchAnalysisData();
  }, [legislationId]);

  const triggerNewAnalysis = async () => {
    if (!legislationId) return;
    
    setLoading(true);
    try {
      const response = await apiService.post(`/legislation/${legislationId}/analysis`);
      if (response.status === "processing") {
        // If analysis is being processed asynchronously
        alert("Analysis request has been submitted. Please check back later.");
      } else if (response.status === "completed") {
        // If analysis completed synchronously, fetch the latest results
        const updatedResponse = await apiService.get(`/legislation/${legislationId}`);
        if (updatedResponse && updatedResponse.latest_analysis) {
          setAnalysis(updatedResponse.latest_analysis);
        }
      }
    } catch (err) {
      console.error("Error triggering analysis:", err);
      setError("Failed to trigger new analysis. Please try again later.");
    } finally {
      setLoading(false);
    }
  };

  const loadAnalysisHistory = async () => {
    if (!legislationId) return;
    
    setLoading(true);
    try {
      const response = await apiService.get(`/legislation/${legislationId}/analysis/history`);
      if (response && response.analyses) {
        setAnalysisHistory(response.analyses);
        setHistoryOpen(true);
      }
    } catch (err) {
      console.error("Error fetching analysis history:", err);
      setError("Failed to load analysis history. Please try again later.");
    } finally {
      setLoading(false);
    }
  };

  const renderImpactCategory = (category) => {
    const categoryColors = {
      public_health: "bg-red-100 text-red-800",
      local_gov: "bg-blue-100 text-blue-800",
      economic: "bg-green-100 text-green-800",
      environmental: "bg-teal-100 text-teal-800",
      education: "bg-purple-100 text-purple-800",
      infrastructure: "bg-orange-100 text-orange-800"
    };
    
    const colorClass = categoryColors[category] || "bg-gray-100 text-gray-800";
    
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${colorClass}`}>
        {category.replace("_", " ")}
      </span>
    );
  };

  const renderImpactLevel = (level) => {
    const levelColors = {
      low: "bg-green-100 text-green-800",
      moderate: "bg-yellow-100 text-yellow-800",
      high: "bg-orange-100 text-orange-800",
      critical: "bg-red-100 text-red-800"
    };
    
    const colorClass = levelColors[level] || "bg-gray-100 text-gray-800";
    
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${colorClass}`}>
        {level}
      </span>
    );
  };

  if (loading) {
    return <div className="p-4 bg-white rounded-lg shadow"><div className="animate-pulse">Loading analysis...</div></div>;
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 text-red-800 rounded-lg">
        <h3 className="text-lg font-semibold">Error</h3>
        <p>{error}</p>
        <button 
          onClick={triggerNewAnalysis}
          className="mt-2 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
          Request Analysis
        </button>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="p-4 bg-gray-50 rounded-lg">
        <h3 className="text-lg font-semibold">No Analysis Available</h3>
        <p>There is no AI analysis available for this legislation yet.</p>
        <button 
          onClick={triggerNewAnalysis}
          className="mt-2 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
          Request Analysis
        </button>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Analysis Header */}
      <div className="border-b border-gray-200 p-4">
        <div className="flex justify-between items-center">
          <h2 className="text-xl font-semibold">AI Analysis</h2>
          <div className="flex space-x-2">
            {analysis.impact_category && renderImpactCategory(analysis.impact_category)}
            {analysis.impact_level && renderImpactLevel(analysis.impact_level)}
          </div>
        </div>
        <div className="flex justify-between items-center mt-2 text-sm text-gray-500">
          <span>Version {analysis.version || analysis.analysis_version}</span>
          <span>{new Date(analysis.date || analysis.analysis_date).toLocaleDateString()}</span>
        </div>
        <div className="mt-2">
          <button 
            onClick={triggerNewAnalysis}
            className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 mr-2">
            Request New Analysis
          </button>
          <button 
            onClick={loadAnalysisHistory}
            className="px-3 py-1 bg-gray-200 text-gray-800 text-sm rounded hover:bg-gray-300">
            View History
          </button>
        </div>
      </div>

      {/* Analysis Content */}
      <div className="p-4">
        <div className="mb-4">
          <h3 className="font-semibold mb-2">Summary</h3>
          <p className="text-gray-700">{analysis.summary}</p>
        </div>
        
        {analysis.key_points && analysis.key_points.length > 0 && (
          <div className="mb-4">
            <h3 className="font-semibold mb-2">Key Points</h3>
            <ul className="list-disc pl-5">
              {analysis.key_points.map((point, index) => (
                <li key={index} className="mb-1">
                  <span className={`${
                    point.impact_type === 'positive' ? 'text-green-700' : 
                    point.impact_type === 'negative' ? 'text-red-700' : 'text-gray-700'
                  }`}>
                    {point.point}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        
        {/* Public Health Impacts */}
        {analysis.public_health_impacts && (
          <div className="mb-4">
            <h3 className="font-semibold mb-2">Public Health Impacts</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {analysis.public_health_impacts.direct_effects && (
                <div className="bg-red-50 p-3 rounded">
                  <h4 className="text-sm font-semibold text-red-800 mb-1">Direct Effects</h4>
                  <ul className="list-disc pl-5 text-sm">
                    {analysis.public_health_impacts.direct_effects.map((effect, index) => (
                      <li key={index}>{effect}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              {analysis.public_health_impacts.funding_impact && (
                <div className="bg-blue-50 p-3 rounded">
                  <h4 className="text-sm font-semibold text-blue-800 mb-1">Funding Impact</h4>
                  <ul className="list-disc pl-5 text-sm">
                    {analysis.public_health_impacts.funding_impact.map((impact, index) => (
                      <li key={index}>{impact}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
        
        {/* Local Government Impacts */}
        {analysis.local_government_impacts && (
          <div className="mb-4">
            <h3 className="font-semibold mb-2">Local Government Impacts</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {analysis.local_government_impacts.fiscal && (
                <div className="bg-green-50 p-3 rounded">
                  <h4 className="text-sm font-semibold text-green-800 mb-1">Fiscal Impact</h4>
                  <ul className="list-disc pl-5 text-sm">
                    {analysis.local_government_impacts.fiscal.map((impact, index) => (
                      <li key={index}>{impact}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              {analysis.local_government_impacts.implementation && (
                <div className="bg-yellow-50 p-3 rounded">
                  <h4 className="text-sm font-semibold text-yellow-800 mb-1">Implementation</h4>
                  <ul className="list-disc pl-5 text-sm">
                    {analysis.local_government_impacts.implementation.map((item, index) => (
                      <li key={index}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
        
        {/* Recommended Actions */}
        {analysis.recommended_actions && analysis.recommended_actions.length > 0 && (
          <div className="mb-4">
            <h3 className="font-semibold mb-2">Recommended Actions</h3>
            <ul className="list-disc pl-5">
              {analysis.recommended_actions.map((action, index) => (
                <li key={index} className="mb-1">{action}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      
      {/* Analysis History Modal */}
      {historyOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-3xl w-full max-h-[80vh] overflow-auto">
            <div className="p-4 border-b border-gray-200">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-semibold">Analysis History</h3>
                <button 
                  onClick={() => setHistoryOpen(false)}
                  className="text-gray-500 hover:text-gray-700">
                  ✕
                </button>
              </div>
            </div>
            <div className="p-4">
              {analysisHistory.length === 0 ? (
                <p>No analysis history available.</p>
              ) : (
                <ul className="divide-y divide-gray-200">
                  {analysisHistory.map((item, index) => (
                    <li key={index} className="py-3">
                      <div className="flex justify-between items-center">
                        <div>
                          <p className="font-medium">Version {item.version}</p>
                          <p className="text-sm text-gray-500">{new Date(item.date).toLocaleDateString()}</p>
                        </div>
                        <div className="flex space-x-2">
                          {item.impact_category && renderImpactCategory(item.impact_category)}
                          {item.impact_level && renderImpactLevel(item.impact_level)}
                        </div>
                      </div>
                      <p className="text-sm mt-2 text-gray-700">{item.summary}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalysisViewer;
