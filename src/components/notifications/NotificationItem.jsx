import React from 'react';
import { format } from 'date-fns';
import { useNotifications } from '../../contexts/NotificationContext';
import { Link } from 'react-router-dom';
import { 
  BellIcon, 
  DocumentTextIcon, 
  ChartBarIcon, 
  XMarkIcon,
  EyeIcon
} from '@heroicons/react/24/outline';

const NotificationItem = ({ notification }) => {
  const { markAsRead, deleteNotification } = useNotifications();
  
  // Get icon based on notification type
  const getIcon = () => {
    switch (notification.type) {
      case 'status':
        return <DocumentTextIcon className="h-5 w-5 text-blue-500" />;
      case 'analysis':
        return <ChartBarIcon className="h-5 w-5 text-purple-500" />;
      default:
        return <BellIcon className="h-5 w-5 text-gray-500" />;
    }
  };
  
  // Format timestamp
  const formattedTime = format(new Date(notification.timestamp), 'MMM d, yyyy h:mm a');
  
  return (
    <div className={`p-4 border-b ${notification.read ? 'bg-white dark:bg-gray-800' : 'bg-blue-50 dark:bg-gray-700'}`}>
      <div className="flex items-start">
        <div className="flex-shrink-0 mr-3">
          {getIcon()}
        </div>
        <div className="flex-grow">
          <div className="flex justify-between items-start">
            <h4 className="text-sm font-medium text-gray-900 dark:text-white">
              {notification.title}
            </h4>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {formattedTime}
            </span>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
            {notification.message}
          </p>
          <div className="mt-2 flex space-x-2">
            {notification.billId && (
              <Link 
                to={`/bills/${notification.billId}`}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
              >
                View Bill
              </Link>
            )}
            {!notification.read && (
              <button
                onClick={() => markAsRead(notification.id)}
                className="text-xs text-gray-600 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 flex items-center"
              >
                <EyeIcon className="h-3 w-3 mr-1" />
                Mark as read
              </button>
            )}
          </div>
        </div>
        <button
          onClick={() => deleteNotification(notification.id)}
          className="ml-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
          aria-label="Delete notification"
        >
          <XMarkIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

export default NotificationItem; 