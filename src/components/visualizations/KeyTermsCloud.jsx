import React from 'react';
import Cloud from 'react-d3-cloud';
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

  // Transform data if needed - react-d3-cloud expects { text, value } format
  const formattedData = wordCloudData.map(item => ({
    text: item.text,
    value: item.value || item.weight || 1 // Adjust based on your data structure
  }));

  const fontSizeMapper = word => Math.log2(word.value) * 5 + 12; // Scale font size (12-60)

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
        <Cloud
          data={formattedData}
          fontSizeMapper={fontSizeMapper}
          fill={d => {
            // Rotating through your color palette
            const colors = ['#3b82f6', '#60a5fa', '#93c5fd', '#2563eb', '#1d4ed8'];
            return colors[Math.floor(Math.random() * colors.length)];
          }}
          rotate={(word) => (word.value % 2) * 90} // Alternate between 0 and 90 degrees
          padding={2}
          font="Inter, sans-serif"
          width={500} // Set width of SVG
          height={250} // Set height of SVG
        />
      </div>
      <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
        Word size indicates term relevance in the bill text
      </p>
    </div>
  );
};

export default KeyTermsCloud;