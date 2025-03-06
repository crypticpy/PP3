
import React, { useEffect, useRef } from 'react';
import Chart from 'chart.js/auto';
import { prepareImpactData } from '../../services/visualizationService';

const ImpactChart = ({ impactData }) => {
  const chartRef = useRef(null);
  const chartInstance = useRef(null);

  useEffect(() => {
    if (!impactData) return;
    
    const formattedData = prepareImpactData(impactData);
    
    if (chartInstance.current) {
      chartInstance.current.destroy();
    }
    
    const ctx = chartRef.current.getContext('2d');
    
    chartInstance.current = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: formattedData.categories,
        datasets: [{
          label: 'Impact Score',
          data: formattedData.values,
          backgroundColor: [
            'rgba(75, 192, 192, 0.6)',
            'rgba(54, 162, 235, 0.6)',
            'rgba(153, 102, 255, 0.6)',
            'rgba(255, 159, 64, 0.6)',
            'rgba(255, 99, 132, 0.6)',
          ],
          borderColor: [
            'rgba(75, 192, 192, 1)',
            'rgba(54, 162, 235, 1)',
            'rgba(153, 102, 255, 1)',
            'rgba(255, 159, 64, 1)',
            'rgba(255, 99, 132, 1)',
          ],
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            position: 'top',
          },
          title: {
            display: true,
            text: 'Stakeholder Impact Analysis'
          },
          tooltip: {
            callbacks: {
              label: function(context) {
                return `Impact: ${context.raw}`;
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            title: {
              display: true,
              text: 'Impact Level'
            }
          },
          x: {
            title: {
              display: true,
              text: 'Stakeholder Category'
            }
          }
        }
      }
    });
    
    return () => {
      if (chartInstance.current) {
        chartInstance.current.destroy();
      }
    };
  }, [impactData]);

  return (
    <div className="bg-white p-4 rounded-lg shadow-md">
      <h3 className="text-lg font-semibold mb-4">Impact Analysis</h3>
      <div className="aspect-w-16 aspect-h-9">
        <canvas ref={chartRef} />
      </div>
      {!impactData && (
        <div className="text-center py-4 text-gray-500">
          No impact data available
        </div>
      )}
    </div>
  );
};

export default ImpactChart;
