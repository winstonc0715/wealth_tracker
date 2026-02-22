/**
 * WealthTracker Mobile - API Client
 *
 * 與 Web 端共用相同的 API 介面與型別定義，
 * 但使用 AsyncStorage 取代 localStorage。
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000/api';

const TOKEN_KEY = 'wt_token';

// === Types (與 Web 端一致) ===
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

export interface SearchResult {
    symbol: string;
    name: string;
    type_box?: string;
    exchange?: string;
    currency?: string;
}

export interface ExchangeRateResponse {
    rates: Record<string, number>;
    base: string;
}

interface ApiResponse<T> {
    success: boolean;
    data: T | null;
    message: string;
}

// === API Client ===

class MobileApiClient {
    private baseUrl: string;

    constructor() {
        this.baseUrl = API_BASE;
    }

    async getToken(): Promise<string | null> {
        return AsyncStorage.getItem(TOKEN_KEY);
    }

    async setToken(token: string): Promise<void> {
        await AsyncStorage.setItem(TOKEN_KEY, token);
    }

    async clearToken(): Promise<void> {
        await AsyncStorage.removeItem(TOKEN_KEY);
    }

    async isAuthenticated(): Promise<boolean> {
        const token = await this.getToken();
        return !!token;
    }

    private async request<T>(
        path: string,
        options: RequestInit = {}
    ): Promise<ApiResponse<T>> {
        const token = await this.getToken();
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

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || data.error || '請求失敗');
        }
        return data;
    }

    // Auth
    async login(email: string, password: string) {
        const result = await this.request<{
            access_token: string;
            expires_in: number;
        }>('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
        });
        if (result.data?.access_token) {
            await this.setToken(result.data.access_token);
        }
        return result;
    }

    async register(email: string, username: string, password: string) {
        return this.request('/auth/register', {
            method: 'POST',
            body: JSON.stringify({ email, username, password }),
        });
    }

    // Portfolio
    async getPortfolios() {
        return this.request<Portfolio[]>('/portfolio/');
    }

    async getPortfolioSummary(portfolioId: string) {
        return this.request<PortfolioSummary>(`/portfolio/${portfolioId}/summary`);
    }

    async getAllocations(portfolioId: string) {
        return this.request<AllocationResponse>(`/portfolio/${portfolioId}/allocations`);
    }

    // Transactions
    async createTransaction(data: any) {
        return this.request('/transactions/', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    // Search
    async searchSymbols(query: string, category_slug: string) {
        return this.request<SearchResult[]>(`/portfolio/search?query=${encodeURIComponent(query)}&category_slug=${encodeURIComponent(category_slug)}`);
    }

    // Exchange Rates
    async getExchangeRates() {
        return this.request<ExchangeRateResponse>('/portfolio/exchange-rates');
    }
}

export const apiClient = new MobileApiClient();
export default apiClient;
