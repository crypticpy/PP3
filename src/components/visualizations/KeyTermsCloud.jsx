import React from 'react';
import ReactWordcloud from 'react-wordcloud';
import { prepareWordCloudData } from '../../services/visualizationService';

/**
 * Key Terms Word Cloud Component
 * 
 * Displays a word cloud visualization of key terms from bill analysis
 * 
 * @param {Object} analysis - The bill analysis data containing key terms
 */
const KeyTermsCloud = ({ analysis }) => {
  const wordCloudData = prepareWordCloudData(analysis);
  
  const options = {
    colors: ['#3b82f6', '#60a5fa', '#93c5fd', '#2563eb', '#1d4ed8'],
    enableTooltip: true,
    deterministic: false,
    fontFamily: 'Inter, sans-serif',
    fontSizes: [12, 60],
    fontStyle: 'normal',
    fontWeight: 'normal',
    padding: 1,
    rotations: 3,
    rotationAngles: [0, 90],
    scale: 'sqrt',
    spiral: 'archimedean',
    transitionDuration: 1000,
  };
  
  if (!wordCloudData.length) {
    return (
      <div className="p-4 text-center text-gray-500 dark:text-gray-400">
        No key terms data available for this bill.
      </div>
    );
  }

  return (
    <div className="key-terms-cloud mt-4 bg-white dark:bg-gray-800 rounded-lg shadow p-4">
      <h3 className="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200">
        Key Terms Analysis
      </h3>
      <div className="h-64 w-full">
        <ReactWordcloud words={wordCloudData} options={options} />
      </div>
      <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
        Word size indicates term relevance in the bill text
      </p>
    </div>
  );
};

export default KeyTermsCloud; 