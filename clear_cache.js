
// Script to remove stale WebSocket connections and clear cache
console.log('Clearing WebSocket connections and cache...');

// This will be executed in the browser console when needed
function clearWsConnections() {
  // Close any existing WebSocket connections
  const wsKeys = Object.keys(window).filter(key => 
    key.startsWith('ws') || 
    (window[key] && window[key] instanceof WebSocket)
  );
  
  wsKeys.forEach(key => {
    try {
      if (window[key] && window[key].close) {
        window[key].close();
        console.log(`Closed WebSocket: ${key}`);
      }
    } catch (e) {
      console.error(`Error closing ${key}:`, e);
    }
  });
  
  // Clear cache if supported
  if (window.caches) {
    caches.keys().then(names => {
      names.forEach(name => {
        caches.delete(name);
        console.log(`Deleted cache: ${name}`);
      });
    });
  }
  
  console.log('WebSocket connections and cache cleared');
  
  // Reload the page after a brief delay
  setTimeout(() => {
    window.location.reload();
  }, 500);
}

// Export the function so it can be used in the browser console
if (typeof window !== 'undefined') {
  window.clearWsConnections = clearWsConnections;
}
