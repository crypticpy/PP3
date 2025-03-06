
import React, { useEffect, useRef } from 'react';
import Chart from 'chart.js/auto';
import { prepareImpactData } from '../../services/visualizationService';

const ImpactChart = ({ impactData }) => {
  const chartRef = useRef(null);
  const chartInstance = useRef(null);

  useEffect(() => {
    if (!impactData) return;

    const { labels, values } = prepareImpactData(impactData);
    
    if (!labels || !values || labels.length === 0) {
      return;
    }

    // Clean up previous chart instance
    if (chartInstance.current) {
      chartInstance.current.destroy();
    }

    // Create new chart
    const ctx = chartRef.current.getContext('2d');
    chartInstance.current = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Impact Score',
            data: values,
            backgroundColor: 'rgba(54, 162, 235, 0.6)',
            borderColor: 'rgba(54, 162, 235, 1)',
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            beginAtZero: true,
            title: {
              display: true,
              text: 'Impact Score',
            },
          },
          x: {
            title: {
              display: true,
              text: 'Impact Areas',
            },
          },
        },
        plugins: {
          title: {
            display: true,
            text: 'Legislative Impact Assessment',
            font: {
              size: 16,
            },
          },
          legend: {
            display: false,
          },
          tooltip: {
            callbacks: {
              label: (context) => {
                return `Impact: ${context.parsed.y}`;
              },
            },
          },
        },
      },
    });

    // Clean up on unmount
    return () => {
      if (chartInstance.current) {
        chartInstance.current.destroy();
      }
    };
  }, [impactData]);

  return (
    <div className="impact-chart-container" style={{ height: '300px', width: '100%' }}>
      {!impactData ? (
        <div className="flex justify-center items-center h-full">
          <p className="text-gray-500">No impact data available</p>
        </div>
      ) : (
        <canvas ref={chartRef} />
      )}
    </div>
  );
};

export default ImpactChart;
