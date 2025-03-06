
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Paths to clean
const cacheDirs = [
  '.vite',
  'node_modules/.vite'
];

console.log('Clearing Vite cache directories...');
cacheDirs.forEach(dir => {
  const fullPath = path.join(__dirname, dir);
  if (fs.existsSync(fullPath)) {
    console.log(`Removing ${dir}...`);
    try {
      if (process.platform === 'win32') {
        execSync(`rmdir /s /q "${fullPath}"`);
      } else {
        execSync(`rm -rf "${fullPath}"`);
      }
      console.log(`Successfully removed ${dir}`);
    } catch (err) {
      console.error(`Error removing ${dir}:`, err);
    }
  } else {
    console.log(`${dir} does not exist, skipping`);
  }
});

console.log('Cache clearing complete!');
