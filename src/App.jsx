
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
import HealthCheck from './components/HealthCheck';

function App() {
  return (
    <UserPreferencesProvider>
      <NotificationProvider>
        <div className="App">
          <header className="bg-blue-600 text-white p-4">
            <h1 className="text-2xl font-bold">PolicyPulse</h1>
            <p>Texas Legislative Analysis Platform</p>
          </header>

          <main className="container mx-auto p-4">
            <HealthCheck />
            <Routes>
              <Route path="/" element={<Layout />}>
                <Route index element={<Dashboard />} />
                <Route path="bills" element={<BillList />} />
                <Route path="bills/:billId" element={<BillDetail />} />
                <Route path="preferences" element={<UserPreferences />} />
                <Route path="*" element={<NotFound />} />
              </Route>
            </Routes>
          </main>
        </div>
      </NotificationProvider>
    </UserPreferencesProvider>
  );
}

export default App;
