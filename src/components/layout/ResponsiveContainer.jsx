import React from 'react';
import { useUserPreferences } from '../../context/UserPreferencesContext';

const ResponsiveContainer = ({ children, className = '' }) => {
  const { preferences } = useUserPreferences();
  
  // Apply theme class based on user preferences
  const themeClass = preferences.theme === 'dark' ? 'bg-gray-900 text-white' : 'bg-gray-50 text-gray-900';
  
  return (
    <div className={`w-full transition-colors ${themeClass} ${className}`}>
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        {children}
      </div>
    </div>
  );
};

export default ResponsiveContainer; 