
import React from 'react';
import { Routes, Route, Link } from 'react-router-dom';
import HealthCheck from './components/HealthCheck';

// Import your existing pages
// You may need to adjust these imports based on your actual file structure
import Dashboard from './pages/Dashboard';
import BillList from './pages/BillList';
import BillDetail from './pages/BillDetail';
import UserPreferences from './pages/UserPreferences';
import SearchPage from './pages/SearchPage';
import NotFound from './pages/NotFound';

function App() {
  return (
    <div className="App">
      <header className="bg-gray-800 text-white py-4 px-6 shadow-md">
        <div className="container mx-auto flex justify-between items-center">
          <h1 className="text-2xl font-bold">Texas Legislative Tracker</h1>
          <nav>
            <ul className="flex space-x-6">
              <li><Link to="/" className="hover:text-blue-300">Dashboard</Link></li>
              <li><Link to="/bills" className="hover:text-blue-300">Bills</Link></li>
              <li><Link to="/search" className="hover:text-blue-300">Search</Link></li>
              <li><Link to="/preferences" className="hover:text-blue-300">Preferences</Link></li>
            </ul>
          </nav>
        </div>
      </header>

      <main className="container mx-auto p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/bills" element={<BillList />} />
          <Route path="/bills/:billId" element={<BillDetail />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/preferences" element={<UserPreferences />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>

      <footer className="bg-gray-200 p-4 mt-10">
        <div className="container mx-auto text-center text-gray-600">
          <p>Texas Legislative Tracker © {new Date().getFullYear()}</p>
          <HealthCheck />
        </div>
      </footer>
    </div>
  );
}

export default App;
