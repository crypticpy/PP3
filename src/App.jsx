import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import './index.css';
import Header from './components/Header';
import Footer from './components/Footer';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import BillList from './pages/BillList';
import BillDetail from './pages/BillDetail';
import UserPreferences from './pages/UserPreferences';
import NotFound from './pages/NotFound';

function App() {
  return (
    <Router>
      <div className="flex flex-col min-h-screen">
        <Header />
        <div className="flex flex-1">
          <Sidebar />
          <main className="flex-1 p-4 overflow-auto">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/bills" element={<BillList />} />
              <Route path="/bills/:id" element={<BillDetail />} />
              <Route path="/preferences" element={<UserPreferences />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </main>
        </div>
        <Footer />
      </div>
    </Router>
  );
}

export default App;