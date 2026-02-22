/**
 * 投資組合全域狀態 (Zustand)
 *
 * 管理投資組合清單、選中的組合、淨值摘要與資產配置。
 */

import { create } from 'zustand';
import apiClient, {
    Portfolio,
    PortfolioSummary,
    AllocationResponse,
    PortfolioHistoryResponse,
} from '@/lib/api-client';

interface PortfolioState {
    // 狀態
    portfolios: Portfolio[];
    selectedPortfolio: Portfolio | null;
    summary: PortfolioSummary | null;
    allocations: AllocationResponse | null;
    history: PortfolioHistoryResponse | null;
    isLoading: boolean;
    error: string | null;

    // 多幣別支援
    displayCurrency: 'TWD' | 'USD';
    exchangeRate: number; // 1 USD = ? TWD

    // 動作
    fetchPortfolios: () => Promise<void>;
    selectPortfolio: (portfolio: Portfolio) => Promise<void>;
    fetchSummary: (portfolioId: string) => Promise<void>;
    fetchAllocations: (portfolioId: string) => Promise<void>;
    fetchHistory: (portfolioId: string) => Promise<void>;
    refreshAll: () => Promise<void>;
    createPortfolio: (name: string, description?: string) => Promise<void>;

    // 多幣別動作
    setDisplayCurrency: (currency: 'TWD' | 'USD') => void;
    fetchExchangeRates: () => Promise<void>;
}

export const usePortfolioStore = create<PortfolioState>((set, get) => ({
    portfolios: [],
    selectedPortfolio: null,
    summary: null,
    allocations: null,
    history: null,
    isLoading: false,
    error: null,
    displayCurrency: 'TWD',
    exchangeRate: 32.0, // 預設值，後續由 API 更新

    fetchPortfolios: async () => {
        set({ isLoading: true, error: null });
        try {
            const result = await apiClient.getPortfolios();
            const portfolios = result.data || [];
            set({ portfolios, isLoading: false });

            // 自動選擇第一個投資組合
            if (portfolios.length > 0 && !get().selectedPortfolio) {
                await get().selectPortfolio(portfolios[0]);
            }
        } catch (error) {
            set({ error: (error as Error).message, isLoading: false });
        }
    },

    selectPortfolio: async (portfolio) => {
        set({ selectedPortfolio: portfolio, isLoading: true });
        try {
            await get().fetchExchangeRates(); // 切換投資組合前先確保有最新匯率
            await Promise.all([
                get().fetchSummary(portfolio.id),
                get().fetchAllocations(portfolio.id),
                get().fetchHistory(portfolio.id),
            ]);
        } finally {
            set({ isLoading: false });
        }
    },

    fetchSummary: async (portfolioId) => {
        try {
            const result = await apiClient.getPortfolioSummary(portfolioId);
            set({ summary: result.data });
        } catch (error) {
            set({ error: (error as Error).message });
        }
    },

    fetchAllocations: async (portfolioId) => {
        try {
            const result = await apiClient.getAllocations(portfolioId);
            set({ allocations: result.data });
        } catch (error) {
            set({ error: (error as Error).message });
        }
    },

    fetchHistory: async (portfolioId) => {
        try {
            const result = await apiClient.getPortfolioHistory(portfolioId);
            set({ history: result.data });
        } catch (error) {
            set({ error: (error as Error).message });
        }
    },

    refreshAll: async () => {
        const { selectedPortfolio } = get();
        if (selectedPortfolio) {
            set({ isLoading: true });
            await get().fetchExchangeRates();
            await Promise.all([
                get().fetchSummary(selectedPortfolio.id),
                get().fetchAllocations(selectedPortfolio.id),
                get().fetchHistory(selectedPortfolio.id),
            ]);
            set({ isLoading: false });
        }
    },

    createPortfolio: async (name, description) => {
        try {
            await apiClient.createPortfolio(name, description);
            await get().fetchPortfolios();
        } catch (error) {
            set({ error: (error as Error).message });
        }
    },

    setDisplayCurrency: (currency) => {
        set({ displayCurrency: currency });
    },

    fetchExchangeRates: async () => {
        try {
            const result = await apiClient.getExchangeRates();
            // result.data 是形如 { "USD": 32.15, "TWD": 1.0 }
            if (result.data && result.data['USD']) {
                set({ exchangeRate: result.data['USD'] });
            }
        } catch (error) {
            console.error('Failed to fetch exchange rates:', error);
        }
    },
}));
