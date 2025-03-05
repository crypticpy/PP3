import { FaCog } from 'react-icons/fa';
import { useUserPreferences } from '../../context/UserPreferencesContext';
import NotificationCenter from '../notifications/NotificationCenter';

const Header = () => {
  const { preferences } = useUserPreferences();
  
  return (
    <header className="bg-white shadow-md">
      <div className="container mx-auto px-4 py-3 flex justify-between items-center">
        <div className="flex items-center space-x-4">
          <NotificationCenter />
          <Link 
            to="/preferences" 
            className="text-gray-600 hover:text-blue-600 transition-colors"
            aria-label="User Preferences"
          >
            <FaCog className="text-xl" />
          </Link>
        </div>
      </div>
    </header>
  );
};

export default Header; 