import React from 'react';

function SentimentAnalysis({ sentiment }) {
  if (!sentiment) {
    return null;
  }
  
  // Calculate percentage for the gauge
  const sentimentScore = sentiment.score || 0;
  const percentage = ((sentimentScore + 1) / 2) * 100; // Convert -1 to 1 range to 0 to 100
  
  // Determine color based on sentiment
  const getColor = () => {
    if (sentimentScore < -0.3) return 'text-red-500';
    if (sentimentScore > 0.3) return 'text-green-500';
    return 'text-yellow-500';
  };
  
  const getSentimentLabel = () => {
    if (sentimentScore < -0.3) return 'Negative';
    if (sentimentScore > 0.3) return 'Positive';
    return 'Neutral';
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <h3 className="text-lg font-semibold text-primary-800 mb-4">Sentiment Analysis</h3>
      
      <div className="flex items-center justify-center mb-4">
        <div className="relative w-48 h-24">
          {/* Gauge background */}
          <div className="absolute w-full h-full bg-secondary-100 rounded-t-full"></div>
          
          {/* Gauge fill */}
          <div 
            className={`absolute bottom-0 rounded-t-full ${getColor()}`} 
            style={{ 
              width: '100%', 
              height: `${percentage}%`,
              opacity: 0.3
            }}
          ></div>
          
          {/* Gauge needle */}
          <div 
            className="absolute bottom-0 left-1/2 w-1 bg-secondary-800 transform -translate-x-1/2 origin-bottom"
            style={{ 
              height: '90%', 
              transform: `translateX(-50%) rotate(${(percentage - 50) * 1.8}deg)`
            }}
          ></div>
          
          {/* Gauge center point */}
          <div className="absolute bottom-0 left-1/2 w-3 h-3 bg-secondary-800 rounded-full transform -translate-x-1/2"></div>
        </div>
      </div>
      
      <div className="text-center">
        <span className={`text-xl font-bold ${getColor()}`}>
          {getSentimentLabel()}
        </span>
        <p className="text-secondary-600 mt-1">
          Score: {sentimentScore.toFixed(2)}
        </p>
      </div>
      
      {sentiment.explanation && (
        <div className="mt-4 p-3 bg-secondary-50 rounded-lg">
          <p className="text-sm text-secondary-700">{sentiment.explanation}</p>
        </div>
      )}
    </div>
  );
}

export default SentimentAnalysis; 