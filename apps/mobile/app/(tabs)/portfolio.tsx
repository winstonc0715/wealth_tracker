/**
 * 投資組合 Tab
 */

import React from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { usePortfolioStore } from '@/stores/portfolio-store';

export default function PortfolioTab() {
    const { portfolios, selectedPortfolio, selectPortfolio } = usePortfolioStore();

    return (
        <ScrollView style={styles.container}>
            <Text style={styles.title}>投資組合</Text>

            {portfolios.map((portfolio) => (
                <TouchableOpacity
                    key={portfolio.id}
                    style={[
                        styles.portfolioCard,
                        selectedPortfolio?.id === portfolio.id && styles.portfolioCardActive,
                    ]}
                    onPress={() => selectPortfolio(portfolio)}
                >
                    <View style={styles.portfolioHeader}>
                        <Ionicons name="briefcase" size={20} color="#6366f1" />
                        <Text style={styles.portfolioName}>{portfolio.name}</Text>
                    </View>
                    {portfolio.description && (
                        <Text style={styles.portfolioDesc}>{portfolio.description}</Text>
                    )}
                    <Text style={styles.portfolioCurrency}>
                        基準幣別: {portfolio.base_currency}
                    </Text>
                </TouchableOpacity>
            ))}

            {portfolios.length === 0 && (
                <View style={styles.emptyState}>
                    <Ionicons name="folder-open" size={48} color="#555577" />
                    <Text style={styles.emptyText}>尚無投資組合</Text>
                    <Text style={styles.emptySubtext}>在 Web 端建立你的第一個投資組合</Text>
                </View>
            )}
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
    portfolioCard: {
        backgroundColor: '#16163a',
        borderRadius: 16,
        padding: 20,
        marginBottom: 12,
        borderWidth: 1,
        borderColor: '#2a2a5a',
    },
    portfolioCardActive: {
        borderColor: '#6366f1',
        shadowColor: '#6366f1',
        shadowOffset: { width: 0, height: 0 },
        shadowOpacity: 0.15,
        shadowRadius: 10,
    },
    portfolioHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 10,
        marginBottom: 6,
    },
    portfolioName: {
        color: '#f0f0ff',
        fontSize: 18,
        fontWeight: '600',
    },
    portfolioDesc: {
        color: '#8888aa',
        fontSize: 14,
        marginTop: 4,
    },
    portfolioCurrency: {
        color: '#555577',
        fontSize: 12,
        marginTop: 8,
    },
    emptyState: {
        alignItems: 'center',
        paddingVertical: 60,
    },
    emptyText: {
        color: '#8888aa',
        fontSize: 16,
        marginTop: 12,
    },
    emptySubtext: {
        color: '#555577',
        fontSize: 13,
        marginTop: 4,
    },
});
