'use client';

/**
 * 總覽儀表板 (Dashboard)
 *
 * 頂部統計卡片 + 淨值走勢圖 + 資產配置圓餅圖 + 持倉明細表格 + 新增交易 Modal
 */

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import apiClient, { SearchResult } from '@/lib/api-client';
import type { PositionDetail } from '@/lib/api-client';
import { usePortfolioStore } from '@/stores/portfolio-store';
import NetWorthChart from '@/components/charts/NetWorthChart';
import AllocationPie from '@/components/charts/AllocationPie';
import PositionTable, { CATEGORY_IDS } from '@/components/tables/PositionTable';
import SettingsModal from '@/components/SettingsModal';

// 交易類型
const TX_TYPES = [
    { key: 'buy', label: '買入', icon: '📈' },
    { key: 'sell', label: '賣出', icon: '📉' },
    { key: 'dividend', label: '配息', icon: '💰' },
    { key: 'deposit', label: '存入', icon: '💵' },
    { key: 'withdraw', label: '提出', icon: '💳' },
];

// 資產類別
const CATEGORIES = [
    { id: 1, label: '台股', icon: '🇹🇼', slug: 'tw_stock' },
    { id: 2, label: '美股', icon: '🇺🇸', slug: 'us_stock' },
    { id: 3, label: '加密貨幣', icon: '₿', slug: 'crypto' },
    { id: 4, label: '法幣', icon: '💵', slug: 'fiat' },
    { id: 5, label: '負債', icon: '💳', slug: 'liability' },
];

export default function DashboardPage() {
    const router = useRouter();
    const {
        portfolios, selectedPortfolio, summary, allocations, history,
        isLoading, displayCurrency, exchangeRate,
        fetchPortfolios, refreshAll, setDisplayCurrency
    } = usePortfolioStore();
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [showTxModal, setShowTxModal] = useState(false);
    const [showSettings, setShowSettings] = useState(false);
    const [newPortfolioName, setNewPortfolioName] = useState('');

    // 交易表單狀態
    const [txType, setTxType] = useState('buy');
    const [categoryId, setCategoryId] = useState(1);
    const [symbol, setSymbol] = useState('');
    const [assetName, setAssetName] = useState('');
    const [quantity, setQuantity] = useState('');
    const [unitPrice, setUnitPrice] = useState('');
    const [totalCost, setTotalCost] = useState('');
    const [currency, setCurrency] = useState('TWD');
    const [txDate, setTxDate] = useState(new Date().toISOString().slice(0, 16));
    const [txNote, setTxNote] = useState('');
    const [txLoading, setTxLoading] = useState(false);
    const [txError, setTxError] = useState('');
    const [txSuccess, setTxSuccess] = useState('');

    // Autocomplete 狀態
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
    const [isSearching, setIsSearching] = useState(false);

    // Debounce search effect
    useEffect(() => {
        if (!symbol.trim() || symbol.trim().length === 0) {
            setSearchResults([]);
            return;
        }

        const timer = setTimeout(async () => {
            setIsSearching(true);
            try {
                const res = await apiClient.searchSymbols(symbol.trim(), 'all');
                setSearchResults(res.data || []);
            } catch (err) {
                console.error("搜尋失敗", err);
                setSearchResults([]);
            } finally {
                setIsSearching(false);
            }
        }, 300);

        return () => clearTimeout(timer);
    }, [symbol]);

    useEffect(() => {
        if (!apiClient.isAuthenticated()) {
            router.push('/');
            return;
        }
        fetchPortfolios();

        // 設置定期輪詢機制：每 60 秒刷新一次報價資料
        const pollInterval = setInterval(() => {
            console.log('[WealthTracker] 定期自動刷新報價...');
            refreshAll();
        }, 60000);

        return () => clearInterval(pollInterval);
    }, []);

    const handleCreatePortfolio = async () => {
        if (!newPortfolioName.trim()) return;
        const { createPortfolio } = usePortfolioStore.getState();
        await createPortfolio(newPortfolioName);
        setNewPortfolioName('');
        setShowCreateModal(false);
    };

    // 從持倉表格快速加碼/減碼
    const handleQuickTrade = (position: PositionDetail, action: 'buy' | 'sell') => {
        resetTxForm();
        setTxType(action);
        setCategoryId(CATEGORY_IDS[position.category_slug] || 1);
        setSymbol(position.symbol);
        setAssetName(position.name || '');
        setCurrency(position.currency);
        setUnitPrice(String(Number(position.current_price)));
        setShowTxModal(true);
    };

    const resetTxForm = () => {
        setTxType('buy');
        setCategoryId(1);
        setSymbol('');
        setAssetName('');
        setQuantity('');
        setUnitPrice('');
        setTotalCost('');
        setCurrency('TWD');
        setTxDate(new Date().toISOString().slice(0, 16));
        setTxNote('');
        setTxError('');
        setTxSuccess('');
    };

    const handleAddTransaction = async () => {
        if (!selectedPortfolio) {
            setTxError('請先建立投資組合');
            return;
        }
        if (!symbol.trim() || !quantity || !unitPrice) {
            setTxError('請填寫標的代碼、數量和均價');
            return;
        }

        setTxLoading(true);
        setTxError('');
        setTxSuccess('');

        try {
            await apiClient.createTransaction({
                portfolio_id: selectedPortfolio.id,
                category_id: categoryId,
                symbol: symbol.toUpperCase().trim(),
                asset_name: assetName || undefined,
                tx_type: txType,
                quantity: parseFloat(quantity),
                unit_price: parseFloat(unitPrice),
                fee: 0,
                currency,
                executed_at: new Date(txDate).toISOString(),
                note: txNote || undefined,
            });

            setTxSuccess(`✅ 成功${txType === 'buy' ? '買入' : txType === 'sell' ? '賣出' : '新增'} ${symbol.toUpperCase()}`);
            // 重新整理持倉
            await refreshAll();
            // 2 秒後關閉
            setTimeout(() => {
                setShowTxModal(false);
                resetTxForm();
            }, 1500);
        } catch (err) {
            setTxError((err as Error).message);
        } finally {
            setTxLoading(false);
        }
    };

    const formatCurrency = (value: number) => {
        let num = Number(value || 0);
        if (displayCurrency === 'USD') {
            num = num / exchangeRate;
            return `$ ${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        }
        return `NT$ ${num.toLocaleString('zh-TW', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
    };

    // 預覽金額
    const previewAmount = parseFloat(totalCost || '0');

    const handleQuantityChange = (val: string) => {
        setQuantity(val);
        const q = parseFloat(val);
        const p = parseFloat(unitPrice);
        const t = parseFloat(totalCost);
        if (q > 0) {
            if (unitPrice && !totalCost) setTotalCost((q * p).toString());
            else if (totalCost && !unitPrice) setUnitPrice((t / q).toString());
            else if (unitPrice && totalCost) setTotalCost((q * p).toString());
        }
    };

    const handlePriceChange = (val: string) => {
        setUnitPrice(val);
        const q = parseFloat(quantity);
        const p = parseFloat(val);
        const t = parseFloat(totalCost);
        if (p > 0) {
            if (quantity && !totalCost) setTotalCost((q * p).toString());
            else if (totalCost && !quantity) setQuantity((t / p).toString());
            else if (quantity && totalCost) setTotalCost((q * p).toString());
        }
    };

    const handleTotalCostChange = (val: string) => {
        setTotalCost(val);
        const q = parseFloat(quantity);
        const p = parseFloat(unitPrice);
        const t = parseFloat(val);
        if (t > 0) {
            if (quantity && !unitPrice) setUnitPrice((t / q).toString());
            else if (unitPrice && !quantity) setQuantity((t / p).toString());
            else if (quantity && unitPrice) setUnitPrice((t / q).toString());
        }
    };

    return (
        <div style={{ minHeight: '100vh', background: 'var(--color-bg-primary)' }}>
            {/* 頂部導覽列 */}
            <header style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '16px 32px',
                borderBottom: '1px solid var(--color-border)',
                background: 'var(--color-bg-secondary)',
                position: 'sticky',
                top: 0,
                zIndex: 100,
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
                    <h1 style={{
                        fontSize: '1.3rem',
                        fontWeight: 800,
                        background: 'linear-gradient(135deg, #6366f1, #a855f7)',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                    }}>
                        WealthTracker
                    </h1>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    {/* 投資組合選擇器 */}
                    <select
                        style={{
                            background: 'var(--color-bg-secondary)',
                            border: '1px solid var(--color-border)',
                            borderRadius: '8px',
                            padding: '8px 12px',
                            color: 'var(--color-text-primary)',
                            cursor: 'pointer',
                        }}
                        value={selectedPortfolio?.id || ''}
                        onChange={(e) => {
                            const p = portfolios.find((p) => p.id === e.target.value);
                            if (p) usePortfolioStore.getState().selectPortfolio(p);
                        }}
                    >
                        {portfolios.map((p) => (
                            <option key={p.id} value={p.id}>{p.name}</option>
                        ))}
                    </select>

                    <div style={{
                        display: 'flex',
                        background: 'var(--color-bg-secondary)',
                        borderRadius: '8px',
                        overflow: 'hidden',
                        border: '1px solid var(--color-border)',
                    }}>
                        <button
                            style={{
                                padding: '6px 12px',
                                background: displayCurrency === 'TWD' ? 'var(--color-primary)' : 'transparent',
                                color: displayCurrency === 'TWD' ? 'var(--color-primary-text)' : 'var(--color-text-muted)',
                                border: 'none',
                                cursor: 'pointer',
                                fontSize: '0.85rem',
                                fontWeight: displayCurrency === 'TWD' ? 600 : 400,
                            }}
                            onClick={() => setDisplayCurrency('TWD')}
                        >
                            TWD
                        </button>
                        <button
                            style={{
                                padding: '6px 12px',
                                background: displayCurrency === 'USD' ? 'var(--color-primary)' : 'transparent',
                                color: displayCurrency === 'USD' ? 'var(--color-primary-text)' : 'var(--color-text-muted)',
                                border: 'none',
                                cursor: 'pointer',
                                fontSize: '0.85rem',
                                fontWeight: displayCurrency === 'USD' ? 600 : 400,
                            }}
                            onClick={() => setDisplayCurrency('USD')}
                        >
                            USD
                        </button>
                    </div>

                    <button
                        className="btn-primary"
                        style={{ padding: '8px 16px', fontSize: '0.85rem' }}
                        onClick={() => {
                            resetTxForm();
                            setShowTxModal(true);
                        }}
                    >
                        + 新增交易
                    </button>
                    <button
                        className="btn-secondary"
                        style={{ padding: '8px 16px', fontSize: '0.85rem' }}
                        onClick={() => setShowCreateModal(true)}
                    >
                        + 新增組合
                    </button>
                    <button
                        className="btn-secondary"
                        style={{ padding: '8px 12px', fontSize: '0.85rem' }}
                        onClick={() => refreshAll()}
                        disabled={isLoading}
                    >
                        {isLoading ? '⟳' : '🔄'} 更新
                    </button>
                    <button
                        className="btn-secondary"
                        style={{ padding: '8px 12px', fontSize: '0.85rem' }}
                        onClick={() => setShowSettings(true)}
                    >
                        ⚙️ 設定
                    </button>
                    <button
                        className="btn-secondary"
                        style={{ padding: '8px 12px', fontSize: '0.85rem' }}
                        onClick={() => {
                            apiClient.clearToken();
                            router.push('/');
                        }}
                    >
                        登出
                    </button>
                </div>
            </header>

            {/* 主要內容 */}
            <main style={{ padding: '24px 32px', maxWidth: '1400px', margin: '0 auto' }}>
                {/* 統計卡片 */}
                <div className="dashboard-grid" style={{ marginBottom: '24px' }}>
                    <div className="card stat-card" style={{}}>
                        <span style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>總資產</span>
                        <div style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", marginTop: '4px' }}>
                            {formatCurrency(summary?.total_assets || 0)}
                        </div>
                    </div>
                    <div className="card stat-card">
                        <span style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>總負債</span>
                        <div style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", marginTop: '4px', color: 'var(--color-loss)' }}>
                            {formatCurrency(summary?.total_liabilities || 0)}
                        </div>
                    </div>
                    <div className={`card stat-card ${(summary?.net_worth || 0) >= 0 ? 'profit' : 'loss'}`}>
                        <span style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>淨值</span>
                        <div style={{
                            fontSize: '1.4rem',
                            fontWeight: 700,
                            fontFamily: "'JetBrains Mono', monospace",
                            marginTop: '4px',
                            color: (summary?.net_worth || 0) >= 0 ? 'var(--color-profit)' : 'var(--color-loss)',
                        }}>
                            {formatCurrency(summary?.net_worth || 0)}
                        </div>
                    </div>
                    <div className={`card stat-card ${(summary?.total_unrealized_pnl || 0) >= 0 ? 'profit' : 'loss'}`}>
                        <span style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>未實現損益</span>
                        <div style={{
                            fontSize: '1.4rem',
                            fontWeight: 700,
                            fontFamily: "'JetBrains Mono', monospace",
                            marginTop: '4px',
                        }}>
                            <span className={(summary?.total_unrealized_pnl || 0) >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                                {(summary?.total_unrealized_pnl || 0) >= 0 ? '+' : ''}{formatCurrency(summary?.total_unrealized_pnl || 0)}
                            </span>
                        </div>
                    </div>
                    <div
                        className={`card stat-card ${(summary?.total_realized_pnl || 0) >= 0 ? 'profit' : 'loss'}`}
                        style={{ cursor: 'pointer', transition: 'transform 0.2s' }}
                        onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-4px)'}
                        onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}
                        onClick={() => router.push('/dashboard/transactions')}
                    >
                        <span style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>已實現損益</span>
                        <div style={{
                            fontSize: '1.4rem',
                            fontWeight: 700,
                            fontFamily: "'JetBrains Mono', monospace",
                            marginTop: '4px',
                        }}>
                            <span className={(summary?.total_realized_pnl || 0) >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                                {(summary?.total_realized_pnl || 0) >= 0 ? '+' : ''}{formatCurrency(summary?.total_realized_pnl || 0)}
                            </span>
                        </div>
                    </div>
                </div>

                {/* 圖表區域 */}
                <div className="charts-grid" style={{ marginBottom: '24px' }}>
                    <NetWorthChart data={history?.history || []} />
                    <AllocationPie
                        data={allocations?.allocations || []}
                        totalValue={Number(allocations?.total_value || 0)}
                    />
                </div>

                {/* 持倉表格 */}
                <PositionTable positions={summary?.positions || []} onQuickTrade={handleQuickTrade} />
            </main>

            {/* ====== 新增交易 Modal ====== */}
            {showTxModal && (
                <div style={{
                    position: 'fixed', inset: 0,
                    background: 'rgba(0,0,0,0.6)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    zIndex: 200, backdropFilter: 'blur(6px)',
                }} onClick={() => { setShowTxModal(false); resetTxForm(); }}>
                    <div className="card-glass" style={{
                        maxWidth: '520px', width: '100%', maxHeight: '90vh', overflowY: 'auto',
                    }} onClick={(e) => e.stopPropagation()}>
                        <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '20px' }}>
                            📝 新增交易
                        </h3>

                        {/* 交易類型 */}
                        <label style={labelStyle}>交易類型</label>
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '16px' }}>
                            {TX_TYPES.map((t) => (
                                <button key={t.key} onClick={() => setTxType(t.key)} style={{
                                    padding: '6px 14px', borderRadius: '8px', border: '1px solid',
                                    borderColor: txType === t.key ? 'var(--color-primary)' : 'var(--color-border)',
                                    background: txType === t.key ? 'rgba(99,102,241,0.15)' : 'var(--color-bg-secondary)',
                                    color: txType === t.key ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                                    cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600,
                                }}>
                                    {t.icon} {t.label}
                                </button>
                            ))}
                        </div>

                        {/* 資產類別 */}
                        <label style={labelStyle}>資產類別</label>
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '16px' }}>
                            {CATEGORIES.map((c) => (
                                <button key={c.id} onClick={() => setCategoryId(c.id)} style={{
                                    padding: '6px 14px', borderRadius: '8px', border: '1px solid',
                                    borderColor: categoryId === c.id ? 'var(--color-primary)' : 'var(--color-border)',
                                    background: categoryId === c.id ? 'rgba(99,102,241,0.15)' : 'var(--color-bg-secondary)',
                                    color: categoryId === c.id ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                                    cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600,
                                }}>
                                    {c.icon} {c.label}
                                </button>
                            ))}
                        </div>

                        {/* 標的代碼 + 名稱 */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                            <div style={{ position: 'relative' }}>
                                <label style={labelStyle}>標的代碼 *</label>
                                <input className="input-field" placeholder="如 2330, AAPL, BTC"
                                    value={symbol}
                                    onChange={(e) => {
                                        setSymbol(e.target.value.toUpperCase());
                                        setShowSuggestions(true);
                                    }}
                                    onFocus={() => setShowSuggestions(true)}
                                    // 延遲關閉，使得點擊選項時不會先觸發 blur 導致選單消失
                                    onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                                />

                                {showSuggestions && (searchResults.length > 0 || isSearching) && (
                                    <div style={{
                                        position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0,
                                        background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)',
                                        borderRadius: '8px', zIndex: 50, maxHeight: '200px', overflowY: 'auto',
                                        boxShadow: '0 4px 12px rgba(0,0,0,0.5)'
                                    }}>
                                        {isSearching ? (
                                            <div style={{ padding: '10px 12px', color: 'var(--color-text-muted)', fontSize: '0.9rem', textAlign: 'center' }}>
                                                搜尋中...
                                            </div>
                                        ) : (
                                            searchResults.map(asset => (
                                                <div key={asset.symbol}
                                                    style={{
                                                        padding: '10px 12px', cursor: 'pointer',
                                                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                                        borderBottom: '1px solid var(--color-border)'
                                                    }}
                                                    onClick={() => {
                                                        setSymbol(asset.symbol);
                                                        setAssetName(asset.name);
                                                        setShowSuggestions(false);
                                                        // 自動切換資產類別
                                                        let newCategoryId = categoryId;
                                                        if (asset.category_slug) {
                                                            const cat = CATEGORIES.find(c => c.slug === asset.category_slug);
                                                            if (cat) {
                                                                setCategoryId(cat.id);
                                                                newCategoryId = cat.id;
                                                            }
                                                        }
                                                        // 智能切換預設幣別
                                                        if (asset.currency) {
                                                            setCurrency(asset.currency);
                                                        } else {
                                                            if (newCategoryId === 2 || newCategoryId === 3) setCurrency('USD');
                                                            if (newCategoryId === 1 || newCategoryId === 4 || newCategoryId === 5) setCurrency('TWD');
                                                        }
                                                    }}
                                                >
                                                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                                                        <span style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>{asset.symbol}</span>
                                                        <span style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>{asset.name}</span>
                                                    </div>
                                                    {asset.type_box && (
                                                        <span style={{
                                                            fontSize: '0.7rem', color: 'var(--color-text-secondary)', background: 'var(--color-bg-primary)',
                                                            padding: '2px 6px', borderRadius: '4px'
                                                        }}>{asset.type_box} {asset.exchange ? `(${asset.exchange})` : ''}</span>
                                                    )}
                                                </div>
                                            ))
                                        )}
                                    </div>
                                )}
                            </div>
                            <div>
                                <label style={labelStyle}>標的名稱</label>
                                <input className="input-field" placeholder="如 台積電, Apple"
                                    value={assetName} onChange={(e) => setAssetName(e.target.value)} />
                            </div>
                        </div>

                        {/* 數量 + 均價 */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                            <div>
                                <label style={labelStyle}>數量 *</label>
                                <input className="input-field" placeholder="0" type="number" step="any"
                                    value={quantity} onChange={(e) => handleQuantityChange(e.target.value)} />
                            </div>
                            <div>
                                <label style={labelStyle}>均價 *</label>
                                <input className="input-field" placeholder="0.00" type="number" step="any"
                                    value={unitPrice} onChange={(e) => handlePriceChange(e.target.value)} />
                            </div>
                        </div>

                        {/* 總成本 + 幣別 */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                            <div>
                                <label style={labelStyle}>總成本</label>
                                <input className="input-field" placeholder="0" type="number" step="any"
                                    value={totalCost} onChange={(e) => handleTotalCostChange(e.target.value)} />
                            </div>
                            <div>
                                <label style={labelStyle}>幣別</label>
                                <select className="input-field" value={currency}
                                    onChange={(e) => setCurrency(e.target.value)}>
                                    <option value="TWD">TWD 新台幣</option>
                                    <option value="USD">USD 美元</option>
                                </select>
                            </div>
                        </div>

                        {/* 日期 + 備註 */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                            <div>
                                <label style={labelStyle}>交易日期</label>
                                <input className="input-field" type="datetime-local"
                                    value={txDate} onChange={(e) => setTxDate(e.target.value)} />
                            </div>
                            <div>
                                <label style={labelStyle}>備註</label>
                                <input className="input-field" placeholder="選填"
                                    value={txNote} onChange={(e) => setTxNote(e.target.value)} />
                            </div>
                        </div>

                        {/* 金額預覽 */}
                        {previewAmount > 0 && (
                            <div style={{
                                background: 'var(--color-bg-primary)', borderRadius: '10px', padding: '12px 16px',
                                textAlign: 'center', marginBottom: '16px', border: '1px solid var(--color-border)',
                            }}>
                                <span style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>交易總額</span>
                                <div style={{
                                    fontSize: '1.5rem', fontWeight: 700,
                                    fontFamily: "'JetBrains Mono', monospace", marginTop: '4px',
                                }}>
                                    {currency === 'USD' ? '$' : 'NT$'} {previewAmount.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                                </div>
                            </div>
                        )}

                        {/* 錯誤/成功訊息 */}
                        {txError && (
                            <div style={{
                                padding: '10px 14px', borderRadius: '8px', marginBottom: '12px',
                                background: 'var(--color-loss-bg)', color: 'var(--color-loss)', fontSize: '0.9rem',
                            }}>{txError}</div>
                        )}
                        {txSuccess && (
                            <div style={{
                                padding: '10px 14px', borderRadius: '8px', marginBottom: '12px',
                                background: 'var(--color-profit-bg)', color: 'var(--color-profit)', fontSize: '0.9rem',
                            }}>{txSuccess}</div>
                        )}

                        {/* 按鈕 */}
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                            <button className="btn-secondary" onClick={() => { setShowTxModal(false); resetTxForm(); }}>取消</button>
                            <button className="btn-primary" onClick={handleAddTransaction} disabled={txLoading}
                                style={{ opacity: txLoading ? 0.6 : 1, minWidth: '120px' }}>
                                {txLoading ? '處理中...' : '確認新增'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* ====== 新增投資組合 Modal ====== */}
            {showCreateModal && (
                <div style={{
                    position: 'fixed', inset: 0,
                    background: 'rgba(0,0,0,0.5)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    zIndex: 200, backdropFilter: 'blur(4px)',
                }} onClick={() => setShowCreateModal(false)}>
                    <div className="card-glass" style={{ maxWidth: '400px', width: '100%' }}
                        onClick={(e) => e.stopPropagation()}>
                        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '16px' }}>
                            新增投資組合
                        </h3>
                        <input className="input-field" placeholder="組合名稱, 例如「長期投資」"
                            value={newPortfolioName} onChange={(e) => setNewPortfolioName(e.target.value)}
                            autoFocus onKeyDown={(e) => e.key === 'Enter' && handleCreatePortfolio()} />
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                            <button className="btn-secondary" onClick={() => setShowCreateModal(false)}>取消</button>
                            <button className="btn-primary" onClick={handleCreatePortfolio}>建立</button>
                        </div>
                    </div>
                </div>
            )}

            {/* ====== 設定 Modal ====== */}
            {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
        </div>
    );
}

// 共用 label 樣式
const labelStyle: React.CSSProperties = {
    display: 'block',
    color: 'var(--color-text-muted)',
    fontSize: '0.8rem',
    fontWeight: 600,
    marginBottom: '6px',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.03em',
};
