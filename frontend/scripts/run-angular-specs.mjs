import { existsSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { spawnSync } from 'node:child_process';

const root = process.cwd();
const searchRoot = join(root, 'src', 'app');
const angularCli = join(root, 'node_modules', '@angular', 'cli', 'bin', 'ng.js');

function collectSpecs(dir, acc = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      collectSpecs(full, acc);
    } else if (entry.endsWith('.spec.ts')) {
      acc.push(full);
    }
  }
  return acc;
}

if (!existsSync(angularCli)) {
  console.error(`Angular CLI local no encontrado: ${angularCli}`);
  console.error('Ejecuta npm ci antes de npm run test:isolated.');
  process.exit(1);
}

const specs = collectSpecs(searchRoot).sort();
if (specs.length === 0) {
  console.error('No Angular specs were found under src/app.');
  process.exit(1);
}

const childEnv = {
  ...process.env,
  NODE_OPTIONS: process.env.NODE_OPTIONS || '--max-old-space-size=4096',
};

for (const [index, spec] of specs.entries()) {
  const include = relative(root, spec).split(sep).join('/');
  console.log(`\n==> Angular principal ${index + 1}/${specs.length} - ${include}`);

  const result = spawnSync(
    process.execPath,
    [
      angularCli,
      'test',
      'frontend',
      '--watch=false',
      `--include=${include}`,
    ],
    {
      cwd: root,
      stdio: 'inherit',
      env: childEnv,
    },
  );

  if (result.error) {
    console.error(`No se pudo iniciar Angular CLI para ${include}: ${result.error.message}`);
    process.exit(1);
  }

  if (result.signal) {
    console.error(`Angular CLI terminó por señal ${result.signal} en ${include}.`);
    process.exit(1);
  }

  if (result.status !== 0) {
    console.error(`Angular spec falló (${result.status ?? 'sin código'}): ${include}`);
    process.exit(result.status ?? 1);
  }
}

console.log(`\nOK: ${specs.length} spec files passed in isolated processes.`);
