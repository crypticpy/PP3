import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { prepareComparativeData } from '../../services/visualizationService';

/**
 * Comparative Analysis Component
 * 
 * Displays a bar chart comparing the current bill with similar bills
 * 
 * @param {Array} similarBills - Array of similar bills for comparison
 * @param {Object} currentBill - The current bill being viewed
 */
const ComparativeAnalysis = ({ similarBills, currentBill }) => {
  // Combine current bill with similar bills for comparison
  const allBills = currentBill ? [currentBill, ...similarBills] : similarBills;
  const chartData = prepareComparativeData(allBills);
  
  // Custom tooltip to display more information
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white dark:bg-gray-800 p-3 border border-gray-200 dark:border-gray-700 rounded shadow-lg">
          <p className="font-semibold">{data.title}</p>
          <p className="text-sm">Status: <span className="font-medium">{data.status}</span></p>
          <p className="text-sm">Support: <span className="font-medium">{data.support}%</span></p>
          <p className="text-sm">Opposition: <span className="font-medium">{data.opposition}%</span></p>
          <p className="text-sm">Introduced: <span className="font-medium">{data.introduced.toLocaleDateString()}</span></p>
        </div>
      );
    }
    return null;
  };
  
  if (!chartData.length) {
    return (
      <div className="p-4 text-center text-gray-500 dark:text-gray-400">
        No comparative data available.
      </div>
    );
  }

  return (
    <div className="comparative-analysis mt-4 bg-white dark:bg-gray-800 rounded-lg shadow p-4">
      <h3 className="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200">
        Comparative Bill Analysis
      </h3>
      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 20, right: 30, left: 20, bottom: 70 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis 
              dataKey="title" 
              angle={-45} 
              textAnchor="end" 
              height={70} 
              tick={{ fontSize: 12 }}
            />
            <YAxis label={{ value: 'Percentage', angle: -90, position: 'insideLeft' }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <Bar 
              dataKey="support" 
              name="Support" 
              fill="#10b981" 
              radius={[4, 4, 0, 0]} 
              barSize={30}
            />
            <Bar 
              dataKey="opposition" 
              name="Opposition" 
              fill="#ef4444" 
              radius={[4, 4, 0, 0]} 
              barSize={30}
            />
            <Bar 
              dataKey="progress" 
              name="Progress" 
              fill="#3b82f6" 
              radius={[4, 4, 0, 0]} 
              barSize={30}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
        Comparison of current bill (first bar) with similar legislation
      </p>
    </div>
  );
};

export default ComparativeAnalysis; 