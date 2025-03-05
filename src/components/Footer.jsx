import React from 'react';

function Footer() {
  return (
    <footer className="bg-secondary-800 text-white py-6">
      <div className="container mx-auto px-4">
        <div className="flex flex-col md:flex-row justify-between items-center">
          <div className="mb-4 md:mb-0">
            <p className="text-sm">&copy; {new Date().getFullYear()} LegiScan Tracker. All rights reserved.</p>
          </div>
          <div>
            <ul className="flex space-x-4">
              <li><a href="#" className="text-sm hover:text-primary-300">Privacy Policy</a></li>
              <li><a href="#" className="text-sm hover:text-primary-300">Terms of Service</a></li>
              <li><a href="#" className="text-sm hover:text-primary-300">Contact</a></li>
            </ul>
          </div>
        </div>
      </div>
    </footer>
  );
}

export default Footer; 