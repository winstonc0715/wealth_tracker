'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import apiClient from '@/lib/api-client';
import type { Transaction } from '@/lib/api-client';
import { usePortfolioStore } from '@/stores/portfolio-store';
import SettingsModal from '@/components/SettingsModal';

export default function TransactionsPage() {
    const router = useRouter();
    const { selectedPortfolio, refreshAll, displayCurrency, exchangeRate } = usePortfolioStore();
    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);

    // 編輯 Modal 狀態
    const [editingTx, setEditingTx] = useState<Transaction | null>(null);
    const [editNote, setEditNote] = useState('');
    const [editQuantity, setEditQuantity] = useState<string>('');
    const [editPrice, setEditPrice] = useState<string>('');
    const [editTotalCost, setEditTotalCost] = useState<string>('');
    const [editExecutedAt, setEditExecutedAt] = useState('');
    const [isUpdating, setIsUpdating] = useState(false);
    const [isRecalculating, setIsRecalculating] = useState(false);
    const [showSettings, setShowSettings] = useState(false);

    useEffect(() => {
        if (!selectedPortfolio) {
            router.push('/dashboard');
            return;
        }
        fetchTransactions();
    }, [selectedPortfolio, page]);

    const fetchTransactions = async () => {
        if (!selectedPortfolio) return;
        setIsLoading(true);
        try {
            const result = await apiClient.getTransactions(selectedPortfolio.id, page, 20);
            if (result.data) {
                setTransactions(result.data.items);
                setTotalPages(result.data.total_pages);
            }
        } catch (error) {
            console.error('取得交易紀錄失敗:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleDelete = async (txId: string) => {
        if (!confirm('確定要刪除此筆交易嗎？相關的持倉成本與損益將會自動重新計算。')) return;
        try {
            await apiClient.deleteTransaction(txId);
            await fetchTransactions();
            await refreshAll();
        } catch (error) {
            alert('刪除失敗: ' + (error as Error).message);
        }
    };

    // 編輯交易：三欄互算邏輯
    const handleEditQuantityChange = (val: string) => {
        setEditQuantity(val);
        const q = parseFloat(val);
        const p = parseFloat(editPrice);
        if (q > 0 && p > 0) setEditTotalCost((q * p).toFixed(2));
    };
    const handleEditPriceChange = (val: string) => {
        setEditPrice(val);
        const q = parseFloat(editQuantity);
        const p = parseFloat(val);
        if (q > 0 && p > 0) setEditTotalCost((q * p).toFixed(2));
    };
    const handleEditTotalCostChange = (val: string) => {
        setEditTotalCost(val);
        const q = parseFloat(editQuantity);
        const t = parseFloat(val);
        if (q > 0 && t > 0) setEditPrice((t / q).toFixed(4));
    };

    const handleUpdate = async () => {
        if (!editingTx) return;
        setIsUpdating(true);
        try {
            await apiClient.updateTransaction(editingTx.id, {
                note: editNote,
                quantity: parseFloat(editQuantity) || 0,
                unit_price: parseFloat(editPrice) || 0,
                fee: 0,
                executed_at: editExecutedAt
            });
            setEditingTx(null);
            await fetchTransactions();
            await refreshAll();
        } catch (error) {
            alert('更新失敗: ' + (error as Error).message);
        } finally {
            setIsUpdating(false);
        }
    };

    const handleRecalculateAll = async () => {
        if (!selectedPortfolio) return;
        if (!confirm('將會重新計算本組合所有的歷史持倉與實現損益，確定執行嗎？')) return;

        setIsRecalculating(true);
        try {
            await apiClient.recalculatePortfolioPnl(selectedPortfolio.id);
            alert('歷史損益重算完成！');
            await fetchTransactions();
            await refreshAll();
        } catch (error) {
            alert('重算失敗: ' + (error as Error).message);
        } finally {
            setIsRecalculating(false);
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

    return (
        <div style={{ minHeight: '100vh', background: 'var(--color-bg-primary)', padding: '32px' }}>
            <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                        <button
                            className="btn-secondary"
                            style={{ padding: '8px 12px' }}
                            onClick={() => router.push('/dashboard')}
                        >
                            ← 返回
                        </button>
                        <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--color-text-primary)' }}>交易管理中心</h1>
                    </div>
                    <div style={{ display: 'flex', gap: '12px' }}>
                        <button
                            className="btn-secondary"
                            style={{ padding: '8px 16px' }}
                            onClick={() => setShowSettings(true)}
                        >
                            ⚙️ 設定
                        </button>
                        <button
                            className="btn-secondary"
                            style={{ padding: '8px 16px' }}
                            onClick={handleRecalculateAll}
                            disabled={isRecalculating}
                        >
                            {isRecalculating ? '重算中...' : '⟳ 重算歷史損益'}
                        </button>
                    </div>
                </div>

                {/* overflowX: auto — 窄視窗時表格可橫向捲動，「操作」欄不再被裁掉 */}
                <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '720px' }}>
                        <thead style={{ background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid var(--color-border)' }}>
                            <tr>
                                <th style={thStyle}>日期</th>
                                <th style={thStyle}>標的</th>
                                <th style={thStyle}>類型</th>
                                <th style={thStyle}>數量</th>
                                <th style={thStyle}>價格</th>
                                <th style={thStyle}>實現損益</th>
                                <th style={thStyle}>備註</th>
                                <th style={thStyle}>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {transactions.map((tx) => (
                                <tr key={tx.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                                    <td style={tdStyle}>{new Date(tx.executed_at).toLocaleDateString()}</td>
                                    <td style={tdStyle}>
                                        <div style={{ fontWeight: 600 }}>{tx.symbol}</div>
                                        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>{tx.asset_name}</div>
                                    </td>
                                    <td style={tdStyle}>
                                        <span style={{
                                            padding: '4px 8px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600,
                                            background: getTxTypeColor(tx.tx_type), color: '#fff'
                                        }}>
                                            {getTxTypeLabel(tx.tx_type)}
                                        </span>
                                    </td>
                                    <td style={tdStyle}>{Number(tx.quantity)}</td>
                                    <td style={tdStyle}>{formatCurrency(tx.unit_price)}</td>
                                    <td style={tdStyle}>
                                        {tx.realized_pnl !== 0 ? (
                                            <span style={{ color: tx.realized_pnl > 0 ? 'var(--color-profit)' : 'var(--color-loss)', fontWeight: 600 }}>
                                                {tx.realized_pnl > 0 ? '+' : ''}{formatCurrency(tx.realized_pnl)}
                                            </span>
                                        ) : '-'}
                                    </td>
                                    <td style={tdStyle}>{tx.note || '-'}</td>
                                    <td style={tdStyle}>
                                        <div style={{ display: 'flex', gap: '8px' }}>
                                            <button
                                                className="btn-secondary"
                                                style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                                                onClick={() => {
                                                    setEditingTx(tx);
                                                    setEditNote(tx.note || '');
                                                    const q = Number(tx.quantity);
                                                    const p = Number(tx.unit_price);
                                                    setEditQuantity(q.toString());
                                                    setEditPrice(p.toString());
                                                    setEditTotalCost((q * p).toFixed(2));
                                                    // 將 ISO 時間轉換為 datetime-local 格式
                                                    const dt = new Date(tx.executed_at);
                                                    const localStr = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}T${String(dt.getHours()).padStart(2, '0')}:${String(dt.getMinutes()).padStart(2, '0')}`;
                                                    setEditExecutedAt(localStr);
                                                }}
                                            >
                                                編輯
                                            </button>
                                            <button
                                                className="btn-secondary"
                                                style={{ padding: '4px 8px', fontSize: '0.75rem', color: 'var(--color-loss)' }}
                                                onClick={() => handleDelete(tx.id)}
                                            >
                                                刪除
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                            {transactions.length === 0 && (
                                <tr>
                                    <td colSpan={8} style={{ padding: '40px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
                                        暫無交易紀錄
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>

                {/* 分頁 */}
                <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginTop: '24px' }}>
                    <button className="btn-secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>上一頁</button>
                    <span style={{ display: 'flex', alignItems: 'center', padding: '0 12px' }}>第 {page} 頁 / 共 {totalPages} 頁</span>
                    <button className="btn-secondary" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>下一頁</button>
                </div>
            </div>

            {/* 編輯 Modal */}
            {editingTx && (
                <div style={{
                    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 300, backdropFilter: 'blur(4px)'
                }} onClick={() => setEditingTx(null)}>
                    <div className="card-glass" style={{ maxWidth: '450px', width: '90%' }} onClick={e => e.stopPropagation()}>
                        <h3 style={{ marginBottom: '16px' }}>📝 編輯交易</h3>
                        <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', marginBottom: '20px' }}>
                            標的: {editingTx.symbol} ({editingTx.asset_name})
                        </p>

                        <div style={{ marginBottom: '16px' }}>
                            <label style={labelStyle}>交易時間</label>
                            <input
                                type="datetime-local"
                                className="input-field"
                                value={editExecutedAt}
                                onChange={e => setEditExecutedAt(e.target.value)}
                            />
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                            <div>
                                <label style={labelStyle}>數量</label>
                                <input
                                    type="number"
                                    className="input-field"
                                    step="any"
                                    value={editQuantity}
                                    onChange={e => handleEditQuantityChange(e.target.value)}
                                />
                            </div>
                            <div>
                                <label style={labelStyle}>均價</label>
                                <input
                                    type="number"
                                    className="input-field"
                                    step="any"
                                    value={editPrice}
                                    onChange={e => handleEditPriceChange(e.target.value)}
                                />
                            </div>
                        </div>

                        <div style={{ marginBottom: '16px' }}>
                            <label style={labelStyle}>總成本</label>
                            <input
                                type="number"
                                className="input-field"
                                step="any"
                                value={editTotalCost}
                                onChange={e => handleEditTotalCostChange(e.target.value)}
                            />
                        </div>

                        <div style={{ marginBottom: '20px' }}>
                            <label style={labelStyle}>備註</label>
                            <textarea
                                className="input-field"
                                style={{ height: '80px', resize: 'none' }}
                                value={editNote}
                                onChange={e => setEditNote(e.target.value)}
                                placeholder="輸入交易備註..."
                            />
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                            <button className="btn-secondary" onClick={() => setEditingTx(null)}>取消</button>
                            <button className="btn-primary" onClick={handleUpdate} disabled={isUpdating}>
                                {isUpdating ? '儲存中...' : '確定儲存'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* ====== 設定 Modal ====== */}
            {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
        </div>
    );
}

const thStyle: React.CSSProperties = { padding: '16px', textAlign: 'left', color: 'var(--color-text-muted)', fontSize: '0.85rem', fontWeight: 600, whiteSpace: 'nowrap' };
const tdStyle: React.CSSProperties = { padding: '16px', fontSize: '0.9rem', whiteSpace: 'nowrap' };
const labelStyle: React.CSSProperties = { display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' };

const getTxTypeLabel = (type: string) => {
    switch (type) {
        case 'buy': return '買入';
        case 'sell': return '賣出';
        case 'dividend': return '配息';
        case 'deposit': return '存入';
        case 'withdraw': return '提出';
        default: return type;
    }
};

const getTxTypeColor = (type: string) => {
    switch (type) {
        case 'buy': return 'var(--color-primary)';
        case 'sell': return '#f59e0b';
        case 'dividend': return 'var(--color-profit)';
        case 'deposit': return '#8b5cf6';
        case 'withdraw': return 'var(--color-loss)';
        default: return 'var(--color-text-muted)';
    }
};
