
import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const ImpactChart = ({ data }) => {
  // Default data if none is provided
  const defaultData = [
    { name: 'Public Health', impact: 65 },
    { name: 'Local Government', impact: 45 },
    { name: 'Economic', impact: 30 },
    { name: 'Environmental', impact: 25 },
    { name: 'Social', impact: 40 }
  ];

  const chartData = data || defaultData;

  return (
    <div className="impact-chart-container">
      <h3 className="text-lg font-medium mb-2">Impact Assessment</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis domain={[0, 100]} />
            <Tooltip />
            <Legend />
            <Bar dataKey="impact" fill="#8884d8" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default ImpactChart;
