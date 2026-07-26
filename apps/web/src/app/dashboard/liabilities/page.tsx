'use client';

/**
 * 負債管理頁面
 *
 * 負債列表（還款進度條）、新增負債 Modal、記錄還款 Modal
 */

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import apiClient from '@/lib/api-client';
import type { Liability } from '@/lib/api-client';
import { usePortfolioStore } from '@/stores/portfolio-store';
import {
    ArrowLeft, Plus, Trash2, Banknote, CalendarClock,
    CheckCircle2, ChevronDown, ChevronUp, Loader2,
} from 'lucide-react';

const CYCLE_LABELS: Record<string, string> = {
    weekly: '每週',
    biweekly: '每兩週',
    monthly: '每月',
    quarterly: '每季',
};

export default function LiabilitiesPage() {
    const router = useRouter();
    const { selectedPortfolio, fetchPortfolios, refreshAll } = usePortfolioStore();

    const [liabilities, setLiabilities] = useState<Liability[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState('');
    const [successMsg, setSuccessMsg] = useState('');
    const [expandedId, setExpandedId] = useState<string | null>(null);

    // 新增負債 Modal
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [formName, setFormName] = useState('');
    const [formPrincipal, setFormPrincipal] = useState('');
    const [formCycle, setFormCycle] = useState<'weekly' | 'biweekly' | 'monthly' | 'quarterly'>('monthly');
    const [formPeriods, setFormPeriods] = useState('');
    const [formAmount, setFormAmount] = useState('');
    const [formPaymentDay, setFormPaymentDay] = useState('');
    const [formStartDate, setFormStartDate] = useState('');
    const [formNote, setFormNote] = useState('');
    const [formLoading, setFormLoading] = useState(false);
    const [formError, setFormError] = useState('');

    // 記錄還款 Modal
    const [payingLiability, setPayingLiability] = useState<Liability | null>(null);
    const [payAmount, setPayAmount] = useState('');
    const [payDate, setPayDate] = useState(new Date().toISOString().slice(0, 10));
    const [payNote, setPayNote] = useState('');
    const [payLoading, setPayLoading] = useState(false);
    const [payError, setPayError] = useState('');

    const fetchLiabilities = useCallback(async () => {
        if (!selectedPortfolio) return;
        setIsLoading(true);
        try {
            const data = await apiClient.getLiabilities(selectedPortfolio.id);
            setLiabilities(data);
            setError('');
        } catch (err) {
            console.error('載入負債資料失敗:', err);
            setError('載入資料失敗，請稍後重試');
        } finally {
            setIsLoading(false);
        }
    }, [selectedPortfolio]);

    useEffect(() => {
        if (!apiClient.isAuthenticated()) {
            router.push('/');
            return;
        }
        if (!selectedPortfolio) fetchPortfolios();
    }, []);

    useEffect(() => {
        fetchLiabilities();
    }, [fetchLiabilities]);

    const flash = (msg: string) => {
        setSuccessMsg(msg);
        setTimeout(() => setSuccessMsg(''), 2500);
    };

    const resetForm = () => {
        setFormName('');
        setFormPrincipal('');
        setFormCycle('monthly');
        setFormPeriods('');
        setFormAmount('');
        setFormPaymentDay('');
        setFormStartDate('');
        setFormNote('');
        setFormError('');
    };

    const handleCreate = async () => {
        if (!selectedPortfolio) return;
        if (!formName.trim() || !formPrincipal || !formPeriods || !formAmount) {
            setFormError('請填寫名稱、總金額、期數與每期金額');
            return;
        }
        setFormLoading(true);
        setFormError('');
        try {
            await apiClient.createLiability({
                portfolio_id: selectedPortfolio.id,
                name: formName.trim(),
                principal: parseFloat(formPrincipal),
                payment_cycle: formCycle,
                total_periods: parseInt(formPeriods, 10),
                payment_amount: parseFloat(formAmount),
                payment_day: formPaymentDay ? parseInt(formPaymentDay, 10) : undefined,
                start_date: formStartDate || undefined,
                note: formNote || undefined,
            });
            setShowCreateModal(false);
            resetForm();
            flash('✅ 負債已建立');
            await Promise.all([fetchLiabilities(), refreshAll()]);
        } catch (err) {
            setFormError((err as Error).message);
        } finally {
            setFormLoading(false);
        }
    };

    const openPayModal = (li: Liability) => {
        setPayingLiability(li);
        setPayAmount(String(li.payment_amount));
        setPayDate(new Date().toISOString().slice(0, 10));
        setPayNote('');
        setPayError('');
    };

    const handlePay = async () => {
        if (!payingLiability) return;
        const amount = parseFloat(payAmount);
        if (isNaN(amount) || amount <= 0) {
            setPayError('金額必須大於 0');
            return;
        }
        setPayLoading(true);
        setPayError('');
        try {
            await apiClient.recordLiabilityPayment(payingLiability.id, {
                amount,
                payment_date: payDate || undefined,
                note: payNote || undefined,
            });
            setPayingLiability(null);
            flash('✅ 還款已記錄');
            await Promise.all([fetchLiabilities(), refreshAll()]);
        } catch (err) {
            setPayError((err as Error).message);
        } finally {
            setPayLoading(false);
        }
    };

    const handleDelete = async (li: Liability) => {
        if (!confirm(`確定刪除負債「${li.name}」？\n（交易紀錄與持倉會保留，只移除負債設定與還款紀錄）`)) return;
        try {
            await apiClient.deleteLiability(li.id);
            flash('已刪除');
            await fetchLiabilities();
        } catch (err) {
            setError((err as Error).message);
        }
    };

    const handleDeletePayment = async (li: Liability, paymentId: string) => {
        if (!confirm('確定刪除這筆還款紀錄？餘額會自動回補。')) return;
        try {
            await apiClient.deleteLiabilityPayment(li.id, paymentId);
            flash('還款紀錄已刪除');
            await Promise.all([fetchLiabilities(), refreshAll()]);
        } catch (err) {
            setError((err as Error).message);
        }
    };

    const fmtMoney = (v: number, currency: string) =>
        `${currency === 'USD' ? '$' : 'NT$'} ${Number(v).toLocaleString('zh-TW', { maximumFractionDigits: 0 })}`;

    return (
        <div style={{ minHeight: '100vh', background: 'var(--color-bg-primary)' }}>
            {/* 頂部導覽 */}
            <header style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '16px 32px', borderBottom: '1px solid var(--color-border)',
                background: 'var(--color-bg-secondary)', position: 'sticky', top: 0, zIndex: 100,
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <button className="btn-secondary" style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}
                        onClick={() => router.push('/dashboard')}>
                        <ArrowLeft size={15} /> 返回
                    </button>
                    <h1 style={{ fontSize: '1.2rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                        💳 負債管理
                    </h1>
                </div>
                <button className="btn-primary" style={{ padding: '8px 16px', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '6px' }}
                    onClick={() => { resetForm(); setShowCreateModal(true); }}>
                    <Plus size={15} /> 新增負債
                </button>
            </header>

            <main style={{ padding: '24px 32px', maxWidth: '1000px', margin: '0 auto' }}>
                {successMsg && (
                    <div style={{
                        padding: '10px 14px', borderRadius: '8px', marginBottom: '16px',
                        background: 'var(--color-profit-bg)', color: 'var(--color-profit)', fontSize: '0.9rem',
                    }}>{successMsg}</div>
                )}
                {error && (
                    <div style={{
                        padding: '10px 14px', borderRadius: '8px', marginBottom: '16px',
                        background: 'var(--color-loss-bg)', color: 'var(--color-loss)', fontSize: '0.9rem',
                    }}>{error}</div>
                )}

                {isLoading ? (
                    <div style={{ textAlign: 'center', padding: '60px', color: 'var(--color-text-muted)' }}>
                        <Loader2 size={28} style={{ animation: 'spin 1s linear infinite' }} />
                        <p style={{ marginTop: '12px' }}>載入中...</p>
                    </div>
                ) : liabilities.length === 0 ? (
                    <div className="card" style={{ padding: '60px', textAlign: 'center' }}>
                        <p style={{ fontSize: '2.5rem', marginBottom: '12px' }}>💳</p>
                        <p style={{ color: 'var(--color-text-muted)', fontSize: '1.05rem', marginBottom: '20px' }}>
                            尚未設定任何負債
                        </p>
                        <button className="btn-primary" onClick={() => { resetForm(); setShowCreateModal(true); }}>
                            + 新增第一筆負債
                        </button>
                    </div>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        {liabilities.map((li) => {
                            const isExpanded = expandedId === li.id;
                            const progress = Math.min(100, Math.max(0, li.progress_pct));
                            return (
                                <div key={li.id} className="card" style={{ padding: '20px 24px' }}>
                                    {/* 標題列 */}
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                                        <div>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                                <span style={{ fontSize: '1.05rem', fontWeight: 700 }}>{li.name}</span>
                                                {!li.is_active && (
                                                    <span style={{
                                                        fontSize: '0.7rem', padding: '2px 8px', borderRadius: '10px',
                                                        background: 'rgba(34,197,94,0.15)', color: '#22c55e', fontWeight: 600,
                                                        display: 'inline-flex', alignItems: 'center', gap: '4px',
                                                    }}>
                                                        <CheckCircle2 size={11} /> 已結清
                                                    </span>
                                                )}
                                            </div>
                                            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                                                {CYCLE_LABELS[li.payment_cycle]}還 {fmtMoney(li.payment_amount, li.currency)}
                                                ・共 {li.total_periods} 期
                                                {li.next_payment_date && li.is_active && (
                                                    <span> ・下次繳款 {li.next_payment_date}</span>
                                                )}
                                            </div>
                                        </div>
                                        <div style={{ display: 'flex', gap: '8px' }}>
                                            {li.is_active && (
                                                <button className="btn-primary" style={{ padding: '6px 14px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '5px' }}
                                                    onClick={() => openPayModal(li)}>
                                                    <Banknote size={14} /> 記錄還款
                                                </button>
                                            )}
                                            <button className="btn-secondary" style={{ padding: '6px 10px', fontSize: '0.8rem' }}
                                                onClick={() => handleDelete(li)}>
                                                <Trash2 size={14} />
                                            </button>
                                        </div>
                                    </div>

                                    {/* 進度條 */}
                                    <div style={{ marginBottom: '10px' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '6px' }}>
                                            <span style={{ color: 'var(--color-text-muted)' }}>
                                                已還 {li.paid_periods}/{li.total_periods} 期・{fmtMoney(li.paid_amount, li.currency)}
                                            </span>
                                            <span style={{ fontWeight: 700, color: progress >= 100 ? '#22c55e' : 'var(--color-primary)' }}>
                                                {progress.toFixed(1)}%
                                            </span>
                                        </div>
                                        <div style={{
                                            height: '10px', borderRadius: '6px', overflow: 'hidden',
                                            background: 'rgba(255,255,255,0.07)',
                                        }}>
                                            <div style={{
                                                width: `${progress}%`, height: '100%', borderRadius: '6px',
                                                background: progress >= 100
                                                    ? 'linear-gradient(90deg, #22c55e, #16a34a)'
                                                    : 'linear-gradient(90deg, #6366f1, #a855f7)',
                                                transition: 'width 0.4s ease',
                                            }} />
                                        </div>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginTop: '6px' }}>
                                            <span style={{ color: 'var(--color-text-muted)' }}>
                                                剩餘 <span style={{ color: 'var(--color-loss)', fontWeight: 700 }}>{fmtMoney(li.outstanding_balance, li.currency)}</span>
                                            </span>
                                            <span style={{ color: 'var(--color-text-muted)' }}>
                                                總額 {fmtMoney(li.principal, li.currency)}
                                            </span>
                                        </div>
                                    </div>

                                    {/* 還款歷史（展開） */}
                                    <button
                                        onClick={() => setExpandedId(isExpanded ? null : li.id)}
                                        style={{
                                            background: 'none', border: 'none', cursor: 'pointer',
                                            color: 'var(--color-text-muted)', fontSize: '0.78rem',
                                            display: 'flex', alignItems: 'center', gap: '4px', padding: 0,
                                        }}>
                                        {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                                        還款紀錄（{li.payments.length}）
                                    </button>
                                    {isExpanded && (
                                        <div style={{ marginTop: '10px', borderTop: '1px solid var(--color-border)', paddingTop: '10px' }}>
                                            {li.payments.length === 0 ? (
                                                <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>尚無還款紀錄</p>
                                            ) : (
                                                [...li.payments].reverse().map((p, idx) => (
                                                    <div key={p.id} style={{
                                                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                                        padding: '6px 0', fontSize: '0.82rem',
                                                        borderBottom: '1px solid rgba(255,255,255,0.04)',
                                                    }}>
                                                        <span style={{ color: 'var(--color-text-muted)' }}>
                                                            第 {li.payments.length - idx} 期・{p.payment_date}
                                                            {p.note && <span style={{ marginLeft: '8px', fontSize: '0.72rem' }}>({p.note})</span>}
                                                        </span>
                                                        <span style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                                            <span className="number" style={{ fontWeight: 600 }}>{fmtMoney(p.amount, li.currency)}</span>
                                                            <button onClick={() => handleDeletePayment(li, p.id)} style={{
                                                                background: 'none', border: 'none', cursor: 'pointer',
                                                                color: 'var(--color-text-muted)', padding: '2px',
                                                            }}>
                                                                <Trash2 size={12} />
                                                            </button>
                                                        </span>
                                                    </div>
                                                ))
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </main>

            {/* ====== 新增負債 Modal ====== */}
            {showCreateModal && (
                <div style={{
                    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    zIndex: 200, backdropFilter: 'blur(6px)',
                }} onClick={() => setShowCreateModal(false)}>
                    <div className="card-glass" style={{ maxWidth: '480px', width: '100%', maxHeight: '90vh', overflowY: 'auto' }}
                        onClick={(e) => e.stopPropagation()}>
                        <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '20px' }}>💳 新增負債</h3>

                        <label style={labelStyle}>名稱 *</label>
                        <input className="input-field" placeholder="如 房貸、車貸、學貸" style={{ marginBottom: '12px' }}
                            value={formName} onChange={(e) => setFormName(e.target.value)} />

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                            <div>
                                <label style={labelStyle}>負債總額 *</label>
                                <input className="input-field" type="number" step="any" min="0" placeholder="如 5000000"
                                    value={formPrincipal} onChange={(e) => setFormPrincipal(e.target.value)} />
                            </div>
                            <div>
                                <label style={labelStyle}>每期還款金額 *</label>
                                <input className="input-field" type="number" step="any" min="0" placeholder="如 25000"
                                    value={formAmount} onChange={(e) => setFormAmount(e.target.value)} />
                            </div>
                        </div>

                        <label style={labelStyle}>還款週期</label>
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '12px' }}>
                            {(Object.keys(CYCLE_LABELS) as Array<keyof typeof CYCLE_LABELS>).map((key) => (
                                <button key={key} onClick={() => setFormCycle(key as typeof formCycle)} style={{
                                    padding: '6px 14px', borderRadius: '8px', border: '1px solid',
                                    borderColor: formCycle === key ? 'var(--color-primary)' : 'var(--color-border)',
                                    background: formCycle === key ? 'rgba(99,102,241,0.15)' : 'var(--color-bg-secondary)',
                                    color: formCycle === key ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                                    cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600,
                                }}>
                                    {CYCLE_LABELS[key]}
                                </button>
                            ))}
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                            <div>
                                <label style={labelStyle}>總期數 *</label>
                                <input className="input-field" type="number" min="1" placeholder="如 240"
                                    value={formPeriods} onChange={(e) => setFormPeriods(e.target.value)} />
                            </div>
                            <div>
                                <label style={labelStyle}>每期繳款日（1-31，選填）</label>
                                <input className="input-field" type="number" min="1" max="31" placeholder="如 5"
                                    value={formPaymentDay} onChange={(e) => setFormPaymentDay(e.target.value)} />
                            </div>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                            <div>
                                <label style={labelStyle}>起始日（選填）</label>
                                <input className="input-field" type="date"
                                    value={formStartDate} onChange={(e) => setFormStartDate(e.target.value)} />
                            </div>
                            <div>
                                <label style={labelStyle}>備註</label>
                                <input className="input-field" placeholder="選填"
                                    value={formNote} onChange={(e) => setFormNote(e.target.value)} />
                            </div>
                        </div>

                        <p style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginBottom: '14px' }}>
                            建立後會自動在持倉中新增等額的負債部位，總負債與淨值即時反映;每次記錄還款會自動沖減餘額。
                        </p>

                        {formError && (
                            <div style={{
                                padding: '10px 14px', borderRadius: '8px', marginBottom: '12px',
                                background: 'var(--color-loss-bg)', color: 'var(--color-loss)', fontSize: '0.9rem',
                            }}>{formError}</div>
                        )}

                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                            <button className="btn-secondary" onClick={() => setShowCreateModal(false)}>取消</button>
                            <button className="btn-primary" onClick={handleCreate} disabled={formLoading}
                                style={{ opacity: formLoading ? 0.6 : 1, minWidth: '110px' }}>
                                {formLoading ? '處理中...' : '建立負債'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* ====== 記錄還款 Modal ====== */}
            {payingLiability && (
                <div style={{
                    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    zIndex: 200, backdropFilter: 'blur(6px)',
                }} onClick={() => setPayingLiability(null)}>
                    <div className="card-glass" style={{ maxWidth: '400px', width: '100%' }}
                        onClick={(e) => e.stopPropagation()}>
                        <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '6px' }}>
                            <CalendarClock size={17} style={{ verticalAlign: '-3px', marginRight: '6px' }} />
                            記錄還款 — {payingLiability.name}
                        </h3>
                        <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
                            剩餘 {fmtMoney(payingLiability.outstanding_balance, payingLiability.currency)}
                            ・已還 {payingLiability.paid_periods}/{payingLiability.total_periods} 期
                        </p>

                        <label style={labelStyle}>還款金額 *</label>
                        <input className="input-field" type="number" step="any" min="0" style={{ marginBottom: '12px' }}
                            value={payAmount} onChange={(e) => setPayAmount(e.target.value)} />

                        <label style={labelStyle}>還款日期</label>
                        <input className="input-field" type="date" style={{ marginBottom: '12px' }}
                            value={payDate} onChange={(e) => setPayDate(e.target.value)} />

                        <label style={labelStyle}>備註</label>
                        <input className="input-field" placeholder="選填" style={{ marginBottom: '16px' }}
                            value={payNote} onChange={(e) => setPayNote(e.target.value)} />

                        {payError && (
                            <div style={{
                                padding: '10px 14px', borderRadius: '8px', marginBottom: '12px',
                                background: 'var(--color-loss-bg)', color: 'var(--color-loss)', fontSize: '0.9rem',
                            }}>{payError}</div>
                        )}

                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                            <button className="btn-secondary" onClick={() => setPayingLiability(null)}>取消</button>
                            <button className="btn-primary" onClick={handlePay} disabled={payLoading}
                                style={{ opacity: payLoading ? 0.6 : 1, minWidth: '110px' }}>
                                {payLoading ? '處理中...' : '確認還款'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <style jsx>{`
                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    );
}

const labelStyle: React.CSSProperties = {
    display: 'block',
    color: 'var(--color-text-muted)',
    fontSize: '0.8rem',
    fontWeight: 600,
    marginBottom: '6px',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.03em',
};
