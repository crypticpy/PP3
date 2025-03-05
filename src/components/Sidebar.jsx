import React from 'react';
import { Link } from 'react-router-dom';

function Sidebar() {
  return (
    <aside className="w-64 bg-white shadow-md hidden md:block">
      <div className="p-4">
        <h2 className="text-lg font-semibold mb-4 text-primary-700">Navigation</h2>
        <nav>
          <ul className="space-y-2">
            <li>
              <Link 
                to="/" 
                className="block px-4 py-2 rounded hover:bg-primary-50 hover:text-primary-700"
              >
                Dashboard
              </Link>
            </li>
            <li>
              <Link 
                to="/bills" 
                className="block px-4 py-2 rounded hover:bg-primary-50 hover:text-primary-700"
              >
                Bills
              </Link>
            </li>
          </ul>
        </nav>
      </div>
    </aside>
  );
}

export default Sidebar; 