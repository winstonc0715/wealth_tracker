/**
 * 新增交易 Tab
 */

import React, { useState, useEffect } from 'react';
import {
    View,
    Text,
    ScrollView,
    TextInput,
    TouchableOpacity,
    StyleSheet,
    Alert,
    ActivityIndicator,
} from 'react-native';
import apiClient, { SearchResult } from '@/lib/api-client';
import { usePortfolioStore } from '@/stores/portfolio-store';

const TX_TYPES = [
    { key: 'buy', label: '買入', icon: '📈' },
    { key: 'sell', label: '賣出', icon: '📉' },
    { key: 'dividend', label: '配息', icon: '💰' },
    { key: 'deposit', label: '存入', icon: '💵' },
    { key: 'withdraw', label: '提出', icon: '💳' },
];

const CATEGORIES = [
    { id: 1, label: '台股', icon: '🇹🇼' },
    { id: 2, label: '美股', icon: '🇺🇸' },
    { id: 3, label: '加密貨幣', icon: '₿' },
    { id: 4, label: '法幣', icon: '💵' },
    { id: 5, label: '負債', icon: '💳' },
];

export default function AddTransactionTab() {
    const { selectedPortfolio, refreshAll } = usePortfolioStore();
    const [txType, setTxType] = useState('buy');
    const [categoryId, setCategoryId] = useState(1);
    const [symbol, setSymbol] = useState('');
    const [assetName, setAssetName] = useState('');
    const [quantity, setQuantity] = useState('');
    const [unitPrice, setUnitPrice] = useState('');
    const [fee, setFee] = useState('0');
    const [loading, setLoading] = useState(false);
    const [currency, setCurrency] = useState('TWD');
    const [isSearching, setIsSearching] = useState(false);
    const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
    const [showSuggestions, setShowSuggestions] = useState(false);

    // 即時搜尋邏輯
    useEffect(() => {
        if (!symbol.trim()) {
            setSearchResults([]);
            return;
        }

        const category = CATEGORIES.find(c => c.id === categoryId);
        const categorySlug = category?.id === 1 ? 'tw_stock' : category?.id === 2 ? 'us_stock' : category?.id === 3 ? 'crypto' : '';

        if (!categorySlug) return;

        const timer = setTimeout(async () => {
            setIsSearching(true);
            try {
                const res = await apiClient.searchSymbols(symbol.trim(), categorySlug);
                setSearchResults(res.data || []);
                setShowSuggestions(true);
            } catch (err) {
                console.error("搜尋失敗", err);
            } finally {
                setIsSearching(false);
            }
        }, 500);

        return () => clearTimeout(timer);
    }, [symbol, categoryId]);

    const handleSubmit = async () => {
        if (!selectedPortfolio) {
            Alert.alert('錯誤', '請先選擇投資組合');
            return;
        }
        if (!symbol || !quantity || !unitPrice) {
            Alert.alert('錯誤', '請填寫必要欄位');
            return;
        }

        setLoading(true);
        try {
            await apiClient.createTransaction({
                portfolio_id: selectedPortfolio.id,
                category_id: categoryId,
                symbol: symbol.toUpperCase(),
                asset_name: assetName || undefined,
                tx_type: txType,
                quantity: parseFloat(quantity),
                unit_price: parseFloat(unitPrice),
                fee: parseFloat(fee || '0'),
                currency: currency,
                executed_at: new Date().toISOString(),
            });

            Alert.alert('成功', '交易已新增');
            // 重置表單
            setSymbol('');
            setAssetName('');
            setQuantity('');
            setUnitPrice('');
            setFee('0');
            // 重新整理持倉
            await refreshAll();
        } catch (error) {
            Alert.alert('錯誤', (error as Error).message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <ScrollView style={styles.container}>
            <Text style={styles.title}>新增交易</Text>

            {/* 交易類型 */}
            <Text style={styles.label}>交易類型</Text>
            <View style={styles.chipRow}>
                {TX_TYPES.map((type) => (
                    <TouchableOpacity
                        key={type.key}
                        style={[styles.chip, txType === type.key && styles.chipActive]}
                        onPress={() => setTxType(type.key)}
                    >
                        <Text style={styles.chipIcon}>{type.icon}</Text>
                        <Text style={[styles.chipText, txType === type.key && styles.chipTextActive]}>
                            {type.label}
                        </Text>
                    </TouchableOpacity>
                ))}
            </View>

            {/* 資產類別 */}
            <Text style={styles.label}>資產類別</Text>
            <View style={styles.chipRow}>
                {CATEGORIES.map((cat) => (
                    <TouchableOpacity
                        key={cat.id}
                        style={[styles.chip, categoryId === cat.id && styles.chipActive]}
                        onPress={() => setCategoryId(cat.id)}
                    >
                        <Text style={styles.chipIcon}>{cat.icon}</Text>
                        <Text style={[styles.chipText, categoryId === cat.id && styles.chipTextActive]}>
                            {cat.label}
                        </Text>
                    </TouchableOpacity>
                ))}
            </View>

            {/* 輸入欄位 */}
            <Text style={styles.label}>標的代碼 *</Text>
            <View style={{ zIndex: 10 }}>
                <TextInput
                    style={styles.input}
                    placeholder="如 2330, AAPL, BTC"
                    placeholderTextColor="#555577"
                    value={symbol}
                    onChangeText={setSymbol}
                    autoCapitalize="characters"
                    onFocus={() => setShowSuggestions(true)}
                />

                {showSuggestions && (searchResults.length > 0 || isSearching) && (
                    <View style={styles.suggestions}>
                        {isSearching ? (
                            <ActivityIndicator style={{ padding: 12 }} color="#6366f1" />
                        ) : (
                            searchResults.map((item) => (
                                <TouchableOpacity
                                    key={item.symbol}
                                    style={styles.suggestionItem}
                                    onPress={() => {
                                        setSymbol(item.symbol);
                                        setAssetName(item.name);
                                        if (item.currency) setCurrency(item.currency);
                                        setShowSuggestions(false);
                                    }}
                                >
                                    <View>
                                        <Text style={styles.suggestSymbol}>{item.symbol}</Text>
                                        <Text style={styles.suggestName}>{item.name}</Text>
                                    </View>
                                    <Text style={styles.suggestMeta}>{item.type_box} {item.exchange}</Text>
                                </TouchableOpacity>
                            ))
                        )}
                    </View>
                )}
            </View>

            <Text style={styles.label}>標的名稱</Text>
            <TextInput
                style={styles.input}
                placeholder="如 台積電, Apple"
                placeholderTextColor="#555577"
                value={assetName}
                onChangeText={setAssetName}
                onFocus={() => setShowSuggestions(false)}
            />

            <View style={styles.row}>
                <View style={styles.halfField}>
                    <Text style={styles.label}>數量 *</Text>
                    <TextInput
                        style={styles.input}
                        placeholder="0"
                        placeholderTextColor="#555577"
                        value={quantity}
                        onChangeText={setQuantity}
                        keyboardType="decimal-pad"
                    />
                </View>
                <View style={styles.halfField}>
                    <Text style={styles.label}>單價 *</Text>
                    <TextInput
                        style={styles.input}
                        placeholder="0.00"
                        placeholderTextColor="#555577"
                        value={unitPrice}
                        onChangeText={setUnitPrice}
                        keyboardType="decimal-pad"
                    />
                </View>
            </View>

            <Text style={styles.label}>手續費</Text>
            <TextInput
                style={styles.input}
                placeholder="0"
                placeholderTextColor="#555577"
                value={fee}
                onChangeText={setFee}
                keyboardType="decimal-pad"
            />

            {/* 金額預覽 */}
            {quantity && unitPrice && (
                <View style={styles.previewCard}>
                    <Text style={styles.previewLabel}>交易總額</Text>
                    <Text style={styles.previewValue}>
                        {currency} {(parseFloat(quantity) * parseFloat(unitPrice) + parseFloat(fee || '0')).toLocaleString()}
                    </Text>
                </View>
            )}

            {/* 送出按鈕 */}
            <TouchableOpacity
                style={[styles.submitBtn, loading && styles.submitBtnDisabled]}
                onPress={handleSubmit}
                disabled={loading}
            >
                <Text style={styles.submitBtnText}>
                    {loading ? '處理中...' : '確認新增'}
                </Text>
            </TouchableOpacity>

            <View style={{ height: 32 }} />
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
    label: {
        color: '#8888aa',
        fontSize: 13,
        fontWeight: '600',
        marginBottom: 8,
        marginTop: 16,
    },
    chipRow: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: 8,
    },
    chip: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 4,
        paddingHorizontal: 14,
        paddingVertical: 8,
        borderRadius: 10,
        backgroundColor: '#16163a',
        borderWidth: 1,
        borderColor: '#2a2a5a',
    },
    chipActive: {
        backgroundColor: 'rgba(99, 102, 241, 0.15)',
        borderColor: '#6366f1',
    },
    chipIcon: {
        fontSize: 14,
    },
    chipText: {
        color: '#8888aa',
        fontSize: 13,
        fontWeight: '600',
    },
    chipTextActive: {
        color: '#6366f1',
    },
    input: {
        backgroundColor: '#111128',
        borderWidth: 1,
        borderColor: '#2a2a5a',
        borderRadius: 10,
        padding: 14,
        color: '#f0f0ff',
        fontSize: 15,
    },
    row: {
        flexDirection: 'row',
        gap: 12,
    },
    halfField: {
        flex: 1,
    },
    previewCard: {
        backgroundColor: '#16163a',
        borderRadius: 12,
        padding: 16,
        marginTop: 20,
        borderWidth: 1,
        borderColor: '#2a2a5a',
        alignItems: 'center',
    },
    previewLabel: {
        color: '#8888aa',
        fontSize: 13,
    },
    previewValue: {
        color: '#f0f0ff',
        fontSize: 24,
        fontWeight: '700',
        marginTop: 4,
        fontVariant: ['tabular-nums'],
    },
    submitBtn: {
        backgroundColor: '#6366f1',
        borderRadius: 12,
        padding: 16,
        alignItems: 'center',
        marginTop: 24,
    },
    submitBtnDisabled: {
        opacity: 0.6,
    },
    submitBtnText: {
        color: 'white',
        fontSize: 16,
        fontWeight: '700',
    },
    suggestions: {
        position: 'absolute',
        top: '100%',
        left: 0,
        right: 0,
        backgroundColor: '#1c1c3d',
        borderRadius: 10,
        marginTop: 4,
        borderWidth: 1,
        borderColor: '#3a3a7a',
        maxHeight: 200,
        elevation: 5,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
    },
    suggestionItem: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: 12,
        borderBottomWidth: 1,
        borderBottomColor: '#2a2a5a',
    },
    suggestSymbol: {
        color: '#f0f0ff',
        fontWeight: '700',
        fontSize: 14,
    },
    suggestName: {
        color: '#8888aa',
        fontSize: 12,
    },
    suggestMeta: {
        color: '#555577',
        fontSize: 11,
        backgroundColor: '#111128',
        paddingHorizontal: 6,
        paddingVertical: 2,
        borderRadius: 4,
    },
});
