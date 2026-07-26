'use client';

/**
 * 定期定額管理頁面 (DCA Management)
 *
 * 包含：待確認交易、計畫列表、執行歷史、新增/編輯計畫 Modal
 */

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import apiClient, { SearchResult } from '@/lib/api-client';
import type {
    DCASchedule, DCAScheduleInput, DCAExecution, DCAImportResult,
    DCAImportColumnInfo, PaginatedResponse,
} from '@/lib/api-client';
import { usePortfolioStore } from '@/stores/portfolio-store';
import {
    Calendar, Plus, Check, X, ArrowLeft, Pause, Play,
    Trash2, Edit2, TrendingUp, DollarSign, Clock,
    AlertCircle, CheckCircle2, XCircle, SkipForward,
    ChevronDown, ChevronUp, Search, Loader2, Upload,
    Download, Eye, HelpCircle,
} from 'lucide-react';

// 扣款日選項
const EXECUTION_DAY_OPTIONS = [3, 6, 9, 13, 16, 19, 23, 26, 29];

// 券商列表（目前僅支援永豐）
const BROKERS = [
    { key: 'sinopac', label: '永豐證券', enabled: true },
    { key: 'fubon', label: '富邦證券', enabled: false },
    { key: 'cathay', label: '國泰證券', enabled: false },
];

// 資產類別
const CATEGORIES = [
    { id: 1, label: '台股', slug: 'tw_stock' },
    { id: 2, label: '美股', slug: 'us_stock' },
    { id: 3, label: '加密貨幣', slug: 'crypto' },
];

// 匯入預覽動作標籤
const IMPORT_ACTION_LABELS: Record<string, string> = {
    create: '新增',
    update: '更新',
    unchanged: '不變',
    none: '—',
};

export default function DCAPage() {
    const router = useRouter();
    const { selectedPortfolio } = usePortfolioStore();

    // 核心數據
    const [schedules, setSchedules] = useState<DCASchedule[]>([]);
    const [pendingExecutions, setPendingExecutions] = useState<DCAExecution[]>([]);
    const [executionHistory, setExecutionHistory] = useState<PaginatedResponse<DCAExecution> | null>(null);
    const [historyPage, setHistoryPage] = useState(1);

    // UI 狀態
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState('');
    const [successMsg, setSuccessMsg] = useState('');
    const [showModal, setShowModal] = useState(false);
    const [editingSchedule, setEditingSchedule] = useState<DCASchedule | null>(null);
    const [expandedExecId, setExpandedExecId] = useState<string | null>(null);
    const [confirmPriceMap, setConfirmPriceMap] = useState<Record<string, string>>({});
    const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});
    const [showHistory, setShowHistory] = useState(false);
    const [showImportModal, setShowImportModal] = useState(false);
    const [importFile, setImportFile] = useState<File | null>(null);
    const [importCategoryId, setImportCategoryId] = useState(1);
    const [importBrokerFormat, setImportBrokerFormat] = useState('standard');
    const [importBroker, setImportBroker] = useState('sinopac');
    const [importAutoConfirm, setImportAutoConfirm] = useState(false);
    const [importLoading, setImportLoading] = useState(false);
    const [importError, setImportError] = useState('');
    const [importResult, setImportResult] = useState<DCAImportResult | null>(null);
    const [importPreview, setImportPreview] = useState<DCAImportResult | null>(null);
    const [previewLoading, setPreviewLoading] = useState(false);
    const [importColumns, setImportColumns] = useState<DCAImportColumnInfo[]>([]);
    const [showColumnHelp, setShowColumnHelp] = useState(false);

    // Modal 表單狀態
    const [formSymbol, setFormSymbol] = useState('');
    const [formAssetName, setFormAssetName] = useState('');
    const [formCategoryId, setFormCategoryId] = useState(1);
    const [formBroker, setFormBroker] = useState('sinopac');
    const [formInvestmentType, setFormInvestmentType] = useState<'amount' | 'shares'>('amount');
    const [formTargetAmount, setFormTargetAmount] = useState('');
    const [formTargetShares, setFormTargetShares] = useState('');
    const [formExecutionDays, setFormExecutionDays] = useState<number[]>([]);
    const [formFeeDiscount, setFormFeeDiscount] = useState('0.1');
    const [formAutoConfirm, setFormAutoConfirm] = useState(false);
    const [formLoading, setFormLoading] = useState(false);
    const [formError, setFormError] = useState('');

    // 標的搜尋
    const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [isSearching, setIsSearching] = useState(false);

    // 載入所有數據
    const fetchAll = useCallback(async () => {
        setIsLoading(true);
        try {
            const [schedulesData, pendingData, historyData] = await Promise.all([
                apiClient.getDCASchedules(),
                apiClient.getPendingExecutions(),
                apiClient.getExecutionHistory(historyPage, 10),
            ]);
            setSchedules(schedulesData || []);
            setPendingExecutions(pendingData || []);
            setExecutionHistory(historyData || null);
        } catch (err) {
            console.error('載入定期定額資料失敗:', err);
            setError('載入資料失敗，請稍後重試');
        } finally {
            setIsLoading(false);
        }
    }, [historyPage]);

    useEffect(() => {
        if (!apiClient.isAuthenticated()) {
            router.push('/');
            return;
        }
        fetchAll();
    }, [fetchAll]);

    // 標的搜尋 debounce
    useEffect(() => {
        if (!formSymbol.trim()) {
            setSearchResults([]);
            return;
        }
        const timer = setTimeout(async () => {
            setIsSearching(true);
            try {
                const res = await apiClient.searchSymbols(formSymbol.trim(), 'all');
                setSearchResults(res.data || []);
            } catch {
                setSearchResults([]);
            } finally {
                setIsSearching(false);
            }
        }, 300);
        return () => clearTimeout(timer);
    }, [formSymbol]);

    // 自動清除成功/錯誤訊息
    useEffect(() => {
        if (successMsg) {
            const t = setTimeout(() => setSuccessMsg(''), 3000);
            return () => clearTimeout(t);
        }
    }, [successMsg]);

    // 開啟匯入視窗時載入欄位對照（僅載入一次）
    useEffect(() => {
        if (showImportModal && importColumns.length === 0) {
            apiClient.getDCAImportColumns()
                .then(setImportColumns)
                .catch(() => { /* 欄位提示載入失敗不阻擋匯入 */ });
        }
    }, [showImportModal, importColumns.length]);

    // === 操作方法 ===

    const handleToggleSchedule = async (id: string) => {
        setActionLoading(prev => ({ ...prev, [id]: true }));
        try {
            const updated = await apiClient.toggleDCASchedule(id);
            setSchedules(prev => prev.map(s => s.id === id ? updated : s));
            setSuccessMsg(updated.is_active ? '已啟用計畫' : '已暫停計畫');
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setActionLoading(prev => ({ ...prev, [id]: false }));
        }
    };

    const handleDeleteSchedule = async (id: string) => {
        if (!confirm('確定要刪除這個定期定額計畫嗎？')) return;
        setActionLoading(prev => ({ ...prev, [id]: true }));
        try {
            await apiClient.deleteDCASchedule(id);
            setSchedules(prev => prev.filter(s => s.id !== id));
            setSuccessMsg('已刪除計畫');
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setActionLoading(prev => ({ ...prev, [id]: false }));
        }
    };

    const handleConfirmExecution = async (id: string) => {
        setActionLoading(prev => ({ ...prev, [id]: true }));
        try {
            const priceStr = confirmPriceMap[id];
            const data = priceStr ? { actual_price: parseFloat(priceStr) } : undefined;
            await apiClient.confirmExecution(id, data);
            setPendingExecutions(prev => prev.filter(e => e.id !== id));
            setSuccessMsg('已確認入帳');
            // 重新載入歷史
            const hist = await apiClient.getExecutionHistory(historyPage, 10);
            setExecutionHistory(hist);
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setActionLoading(prev => ({ ...prev, [id]: false }));
        }
    };

    const handleSkipExecution = async (id: string) => {
        setActionLoading(prev => ({ ...prev, [id]: true }));
        try {
            await apiClient.skipExecution(id);
            setPendingExecutions(prev => prev.filter(e => e.id !== id));
            setSuccessMsg('已跳過此筆');
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setActionLoading(prev => ({ ...prev, [id]: false }));
        }
    };

    const handleConfirmAll = async () => {
        setActionLoading(prev => ({ ...prev, confirmAll: true }));
        try {
            await Promise.all(pendingExecutions.map(e => {
                const priceStr = confirmPriceMap[e.id];
                const data = priceStr ? { actual_price: parseFloat(priceStr) } : undefined;
                return apiClient.confirmExecution(e.id, data);
            }));
            setPendingExecutions([]);
            setSuccessMsg(`已確認 ${pendingExecutions.length} 筆交易`);
            const hist = await apiClient.getExecutionHistory(historyPage, 10);
            setExecutionHistory(hist);
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setActionLoading(prev => ({ ...prev, confirmAll: false }));
        }
    };

    const resetImportForm = () => {
        setImportFile(null);
        setImportCategoryId(1);
        setImportBrokerFormat('standard');
        setImportBroker('sinopac');
        setImportAutoConfirm(false);
        setImportError('');
        setImportResult(null);
        setImportPreview(null);
        setShowColumnHelp(false);
    };

    // 檔案或設定變更後，舊的預覽/結果不再有效
    const invalidateImportPreview = () => {
        setImportPreview(null);
        setImportResult(null);
        setImportError('');
    };

    const importOptions = () => ({
        categoryId: importCategoryId,
        brokerFormat: importBrokerFormat,
        broker: importBroker,
        autoConfirm: importAutoConfirm,
    });

    const handleImportPreview = async () => {
        if (!selectedPortfolio) { setImportError('請先選擇投資組合'); return; }
        if (!importFile) { setImportError('請選擇 CSV 檔案'); return; }

        setPreviewLoading(true);
        setImportError('');
        setImportResult(null);
        try {
            const result = await apiClient.previewDCACSV(
                selectedPortfolio.id, importFile, importOptions(),
            );
            setImportPreview(result);
        } catch (err) {
            setImportError((err as Error).message);
        } finally {
            setPreviewLoading(false);
        }
    };

    const handleImportSubmit = async () => {
        if (!selectedPortfolio) { setImportError('請先選擇投資組合'); return; }
        if (!importFile) { setImportError('請選擇 CSV 檔案'); return; }

        setImportLoading(true);
        setImportError('');
        setImportResult(null);
        try {
            const result = await apiClient.importDCACSV(
                selectedPortfolio.id, importFile, importOptions(),
            );
            setImportPreview(null);
            setImportResult(result);
            setSuccessMsg(`匯入完成：${result.imported} 筆成功，${result.skipped} 筆略過`);
            await fetchAll();
        } catch (err) {
            setImportError((err as Error).message);
        } finally {
            setImportLoading(false);
        }
    };

    // Modal 表單提交
    const resetForm = () => {
        setFormSymbol('');
        setFormAssetName('');
        setFormCategoryId(1);
        setFormBroker('sinopac');
        setFormInvestmentType('amount');
        setFormTargetAmount('');
        setFormTargetShares('');
        setFormExecutionDays([]);
        setFormFeeDiscount('0.1');
        setFormAutoConfirm(false);
        setFormError('');
        setEditingSchedule(null);
    };

    const openCreateModal = () => {
        resetForm();
        setShowModal(true);
    };

    const openEditModal = (schedule: DCASchedule) => {
        setEditingSchedule(schedule);
        setFormSymbol(schedule.symbol);
        setFormAssetName(schedule.asset_name || '');
        setFormCategoryId(schedule.category_id);
        setFormBroker(schedule.broker);
        setFormInvestmentType(schedule.investment_type);
        setFormTargetAmount(schedule.target_amount?.toString() || '');
        setFormTargetShares(schedule.target_shares?.toString() || '');
        setFormExecutionDays([...schedule.execution_days]);
        setFormFeeDiscount(schedule.fee_discount.toString());
        setFormAutoConfirm(schedule.auto_confirm);
        setFormError('');
        setShowModal(true);
    };

    const toggleExecutionDay = (day: number) => {
        setFormExecutionDays(prev =>
            prev.includes(day) ? prev.filter(d => d !== day) : [...prev, day].sort((a, b) => a - b)
        );
    };

    const handleFormSubmit = async () => {
        // 驗證
        if (!formSymbol.trim()) { setFormError('請輸入標的代碼'); return; }
        if (formExecutionDays.length === 0) { setFormError('請至少選擇一個扣款日'); return; }
        if (formInvestmentType === 'amount' && (!formTargetAmount || parseFloat(formTargetAmount) <= 0)) {
            setFormError('請輸入有效的投資金額'); return;
        }
        if (formInvestmentType === 'shares' && (!formTargetShares || parseFloat(formTargetShares) <= 0)) {
            setFormError('請輸入有效的股數'); return;
        }
        if (!selectedPortfolio) { setFormError('請先選擇投資組合'); return; }

        setFormLoading(true);
        setFormError('');

        const payload: DCAScheduleInput = {
            portfolio_id: selectedPortfolio.id,
            symbol: formSymbol.toUpperCase().trim(),
            asset_name: formAssetName || undefined,
            category_id: formCategoryId,
            broker: formBroker,
            investment_type: formInvestmentType,
            target_amount: formInvestmentType === 'amount' ? parseFloat(formTargetAmount) : undefined,
            target_shares: formInvestmentType === 'shares' ? parseFloat(formTargetShares) : undefined,
            execution_days: formExecutionDays,
            fee_discount: parseFloat(formFeeDiscount) || 0.1,
            auto_confirm: formAutoConfirm,
        };

        try {
            if (editingSchedule) {
                const updated = await apiClient.updateDCASchedule(editingSchedule.id, payload);
                setSchedules(prev => prev.map(s => s.id === editingSchedule.id ? updated : s));
                setSuccessMsg('已更新計畫');
            } else {
                const created = await apiClient.createDCASchedule(payload);
                setSchedules(prev => [...prev, created]);
                setSuccessMsg('已建立計畫');
            }
            setShowModal(false);
            resetForm();
        } catch (err) {
            setFormError((err as Error).message);
        } finally {
            setFormLoading(false);
        }
    };

    // 格式化工具
    const formatPrice = (val: number | null) => {
        if (val === null || val === undefined) return '-';
        return `$${val.toLocaleString('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    };

    const getStatusBadge = (status: string) => {
        switch (status) {
            case 'confirmed':
                return { label: '已確認', bg: 'var(--color-profit-bg)', color: 'var(--color-profit)', icon: <CheckCircle2 size={12} /> };
            case 'skipped':
                return { label: '已跳過', bg: 'rgba(245,158,11,0.15)', color: '#f59e0b', icon: <SkipForward size={12} /> };
            case 'failed':
                return { label: '失敗', bg: 'var(--color-loss-bg)', color: 'var(--color-loss)', icon: <XCircle size={12} /> };
            case 'pending':
                return { label: '待確認', bg: 'rgba(99,102,241,0.15)', color: 'var(--color-primary)', icon: <Clock size={12} /> };
            default:
                return { label: status, bg: 'var(--color-bg-secondary)', color: 'var(--color-text-muted)', icon: null };
        }
    };

    return (
        <div style={{ minHeight: '100vh', background: 'var(--color-bg-primary)' }}>
            {/* Header */}
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
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <button
                        className="btn-secondary"
                        style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}
                        onClick={() => router.push('/dashboard')}
                    >
                        <ArrowLeft size={16} /> 返回
                    </button>
                    <h1 style={{
                        fontSize: '1.3rem',
                        fontWeight: 800,
                        color: 'var(--color-text-primary)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                    }}>
                        <Calendar size={22} style={{ color: 'var(--color-primary)' }} />
                        定期定額管理
                    </h1>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <button
                        className="btn-secondary"
                        style={{ padding: '8px 16px', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '6px' }}
                        onClick={() => setShowImportModal(true)}
                    >
                        <Upload size={16} /> 匯入資料
                    </button>
                    <button
                        className="btn-primary"
                        style={{ padding: '8px 18px', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '6px' }}
                        onClick={openCreateModal}
                    >
                        <Plus size={16} /> 新增計畫
                    </button>
                </div>
            </header>

            {/* 主要內容 */}
            <main style={{ padding: '24px 32px', maxWidth: '1200px', margin: '0 auto' }}>
                {/* 全域訊息 */}
                {error && (
                    <div style={{
                        padding: '12px 16px', borderRadius: '10px', marginBottom: '16px',
                        background: 'var(--color-loss-bg)', color: 'var(--color-loss)', fontSize: '0.9rem',
                        display: 'flex', alignItems: 'center', gap: '8px',
                    }}>
                        <AlertCircle size={16} /> {error}
                        <button onClick={() => setError('')} style={{
                            marginLeft: 'auto', background: 'none', border: 'none',
                            color: 'var(--color-loss)', cursor: 'pointer',
                        }}><X size={14} /></button>
                    </div>
                )}
                {successMsg && (
                    <div style={{
                        padding: '12px 16px', borderRadius: '10px', marginBottom: '16px',
                        background: 'var(--color-profit-bg)', color: 'var(--color-profit)', fontSize: '0.9rem',
                        display: 'flex', alignItems: 'center', gap: '8px',
                    }}>
                        <CheckCircle2 size={16} /> {successMsg}
                    </div>
                )}

                {/* Loading */}
                {isLoading ? (
                    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '80px 0' }}>
                        <Loader2 size={32} style={{ color: 'var(--color-primary)', animation: 'spin 1s linear infinite' }} />
                        <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
                    </div>
                ) : (
                    <>
                        {/* ======== 待確認交易區塊 ======== */}
                        <section style={{ marginBottom: '32px' }}>
                            <h2 style={{
                                fontSize: '1.1rem', fontWeight: 700, marginBottom: '16px',
                                color: 'var(--color-text-primary)', display: 'flex', alignItems: 'center', gap: '8px',
                            }}>
                                <AlertCircle size={18} style={{ color: pendingExecutions.length > 0 ? 'var(--color-loss)' : 'var(--color-text-muted)' }} />
                                待確認交易
                                {pendingExecutions.length > 0 && (
                                    <span style={{
                                        background: 'var(--color-loss)', color: '#fff',
                                        borderRadius: '12px', padding: '2px 10px', fontSize: '0.8rem', fontWeight: 700,
                                    }}>{pendingExecutions.length}</span>
                                )}
                            </h2>

                            {pendingExecutions.length === 0 ? (
                                <div className="card" style={{
                                    textAlign: 'center', padding: '40px', color: 'var(--color-text-muted)',
                                }}>
                                    <CheckCircle2 size={36} style={{ marginBottom: '12px', opacity: 0.4 }} />
                                    <p>目前沒有待確認的交易 ✓</p>
                                </div>
                            ) : (
                                <div style={{
                                    background: 'var(--color-bg-card)',
                                    border: '2px solid var(--color-primary)',
                                    borderRadius: '16px',
                                    overflow: 'hidden',
                                    boxShadow: '0 0 20px rgba(99,102,241,0.1)',
                                }}>
                                    {/* 頂部操作列 */}
                                    <div style={{
                                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                        padding: '14px 20px',
                                        background: 'rgba(99,102,241,0.08)',
                                        borderBottom: '1px solid var(--color-border)',
                                    }}>
                                        <span style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
                                            共 {pendingExecutions.length} 筆待確認
                                        </span>
                                        <button
                                            className="btn-primary"
                                            style={{ padding: '6px 16px', fontSize: '0.8rem' }}
                                            onClick={handleConfirmAll}
                                            disabled={!!actionLoading.confirmAll}
                                        >
                                            {actionLoading.confirmAll ? (
                                                <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
                                            ) : (
                                                <><Check size={14} /> 全部確認</>
                                            )}
                                        </button>
                                    </div>

                                    {/* 待確認列表 */}
                                    {pendingExecutions.map((exec) => (
                                        <div key={exec.id} style={{
                                            padding: '16px 20px',
                                            borderBottom: '1px solid var(--color-border)',
                                            transition: 'background 0.15s ease',
                                        }}>
                                            <div style={{
                                                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                                flexWrap: 'wrap', gap: '12px',
                                            }}>
                                                {/* 左：標的資訊 */}
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: '200px' }}>
                                                    <div style={{
                                                        width: '40px', height: '40px', borderRadius: '10px',
                                                        background: 'rgba(99,102,241,0.12)', display: 'flex',
                                                        alignItems: 'center', justifyContent: 'center',
                                                    }}>
                                                        <DollarSign size={18} style={{ color: 'var(--color-primary)' }} />
                                                    </div>
                                                    <div>
                                                        <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>
                                                            {exec.schedule_symbol}
                                                            {exec.schedule_asset_name && (
                                                                <span style={{ fontWeight: 400, color: 'var(--color-text-muted)', marginLeft: '6px', fontSize: '0.85rem' }}>
                                                                    {exec.schedule_asset_name}
                                                                </span>
                                                            )}
                                                        </div>
                                                        <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                                                            {new Date(exec.execution_date).toLocaleDateString('zh-TW')}
                                                        </div>
                                                    </div>
                                                </div>

                                                {/* 中：數據 */}
                                                <div style={{
                                                    display: 'flex', gap: '20px', alignItems: 'center',
                                                    flexWrap: 'wrap', flex: 1, justifyContent: 'center',
                                                }}>
                                                    <div style={{ textAlign: 'center' }}>
                                                        <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '2px' }}>預估價</div>
                                                        <div style={{ fontWeight: 600, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.9rem' }}>
                                                            {formatPrice(exec.estimated_price)}
                                                        </div>
                                                    </div>
                                                    <div style={{ textAlign: 'center' }}>
                                                        <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '2px' }}>股數</div>
                                                        <div style={{ fontWeight: 600, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.9rem' }}>
                                                            {exec.quantity ?? '-'}
                                                        </div>
                                                    </div>
                                                    <div style={{ textAlign: 'center' }}>
                                                        <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '2px' }}>手續費</div>
                                                        <div style={{ fontWeight: 600, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.9rem' }}>
                                                            {formatPrice(exec.fee)}
                                                        </div>
                                                    </div>
                                                    <div style={{ textAlign: 'center' }}>
                                                        <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '2px' }}>扣款金額</div>
                                                        <div style={{ fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.95rem', color: 'var(--color-primary)' }}>
                                                            {formatPrice(exec.total_cost)}
                                                        </div>
                                                    </div>
                                                </div>

                                                {/* 右：操作 */}
                                                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                                                    <button
                                                        style={{
                                                            ...iconBtnStyle,
                                                            color: 'var(--color-text-muted)',
                                                        }}
                                                        title="修正實際價格"
                                                        onClick={() => setExpandedExecId(expandedExecId === exec.id ? null : exec.id)}
                                                    >
                                                        {expandedExecId === exec.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                                                    </button>
                                                    <button
                                                        className="btn-primary"
                                                        style={{ padding: '6px 14px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                                                        onClick={() => handleConfirmExecution(exec.id)}
                                                        disabled={!!actionLoading[exec.id]}
                                                    >
                                                        {actionLoading[exec.id] ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Check size={14} />}
                                                        確認
                                                    </button>
                                                    <button
                                                        className="btn-secondary"
                                                        style={{ padding: '6px 14px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                                                        onClick={() => handleSkipExecution(exec.id)}
                                                        disabled={!!actionLoading[exec.id]}
                                                    >
                                                        <SkipForward size={14} /> 跳過
                                                    </button>
                                                </div>
                                            </div>

                                            {/* 展開區：修正實際成交價 */}
                                            {expandedExecId === exec.id && (
                                                <div style={{
                                                    marginTop: '12px', padding: '12px 16px',
                                                    background: 'var(--color-bg-secondary)', borderRadius: '10px',
                                                    display: 'flex', alignItems: 'center', gap: '12px',
                                                }}>
                                                    <label style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', whiteSpace: 'nowrap' }}>
                                                        實際成交價：
                                                    </label>
                                                    <input
                                                        className="input-field"
                                                        type="number"
                                                        step="any"
                                                        placeholder={exec.estimated_price?.toString() || '輸入實際價格'}
                                                        value={confirmPriceMap[exec.id] || ''}
                                                        onChange={(e) => setConfirmPriceMap(prev => ({ ...prev, [exec.id]: e.target.value }))}
                                                        style={{ maxWidth: '200px' }}
                                                    />
                                                    <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                                                        留空則使用預估價格
                                                    </span>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </section>

                        {/* ======== 計畫列表 ======== */}
                        <section style={{ marginBottom: '32px' }}>
                            <h2 style={{
                                fontSize: '1.1rem', fontWeight: 700, marginBottom: '16px',
                                color: 'var(--color-text-primary)', display: 'flex', alignItems: 'center', gap: '8px',
                            }}>
                                <TrendingUp size={18} style={{ color: 'var(--color-primary)' }} />
                                我的定期定額計畫
                                <span style={{ fontSize: '0.85rem', fontWeight: 400, color: 'var(--color-text-muted)' }}>
                                    ({schedules.length})
                                </span>
                            </h2>

                            {schedules.length === 0 ? (
                                <div className="card" style={{
                                    textAlign: 'center', padding: '60px 20px', color: 'var(--color-text-muted)',
                                }}>
                                    <Calendar size={48} style={{ marginBottom: '16px', opacity: 0.3 }} />
                                    <p style={{ fontSize: '1rem', marginBottom: '8px' }}>還沒有任何定期定額計畫</p>
                                    <p style={{ fontSize: '0.85rem', marginBottom: '20px' }}>建立你的第一個定期定額計畫，讓投資自動化！</p>
                                    <button
                                        className="btn-primary"
                                        style={{ padding: '10px 24px' }}
                                        onClick={openCreateModal}
                                    >
                                        <Plus size={16} style={{ marginRight: '6px', verticalAlign: 'middle' }} />
                                        建立計畫
                                    </button>
                                </div>
                            ) : (
                                <div style={{
                                    display: 'grid',
                                    gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
                                    gap: '16px',
                                }}>
                                    {schedules.map((schedule) => (
                                        <div
                                            key={schedule.id}
                                            className="card"
                                            style={{
                                                position: 'relative',
                                                opacity: schedule.is_active ? 1 : 0.6,
                                                transition: 'all 0.2s ease',
                                            }}
                                        >
                                            {/* 頂部：標的 + 開關 */}
                                            <div style={{
                                                display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
                                                marginBottom: '16px',
                                            }}>
                                                <div>
                                                    <div style={{ fontWeight: 700, fontSize: '1.05rem' }}>
                                                        {schedule.symbol}
                                                    </div>
                                                    <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                                                        {schedule.asset_name || '-'}
                                                    </div>
                                                </div>
                                                {/* Toggle Switch */}
                                                <button
                                                    onClick={() => handleToggleSchedule(schedule.id)}
                                                    disabled={!!actionLoading[schedule.id]}
                                                    style={{
                                                        width: '44px', height: '24px', borderRadius: '12px',
                                                        border: 'none', cursor: 'pointer',
                                                        background: schedule.is_active ? 'var(--color-profit)' : 'var(--color-border)',
                                                        position: 'relative',
                                                        transition: 'background 0.2s ease',
                                                    }}
                                                >
                                                    <div style={{
                                                        width: '18px', height: '18px', borderRadius: '50%',
                                                        background: '#fff',
                                                        position: 'absolute', top: '3px',
                                                        left: schedule.is_active ? '23px' : '3px',
                                                        transition: 'left 0.2s ease',
                                                        boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                                                    }} />
                                                </button>
                                            </div>

                                            {/* 中間：投資資訊 */}
                                            <div style={{
                                                display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px',
                                                marginBottom: '14px',
                                            }}>
                                                <div>
                                                    <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '2px', textTransform: 'uppercase' }}>
                                                        投資方式
                                                    </div>
                                                    <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                                                        {schedule.investment_type === 'amount' ? (
                                                            <><DollarSign size={14} style={{ verticalAlign: 'middle', marginRight: '2px' }} />定額</>
                                                        ) : (
                                                            <><TrendingUp size={14} style={{ verticalAlign: 'middle', marginRight: '2px' }} />定股</>
                                                        )}
                                                    </div>
                                                </div>
                                                <div>
                                                    <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '2px', textTransform: 'uppercase' }}>
                                                        {schedule.investment_type === 'amount' ? '每次金額' : '每次股數'}
                                                    </div>
                                                    <div style={{
                                                        fontWeight: 700, fontSize: '0.95rem',
                                                        fontFamily: "'JetBrains Mono', monospace",
                                                        color: 'var(--color-primary)',
                                                    }}>
                                                        {schedule.investment_type === 'amount'
                                                            ? `$${(schedule.target_amount || 0).toLocaleString()}`
                                                            : `${schedule.target_shares || 0} 股`}
                                                    </div>
                                                </div>
                                                <div>
                                                    <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '2px', textTransform: 'uppercase' }}>
                                                        券商
                                                    </div>
                                                    <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>
                                                        {BROKERS.find(b => b.key === schedule.broker)?.label || schedule.broker}
                                                    </div>
                                                </div>
                                                <div>
                                                    <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '2px', textTransform: 'uppercase' }}>
                                                        下次執行
                                                    </div>
                                                    <div style={{ fontWeight: 500, fontSize: '0.85rem' }}>
                                                        {schedule.next_execution_date
                                                            ? new Date(schedule.next_execution_date).toLocaleDateString('zh-TW')
                                                            : '-'}
                                                    </div>
                                                </div>
                                            </div>

                                            {/* 扣款日 */}
                                            <div style={{ marginBottom: '14px' }}>
                                                <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '6px', textTransform: 'uppercase' }}>
                                                    扣款日
                                                </div>
                                                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                                    {schedule.execution_days.map(day => (
                                                        <span key={day} style={{
                                                            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                                                            width: '28px', height: '28px', borderRadius: '50%',
                                                            background: 'rgba(99,102,241,0.12)',
                                                            color: 'var(--color-primary)',
                                                            fontSize: '0.8rem', fontWeight: 700,
                                                        }}>
                                                            {day}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>

                                            {/* 底部：手續費折扣 + 自動確認 + 操作 */}
                                            <div style={{
                                                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                                paddingTop: '12px', borderTop: '1px solid var(--color-border)',
                                            }}>
                                                <div style={{ display: 'flex', gap: '16px', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                                                    <span>手續費 {(schedule.fee_discount * 10).toFixed(0)} 折</span>
                                                    <span>{schedule.auto_confirm ? '🤖 自動確認' : '👤 手動確認'}</span>
                                                </div>
                                                <div style={{ display: 'flex', gap: '4px' }}>
                                                    <button
                                                        onClick={() => openEditModal(schedule)}
                                                        style={iconBtnStyle}
                                                        title="編輯"
                                                    >
                                                        <Edit2 size={15} />
                                                    </button>
                                                    <button
                                                        onClick={() => handleDeleteSchedule(schedule.id)}
                                                        disabled={!!actionLoading[schedule.id]}
                                                        style={{ ...iconBtnStyle, color: 'var(--color-loss)' }}
                                                        title="刪除"
                                                    >
                                                        <Trash2 size={15} />
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </section>

                        {/* ======== 執行歷史 ======== */}
                        <section>
                            <button
                                onClick={() => setShowHistory(!showHistory)}
                                style={{
                                    display: 'flex', alignItems: 'center', gap: '8px',
                                    fontSize: '1.1rem', fontWeight: 700, marginBottom: '16px',
                                    color: 'var(--color-text-primary)',
                                    background: 'none', border: 'none', cursor: 'pointer',
                                    padding: 0,
                                }}
                            >
                                <Clock size={18} style={{ color: 'var(--color-primary)' }} />
                                執行歷史
                                {showHistory ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                            </button>

                            {showHistory && executionHistory && (
                                <>
                                    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                            <thead style={{ borderBottom: '1px solid var(--color-border)' }}>
                                                <tr>
                                                    <th style={thStyle}>日期</th>
                                                    <th style={thStyle}>標的</th>
                                                    <th style={thStyle}>成交價</th>
                                                    <th style={thStyle}>股數</th>
                                                    <th style={thStyle}>手續費</th>
                                                    <th style={thStyle}>總額</th>
                                                    <th style={thStyle}>狀態</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {executionHistory.items.length === 0 ? (
                                                    <tr>
                                                        <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
                                                            暫無執行紀錄
                                                        </td>
                                                    </tr>
                                                ) : (
                                                    executionHistory.items.map((exec) => {
                                                        const badge = getStatusBadge(exec.status);
                                                        return (
                                                            <tr key={exec.id} style={{ borderBottom: '1px solid var(--color-border)', transition: 'background 0.15s ease' }}>
                                                                <td style={tdStyle}>
                                                                    {new Date(exec.execution_date).toLocaleDateString('zh-TW')}
                                                                </td>
                                                                <td style={tdStyle}>
                                                                    <div style={{ fontWeight: 600 }}>{exec.schedule_symbol}</div>
                                                                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>{exec.schedule_asset_name}</div>
                                                                </td>
                                                                <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace" }}>
                                                                    {formatPrice(exec.actual_price || exec.estimated_price)}
                                                                </td>
                                                                <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace" }}>
                                                                    {exec.quantity ?? '-'}
                                                                </td>
                                                                <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace" }}>
                                                                    {formatPrice(exec.fee)}
                                                                </td>
                                                                <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
                                                                    {formatPrice(exec.total_cost)}
                                                                </td>
                                                                <td style={tdStyle}>
                                                                    <span style={{
                                                                        display: 'inline-flex', alignItems: 'center', gap: '4px',
                                                                        padding: '3px 10px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600,
                                                                        background: badge.bg, color: badge.color,
                                                                    }}>
                                                                        {badge.icon} {badge.label}
                                                                    </span>
                                                                </td>
                                                            </tr>
                                                        );
                                                    })
                                                )}
                                            </tbody>
                                        </table>
                                    </div>

                                    {/* 分頁 */}
                                    {executionHistory.total_pages > 1 && (
                                        <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginTop: '16px' }}>
                                            <button
                                                className="btn-secondary"
                                                disabled={historyPage <= 1}
                                                onClick={() => setHistoryPage(p => p - 1)}
                                                style={{ padding: '6px 14px', fontSize: '0.85rem' }}
                                            >上一頁</button>
                                            <span style={{ display: 'flex', alignItems: 'center', padding: '0 12px', fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                                                第 {historyPage} 頁 / 共 {executionHistory.total_pages} 頁
                                            </span>
                                            <button
                                                className="btn-secondary"
                                                disabled={historyPage >= executionHistory.total_pages}
                                                onClick={() => setHistoryPage(p => p + 1)}
                                                style={{ padding: '6px 14px', fontSize: '0.85rem' }}
                                            >下一頁</button>
                                        </div>
                                    )}
                                </>
                            )}
                        </section>
                    </>
                )}
            </main>

            {/* ======== 匯入資料 Modal ======== */}
            {showImportModal && (
                <div style={{
                    position: 'fixed', inset: 0,
                    background: 'rgba(0,0,0,0.6)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    zIndex: 200, backdropFilter: 'blur(6px)',
                }} onClick={() => { setShowImportModal(false); resetImportForm(); }}>
                    <div className="card-glass" style={{
                        maxWidth: '540px', width: '95%', maxHeight: '90vh', overflowY: 'auto',
                    }} onClick={(e) => e.stopPropagation()}>
                        <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <Upload size={20} style={{ color: 'var(--color-primary)' }} />
                            匯入定期定額資料
                        </h3>

                        {/* 範本下載 + 欄位說明 */}
                        <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', flexWrap: 'wrap' }}>
                            <a
                                href={apiClient.getDCATemplateUrl()}
                                download="dca_import_template.csv"
                                style={{
                                    display: 'inline-flex', alignItems: 'center', gap: '6px',
                                    fontSize: '0.85rem', color: 'var(--color-primary)',
                                    textDecoration: 'none',
                                }}
                            >
                                <Download size={14} /> 下載 CSV 範本
                            </a>
                            <button
                                type="button"
                                onClick={() => setShowColumnHelp(!showColumnHelp)}
                                style={{
                                    display: 'inline-flex', alignItems: 'center', gap: '6px',
                                    fontSize: '0.85rem', color: 'var(--color-text-secondary)',
                                    background: 'none', border: 'none', cursor: 'pointer', padding: 0,
                                }}
                            >
                                <HelpCircle size={14} /> 支援欄位對照
                                {showColumnHelp ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            </button>
                        </div>

                        {/* 欄位對照提示 */}
                        {showColumnHelp && (
                            <div style={{
                                marginBottom: '16px', borderRadius: '10px',
                                border: '1px solid var(--color-border)',
                                background: 'var(--color-bg-secondary)',
                                maxHeight: '220px', overflowY: 'auto',
                            }}>
                                {importColumns.length === 0 ? (
                                    <div style={{ padding: '12px', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                                        欄位對照載入中...
                                    </div>
                                ) : (
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
                                        <thead>
                                            <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                                                <th style={helpThStyle}>欄位</th>
                                                <th style={helpThStyle}>可用名稱（別名）</th>
                                                <th style={helpThStyle}>說明</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {importColumns.map(col => (
                                                <tr key={col.key} style={{ borderBottom: '1px solid var(--color-border)' }}>
                                                    <td style={{ ...helpTdStyle, whiteSpace: 'nowrap', fontWeight: 600 }}>
                                                        {col.label}
                                                        {col.required && <span style={{ color: 'var(--color-loss)' }}> *</span>}
                                                    </td>
                                                    <td style={{ ...helpTdStyle, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.72rem' }}>
                                                        {col.aliases.join('、')}
                                                    </td>
                                                    <td style={helpTdStyle}>{col.description}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                )}
                            </div>
                        )}

                        <div style={{ marginBottom: '16px' }}>
                            <label style={labelStyle}>CSV 檔案 *</label>
                            <input
                                className="input-field"
                                type="file"
                                accept=".csv,text/csv"
                                onChange={(e) => { setImportFile(e.target.files?.[0] || null); invalidateImportPreview(); }}
                            />
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                            <div>
                                <label style={labelStyle}>匯入格式</label>
                                <select
                                    className="input-field"
                                    value={importBrokerFormat}
                                    onChange={(e) => { setImportBrokerFormat(e.target.value); invalidateImportPreview(); }}
                                >
                                    <option value="standard">標準格式</option>
                                    <option value="sinopac">永豐格式</option>
                                </select>
                            </div>
                            <div>
                                <label style={labelStyle}>券商</label>
                                <select
                                    className="input-field"
                                    value={importBroker}
                                    onChange={(e) => { setImportBroker(e.target.value); invalidateImportPreview(); }}
                                >
                                    {BROKERS.map(b => (
                                        <option key={b.key} value={b.key} disabled={!b.enabled}>
                                            {b.label}{!b.enabled ? ' (即將支援)' : ''}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        </div>

                        <div style={{ marginBottom: '16px' }}>
                            <label style={labelStyle}>預設資產類別</label>
                            <select
                                className="input-field"
                                value={importCategoryId}
                                onChange={(e) => { setImportCategoryId(parseInt(e.target.value)); invalidateImportPreview(); }}
                            >
                                {CATEGORIES.map(c => (
                                    <option key={c.id} value={c.id}>{c.label}</option>
                                ))}
                            </select>
                        </div>

                        <div style={{
                            display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px',
                            padding: '12px 16px', background: 'var(--color-bg-secondary)', borderRadius: '10px',
                        }}>
                            <button
                                type="button"
                                onClick={() => { setImportAutoConfirm(!importAutoConfirm); invalidateImportPreview(); }}
                                style={{
                                    width: '20px', height: '20px', borderRadius: '4px',
                                    border: `2px solid ${importAutoConfirm ? 'var(--color-primary)' : 'var(--color-border)'}`,
                                    background: importAutoConfirm ? 'var(--color-primary)' : 'transparent',
                                    cursor: 'pointer',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    transition: 'all 0.2s ease',
                                }}
                            >
                                {importAutoConfirm && <Check size={14} style={{ color: 'var(--color-primary-text)' }} />}
                            </button>
                            <div>
                                <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>匯入後直接入帳</div>
                                <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                                    重複匯入同一天資料會更新既有交易，不會重複新增
                                </div>
                            </div>
                        </div>

                        {importError && (
                            <div style={{
                                padding: '10px 14px', borderRadius: '8px', marginBottom: '12px',
                                background: 'var(--color-loss-bg)', color: 'var(--color-loss)', fontSize: '0.9rem',
                                display: 'flex', alignItems: 'center', gap: '6px',
                            }}>
                                <AlertCircle size={14} /> {importError}
                            </div>
                        )}

                        {/* 匯入預覽（dry-run）結果 */}
                        {importPreview && !importResult && (
                            <div style={{
                                padding: '12px 14px', borderRadius: '10px', marginBottom: '14px',
                                background: 'var(--color-bg-secondary)', border: '1px solid var(--color-primary)',
                                fontSize: '0.85rem', color: 'var(--color-text-secondary)',
                            }}>
                                <div style={{
                                    fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '8px',
                                    display: 'flex', alignItems: 'center', gap: '6px',
                                }}>
                                    <Eye size={14} style={{ color: 'var(--color-primary)' }} />
                                    匯入預覽（尚未寫入資料）
                                </div>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 12px', marginBottom: '10px' }}>
                                    <span>可匯入 {importPreview.imported} 筆</span>
                                    <span style={{ color: importPreview.skipped > 0 ? 'var(--color-loss)' : undefined }}>
                                        有問題 {importPreview.skipped} 筆
                                    </span>
                                    <span>計畫新增 {importPreview.schedules_created} 筆</span>
                                    <span>計畫更新 {importPreview.schedules_updated} 筆</span>
                                    <span>執行新增 {importPreview.executions_created} 筆</span>
                                    <span>執行更新 {importPreview.executions_updated} 筆</span>
                                    <span>交易新增 {importPreview.transactions_created} 筆</span>
                                    <span>交易更新 {importPreview.transactions_updated} 筆</span>
                                </div>

                                {(importPreview.details?.length ?? 0) > 0 && (
                                    <div style={{
                                        maxHeight: '200px', overflowY: 'auto',
                                        border: '1px solid var(--color-border)', borderRadius: '8px',
                                        marginBottom: importPreview.errors.length > 0 ? '10px' : 0,
                                    }}>
                                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
                                            <thead>
                                                <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                                                    <th style={helpThStyle}>列</th>
                                                    <th style={helpThStyle}>標的</th>
                                                    <th style={helpThStyle}>日期</th>
                                                    <th style={helpThStyle}>股數</th>
                                                    <th style={helpThStyle}>總額</th>
                                                    <th style={helpThStyle}>計畫</th>
                                                    <th style={helpThStyle}>執行</th>
                                                    <th style={helpThStyle}>交易</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {importPreview.details!.map((d) => (
                                                    <tr key={d.row} style={{
                                                        borderBottom: '1px solid var(--color-border)',
                                                        color: d.status === 'error' ? 'var(--color-loss)' : undefined,
                                                    }}>
                                                        <td style={helpTdStyle}>{d.row}</td>
                                                        <td style={{ ...helpTdStyle, fontWeight: 600 }}>{d.symbol || '-'}</td>
                                                        <td style={{ ...helpTdStyle, whiteSpace: 'nowrap' }}>{d.execution_date || '-'}</td>
                                                        <td style={helpTdStyle}>{d.quantity ?? '-'}</td>
                                                        <td style={helpTdStyle}>{d.total_cost ?? '-'}</td>
                                                        {d.status === 'error' ? (
                                                            <td style={helpTdStyle} colSpan={3}>{d.error || '匯入失敗'}</td>
                                                        ) : (
                                                            <>
                                                                <td style={helpTdStyle}>{IMPORT_ACTION_LABELS[d.schedule_action] || d.schedule_action}</td>
                                                                <td style={helpTdStyle}>{IMPORT_ACTION_LABELS[d.execution_action] || d.execution_action}</td>
                                                                <td style={helpTdStyle}>{IMPORT_ACTION_LABELS[d.transaction_action] || d.transaction_action}</td>
                                                            </>
                                                        )}
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}

                                {importPreview.errors.length > 0 && (
                                    <div style={{
                                        color: 'var(--color-loss)', maxHeight: '120px', overflowY: 'auto',
                                        display: 'flex', flexDirection: 'column', gap: '2px',
                                    }}>
                                        <div style={{ fontWeight: 600 }}>錯誤明細（{importPreview.errors.length} 筆）</div>
                                        {importPreview.errors.map((item, idx) => (
                                            <div key={idx}>{item}</div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}

                        {importResult && (
                            <div style={{
                                padding: '12px 14px', borderRadius: '10px', marginBottom: '14px',
                                background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)',
                                fontSize: '0.85rem', color: 'var(--color-text-secondary)',
                            }}>
                                <div style={{ fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '8px' }}>
                                    匯入結果
                                </div>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 12px' }}>
                                    <span>成功 {importResult.imported} 筆</span>
                                    <span>略過 {importResult.skipped} 筆</span>
                                    <span>計畫新增 {importResult.schedules_created} 筆</span>
                                    <span>計畫更新 {importResult.schedules_updated} 筆</span>
                                    <span>執行新增 {importResult.executions_created} 筆</span>
                                    <span>執行更新 {importResult.executions_updated} 筆</span>
                                    <span>交易新增 {importResult.transactions_created} 筆</span>
                                    <span>交易更新 {importResult.transactions_updated} 筆</span>
                                </div>
                                {importResult.errors.length > 0 && (
                                    <div style={{
                                        marginTop: '10px', color: 'var(--color-loss)',
                                        maxHeight: '120px', overflowY: 'auto',
                                        display: 'flex', flexDirection: 'column', gap: '2px',
                                    }}>
                                        <div style={{ fontWeight: 600 }}>錯誤明細（{importResult.errors.length} 筆）</div>
                                        {importResult.errors.map((item, idx) => (
                                            <div key={idx}>{item}</div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}

                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                            <button className="btn-secondary" onClick={() => { setShowImportModal(false); resetImportForm(); }}>
                                關閉
                            </button>
                            <button
                                className="btn-secondary"
                                onClick={handleImportPreview}
                                disabled={previewLoading || importLoading || !importFile}
                                style={{
                                    opacity: (previewLoading || importLoading || !importFile) ? 0.6 : 1,
                                    minWidth: '96px',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                                }}
                            >
                                {previewLoading ? (
                                    <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                                ) : (
                                    <><Eye size={16} /> 預覽</>
                                )}
                            </button>
                            <button
                                className="btn-primary"
                                onClick={handleImportSubmit}
                                disabled={importLoading || previewLoading}
                                style={{ opacity: (importLoading || previewLoading) ? 0.6 : 1, minWidth: '120px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                            >
                                {importLoading ? (
                                    <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                                ) : (
                                    <><Upload size={16} /> {importPreview ? '確認匯入' : '開始匯入'}</>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* ======== 新增/編輯計畫 Modal ======== */}
            {showModal && (
                <div style={{
                    position: 'fixed', inset: 0,
                    background: 'rgba(0,0,0,0.6)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    zIndex: 200, backdropFilter: 'blur(6px)',
                }} onClick={() => { setShowModal(false); resetForm(); }}>
                    <div className="card-glass" style={{
                        maxWidth: '520px', width: '95%', maxHeight: '90vh', overflowY: 'auto',
                    }} onClick={(e) => e.stopPropagation()}>
                        <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <Calendar size={20} style={{ color: 'var(--color-primary)' }} />
                            {editingSchedule ? '編輯定期定額計畫' : '新增定期定額計畫'}
                        </h3>

                        {/* 標的搜尋 */}
                        <div style={{ position: 'relative', marginBottom: '16px' }}>
                            <label style={labelStyle}>標的代碼 *</label>
                            <div style={{ position: 'relative' }}>
                                <input
                                    className="input-field"
                                    placeholder="搜尋標的代碼，如 2330, AAPL"
                                    value={formSymbol}
                                    onChange={(e) => {
                                        setFormSymbol(e.target.value.toUpperCase());
                                        setShowSuggestions(true);
                                    }}
                                    onFocus={() => setShowSuggestions(true)}
                                    onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                                    style={{ paddingLeft: '36px' }}
                                />
                                <Search size={16} style={{
                                    position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)',
                                    color: 'var(--color-text-muted)',
                                }} />
                            </div>
                            {showSuggestions && (searchResults.length > 0 || isSearching) && (
                                <div style={{
                                    position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0,
                                    background: 'var(--color-bg-card)', border: '1px solid var(--color-border)',
                                    borderRadius: '10px', zIndex: 50, maxHeight: '200px', overflowY: 'auto',
                                    boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
                                }}>
                                    {isSearching ? (
                                        <div style={{ padding: '12px', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>
                                            <Loader2 size={16} style={{ animation: 'spin 1s linear infinite', verticalAlign: 'middle', marginRight: '6px' }} />
                                            搜尋中...
                                        </div>
                                    ) : (
                                        searchResults.map(asset => (
                                            <div
                                                key={asset.symbol}
                                                style={{
                                                    padding: '10px 14px', cursor: 'pointer',
                                                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                                    borderBottom: '1px solid var(--color-border)',
                                                    transition: 'background 0.15s ease',
                                                }}
                                                onMouseEnter={(e) => e.currentTarget.style.background = 'var(--color-bg-card-hover)'}
                                                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                                                onClick={() => {
                                                    setFormSymbol(asset.symbol);
                                                    setFormAssetName(asset.name);
                                                    setShowSuggestions(false);
                                                    // 自動切換資產類別
                                                    if (asset.category_slug) {
                                                        const cat = CATEGORIES.find(c => c.slug === asset.category_slug);
                                                        if (cat) setFormCategoryId(cat.id);
                                                    }
                                                }}
                                            >
                                                <div>
                                                    <span style={{ fontWeight: 600 }}>{asset.symbol}</span>
                                                    <span style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', marginLeft: '8px' }}>{asset.name}</span>
                                                </div>
                                                {asset.type_box && (
                                                    <span style={{
                                                        fontSize: '0.7rem', color: 'var(--color-text-secondary)',
                                                        background: 'var(--color-bg-secondary)', padding: '2px 6px', borderRadius: '4px',
                                                    }}>
                                                        {asset.type_box}
                                                    </span>
                                                )}
                                            </div>
                                        ))
                                    )}
                                </div>
                            )}
                        </div>

                        {/* 標的名稱 + 資產類別 */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                            <div>
                                <label style={labelStyle}>標的名稱</label>
                                <input
                                    className="input-field"
                                    placeholder="如 台積電"
                                    value={formAssetName}
                                    onChange={(e) => setFormAssetName(e.target.value)}
                                />
                            </div>
                            <div>
                                <label style={labelStyle}>資產類別</label>
                                <select
                                    className="input-field"
                                    value={formCategoryId}
                                    onChange={(e) => setFormCategoryId(parseInt(e.target.value))}
                                >
                                    {CATEGORIES.map(c => (
                                        <option key={c.id} value={c.id}>{c.label}</option>
                                    ))}
                                </select>
                            </div>
                        </div>

                        {/* 投資方式 Tab */}
                        <label style={labelStyle}>投資方式 *</label>
                        <div style={{
                            display: 'flex', marginBottom: '12px',
                            background: 'var(--color-bg-secondary)', borderRadius: '10px',
                            overflow: 'hidden', border: '1px solid var(--color-border)',
                        }}>
                            <button
                                style={{
                                    flex: 1, padding: '10px', border: 'none', cursor: 'pointer',
                                    background: formInvestmentType === 'amount' ? 'var(--color-primary)' : 'transparent',
                                    color: formInvestmentType === 'amount' ? 'var(--color-primary-text)' : 'var(--color-text-secondary)',
                                    fontWeight: formInvestmentType === 'amount' ? 700 : 400,
                                    fontSize: '0.9rem', transition: 'all 0.2s ease',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                                }}
                                onClick={() => setFormInvestmentType('amount')}
                            >
                                <DollarSign size={16} /> 定額投資
                            </button>
                            <button
                                style={{
                                    flex: 1, padding: '10px', border: 'none', cursor: 'pointer',
                                    background: formInvestmentType === 'shares' ? 'var(--color-primary)' : 'transparent',
                                    color: formInvestmentType === 'shares' ? 'var(--color-primary-text)' : 'var(--color-text-secondary)',
                                    fontWeight: formInvestmentType === 'shares' ? 700 : 400,
                                    fontSize: '0.9rem', transition: 'all 0.2s ease',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                                }}
                                onClick={() => setFormInvestmentType('shares')}
                            >
                                <TrendingUp size={16} /> 定股投資
                            </button>
                        </div>

                        {/* 金額/股數 */}
                        <div style={{ marginBottom: '16px' }}>
                            {formInvestmentType === 'amount' ? (
                                <div>
                                    <label style={labelStyle}>每次投資金額 (TWD) *</label>
                                    <input
                                        className="input-field"
                                        type="number"
                                        step="100"
                                        placeholder="如 3000"
                                        value={formTargetAmount}
                                        onChange={(e) => setFormTargetAmount(e.target.value)}
                                    />
                                </div>
                            ) : (
                                <div>
                                    <label style={labelStyle}>每次投資股數 *</label>
                                    <input
                                        className="input-field"
                                        type="number"
                                        step="any"
                                        placeholder="如 1"
                                        value={formTargetShares}
                                        onChange={(e) => setFormTargetShares(e.target.value)}
                                    />
                                </div>
                            )}
                        </div>

                        {/* 扣款日多選 */}
                        <label style={labelStyle}>扣款日 * (可多選)</label>
                        <div style={{
                            display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px',
                        }}>
                            {EXECUTION_DAY_OPTIONS.map(day => {
                                const selected = formExecutionDays.includes(day);
                                return (
                                    <button
                                        key={day}
                                        type="button"
                                        onClick={() => toggleExecutionDay(day)}
                                        style={{
                                            width: '42px', height: '42px', borderRadius: '50%',
                                            border: selected ? '2px solid var(--color-primary)' : '1px solid var(--color-border)',
                                            background: selected ? 'rgba(99,102,241,0.15)' : 'var(--color-bg-secondary)',
                                            color: selected ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                                            fontSize: '0.9rem', fontWeight: selected ? 700 : 500,
                                            cursor: 'pointer',
                                            transition: 'all 0.2s ease',
                                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        }}
                                    >
                                        {day}
                                    </button>
                                );
                            })}
                        </div>

                        {/* 券商 + 手續費折扣 */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                            <div>
                                <label style={labelStyle}>券商</label>
                                <select
                                    className="input-field"
                                    value={formBroker}
                                    onChange={(e) => setFormBroker(e.target.value)}
                                >
                                    {BROKERS.map(b => (
                                        <option key={b.key} value={b.key} disabled={!b.enabled}>
                                            {b.label}{!b.enabled ? ' (即將支援)' : ''}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label style={labelStyle}>手續費折扣</label>
                                <input
                                    className="input-field"
                                    type="number"
                                    step="0.01"
                                    min="0"
                                    max="1"
                                    placeholder="0.1 = 1折"
                                    value={formFeeDiscount}
                                    onChange={(e) => setFormFeeDiscount(e.target.value)}
                                />
                                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                                    {formFeeDiscount ? `= ${(parseFloat(formFeeDiscount) * 10).toFixed(0)} 折` : '0.1 表示 1 折'}
                                </div>
                            </div>
                        </div>

                        {/* 自動確認 */}
                        <div style={{
                            display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px',
                            padding: '12px 16px', background: 'var(--color-bg-secondary)', borderRadius: '10px',
                        }}>
                            <button
                                type="button"
                                onClick={() => setFormAutoConfirm(!formAutoConfirm)}
                                style={{
                                    width: '20px', height: '20px', borderRadius: '4px',
                                    border: `2px solid ${formAutoConfirm ? 'var(--color-primary)' : 'var(--color-border)'}`,
                                    background: formAutoConfirm ? 'var(--color-primary)' : 'transparent',
                                    cursor: 'pointer',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    transition: 'all 0.2s ease',
                                }}
                            >
                                {formAutoConfirm && <Check size={14} style={{ color: 'var(--color-primary-text)' }} />}
                            </button>
                            <div>
                                <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>自動確認入帳</div>
                                <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                                    開啟後將自動確認交易，無需手動操作
                                </div>
                            </div>
                        </div>

                        {/* 錯誤訊息 */}
                        {formError && (
                            <div style={{
                                padding: '10px 14px', borderRadius: '8px', marginBottom: '12px',
                                background: 'var(--color-loss-bg)', color: 'var(--color-loss)', fontSize: '0.9rem',
                                display: 'flex', alignItems: 'center', gap: '6px',
                            }}>
                                <AlertCircle size={14} /> {formError}
                            </div>
                        )}

                        {/* 按鈕 */}
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                            <button className="btn-secondary" onClick={() => { setShowModal(false); resetForm(); }}>
                                取消
                            </button>
                            <button
                                className="btn-primary"
                                onClick={handleFormSubmit}
                                disabled={formLoading}
                                style={{ opacity: formLoading ? 0.6 : 1, minWidth: '120px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                            >
                                {formLoading ? (
                                    <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                                ) : (
                                    editingSchedule ? '更新計畫' : '建立計畫'
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

// === 共用樣式 ===
const labelStyle: React.CSSProperties = {
    display: 'block',
    color: 'var(--color-text-muted)',
    fontSize: '0.8rem',
    fontWeight: 600,
    marginBottom: '6px',
    textTransform: 'uppercase',
    letterSpacing: '0.03em',
};

const thStyle: React.CSSProperties = {
    padding: '14px 16px',
    textAlign: 'left',
    color: 'var(--color-text-muted)',
    fontSize: '0.8rem',
    fontWeight: 600,
    whiteSpace: 'nowrap',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
};

const tdStyle: React.CSSProperties = {
    padding: '14px 16px',
    fontSize: '0.9rem',
    whiteSpace: 'nowrap',
};

const helpThStyle: React.CSSProperties = {
    padding: '8px 10px',
    textAlign: 'left',
    color: 'var(--color-text-muted)',
    fontWeight: 600,
    whiteSpace: 'nowrap',
    position: 'sticky',
    top: 0,
    background: 'var(--color-bg-secondary)',
};

const helpTdStyle: React.CSSProperties = {
    padding: '7px 10px',
    verticalAlign: 'top',
    color: 'var(--color-text-secondary)',
};

const iconBtnStyle: React.CSSProperties = {
    background: 'none',
    border: '1px solid var(--color-border)',
    borderRadius: '8px',
    padding: '6px',
    cursor: 'pointer',
    color: 'var(--color-text-secondary)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.15s ease',
};
