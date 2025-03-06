import React, { useState } from 'react';
import { useUserPreferences } from '../../context/UserPreferencesContext';

const NotificationPreferences = () => {
  const { preferences, updatePreferences } = useUserPreferences();
  
  // Get notification preferences with defaults
  const notificationPrefs = preferences.notifications || {
    billStatusUpdates: true,
    newAnalysisAlerts: true,
    similarBillAlerts: false,
    emailNotifications: false,
    pushNotifications: true
  };
  
  const [formValues, setFormValues] = useState(notificationPrefs);
  
  const handleChange = (e) => {
    const { name, checked } = e.target;
    setFormValues(prev => ({
      ...prev,
      [name]: checked
    }));
  };
  
  const handleSubmit = (e) => {
    e.preventDefault();
    updatePreferences({
      ...preferences,
      notifications: formValues
    });
  };
  
  return (
    <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
      <h2 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
        Notification Preferences
      </h2>
      
      <form onSubmit={handleSubmit}>
        <div className="space-y-4">
          <div className="flex items-start">
            <div className="flex items-center h-5">
              <input
                id="billStatusUpdates"
                name="billStatusUpdates"
                type="checkbox"
                checked={formValues.billStatusUpdates}
                onChange={handleChange}
                className="focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-300 rounded"
              />
            </div>
            <div className="ml-3 text-sm">
              <label htmlFor="billStatusUpdates" className="font-medium text-gray-700 dark:text-gray-200">
                Bill Status Updates
              </label>
              <p className="text-gray-500 dark:text-gray-400">
                Receive notifications when bills you're tracking change status
              </p>
            </div>
          </div>
          
          <div className="flex items-start">
            <div className="flex items-center h-5">
              <input
                id="newAnalysisAlerts"
                name="newAnalysisAlerts"
                type="checkbox"
                checked={formValues.newAnalysisAlerts}
                onChange={handleChange}
                className="focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-300 rounded"
              />
            </div>
            <div className="ml-3 text-sm">
              <label htmlFor="newAnalysisAlerts" className="font-medium text-gray-700 dark:text-gray-200">
                New Analysis Alerts
              </label>
              <p className="text-gray-500 dark:text-gray-400">
                Get notified when new AI analysis is available for bills
              </p>
            </div>
          </div>
          
          <div className="flex items-start">
            <div className="flex items-center h-5">
              <input
                id="similarBillAlerts"
                name="similarBillAlerts"
                type="checkbox"
                checked={formValues.similarBillAlerts}
                onChange={handleChange}
                className="focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-300 rounded"
              />
            </div>
            <div className="ml-3 text-sm">
              <label htmlFor="similarBillAlerts" className="font-medium text-gray-700 dark:text-gray-200">
                Similar Bill Alerts
              </label>
              <p className="text-gray-500 dark:text-gray-400">
                Receive notifications about bills similar to ones you're tracking
              </p>
            </div>
          </div>
          
          <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
            <h3 className="text-md font-medium text-gray-900 dark:text-white mb-3">
              Delivery Methods
            </h3>
            
            <div className="flex items-start">
              <div className="flex items-center h-5">
                <input
                  id="pushNotifications"
                  name="pushNotifications"
                  type="checkbox"
                  checked={formValues.pushNotifications}
                  onChange={handleChange}
                  className="focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-300 rounded"
                />
              </div>
              <div className="ml-3 text-sm">
                <label htmlFor="pushNotifications" className="font-medium text-gray-700 dark:text-gray-200">
                  In-App Notifications
                </label>
                <p className="text-gray-500 dark:text-gray-400">
                  Receive notifications within the application
                </p>
              </div>
            </div>
            
            <div className="flex items-start mt-4">
              <div className="flex items-center h-5">
                <input
                  id="emailNotifications"
                  name="emailNotifications"
                  type="checkbox"
                  checked={formValues.emailNotifications}
                  onChange={handleChange}
                  className="focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-300 rounded"
                />
              </div>
              <div className="ml-3 text-sm">
                <label htmlFor="emailNotifications" className="font-medium text-gray-700 dark:text-gray-200">
                  Email Notifications
                </label>
                <p className="text-gray-500 dark:text-gray-400">
                  Receive notifications via email (requires account)
                </p>
              </div>
            </div>
          </div>
        </div>
        
        <div className="mt-6">
          <button
            type="submit"
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            Save Preferences
          </button>
        </div>
      </form>
    </div>
  );
};

export default NotificationPreferences; 