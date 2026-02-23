import type { Metadata } from 'next';
import { GoogleOAuthProvider } from '@react-oauth/google';
import './globals.css';
import { ThemeProvider } from '@/components/ThemeProvider';

export const metadata: Metadata = {
    title: 'WealthTracker - 跨平台資產管理系統',
    description: '追蹤台股、美股、加密貨幣，即時淨值計算與資產配置分析',
};

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '';

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="zh-Hant">
            <head>
                <link
                    href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap"
                    rel="stylesheet"
                />
            </head>
            <body>
                <ThemeProvider>
                    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
                        {children}
                    </GoogleOAuthProvider>
                </ThemeProvider>
            </body>
        </html>
    );
}
