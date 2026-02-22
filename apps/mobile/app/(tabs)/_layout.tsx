/**
 * Bottom Tab Navigation Layout
 *
 * 四個 Tab：總覽、投資組合、新增交易、設定
 */

import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

export default function TabLayout() {
    return (
        <Tabs
            screenOptions={{
                headerStyle: {
                    backgroundColor: '#0a0a1a',
                    borderBottomColor: '#2a2a5a',
                    borderBottomWidth: 1,
                },
                headerTintColor: '#f0f0ff',
                headerTitleStyle: { fontWeight: '700' },
                tabBarStyle: {
                    backgroundColor: '#111128',
                    borderTopColor: '#2a2a5a',
                    borderTopWidth: 1,
                    paddingBottom: 8,
                    paddingTop: 8,
                    height: 85,
                },
                tabBarActiveTintColor: '#6366f1',
                tabBarInactiveTintColor: '#555577',
                tabBarLabelStyle: {
                    fontSize: 11,
                    fontWeight: '600',
                },
            }}
        >
            <Tabs.Screen
                name="index"
                options={{
                    title: '總覽',
                    headerTitle: 'WealthTracker',
                    tabBarIcon: ({ color, size }) => (
                        <Ionicons name="pie-chart" size={size} color={color} />
                    ),
                }}
            />
            <Tabs.Screen
                name="portfolio"
                options={{
                    title: '投資組合',
                    tabBarIcon: ({ color, size }) => (
                        <Ionicons name="briefcase" size={size} color={color} />
                    ),
                }}
            />
            <Tabs.Screen
                name="add-transaction"
                options={{
                    title: '新增交易',
                    tabBarIcon: ({ color, size }) => (
                        <Ionicons name="add-circle" size={28} color={color} />
                    ),
                }}
            />
            <Tabs.Screen
                name="settings"
                options={{
                    title: '設定',
                    tabBarIcon: ({ color, size }) => (
                        <Ionicons name="settings" size={size} color={color} />
                    ),
                }}
            />
        </Tabs>
    );
}
