const apiUrl = process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/+$/, "");
let validHttpsOrigin = false;
try {
  const url = new URL(apiUrl);
  validHttpsOrigin = url.protocol === "https:" && url.pathname === "/" &&
    !url.username && !url.password && !url.search && !url.hash;
} catch {}
if (process.env.VERCEL && !validHttpsOrigin) {
  throw new Error("Set NEXT_PUBLIC_API_URL to the EC2 API HTTPS origin in Vercel before building.");
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: apiUrl || "http://localhost:8000",
  },
};

// Keep development's Turbopack files separate from production's Webpack files.
// Running a build while the dev server is open must not replace its runtime.
export default (phase) => ({
  ...nextConfig,
  distDir: phase === "phase-development-server" ? ".next/dev" : process.env.VERCEL ? ".next" : ".next/build",
});
