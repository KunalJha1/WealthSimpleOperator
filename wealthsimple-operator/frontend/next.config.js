/** @type {import('next').NextConfig} */
const backendOrigin = process.env.OPERATOR_BACKEND_ORIGIN || "http://127.0.0.1:8001";

const nextConfig = {
  reactStrictMode: true,
  devIndicators: {
    buildActivity: false,
    buildActivityPosition: 'bottom-right',
    autoOrigin: false,
  },
  onDemandEntries: {
    maxInactiveAge: 60 * 1000,
    pagesBufferLength: 5,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendOrigin}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;

