/**
 * Copy JS vendor assets from node_modules to static/js
 * Run with: npm run build:js
 */
const fs = require('fs');
const path = require('path');

const assets = [
  { src: 'node_modules/alpinejs/dist/cdn.min.js', dest: 'static/js/alpine.min.js' },
  { src: 'node_modules/htmx.org/dist/htmx.min.js', dest: 'static/js/htmx.min.js' },
  { src: 'node_modules/flowbite/dist/flowbite.min.js', dest: 'static/js/flowbite.min.js' },
];

// Ensure output directory exists
const outDir = path.join(__dirname, '..', 'static', 'js');
if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

assets.forEach(({ src, dest }) => {
  const srcPath = path.join(__dirname, '..', src);
  const destPath = path.join(__dirname, '..', dest);
  fs.copyFileSync(srcPath, destPath);
  const size = (fs.statSync(destPath).size / 1024).toFixed(1);
  console.log(`  ${dest} (${size} KB)`);
});

console.log('Assets copied successfully.');
