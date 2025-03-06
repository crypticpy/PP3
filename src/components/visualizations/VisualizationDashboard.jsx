
import React, { useState } from 'react';
import KeyTermsCloud from './KeyTermsCloud';
import ImpactChart from './ImpactChart';
import BillTimeline from './BillTimeline';

const VisualizationDashboard = ({ billData, analysisData }) => {
  const [activeTab, setActiveTab] = useState('keyTerms');

  const tabs = [
    { id: 'keyTerms', label: 'Key Terms', icon: '🔍' },
    { id: 'impact', label: 'Impact Assessment', icon: '📊' },
    { id: 'timeline', label: 'Bill Timeline', icon: '⏱️' }
  ];

  return (
    <div className="bg-white rounded-lg shadow-md p-4 mb-6">
      <h2 className="text-xl font-bold mb-4">Visualizations</h2>
      
      <div className="flex border-b mb-4">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center mr-4 py-2 px-4 border-b-2 font-medium text-sm ${
              activeTab === tab.id
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
            aria-current={activeTab === tab.id ? 'page' : undefined}
          >
            <span className="mr-2">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      <div className="visualization-container h-96">
        {activeTab === 'keyTerms' && (
          <KeyTermsCloud 
            analysisData={analysisData} 
            height={350}
            width={window.innerWidth > 768 ? 700 : window.innerWidth - 100}
          />
        )}
        
        {activeTab === 'impact' && (
          <ImpactChart 
            analysisData={analysisData} 
          />
        )}
        
        {activeTab === 'timeline' && (
          <BillTimeline 
            billData={billData} 
          />
        )}
      </div>
    </div>
  );
};

export default VisualizationDashboard;
