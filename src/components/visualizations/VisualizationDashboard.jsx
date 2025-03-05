import React, { useState } from 'react';
import BillTimeline from './BillTimeline';
import KeyTermsCloud from './KeyTermsCloud';
import ComparativeAnalysis from './ComparativeAnalysis';
import StakeholderNetwork from './StakeholderNetwork';
import { Tab } from '@headlessui/react';

/**
 * Visualization Dashboard Component
 * 
 * A tabbed interface that organizes and displays various data visualizations
 * related to bill analysis
 * 
 * @param {Object} bill - The bill data
 * @param {Object} analysis - The bill analysis data
 * @param {Array} similarBills - Array of similar bills for comparison
 */
const VisualizationDashboard = ({ bill, analysis, similarBills = [] }) => {
  const [selectedTab, setSelectedTab] = useState(0);
  
  const tabs = [
    { name: 'Timeline', component: <BillTimeline bill={bill} /> },
    { name: 'Key Terms', component: <KeyTermsCloud analysis={analysis} /> },
    { name: 'Comparative Analysis', component: <ComparativeAnalysis similarBills={similarBills} currentBill={bill} /> },
    { name: 'Stakeholder Network', component: <StakeholderNetwork analysis={analysis} /> }
  ];

  return (
    <div className="visualization-dashboard mt-6">
      <h2 className="text-xl font-bold mb-4 text-gray-800 dark:text-gray-200">
        Bill Analysis Visualizations
      </h2>
      
      <Tab.Group selectedIndex={selectedTab} onChange={setSelectedTab}>
        <Tab.List className="flex space-x-1 rounded-xl bg-blue-100 dark:bg-gray-700 p-1">
          {tabs.map((tab) => (
            <Tab
              key={tab.name}
              className={({ selected }) =>
                `w-full rounded-lg py-2.5 text-sm font-medium leading-5 transition-all duration-200
                 ${
                   selected
                     ? 'bg-white dark:bg-gray-800 shadow text-blue-700 dark:text-blue-400'
                     : 'text-gray-700 dark:text-gray-300 hover:bg-white/[0.12] hover:text-blue-600'
                 }`
              }
            >
              {tab.name}
            </Tab>
          ))}
        </Tab.List>
        <Tab.Panels className="mt-2">
          {tabs.map((tab, idx) => (
            <Tab.Panel
              key={idx}
              className={`rounded-xl bg-white dark:bg-gray-800 p-3 shadow-md`}
            >
              {tab.component}
            </Tab.Panel>
          ))}
        </Tab.Panels>
      </Tab.Group>
    </div>
  );
};

export default VisualizationDashboard; 