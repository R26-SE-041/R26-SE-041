const { spawn, spawnSync } = require('node:child_process');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const build = spawnSync(process.execPath, [path.join(__dirname, 'build-css.cjs')], {cwd:root, stdio:'inherit'});
if (build.status !== 0) process.exit(build.status ?? 1);
const css = spawn(process.execPath, [require.resolve('tailwindcss/lib/cli.js'), '-i', 'src/styles/globals.css', '-o', 'src/styles/generated.css', '--watch=always'], {cwd:root, stdio:'inherit'});
const expo = spawn(process.execPath, [require.resolve('expo/bin/cli'), 'start', '--web', '--port', process.env.PORT || '3000', ...process.argv.slice(2)], {cwd:root, stdio:'inherit'});
let closing = false;
function close(code) {
  if (closing) return;
  closing = true;
  css.kill();
  expo.kill();
  process.exit(code ?? 0);
}
expo.on('exit', close);
css.on('error', e => {console.error(e);close(1)});
expo.on('error', e => {console.error(e);close(1)});
process.on('SIGINT', () => close(0));
process.on('SIGTERM', () => close(0));
