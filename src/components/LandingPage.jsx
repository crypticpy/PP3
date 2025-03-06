
import React from 'react';
import { Link } from 'react-router-dom';

const LandingPage = () => {
  return (
    <div className="landing-page">
      {/* Hero Section */}
      <section className="hero bg-gradient-to-r from-blue-600 to-indigo-700 text-white py-20">
        <div className="container mx-auto px-6">
          <div className="flex flex-col md:flex-row items-center">
            <div className="md:w-1/2 mb-10 md:mb-0">
              <h1 className="text-4xl md:text-5xl font-bold leading-tight mb-4">
                Track Legislation That Matters
              </h1>
              <p className="text-xl mb-8">
                PolicyPulse provides real-time monitoring and analysis of legislative activities across all states.
              </p>
              <div className="flex flex-col sm:flex-row space-y-4 sm:space-y-0 sm:space-x-4">
                <Link to="/dashboard" className="bg-white text-blue-700 hover:bg-blue-50 font-semibold py-3 px-8 rounded-lg transition duration-300">
                  Get Started
                </Link>
                <Link to="/status" className="bg-transparent border-2 border-white hover:bg-white hover:text-blue-700 text-white font-semibold py-3 px-8 rounded-lg transition duration-300">
                  View API Status
                </Link>
              </div>
            </div>
            <div className="md:w-1/2">
              <img 
                src="https://images.unsplash.com/photo-1575517111839-3a3843ee7f5d?q=80&w=2670&auto=format&fit=crop" 
                alt="Legislature Building" 
                className="rounded-lg shadow-xl"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="features py-20 bg-gray-50">
        <div className="container mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-12">Key Features</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="feature-card bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition duration-300">
              <div className="text-blue-600 text-4xl mb-4">📊</div>
              <h3 className="text-xl font-bold mb-2">Real-time Monitoring</h3>
              <p className="text-gray-600">
                Track bills and legislative activities across all 50 states with real-time updates and notifications.
              </p>
            </div>
            
            <div className="feature-card bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition duration-300">
              <div className="text-blue-600 text-4xl mb-4">🔍</div>
              <h3 className="text-xl font-bold mb-2">Advanced Search</h3>
              <p className="text-gray-600">
                Use powerful filters and search capabilities to find relevant legislation quickly.
              </p>
            </div>
            
            <div className="feature-card bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition duration-300">
              <div className="text-blue-600 text-4xl mb-4">📱</div>
              <h3 className="text-xl font-bold mb-2">Custom Alerts</h3>
              <p className="text-gray-600">
                Receive customized notifications when bills of interest move through the legislative process.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Call to Action */}
      <section className="cta py-16 bg-blue-700 text-white">
        <div className="container mx-auto px-6 text-center">
          <h2 className="text-3xl font-bold mb-4">Ready to get started?</h2>
          <p className="text-xl mb-8 max-w-2xl mx-auto">
            Join thousands of policy professionals who rely on PolicyPulse for their legislative tracking needs.
          </p>
          <Link to="/dashboard" className="bg-white text-blue-700 hover:bg-blue-50 font-semibold py-3 px-8 rounded-lg transition duration-300 inline-block">
            Explore the Dashboard
          </Link>
        </div>
      </section>
    </div>
  );
};

export default LandingPage;
