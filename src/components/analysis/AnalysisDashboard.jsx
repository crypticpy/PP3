import React, { useState } from 'react';
import AnalysisSummary from './AnalysisSummary';
import SentimentAnalysis from './SentimentAnalysis';
import TopicsAnalysis from './TopicsAnalysis';
import StakeholderImpact from './StakeholderImpact';

function AnalysisDashboard({ analysis, isLoading, error }) {
  const [activeTab, setActiveTab] = useState('summary');
  
  if (isLoading) {
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
  
  if (!analysis) {
    return (
      <div className="bg-secondary-50 p-6 rounded-lg text-center">
        <p className="text-secondary-600">No analysis data available for this bill.</p>
      </div>
    );
  }

  const tabs = [
    { id: 'summary', label: 'Summary' },
    { id: 'sentiment', label: 'Sentiment' },
    { id: 'topics', label: 'Topics' },
    { id: 'stakeholders', label: 'Stakeholders' },
    { id: 'all', label: 'Full Analysis' }
  ];

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <div className="border-b border-secondary-200">
        <nav className="flex -mb-px overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`whitespace-nowrap py-4 px-6 border-b-2 font-medium text-sm ${
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-secondary-500 hover:text-secondary-700 hover:border-secondary-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="p-6">
        {(activeTab === 'summary' || activeTab === 'all') && (
          <div className={activeTab === 'all' ? 'mb-8' : ''}>
            <AnalysisSummary analysis={analysis} />
          </div>
        )}
        
        {(activeTab === 'sentiment' || activeTab === 'all') && (
          <div className={activeTab === 'all' ? 'mb-8' : ''}>
            <SentimentAnalysis sentiment={analysis.sentiment} />
          </div>
        )}
        
        {(activeTab === 'topics' || activeTab === 'all') && (
          <div className={activeTab === 'all' ? 'mb-8' : ''}>
            <TopicsAnalysis topics={analysis.topics} />
          </div>
        )}
        
        {(activeTab === 'stakeholders' || activeTab === 'all') && (
          <div>
            <StakeholderImpact stakeholders={analysis.stakeholders} />
          </div>
        )}
      </div>
      
      {activeTab !== 'all' && (
        <div className="bg-secondary-50 px-6 py-3 border-t border-secondary-200">
          <button
            onClick={() => setActiveTab('all')}
            className="text-primary-600 hover:text-primary-800 text-sm font-medium"
          >
            View Full Analysis
          </button>
        </div>
      )}
    </div>
  );
}

export default AnalysisDashboard; 