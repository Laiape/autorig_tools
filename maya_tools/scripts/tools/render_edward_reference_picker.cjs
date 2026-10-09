// Render the native SVG picker layout and vector controller exports with sharp.
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
const root = path.resolve(__dirname, '../../..');
const output = path.join(root, 'maya_tools/assets/Edward/picker/reference_workflow');
function files(folder) {
  return fs.readdirSync(folder, {withFileTypes: true}).flatMap(entry => {
    const name = path.join(folder, entry.name);
    return entry.isDirectory() ? files(name) : name.endsWith('.svg') ? [name] : [];
  });
}
(async () => {
  const inputs = files(output);
  // Bounded batches keep SVG image decoding memory predictable.
  for (let i = 0; i < inputs.length; i += 8) {
    await Promise.all(inputs.slice(i, i + 8).map(file => {
      const density = file === path.join(output, 'backgrounds/face.svg') ? 144 : 72;
      return sharp(file, {density}).png().toFile(file.replace(/\.svg$/, '.png'));
    }));
  }
  console.log(JSON.stringify({rendered: inputs.length, output}));
})().catch(error => { console.error(error); process.exit(1); });
