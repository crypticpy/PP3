import React from 'react';
import { Link } from 'react-router-dom';

function Header() {
  return (
    <header className="bg-primary-700 text-white shadow-md">
      <div className="container mx-auto px-4 py-3 flex justify-between items-center">
        <Link to="/" className="text-xl font-bold">LegiScan Tracker</Link>
        <nav className="hidden md:block">
          <ul className="flex space-x-6">
            <li><Link to="/" className="hover:text-primary-200">Dashboard</Link></li>
            <li><Link to="/bills" className="hover:text-primary-200">Bills</Link></li>
          </ul>
        </nav>
        <div className="flex items-center space-x-4">
          <button className="btn btn-secondary text-sm">Search</button>
        </div>
      </div>
    </header>
  );
}

export default Header; 