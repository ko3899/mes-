const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');


const jsRoot = path.join(__dirname, '..', 'admin', 'static', 'js');


function collectJavaScriptFiles(directory, files = []) {
  for (const entry of fs.readdirSync(directory, {withFileTypes: true})) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) collectJavaScriptFiles(fullPath, files);
    else if (entry.name.endsWith('.js')) files.push(fullPath);
  }
  return files;
}


test('admin page scripts do not overwrite each other with duplicate global functions', () => {
  const definitions = new Map();
  for (const file of collectJavaScriptFiles(jsRoot)) {
    const source = fs.readFileSync(file, 'utf8');
    for (const match of source.matchAll(/^function\s+([A-Za-z_$][\w$]*)\s*\(/gm)) {
      const line = source.slice(0, match.index).split('\n').length;
      const locations = definitions.get(match[1]) || [];
      locations.push(`${path.relative(jsRoot, file)}:${line}`);
      definitions.set(match[1], locations);
    }
  }
  const duplicates = [...definitions.entries()]
    .filter(([, locations]) => locations.length > 1)
    .map(([name, locations]) => `${name}: ${locations.join(', ')}`);
  assert.deepEqual(duplicates, [], `duplicate global functions:\n${duplicates.join('\n')}`);
});
