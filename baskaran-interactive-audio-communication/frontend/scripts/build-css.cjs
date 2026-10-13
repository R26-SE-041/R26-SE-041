const { spawnSync } = require('node:child_process');
const path = require('node:path');
const result = spawnSync(process.execPath, [require.resolve('tailwindcss/lib/cli.js'), '-i', 'src/styles/globals.css', '-o', 'src/styles/generated.css', '--minify'], {cwd:path.resolve(__dirname, '..'), stdio:'inherit'});
if (result.error) throw result.error;
process.exit(result.status ?? 1);
