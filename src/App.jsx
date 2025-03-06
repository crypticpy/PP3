import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import BillList from './pages/BillList';
import BillDetail from './pages/BillDetail';
import NotFound from './pages/NotFound';
import { UserPreferencesProvider } from './context/UserPreferencesContext';
import { NotificationProvider } from './context/NotificationContext';
import UserPreferences from './pages/UserPreferences';

function App() {
  return (
    <UserPreferencesProvider>
      <NotificationProvider>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="bills" element={<BillList />} />
            <Route path="bills/:billId" element={<BillDetail />} />
            <Route path="preferences" element={<UserPreferences />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </NotificationProvider>
    </UserPreferencesProvider>
  );
}

export default App;