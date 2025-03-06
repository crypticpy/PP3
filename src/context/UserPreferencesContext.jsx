import React, { createContext, useState, useEffect, useContext } from 'react';
import { toast } from 'react-toastify';

// Create context
export const UserPreferencesContext = createContext();

// Default preferences
const defaultPreferences = {
  theme: 'light', // light or dark
  billsPerPage: 10, // number of bills to display per page
  defaultView: 'list', // list or grid
  savedFilters: [], // saved search filters
  favoriteTopics: [], // favorite legislative topics
  notifications: {
    enabled: false,
    billUpdates: true,
    newBills: false,
    frequency: 'daily' // daily, weekly, immediate
  }
};

export const UserPreferencesProvider = ({ children }) => {
  const [preferences, setPreferences] = useState(() => {
    // Try to load preferences from localStorage
    const savedPreferences = localStorage.getItem('userPreferences');
    return savedPreferences ? JSON.parse(savedPreferences) : defaultPreferences;
  });

  // Save preferences to localStorage whenever they change
  useEffect(() => {
    try {
      localStorage.setItem('userPreferences', JSON.stringify(preferences));
    } catch (error) {
      console.error('Failed to save preferences to localStorage:', error);
      toast.error('Failed to save your preferences');
    }
  }, [preferences]);

  // Update a specific preference
  const updatePreference = (key, value) => {
    setPreferences(prev => {
      // Handle nested preferences
      if (typeof key === 'string' && key.includes('.')) {
        const [parentKey, childKey] = key.split('.');
        return {
          ...prev,
          [parentKey]: {
            ...prev[parentKey],
            [childKey]: value
          }
        };
      }
      
      // Handle top-level preferences
      return {
        ...prev,
        [key]: value
      };
    });
    
    toast.success('Preferences updated');
  };

  // Reset preferences to default
  const resetPreferences = () => {
    setPreferences(defaultPreferences);
    toast.info('Preferences reset to default');
  };

  // Add a saved filter
  const addSavedFilter = (filter) => {
    setPreferences(prev => ({
      ...prev,
      savedFilters: [...prev.savedFilters, filter]
    }));
    toast.success('Filter saved');
  };

  // Remove a saved filter
  const removeSavedFilter = (filterId) => {
    setPreferences(prev => ({
      ...prev,
      savedFilters: prev.savedFilters.filter(filter => filter.id !== filterId)
    }));
    toast.info('Filter removed');
  };

  // Toggle a favorite topic
  const toggleFavoriteTopic = (topic) => {
    setPreferences(prev => {
      const topicExists = prev.favoriteTopics.includes(topic);
      return {
        ...prev,
        favoriteTopics: topicExists
          ? prev.favoriteTopics.filter(t => t !== topic)
          : [...prev.favoriteTopics, topic]
      };
    });
  };

  return (
    <UserPreferencesContext.Provider
      value={{
        preferences,
        updatePreference,
        resetPreferences,
        addSavedFilter,
        removeSavedFilter,
        toggleFavoriteTopic
      }}
    >
      {children}
    </UserPreferencesContext.Provider>
  );
};

// Custom hook for using preferences
export const useUserPreferences = () => {
  const context = useContext(UserPreferencesContext);
  if (!context) {
    throw new Error('useUserPreferences must be used within a UserPreferencesProvider');
  }
  return context;
}; 
import React, { createContext, useContext, useState, useEffect } from 'react';

// Default preferences
const defaultPreferences = {
  theme: 'light', // 'light' or 'dark'
  fontSize: 'medium', // 'small', 'medium', or 'large'
  notificationsEnabled: true,
  dataRefreshInterval: 30, // minutes
};

// Create context
const UserPreferencesContext = createContext();

export const UserPreferencesProvider = ({ children }) => {
  // Initialize state from localStorage or use defaults
  const [preferences, setPreferences] = useState(() => {
    const savedPreferences = localStorage.getItem('userPreferences');
    return savedPreferences ? JSON.parse(savedPreferences) : defaultPreferences;
  });

  // Save preferences to localStorage when they change
  useEffect(() => {
    localStorage.setItem('userPreferences', JSON.stringify(preferences));
    
    // Apply theme to body
    if (preferences.theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [preferences]);

  // Update individual preference
  const updatePreference = (key, value) => {
    setPreferences(prev => ({
      ...prev,
      [key]: value
    }));
  };

  // Reset preferences to defaults
  const resetPreferences = () => {
    setPreferences(defaultPreferences);
  };

  return (
    <UserPreferencesContext.Provider value={{ 
      preferences, 
      updatePreference,
      resetPreferences
    }}>
      {children}
    </UserPreferencesContext.Provider>
  );
};

// Custom hook for using preferences
export const useUserPreferences = () => {
  const context = useContext(UserPreferencesContext);
  if (!context) {
    throw new Error('useUserPreferences must be used within a UserPreferencesProvider');
  }
  return context;
};
