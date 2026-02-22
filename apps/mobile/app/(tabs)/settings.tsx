/**
 * 設定 Tab
 */

import React from 'react';
import {
    View,
    Text,
    ScrollView,
    TouchableOpacity,
    StyleSheet,
    Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import apiClient from '@/lib/api-client';

export default function SettingsTab() {
    const handleLogout = async () => {
        Alert.alert('登出', '確定要登出嗎？', [
            { text: '取消', style: 'cancel' },
            {
                text: '確定',
                style: 'destructive',
                onPress: async () => {
                    await apiClient.clearToken();
                    // 實際應用中會導向登入頁
                    Alert.alert('已登出');
                },
            },
        ]);
    };

    const settingsItems = [
        { icon: 'person-circle', label: '帳戶資料', onPress: () => { } },
        { icon: 'notifications', label: '通知設定', onPress: () => { } },
        { icon: 'cloud-download', label: '匯入對帳單 (CSV)', onPress: () => { } },
        { icon: 'sync', label: '券商同步 (即將推出)', onPress: () => { } },
        { icon: 'color-palette', label: '外觀設定', onPress: () => { } },
        { icon: 'shield-checkmark', label: '安全性', onPress: () => { } },
        { icon: 'help-circle', label: '使用說明', onPress: () => { } },
        { icon: 'information-circle', label: '關於 WealthTracker', onPress: () => { } },
    ];

    return (
        <ScrollView style={styles.container}>
            <Text style={styles.title}>設定</Text>

            <View style={styles.section}>
                {settingsItems.map((item, index) => (
                    <TouchableOpacity
                        key={index}
                        style={[
                            styles.settingItem,
                            index === settingsItems.length - 1 && { borderBottomWidth: 0 },
                        ]}
                        onPress={item.onPress}
                    >
                        <View style={styles.settingLeft}>
                            <Ionicons name={item.icon as any} size={22} color="#6366f1" />
                            <Text style={styles.settingLabel}>{item.label}</Text>
                        </View>
                        <Ionicons name="chevron-forward" size={18} color="#555577" />
                    </TouchableOpacity>
                ))}
            </View>

            {/* 登出按鈕 */}
            <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
                <Ionicons name="log-out" size={20} color="#ef4444" />
                <Text style={styles.logoutText}>登出</Text>
            </TouchableOpacity>

            {/* 版本資訊 */}
            <Text style={styles.version}>WealthTracker v0.1.0</Text>
        </ScrollView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#0a0a1a',
        padding: 16,
    },
    title: {
        color: '#f0f0ff',
        fontSize: 24,
        fontWeight: '800',
        marginBottom: 20,
    },
    section: {
        backgroundColor: '#16163a',
        borderRadius: 16,
        borderWidth: 1,
        borderColor: '#2a2a5a',
        overflow: 'hidden',
    },
    settingItem: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: 16,
        borderBottomWidth: 1,
        borderBottomColor: 'rgba(42, 42, 90, 0.5)',
    },
    settingLeft: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 12,
    },
    settingLabel: {
        color: '#f0f0ff',
        fontSize: 15,
    },
    logoutBtn: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        marginTop: 24,
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        borderRadius: 12,
        padding: 16,
        borderWidth: 1,
        borderColor: 'rgba(239, 68, 68, 0.2)',
    },
    logoutText: {
        color: '#ef4444',
        fontSize: 15,
        fontWeight: '600',
    },
    version: {
        color: '#555577',
        textAlign: 'center',
        marginTop: 24,
        fontSize: 12,
    },
});
