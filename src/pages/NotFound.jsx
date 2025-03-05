import React from 'react';
import { Link } from 'react-router-dom';

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center h-full py-16">
      <h1 className="text-6xl font-bold text-primary-700 mb-4">404</h1>
      <p className="text-2xl mb-8">Page not found</p>
      <p className="mb-8 text-center max-w-md">
        The page you are looking for might have been removed, had its name changed, 
        or is temporarily unavailable.
      </p>
      <Link to="/" className="btn btn-primary">
        Return to Dashboard
      </Link>
    </div>
  );
}

export default NotFound; 