'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import apiClient from '@/lib/api-client';
import type { Transaction } from '@/lib/api-client';
import { usePortfolioStore } from '@/stores/portfolio-store';

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
    const [isUpdating, setIsUpdating] = useState(false);

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
            setIsLoading(true); // 這裡故意寫成 true？不，應該是 false
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

    const handleUpdate = async () => {
        if (!editingTx) return;
        setIsUpdating(true);
        try {
            await apiClient.updateTransaction(editingTx.id, { note: editNote });
            setEditingTx(null);
            await fetchTransactions();
            await refreshAll();
        } catch (error) {
            alert('更新失敗: ' + (error as Error).message);
        } finally {
            setIsUpdating(false);
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
                        <h1 style={{ fontSize: '1.5rem', fontWeight: 800 }}>交易管理中心</h1>
                    </div>
                </div>

                <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
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
                                    <td style={tdStyle}>{tx.quantity}</td>
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
                    <div className="card-glass" style={{ maxWidth: '400px', width: '100%' }} onClick={e => e.stopPropagation()}>
                        <h3 style={{ marginBottom: '16px' }}>📝 編輯備註</h3>
                        <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', marginBottom: '12px' }}>
                            標的: {editingTx.symbol} ({editingTx.asset_name})
                        </p>
                        <textarea
                            className="input-field"
                            style={{ height: '100px', resize: 'none' }}
                            value={editNote}
                            onChange={e => setEditNote(e.target.value)}
                            placeholder="輸入交易備註..."
                        />
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                            <button className="btn-secondary" onClick={() => setEditingTx(null)}>取消</button>
                            <button className="btn-primary" onClick={handleUpdate} disabled={isUpdating}>
                                {isUpdating ? '儲存中...' : '確定儲存'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

const thStyle: React.CSSProperties = { padding: '16px', textAlign: 'left', color: 'var(--color-text-muted)', fontSize: '0.85rem', fontWeight: 600 };
const tdStyle: React.CSSProperties = { padding: '16px', fontSize: '0.9rem' };

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
