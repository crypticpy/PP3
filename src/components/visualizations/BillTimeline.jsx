import React from 'react';
import { prepareBillTimelineData } from '../../services/visualizationService';
import { 
  VerticalTimeline, 
  VerticalTimelineElement 
} from 'react-vertical-timeline-component';
import 'react-vertical-timeline-component/style.min.css';
import { FaFlag, FaGavel, FaFileSignature, FaVoteYea } from 'react-icons/fa';

/**
 * Bill Timeline Component
 * 
 * Displays a vertical timeline of a bill's progression through the legislative process
 * 
 * @param {Object} bill - The bill data containing history information
 */
const BillTimeline = ({ bill }) => {
  const timelineData = prepareBillTimelineData(bill);
  
  // Get icon based on action type
  const getIcon = (action) => {
    const actionLower = action.toLowerCase();
    if (actionLower.includes('introduced')) return FaFlag;
    if (actionLower.includes('vote')) return FaVoteYea;
    if (actionLower.includes('signed')) return FaFileSignature;
    return FaGavel;
  };
  
  // Get color based on status
  const getColor = (status) => {
    switch(status) {
      case 'major': return '#3b82f6';
      case 'critical': return '#ef4444';
      case 'success': return '#10b981';
      default: return '#6b7280';
    }
  };
  
  if (!timelineData.length) {
    return (
      <div className="p-4 text-center text-gray-500 dark:text-gray-400">
        No timeline data available for this bill.
      </div>
    );
  }

  return (
    <div className="bill-timeline mt-4">
      <h3 className="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200">
        Bill Progression Timeline
      </h3>
      <VerticalTimeline lineColor="#cbd5e1">
        {timelineData.map((event) => {
          const IconComponent = getIcon(event.title);
          return (
            <VerticalTimelineElement
              key={event.id}
              date={event.date.toLocaleDateString()}
              iconStyle={{ background: getColor(event.status), color: '#fff' }}
              icon={<IconComponent />}
              contentStyle={{ 
                background: 'var(--card-bg, #fff)', 
                color: 'var(--text-color, #1f2937)',
                boxShadow: '0 3px 10px rgba(0, 0, 0, 0.1)',
                borderRadius: '0.5rem'
              }}
              contentArrowStyle={{ borderRight: '7px solid var(--card-bg, #fff)' }}
            >
              <h3 className="font-bold">{event.title}</h3>
              {event.description && (
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  {event.description}
                </p>
              )}
            </VerticalTimelineElement>
          );
        })}
      </VerticalTimeline>
    </div>
  );
};

export default BillTimeline; 