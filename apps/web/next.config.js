/** @type {import('next').NextConfig} */
const nextConfig = {
    // 啟用嚴格模式
    reactStrictMode: true,

    // 環境變數
    env: {
        NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || '/api',
    },

    // 代理 API 請求到後端
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: 'http://127.0.0.1:8000/api/:path*', // Proxy to Backend
            },
        ]
    },

    // 路由重新導向
    async redirects() {
        return [
            {
                source: '/login',
                destination: '/',
                permanent: true,
            },
        ]
    },
};

module.exports = nextConfig;
