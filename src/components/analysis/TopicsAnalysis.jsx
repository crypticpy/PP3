import React from 'react';

function TopicsAnalysis({ topics }) {
  if (!topics || topics.length === 0) {
    return null;
  }

  // Sort topics by relevance score
  const sortedTopics = [...topics].sort((a, b) => b.score - a.score);

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <h3 className="text-lg font-semibold text-primary-800 mb-4">Key Topics</h3>
      
      <div className="space-y-4">
        {sortedTopics.map((topic, index) => (
          <div key={index} className="relative">
            <div className="flex items-center justify-between mb-1">
              <span className="text-secondary-700 font-medium">{topic.name}</span>
              <span className="text-secondary-500 text-sm">{(topic.score * 100).toFixed(0)}%</span>
            </div>
            <div className="w-full bg-secondary-200 rounded-full h-2.5">
              <div 
                className="bg-primary-600 h-2.5 rounded-full" 
                style={{ width: `${topic.score * 100}%` }}
              ></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default TopicsAnalysis; 