
import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const ImpactChart = ({ impactData }) => {
  // If no data is provided, use sample data
  const data = impactData || [
    { area: 'Public Health', impact: 85 },
    { area: 'Local Government', impact: 62 },
    { area: 'Education', impact: 45 },
    { area: 'Infrastructure', impact: 30 },
    { area: 'Healthcare Costs', impact: 70 },
  ];

  // Color mapping based on impact value
  const getBarColor = (value) => {
    if (value >= 70) return '#ef4444'; // high impact - red
    if (value >= 40) return '#f59e0b'; // medium impact - amber
    return '#3b82f6'; // low impact - blue
  };

  return (
    <div className="impact-chart">
      <h3 className="text-lg font-medium mb-4">Impact Analysis by Area</h3>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} />
            <XAxis type="number" domain={[0, 100]} />
            <YAxis type="category" dataKey="area" width={80} />
            <Tooltip 
              formatter={(value) => [`${value} Impact Score`, 'Impact']}
              labelFormatter={(value) => `Area: ${value}`}
            />
            <Legend />
            <Bar 
              dataKey="impact" 
              name="Impact Score" 
              radius={[0, 4, 4, 0]}
              // Use different colors based on impact value
              fill="#3b82f6"
              cellRenderer={(props) => {
                const { x, y, width, height, value } = props;
                return (
                  <rect
                    x={x}
                    y={y}
                    width={width}
                    height={height}
                    fill={getBarColor(value)}
                  />
                );
              }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="text-xs text-gray-500 mt-2">
        <span className="inline-block w-3 h-3 bg-red-500 mr-1"></span> High Impact (70-100)
        <span className="inline-block w-3 h-3 bg-amber-500 mx-1 ml-3"></span> Medium Impact (40-69)
        <span className="inline-block w-3 h-3 bg-blue-500 mx-1 ml-3"></span> Low Impact (0-39)
      </div>
    </div>
  );
};

export default ImpactChart;
