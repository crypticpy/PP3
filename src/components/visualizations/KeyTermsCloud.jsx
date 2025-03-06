
import React, { useState, useEffect } from 'react';
import WordCloud from 'react-d3-cloud';
import { prepareWordCloudData } from '../../services/visualizationService';

const KeyTermsCloud = ({ analysisData, height = 300, width = 500 }) => {
  const [wordCloudData, setWordCloudData] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (analysisData) {
      try {
        const data = prepareWordCloudData(analysisData);
        setWordCloudData(data);
      } catch (error) {
        console.error('Error preparing word cloud data:', error);
      } finally {
        setIsLoading(false);
      }
    }
  }, [analysisData]);

  // Custom font size calculator
  const fontSizeMapper = word => Math.log2(word.value) * 5 + 16;
  
  // Custom rotation
  const rotate = word => (word.value % 2) * 90;

  if (isLoading) {
    return <div className="flex justify-center items-center h-64">Loading key terms...</div>;
  }

  if (!wordCloudData || wordCloudData.length === 0) {
    return (
      <div className="flex justify-center items-center h-64 text-gray-500">
        No key terms data available
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-4 h-full">
      <h3 className="text-lg font-semibold mb-4">Key Terms</h3>
      <div className="h-[300px] w-full">
        <WordCloud
          data={wordCloudData}
          width={width}
          height={height}
          font="Impact"
          fontSizeMapper={fontSizeMapper}
          rotate={rotate}
          padding={2}
        />
      </div>
    </div>
  );
};

export default KeyTermsCloud;
