
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

console.log('Clearing Vite cache directories...');

// Clear .vite cache directory if it exists
const viteDir = path.join(__dirname, '.vite');
if (fs.existsSync(viteDir)) {
  console.log(`Removing ${viteDir}...`);
  fs.rmSync(viteDir, { recursive: true, force: true });
  console.log(`Successfully removed ${viteDir}`);
} else {
  console.log('.vite does not exist, skipping');
}

// Clear node_modules/.vite cache if it exists
const nodeModulesVite = path.join(__dirname, 'node_modules', '.vite');
if (fs.existsSync(nodeModulesVite)) {
  console.log(`Removing node_modules/.vite...`);
  fs.rmSync(nodeModulesVite, { recursive: true, force: true });
  console.log(`Successfully removed node_modules/.vite`);
} else {
  console.log('node_modules/.vite does not exist, skipping');
}

// Clean node_modules cache for React-related packages
try {
  console.log('Cleaning npm cache for React packages...');
  execSync('npm cache clean --force react react-dom react-router-dom');
  console.log('React cache cleaned');
} catch (error) {
  console.log('Error cleaning npm cache:', error.message);
}

console.log('Cache clearing complete!');
