import React, { createContext, useContext, useReducer, useEffect } from 'react';

// Initial state
const initialState = {
  notifications: [],
  unreadCount: 0,
  isLoading: false,
  error: null,
};

// Action types
const ACTIONS = {
  FETCH_NOTIFICATIONS_START: 'FETCH_NOTIFICATIONS_START',
  FETCH_NOTIFICATIONS_SUCCESS: 'FETCH_NOTIFICATIONS_SUCCESS',
  FETCH_NOTIFICATIONS_ERROR: 'FETCH_NOTIFICATIONS_ERROR',
  ADD_NOTIFICATION: 'ADD_NOTIFICATION',
  MARK_AS_READ: 'MARK_AS_READ',
  MARK_ALL_AS_READ: 'MARK_ALL_AS_READ',
  DELETE_NOTIFICATION: 'DELETE_NOTIFICATION',
  CLEAR_ALL_NOTIFICATIONS: 'CLEAR_ALL_NOTIFICATIONS',
};

// Reducer function
function notificationReducer(state, action) {
  switch (action.type) {
    case ACTIONS.FETCH_NOTIFICATIONS_START:
      return { ...state, isLoading: true, error: null };
    case ACTIONS.FETCH_NOTIFICATIONS_SUCCESS:
      return {
        ...state,
        notifications: action.payload,
        unreadCount: action.payload.filter(n => !n.read).length,
        isLoading: false,
      };
    case ACTIONS.FETCH_NOTIFICATIONS_ERROR:
      return { ...state, isLoading: false, error: action.payload };
    case ACTIONS.ADD_NOTIFICATION:
      return {
        ...state,
        notifications: [action.payload, ...state.notifications],
        unreadCount: state.unreadCount + 1,
      };
    case ACTIONS.MARK_AS_READ:
      return {
        ...state,
        notifications: state.notifications.map(notification =>
          notification.id === action.payload
            ? { ...notification, read: true }
            : notification
        ),
        unreadCount: state.unreadCount - 1 < 0 ? 0 : state.unreadCount - 1,
      };
    case ACTIONS.MARK_ALL_AS_READ:
      return {
        ...state,
        notifications: state.notifications.map(notification => ({
          ...notification,
          read: true,
        })),
        unreadCount: 0,
      };
    case ACTIONS.DELETE_NOTIFICATION:
      const deletedNotification = state.notifications.find(
        n => n.id === action.payload
      );
      const unreadAdjustment = deletedNotification && !deletedNotification.read ? 1 : 0;
      return {
        ...state,
        notifications: state.notifications.filter(
          notification => notification.id !== action.payload
        ),
        unreadCount: state.unreadCount - unreadAdjustment < 0 ? 0 : state.unreadCount - unreadAdjustment,
      };
    case ACTIONS.CLEAR_ALL_NOTIFICATIONS:
      return {
        ...state,
        notifications: [],
        unreadCount: 0,
      };
    default:
      return state;
  }
}

// Create context
const NotificationContext = createContext();

// Provider component
export function NotificationProvider({ children }) {
  const [state, dispatch] = useReducer(notificationReducer, initialState);

  // Mock function to fetch notifications - will be replaced with actual API call
  const fetchNotifications = async () => {
    dispatch({ type: ACTIONS.FETCH_NOTIFICATIONS_START });
    try {
      // Mock data - replace with actual API call
      const mockNotifications = [
        {
          id: '1',
          title: 'Bill Status Update',
          message: 'HB 123 has moved to committee review',
          timestamp: new Date().toISOString(),
          read: false,
          type: 'status',
          billId: '123',
        },
        {
          id: '2',
          title: 'New Analysis Available',
          message: 'AI analysis for SB 456 is now available',
          timestamp: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
          read: true,
          type: 'analysis',
          billId: '456',
        },
      ];
      
      dispatch({
        type: ACTIONS.FETCH_NOTIFICATIONS_SUCCESS,
        payload: mockNotifications,
      });
    } catch (error) {
      console.error('Error fetching notifications:', error);
      dispatch({
        type: ACTIONS.FETCH_NOTIFICATIONS_ERROR,
        payload: error.message,
      });
    }
  };

  // Add a new notification
  const addNotification = (notification) => {
    const newNotification = {
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
      read: false,
      ...notification,
    };
    
    dispatch({ type: ACTIONS.ADD_NOTIFICATION, payload: newNotification });
  };

  // Mark a notification as read
  const markAsRead = (id) => {
    dispatch({ type: ACTIONS.MARK_AS_READ, payload: id });
  };

  // Mark all notifications as read
  const markAllAsRead = () => {
    dispatch({ type: ACTIONS.MARK_ALL_AS_READ });
  };

  // Delete a notification
  const deleteNotification = (id) => {
    dispatch({ type: ACTIONS.DELETE_NOTIFICATION, payload: id });
  };

  // Clear all notifications
  const clearAllNotifications = () => {
    dispatch({ type: ACTIONS.CLEAR_ALL_NOTIFICATIONS });
  };

  // Load notifications on mount
  useEffect(() => {
    fetchNotifications();
    
    // Set up polling for new notifications (every 5 minutes)
    const intervalId = setInterval(() => {
      fetchNotifications();
    }, 5 * 60 * 1000);
    
    return () => clearInterval(intervalId);
  }, []);

  // Value to be provided to consumers
  const value = {
    notifications: state.notifications,
    unreadCount: state.unreadCount,
    isLoading: state.isLoading,
    error: state.error,
    fetchNotifications,
    addNotification,
    markAsRead,
    markAllAsRead,
    deleteNotification,
    clearAllNotifications,
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
}

// Custom hook for using the notification context
export function useNotifications() {
  const context = useContext(NotificationContext);
  if (context === undefined) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
} 
import React, { createContext, useContext, useState, useEffect } from 'react';

// Sample mock notifications for development
const mockNotifications = [
  {
    id: 1,
    title: 'Bill HB 123 Updated',
    message: 'The status has changed to "In Committee"',
    timestamp: new Date(Date.now() - 3600000).toISOString(),
    read: false,
    type: 'update'
  },
  {
    id: 2,
    title: 'New Analysis Available',
    message: 'AI analysis completed for SB 456',
    timestamp: new Date(Date.now() - 86400000).toISOString(),
    read: true,
    type: 'analysis'
  },
  {
    id: 3,
    title: 'Similar Bill Detected',
    message: 'SB 789 is similar to bills you are tracking',
    timestamp: new Date(Date.now() - 172800000).toISOString(),
    read: false,
    type: 'similarity'
  }
];

const NotificationContext = createContext();

export const NotificationProvider = ({ children }) => {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // In production, this would fetch from the API
    // For now, we'll use mock data
    const fetchNotifications = async () => {
      try {
        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 500));
        setNotifications(mockNotifications);
      } catch (error) {
        console.error('Error fetching notifications:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchNotifications();
  }, []);

  const markAsRead = (id) => {
    setNotifications(prevNotifications =>
      prevNotifications.map(notification =>
        notification.id === id
          ? { ...notification, read: true }
          : notification
      )
    );
  };

  const markAllAsRead = () => {
    setNotifications(prevNotifications =>
      prevNotifications.map(notification => ({
        ...notification,
        read: true
      }))
    );
  };

  const deleteNotification = (id) => {
    setNotifications(prevNotifications =>
      prevNotifications.filter(notification => notification.id !== id)
    );
  };

  const getUnreadCount = () => {
    return notifications.filter(notification => !notification.read).length;
  };

  // For development/testing, add a method to add a notification
  const addNotification = (notification) => {
    const newNotification = {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      read: false,
      ...notification
    };
    setNotifications(prevNotifications => [newNotification, ...prevNotifications]);
  };

  return (
    <NotificationContext.Provider value={{
      notifications,
      loading,
      markAsRead,
      markAllAsRead,
      deleteNotification,
      getUnreadCount,
      addNotification
    }}>
      {children}
    </NotificationContext.Provider>
  );
};

export const useNotifications = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
};
