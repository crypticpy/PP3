import React from 'react';
import { useUserPreferences } from '../context/UserPreferencesContext';
import { FaCog, FaTrash, FaSave, FaUndo, FaBell, FaEye, FaList, FaTh } from 'react-icons/fa';
import NotificationPreferences from '../components/notifications/NotificationPreferences';

const UserPreferences = () => {
  const {
    preferences,
    updatePreference,
    resetPreferences,
    removeSavedFilter
  } = useUserPreferences();

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <div className="flex items-center mb-6">
        <FaCog className="text-blue-600 text-2xl mr-3" />
        <h1 className="text-2xl font-bold text-gray-800">User Preferences</h1>
      </div>

      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4 text-gray-700 border-b pb-2">Display Settings</h2>
        
        <div className="mb-4">
          <label className="block text-gray-700 font-medium mb-2">Theme</label>
          <div className="flex space-x-4">
            <button
              onClick={() => updatePreference('theme', 'light')}
              className={`px-4 py-2 rounded-md ${
                preferences.theme === 'light'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700'
              }`}
            >
              Light
            </button>
            <button
              onClick={() => updatePreference('theme', 'dark')}
              className={`px-4 py-2 rounded-md ${
                preferences.theme === 'dark'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700'
              }`}
            >
              Dark
            </button>
          </div>
        </div>

        <div className="mb-4">
          <label className="block text-gray-700 font-medium mb-2">Bills Per Page</label>
          <select
            value={preferences.billsPerPage}
            onChange={(e) => updatePreference('billsPerPage', Number(e.target.value))}
            className="w-full md:w-1/3 px-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value={5}>5</option>
            <option value={10}>10</option>
            <option value={20}>20</option>
            <option value={50}>50</option>
          </select>
        </div>

        <div className="mb-4">
          <label className="block text-gray-700 font-medium mb-2">Default View</label>
          <div className="flex space-x-4">
            <button
              onClick={() => updatePreference('defaultView', 'list')}
              className={`flex items-center px-4 py-2 rounded-md ${
                preferences.defaultView === 'list'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700'
              }`}
            >
              <FaList className="mr-2" /> List
            </button>
            <button
              onClick={() => updatePreference('defaultView', 'grid')}
              className={`flex items-center px-4 py-2 rounded-md ${
                preferences.defaultView === 'grid'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700'
              }`}
            >
              <FaTh className="mr-2" /> Grid
            </button>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4 text-gray-700 border-b pb-2">
          <div className="flex items-center">
            <FaBell className="mr-2 text-blue-600" />
            Notification Preferences
          </div>
        </h2>
        
        <div className="mb-4">
          <div className="flex items-center mb-4">
            <input
              type="checkbox"
              id="notificationsEnabled"
              checked={preferences.notifications.enabled}
              onChange={(e) => updatePreference('notifications.enabled', e.target.checked)}
              className="h-5 w-5 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <label htmlFor="notificationsEnabled" className="ml-2 block text-gray-700">
              Enable Notifications
            </label>
          </div>
          
          {preferences.notifications.enabled && (
            <div className="pl-7 space-y-3">
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="billUpdates"
                  checked={preferences.notifications.billUpdates}
                  onChange={(e) => updatePreference('notifications.billUpdates', e.target.checked)}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="billUpdates" className="ml-2 block text-gray-700">
                  Bill Status Updates
                </label>
              </div>
              
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="newBills"
                  checked={preferences.notifications.newBills}
                  onChange={(e) => updatePreference('notifications.newBills', e.target.checked)}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="newBills" className="ml-2 block text-gray-700">
                  New Bills Matching Your Interests
                </label>
              </div>
              
              <div className="mt-3">
                <label className="block text-gray-700 text-sm font-medium mb-2">
                  Notification Frequency
                </label>
                <select
                  value={preferences.notifications.frequency}
                  onChange={(e) => updatePreference('notifications.frequency', e.target.value)}
                  className="w-full md:w-1/2 px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="immediate">Immediate</option>
                  <option value="daily">Daily Digest</option>
                  <option value="weekly">Weekly Summary</option>
                </select>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4 text-gray-700 border-b pb-2">
          <div className="flex items-center">
            <FaSave className="mr-2 text-blue-600" />
            Saved Filters
          </div>
        </h2>
        
        {preferences.savedFilters.length > 0 ? (
          <div className="space-y-3">
            {preferences.savedFilters.map((filter) => (
              <div key={filter.id} className="flex justify-between items-center p-3 bg-gray-50 rounded-md">
                <div>
                  <h3 className="font-medium">{filter.name}</h3>
                  <p className="text-sm text-gray-600">
                    {Object.entries(filter.criteria)
                      .filter(([_, value]) => value)
                      .map(([key, value]) => `${key}: ${value}`)
                      .join(', ')}
                  </p>
                </div>
                <button
                  onClick={() => removeSavedFilter(filter.id)}
                  className="text-red-500 hover:text-red-700"
                  aria-label="Remove saved filter"
                >
                  <FaTrash />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 italic">No saved filters yet. Save a search from the bills page to see it here.</p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="md:col-span-2">
          <NotificationPreferences />
        </div>
      </div>

      <div className="flex justify-end space-x-4 mt-6">
        <button
          onClick={resetPreferences}
          className="flex items-center px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
        >
          <FaUndo className="mr-2" /> Reset to Default
        </button>
      </div>
    </div>
  );
};

export default UserPreferences; 