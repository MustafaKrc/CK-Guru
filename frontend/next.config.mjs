/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    // Example: ignore during build if you have it configured
    ignoreDuringBuilds: true,
  },
  typescript: {
    // Example: ignore build errors if you have it configured
    ignoreBuildErrors: true,
  },
  images: {
    // Example: remote patterns if you have them configured
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'example.com',
        port: '',
        pathname: '/images/**',
      },
    ],
  },

  output: 'standalone', // Add this line
};

export default nextConfig;
