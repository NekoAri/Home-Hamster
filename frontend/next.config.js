/** @type {import('next').NextConfig} */
const nextConfig = {
  // 代理后端 API 请求，避免前端跨域问题
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
