import React, { useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { FaTimes, FaHome, FaFileAlt, FaSearch, FaStar, FaChartBar, FaCog } from 'react-icons/fa';
import { useUserPreferences } from '../../context/UserPreferencesContext';

const Sidebar = ({ isOpen, closeSidebar }) => {
  const location = useLocation();
  const { preferences } = useUserPreferences();
  
  // Close sidebar on route change on mobile
  useEffect(() => {
    if (window.innerWidth < 768) {
      closeSidebar();
    }
  }, [location.pathname, closeSidebar]);
  
  // Close sidebar when clicking outside on mobile
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (isOpen && window.innerWidth < 768 && !e.target.closest('.sidebar')) {
        closeSidebar();
      }
    };
    
    document.addEventListener('mousedown', handleOutsideClick);
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
    };
  }, [isOpen, closeSidebar]);
  
  // Apply theme based on user preferences
  const themeClass = preferences.theme === 'dark' 
    ? 'bg-gray-800 text-white' 
    : 'bg-white text-gray-800';
  
  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-20 md:hidden"
          onClick={closeSidebar}
        />
      )}
      
      {/* Sidebar */}
      <aside 
        className={`sidebar fixed top-0 left-0 z-30 h-full w-64 transform transition-transform duration-300 ease-in-out ${themeClass} shadow-lg ${
          isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        } ${preferences.theme === 'dark' ? 'border-r border-gray-700' : 'border-r border-gray-200'}`}
      >
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-xl font-bold">LegisTrack</h2>
          <button 
            onClick={closeSidebar}
            className="md:hidden text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            <FaTimes />
          </button>
        </div>
        
        <nav className="p-4">
          <ul className="space-y-2">
            <li>
              <NavLink to="/" icon={<FaHome />} label="Dashboard" />
            </li>
            <li>
              <NavLink to="/bills" icon={<FaFileAlt />} label="Bills" />
            </li>
            <li>
              <NavLink to="/search" icon={<FaSearch />} label="Advanced Search" />
            </li>
            <li>
              <NavLink to="/favorites" icon={<FaStar />} label="Favorites" />
            </li>
            <li>
              <NavLink to="/analysis" icon={<FaChartBar />} label="Analysis" />
            </li>
            <li>
              <NavLink to="/preferences" icon={<FaCog />} label="Preferences" />
            </li>
          </ul>
        </nav>
        
        {/* Favorite Topics Section */}
        {preferences.favoriteTopics.length > 0 && (
          <div className="mt-6 p-4 border-t border-gray-200 dark:border-gray-700">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
              Favorite Topics
            </h3>
            <ul className="space-y-1">
              {preferences.favoriteTopics.map(topic => (
                <li key={topic}>
                  <Link 
                    to={`/search?topic=${encodeURIComponent(topic)}`}
                    className="block px-3 py-2 rounded-md text-sm hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    {topic}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </aside>
    </>
  );
};

// Helper component for navigation links
const NavLink = ({ to, icon, label }) => {
  const location = useLocation();
  const isActive = location.pathname === to;
  
  return (
    <Link 
      to={to}
      className={`flex items-center px-3 py-2 rounded-md transition-colors ${
        isActive 
          ? 'bg-blue-600 text-white' 
          : 'hover:bg-gray-100 dark:hover:bg-gray-700'
      }`}
    >
      <span className="mr-3">{icon}</span>
      <span>{label}</span>
    </Link>
  );
};

export default Sidebar; 