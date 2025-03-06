import React, { useState } from 'react';
import AnalysisSummary from './AnalysisSummary';
import SentimentAnalysis from './SentimentAnalysis';
import TopicsAnalysis from './TopicsAnalysis';
import StakeholderImpact from './StakeholderImpact';

// Placeholder component implementations if they don't exist
// You can replace these with your actual component implementations
const AnalysisSummaryPlaceholder = ({ data }) => (
  <div className="card">
    <h3 className="text-lg font-semibold mb-2">Analysis Summary</h3>
    <p>{data?.summary || 'No summary available.'}</p>
  </div>
);

const SentimentAnalysisPlaceholder = ({ data }) => (
  <div className="card">
    <h3 className="text-lg font-semibold mb-2">Sentiment Analysis</h3>
    <p>Sentiment score: {data?.sentiment || 'N/A'}</p>
  </div>
);

const TopicsAnalysisPlaceholder = ({ data }) => (
  <div className="card">
    <h3 className="text-lg font-semibold mb-2">Topics Analysis</h3>
    <p>Key topics: {data?.topics?.join(', ') || 'None identified'}</p>
  </div>
);

const StakeholderImpactPlaceholder = ({ data }) => (
  <div className="card">
    <h3 className="text-lg font-semibold mb-2">Stakeholder Impact</h3>
    <p>Impacts: {data?.impacts || 'No impacts identified'}</p>
  </div>
);

const AnalysisDashboard = ({ analysisData }) => {
  // Use actual components if they exist, otherwise use placeholders
  const SummaryComponent = typeof AnalysisSummary === 'function' ? AnalysisSummary : AnalysisSummaryPlaceholder;
  const SentimentComponent = typeof SentimentAnalysis === 'function' ? SentimentAnalysis : SentimentAnalysisPlaceholder;
  const TopicsComponent = typeof TopicsAnalysis === 'function' ? TopicsAnalysis : TopicsAnalysisPlaceholder;
  const ImpactComponent = typeof StakeholderImpact === 'function' ? StakeholderImpact : StakeholderImpactPlaceholder;

  return (
    <div className="analysis-dashboard">
      <h2 className="text-2xl font-bold mb-4">Bill Analysis</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SummaryComponent data={analysisData} />
        <SentimentComponent data={analysisData} />
        <TopicsComponent data={analysisData} />
        <ImpactComponent data={analysisData} />
      </div>
    </div>
  );
};

export default AnalysisDashboard;