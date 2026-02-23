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

    async getAllocations(portfolioId: string) {
        return this.request<AllocationResponse>(`/portfolio/${portfolioId}/allocations`);
    }

    async getPortfolioHistory(portfolioId: string, days = 30) {
        return this.request<PortfolioHistoryResponse>(`/portfolio/${portfolioId}/history?days=${days}`);
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
