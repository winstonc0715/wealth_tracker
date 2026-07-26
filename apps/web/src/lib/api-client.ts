/**
 * WealthTracker API Client
 *
 * 統一處理 API 請求、Token 驗證與錯誤處理。
 */

const getApiBase = () => {
    let url = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
    // 確保路徑以 /api 結尾，且不重複
    if (url.includes('railway.app') && !url.endsWith('/api')) {
        url = url.replace(/\/$/, '') + '/api';
    }
    return url;
};

const API_BASE = getApiBase();

if (typeof window !== 'undefined') {
    console.log('[WealthTracker] API_BASE configuration:', {
        env: process.env.NEXT_PUBLIC_API_URL,
        computed: API_BASE
    });
}

interface ApiResponse<T> {
    success: boolean;
    data: T | null;
    message: string;
}

interface ErrorResponse {
    success: false;
    error: string;
    detail?: string;
}

export interface SearchResult {
    symbol: string;
    name: string;
    type_box: string | null;
    exchange: string | null;
    currency: string | null;
    category_slug?: string;
}

// === 定期定額 (DCA) 介面 ===
export interface DCASchedule {
    id: string;
    user_id: string;
    portfolio_id: string;
    symbol: string;
    asset_name: string | null;
    category_id: number;
    broker: string;
    investment_type: 'amount' | 'shares';
    target_amount: number | null;
    target_shares: number | null;
    execution_days: number[];
    fee_discount: number;
    auto_confirm: boolean;
    is_active: boolean;
    created_at: string;
    updated_at: string;
    next_execution_date: string | null;
    pending_count: number;
}

export interface DCAScheduleInput {
    portfolio_id: string;
    symbol: string;
    asset_name?: string;
    category_id?: number;
    broker?: string;
    investment_type: 'amount' | 'shares';
    target_amount?: number;
    target_shares?: number;
    execution_days: number[];
    fee_discount?: number;
    auto_confirm?: boolean;
}

export interface DCAExecution {
    id: string;
    schedule_id: string;
    execution_date: string;
    status: 'pending' | 'confirmed' | 'skipped' | 'failed';
    estimated_price: number | null;
    actual_price: number | null;
    quantity: number | null;
    fee: number | null;
    total_cost: number | null;
    transaction_id: string | null;
    note: string | null;
    created_at: string;
    confirmed_at: string | null;
    schedule_symbol: string | null;
    schedule_asset_name: string | null;
}

export interface DCAExecutionConfirm {
    actual_price?: number;
    note?: string;
}

export interface DCAImportRowDetail {
    row: number;
    symbol: string | null;
    asset_name: string | null;
    broker: string | null;
    execution_date: string | null;
    actual_price: number | null;
    quantity: number | null;
    total_cost: number | null;
    status: 'ok' | 'error';
    schedule_action: 'create' | 'update' | 'unchanged' | 'none';
    execution_action: 'create' | 'update' | 'none';
    transaction_action: 'create' | 'update' | 'none';
    error: string | null;
}

export interface DCAImportColumnInfo {
    key: string;
    label: string;
    required: boolean;
    aliases: string[];
    description: string;
}

export interface DCAImportResult {
    total_rows: number;
    imported: number;
    skipped: number;
    schedules_created: number;
    schedules_updated: number;
    executions_created: number;
    executions_updated: number;
    transactions_created: number;
    transactions_updated: number;
    errors: string[];
    dry_run?: boolean;
    details?: DCAImportRowDetail[];
}

class ApiClient {
    private baseUrl: string;

    constructor(baseUrl: string = API_BASE) {
        this.baseUrl = baseUrl;
    }

    private getToken(): string | null {
        if (typeof window === 'undefined') return null;
        return localStorage.getItem('wt_token');
    }

    setToken(token: string): void {
        localStorage.setItem('wt_token', token);
    }

    clearToken(): void {
        localStorage.removeItem('wt_token');
    }

    isAuthenticated(): boolean {
        return !!this.getToken();
    }

    private async request<T>(
        path: string,
        options: RequestInit = {}
    ): Promise<ApiResponse<T>> {
        const token = this.getToken();
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
            ...((options.headers as Record<string, string>) || {}),
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`${this.baseUrl}${path}`, {
            ...options,
            headers,
        });

        if (response.status === 401) {
            this.clearToken();
            if (typeof window !== 'undefined') {
                window.location.href = '/';
            }
            throw new Error('認證已過期，請重新登入');
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || data.error || '請求失敗');
        }

        return data;
    }

    // === Auth ===
    async register(email: string, username: string, password: string) {
        return this.request<{ id: string; email: string }>('/auth/register', {
            method: 'POST',
            body: JSON.stringify({ email, username, password }),
        });
    }

    async login(email: string, password: string) {
        const result = await this.request<{
            access_token: string;
            token_type: string;
            expires_in: number;
        }>('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
        });
        if (result.data?.access_token) {
            this.setToken(result.data.access_token);
        }
        return result;
    }

    async googleLogin(idToken: string) {
        const result = await this.request<{
            access_token: string;
            token_type: string;
            expires_in: number;
        }>('/auth/google', {
            method: 'POST',
            body: JSON.stringify({ id_token: idToken }),
        });
        if (result.data?.access_token) {
            this.setToken(result.data.access_token);
        }
        return result;
    }

    // === Portfolio ===
    async getPortfolios() {
        return this.request<Portfolio[]>('/portfolio/');
    }

    async createPortfolio(name: string, description?: string, baseCurrency = 'TWD') {
        return this.request<Portfolio>('/portfolio/', {
            method: 'POST',
            body: JSON.stringify({ name, description, base_currency: baseCurrency }),
        });
    }

    async getPortfolioSummary(portfolioId: string) {
        return this.request<PortfolioSummary>(`/portfolio/${portfolioId}/summary`);
    }

    async getMarketDetail(symbol: string, categorySlug: string) {
        return this.request<MarketDetail>(`/portfolio/market-detail?symbol=${encodeURIComponent(symbol)}&category_slug=${categorySlug}`);
    }

    async getAllocations(portfolioId: string) {
        return this.request<AllocationResponse>(`/portfolio/${portfolioId}/allocations`);
    }

    async getPortfolioHistory(portfolioId: string, days = 30, forceRefresh = false) {
        const params = `days=${days}${forceRefresh ? '&force_refresh=true' : ''}`;
        return this.request<PortfolioHistoryResponse>(`/portfolio/${portfolioId}/history?${params}`);
    }

    async getExchangeRates() {
        return this.request<Record<string, number>>('/portfolio/exchange-rates');
    }

    async searchSymbols(query: string, category_slug: string = 'all') {
        return this.request<SearchResult[]>(`/portfolio/search?query=${encodeURIComponent(query)}&category_slug=${encodeURIComponent(category_slug)}`);
    }

    // === Transactions ===
    async createTransaction(data: TransactionInput) {
        return this.request<Transaction>('/transactions/', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    async getTransactions(portfolioId: string, page = 1, pageSize = 20) {
        return this.request<PaginatedResponse<Transaction>>(
            `/transactions/${portfolioId}?page=${page}&page_size=${pageSize}`
        );
    }

    async updateTransaction(txId: string, data: Partial<TransactionInput>) {
        return this.request<Transaction>(`/transactions/${txId}`, {
            method: 'PATCH',
            body: JSON.stringify(data),
        });
    }

    async deleteTransaction(txId: string) {
        return this.request<boolean>(`/transactions/${txId}`, {
            method: 'DELETE',
        });
    }

    async recalculatePortfolioPnl(portfolioId: string) {
        return this.request<{ message: string, detail: any }>(`/transactions/recalculate/portfolio/${portfolioId}`, {
            method: 'POST',
        });
    }

    // === Broker ===
    async importCSV(portfolioId: string, file: File, brokerFormat = 'standard', categoryId = 1) {
        const formData = new FormData();
        formData.append('portfolio_id', portfolioId);
        formData.append('category_id', categoryId.toString());
        formData.append('broker_format', brokerFormat);
        formData.append('file', file);

        const token = this.getToken();
        const headers: Record<string, string> = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`${this.baseUrl}/broker/import-csv`, {
            method: 'POST',
            headers,
            body: formData,
        });
        return response.json();
    }

    // === 定期定額 (DCA) ===
    async getDCASchedules(): Promise<DCASchedule[]> {
        const res = await this.request<DCASchedule[]>('/dca/schedules');
        return res.data || [];
    }

    async createDCASchedule(data: DCAScheduleInput): Promise<DCASchedule> {
        const res = await this.request<DCASchedule>('/dca/schedules', { method: 'POST', body: JSON.stringify(data) });
        if (!res.data) throw new Error('建立定期定額計畫失敗');
        return res.data;
    }

    async updateDCASchedule(id: string, data: Partial<DCAScheduleInput>): Promise<DCASchedule> {
        const res = await this.request<DCASchedule>(`/dca/schedules/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
        if (!res.data) throw new Error('更新定期定額計畫失敗');
        return res.data;
    }

    async deleteDCASchedule(id: string): Promise<void> {
        await this.request(`/dca/schedules/${id}`, { method: 'DELETE' });
    }

    async toggleDCASchedule(id: string): Promise<DCASchedule> {
        const res = await this.request<DCASchedule>(`/dca/schedules/${id}/toggle`, { method: 'POST' });
        if (!res.data) throw new Error('切換定期定額計畫失敗');
        return res.data;
    }

    async getPendingExecutions(): Promise<DCAExecution[]> {
        const res = await this.request<DCAExecution[]>('/dca/executions/pending');
        return res.data || [];
    }

    async getExecutionHistory(page = 1, pageSize = 20): Promise<PaginatedResponse<DCAExecution>> {
        const res = await this.request<PaginatedResponse<DCAExecution>>(`/dca/executions/history?page=${page}&page_size=${pageSize}`);
        if (!res.data) throw new Error('載入定期定額歷史失敗');
        return res.data;
    }

    async confirmExecution(id: string, data?: DCAExecutionConfirm): Promise<DCAExecution> {
        const res = await this.request<DCAExecution>(`/dca/executions/${id}/confirm`, { method: 'POST', body: JSON.stringify(data || {}) });
        if (!res.data) throw new Error('確認定期定額執行失敗');
        return res.data;
    }

    async skipExecution(id: string): Promise<DCAExecution> {
        const res = await this.request<DCAExecution>(`/dca/executions/${id}/skip`, { method: 'POST' });
        if (!res.data) throw new Error('跳過定期定額執行失敗');
        return res.data;
    }

    private async uploadDCACSV(
        path: string,
        portfolioId: string,
        file: File,
        options: {
            categoryId?: number;
            brokerFormat?: string;
            broker?: string;
            autoConfirm?: boolean;
        } = {},
        failMessage = '匯入定期定額資料失敗'
    ): Promise<DCAImportResult> {
        const formData = new FormData();
        formData.append('portfolio_id', portfolioId);
        formData.append('category_id', String(options.categoryId ?? 1));
        formData.append('broker_format', options.brokerFormat ?? 'standard');
        formData.append('broker', options.broker ?? 'sinopac');
        formData.append('auto_confirm', String(options.autoConfirm ?? false));
        formData.append('file', file);

        const token = this.getToken();
        const headers: Record<string, string> = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`${this.baseUrl}${path}`, {
            method: 'POST',
            headers,
            body: formData,
        });

        if (response.status === 401) {
            this.clearToken();
            if (typeof window !== 'undefined') window.location.href = '/';
            throw new Error('認證已過期，請重新登入');
        }

        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.detail || result.error || failMessage);
        }
        if (!result.data) throw new Error(failMessage);
        return result.data;
    }

    async importDCACSV(
        portfolioId: string,
        file: File,
        options: {
            categoryId?: number;
            brokerFormat?: string;
            broker?: string;
            autoConfirm?: boolean;
        } = {}
    ): Promise<DCAImportResult> {
        return this.uploadDCACSV('/dca/import-csv', portfolioId, file, options);
    }

    /** 匯入預覽（dry-run）：試算結果但不寫入任何資料 */
    async previewDCACSV(
        portfolioId: string,
        file: File,
        options: {
            categoryId?: number;
            brokerFormat?: string;
            broker?: string;
            autoConfirm?: boolean;
        } = {}
    ): Promise<DCAImportResult> {
        return this.uploadDCACSV(
            '/dca/import-csv/preview', portfolioId, file, options,
            '預覽定期定額匯入失敗'
        );
    }

    /** 取得匯入 CSV 支援欄位與別名對照 */
    async getDCAImportColumns(): Promise<DCAImportColumnInfo[]> {
        const res = await this.request<DCAImportColumnInfo[]>('/dca/import-columns');
        return res.data || [];
    }

    /** 匯入範本 CSV 下載網址（無需登入） */
    getDCATemplateUrl(): string {
        return `${this.baseUrl}/dca/import-template`;
    }
}

// === Types ===
export interface Portfolio {
    id: string;
    name: string;
    description: string | null;
    base_currency: string;
    created_at: string;
}

export interface PositionDetail {
    symbol: string;
    name: string | null;
    category_slug: string;
    total_quantity: number;
    avg_cost: number;
    current_price: number;
    total_value: number;
    total_cost: number;
    unrealized_pnl: number;
    unrealized_pnl_pct: number;
    currency: string;
    price_change_24h_pct?: number;
    total_value_base?: number;
    unrealized_pnl_base?: number;
    current_price_base?: number;
}

export interface MarketDetail {
    symbol: string;
    change_pct_24h?: number;
    change_pct_7d?: number;
    change_pct_14d?: number;
    change_pct_30d?: number;
    change_pct_60d?: number;
    change_pct_1y?: number;
    market_cap?: number;
    week_52_high?: number;
    week_52_low?: number;
    pe_ratio?: number;
    currency: string;
}

export interface PortfolioSummary {
    portfolio_id: string;
    portfolio_name: string;
    total_assets: number;
    total_liabilities: number;
    net_worth: number;
    total_unrealized_pnl: number;
    total_realized_pnl: number;
    positions: PositionDetail[];
    last_updated: string;
}

export interface AllocationItem {
    category: string;
    category_slug: string;
    value: number;
    percentage: number;
    color: string | null;
}

export interface AllocationResponse {
    portfolio_id: string;
    total_value: number;
    allocations: AllocationItem[];
}

export interface NetWorthHistoryItem {
    date: string;
    value: number;
}

export interface PortfolioHistoryResponse {
    portfolio_id: string;
    history: NetWorthHistoryItem[];
}

export interface Transaction {
    id: string;
    portfolio_id: string;
    category_id: number;
    category_name: string | null;
    symbol: string;
    asset_name: string | null;
    tx_type: string;
    quantity: number;
    unit_price: number;
    fee: number;
    currency: string;
    executed_at: string;
    note: string | null;
    realized_pnl: number;
    created_at: string;
}

export interface TransactionInput {
    portfolio_id: string;
    category_id: number;
    symbol: string;
    asset_name?: string;
    tx_type: string;
    quantity: number;
    unit_price: number;
    fee?: number;
    currency?: string;
    executed_at: string;
    note?: string;
}

export interface PaginatedResponse<T> {
    items: T[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
}

export const apiClient = new ApiClient();
export default apiClient;
