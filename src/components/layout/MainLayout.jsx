import React from 'react';
import Header from './Header';
import Footer from './Footer';
import Sidebar from './Sidebar';
import ResponsiveContainer from './ResponsiveContainer';
import { useUserPreferences } from '../../context/UserPreferencesContext';

const MainLayout = ({ children }) => {
  const { preferences } = useUserPreferences();
  const [sidebarOpen, setSidebarOpen] = React.useState(false);
  
  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };
  
  return (
    <div className="flex flex-col min-h-screen">
      <Header toggleSidebar={toggleSidebar} />
      
      <div className="flex flex-1">
        <Sidebar isOpen={sidebarOpen} closeSidebar={() => setSidebarOpen(false)} />
        
        <main className={`flex-1 transition-all ${sidebarOpen ? 'md:ml-64' : ''}`}>
          <ResponsiveContainer>
            <div className="py-6">
              {children}
            </div>
          </ResponsiveContainer>
        </main>
      </div>
      
      <Footer />
    </div>
  );
};

export default MainLayout; 