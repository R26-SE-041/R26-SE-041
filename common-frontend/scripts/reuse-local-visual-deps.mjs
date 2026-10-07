// Offline fallback for this workspace. Copies only missing installed packages
// from the original visual frontend; never modifies its files or dependency tree.
import { cpSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
const root = resolve(import.meta.dirname, '..');
const source = resolve(root, '../koji-interactive-infographic-generator/frontend');
const packagePath = resolve(root, 'package.json');
const pkg = JSON.parse(readFileSync(packagePath, 'utf8'));
const original = JSON.parse(readFileSync(resolve(source, 'package-lock.json'), 'utf8'));
const lock = JSON.parse(readFileSync(resolve(root, 'package-lock.json'), 'utf8'));
const deps = { '@react-three/drei': '^10.7.8', '@react-three/fiber': '^9.7.0', three: '^0.185.1', 'react-native-svg': '15.15.4', 'expo-status-bar': '~57.0.1' };
const seen = new Set();
function copy(name) {
  if (seen.has(name)) return; seen.add(name);
  const from = resolve(source, 'node_modules', name), to = resolve(root, 'node_modules', name);
  if (!existsSync(from)) { if (existsSync(to)) return; throw new Error(`Missing local dependency: ${name}`); }
  if (existsSync(to)) return;
  cpSync(from, to, { recursive: true });
  const metadata = JSON.parse(readFileSync(resolve(from, 'package.json'), 'utf8'));
  for (const [path, entry] of Object.entries(original.packages)) if (path === `node_modules/${name}` || path.startsWith(`node_modules/${name}/node_modules/`)) lock.packages[path] = entry;
  for (const dependency of Object.keys(metadata.dependencies || {})) copy(dependency);
  for (const dependency of Object.keys(metadata.peerDependencies || {})) if (!metadata.peerDependenciesMeta?.[dependency]?.optional) copy(dependency);
}
for (const name of [...Object.keys(deps), '@types/three']) copy(name);
pkg.dependencies = { ...pkg.dependencies, ...deps };
pkg.devDependencies['@types/three'] = '^0.183.1';
lock.packages[''].dependencies = pkg.dependencies;
lock.packages[''].devDependencies = pkg.devDependencies;
writeFileSync(packagePath, JSON.stringify(pkg, null, 2) + '\n');
writeFileSync(resolve(root, 'package-lock.json'), JSON.stringify(lock, null, 2) + '\n');
console.log(`Reused installed visualization dependencies (${seen.size} packages inspected).`);
