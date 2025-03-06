import React from 'react';
import { Link } from 'react-router-dom';

const LandingPage = () => {
  return (
    <div className="landing-page">
      <section className="hero">
        <div className="container mx-auto px-8 py-12 hero-content"> {/* Added padding */}
          <div className="max-w-4xl">
            <h1 className="text-4xl md:text-5xl font-bold leading-tight mb-4 text-white"> {/* Added text-white for contrast */}Track Legislation That Matters</h1>
            <p className="text-xl mb-8 text-gray-200"> {/* Added text-gray-200 for contrast */}
              PolicyPulse provides real-time monitoring and analysis of legislative activities across the White House, U.S. Congress, and Texas, 
              helping policy professionals stay ahead of changes that impact their work.
            </p>
            <div className="flex flex-wrap gap-2">
              <Link to="/dashboard" className="cta-button bg-blue-500 hover:bg-blue-700 text-white"> {/* Added styling for better contrast */}
                Get Started
              </Link>
              <Link to="/status" className="cta-button-secondary bg-gray-300 hover:bg-gray-400 text-gray-800"> {/* Added styling for better contrast */}
                View API Status
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-gray-50 py-12"> {/* Added padding */}
        <div className="container mx-auto px-8"> {/* Added padding */}
          <h2 className="text-3xl font-bold text-center mb-12">Key Features</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="feature-card">
              <div className="feature-icon">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6 text-blue-500"> {/* Added color */}
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-14v7h5v-2h-3V6h-2z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold mb-2 text-gray-800"> {/* Added color */}Real-time Monitoring</h3>
              <p className="text-gray-600">Track legislation from the White House, U.S. Congress, and Texas with real-time updates and notifications.</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6 text-blue-500"> {/* Added color */}
                  <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold mb-2 text-gray-800"> {/* Added color */}Advanced Search</h3>
              <p className="text-gray-600">Use powerful filters and search capabilities to find relevant legislation quickly and efficiently.</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6 text-blue-500"> {/* Added color */}
                  <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2zm-2 1H8v-6c0-2.48 1.51-4.5 4-4.5s4 2.02 4 4.5v6z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold mb-2 text-gray-800"> {/* Added color */}Custom Alerts</h3>
              <p className="text-gray-600">Receive customized notifications when bills of interest move through the legislative process.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-12"> {/* Added padding */}
        <div className="container mx-auto px-8 text-center"> {/* Added padding */}
          <h2 className="text-3xl font-bold mb-6 text-gray-800"> {/* Added color */}Ready to get started?</h2>
          <p className="text-lg text-gray-600 mb-8 max-w-2xl mx-auto">
            Join thousands of policy professionals who rely on PolicyPulse for their legislative tracking needs.
          </p>
          <Link to="/dashboard" className="cta-button bg-blue-500 hover:bg-blue-700 text-white"> {/* Added styling for better contrast */}
            Explore the Dashboard
          </Link>
        </div>
      </section>
    </div>
  );
};

export default LandingPage;