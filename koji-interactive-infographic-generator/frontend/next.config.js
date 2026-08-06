/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow loading base64 images from the orchestrator response
  images: {
    dangerouslyAllowSVG: true,
    contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;",
  },
};

module.exports = nextConfig;
