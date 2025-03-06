
import React, { useState } from 'react';
import { Tab } from '@headlessui/react';
import { useUserPreferences } from '../../context/UserPreferencesContext';

// Import visualization components here
// This is a placeholder - you'll need to create or import actual visualization components
const BillTimeline = () => <div>Bill Timeline Visualization</div>;
const KeyTermsCloud = () => <div>Key Terms Word Cloud</div>;
const ComparativeAnalysis = () => <div>Comparative Analysis</div>;
const StakeholderNetwork = () => <div>Stakeholder Network</div>;

const VisualizationDashboard = ({ analysisData }) => {
  const [selectedTab, setSelectedTab] = useState(0);
  const { preferences } = useUserPreferences();
  
  const tabs = [
    { name: 'Timeline', component: <BillTimeline data={analysisData} /> },
    { name: 'Key Terms', component: <KeyTermsCloud data={analysisData} /> },
    { name: 'Comparative', component: <ComparativeAnalysis data={analysisData} /> },
    { name: 'Stakeholders', component: <StakeholderNetwork data={analysisData} /> }
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
