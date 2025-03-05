import React from 'react';

function StakeholderImpact({ stakeholders }) {
  if (!stakeholders || stakeholders.length === 0) {
    return null;
  }

  // Group stakeholders by impact type
  const groupedStakeholders = stakeholders.reduce((acc, stakeholder) => {
    const impact = stakeholder.impact || 'neutral';
    if (!acc[impact]) {
      acc[impact] = [];
    }
    acc[impact].push(stakeholder);
    return acc;
  }, {});

  const renderStakeholderGroup = (title, stakeholders, colorClass) => {
    if (!stakeholders || stakeholders.length === 0) return null;
    
    return (
      <div className={`p-4 rounded-lg ${colorClass}`}>
        <h4 className="font-medium mb-2">{title}</h4>
        <ul className="list-disc pl-5 space-y-1">
          {stakeholders.map((stakeholder, index) => (
            <li key={index} className="text-secondary-700">
              <span className="font-medium">{stakeholder.name}</span>
              {stakeholder.reason && (
                <span className="text-sm"> - {stakeholder.reason}</span>
              )}
            </li>
          ))}
        </ul>
      </div>
    );
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <h3 className="text-lg font-semibold text-primary-800 mb-4">Stakeholder Impact Analysis</h3>
      
      <div className="space-y-4">
        {renderStakeholderGroup(
          'Positively Impacted', 
          groupedStakeholders.positive, 
          'bg-green-50 border-l-4 border-green-500'
        )}
        
        {renderStakeholderGroup(
          'Negatively Impacted', 
          groupedStakeholders.negative, 
          'bg-red-50 border-l-4 border-red-500'
        )}
        
        {renderStakeholderGroup(
          'Mixed or Neutral Impact', 
          groupedStakeholders.neutral, 
          'bg-yellow-50 border-l-4 border-yellow-500'
        )}
      </div>
    </div>
  );
}

export default StakeholderImpact; 