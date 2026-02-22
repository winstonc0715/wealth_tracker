/**
 * 投資組合狀態管理 (Zustand)
 *
 * 與 Web 端共用相同的狀態結構。
 */

import { create } from 'zustand';
import apiClient, {
    Portfolio,
    PortfolioSummary,
    AllocationResponse,
} from '@/lib/api-client';

interface PortfolioState {
    portfolios: Portfolio[];
    selectedPortfolio: Portfolio | null;
    summary: PortfolioSummary | null;
    allocations: AllocationResponse | null;
    isLoading: boolean;
    error: string | null;

    displayCurrency: 'TWD' | 'USD';
    exchangeRate: number;

    fetchPortfolios: () => Promise<void>;
    selectPortfolio: (portfolio: Portfolio) => Promise<void>;
    setDisplayCurrency: (currency: 'TWD' | 'USD') => void;
    refreshAll: () => Promise<void>;
}

export const usePortfolioStore = create<PortfolioState>((set, get) => ({
    portfolios: [],
    selectedPortfolio: null,
    summary: null,
    allocations: null,
    isLoading: false,
    error: null,
    displayCurrency: 'TWD',
    exchangeRate: 32.5, // 預設匯率

    fetchPortfolios: async () => {
        set({ isLoading: true, error: null });
        try {
            const result = await apiClient.getPortfolios();
            const portfolios = result.data || [];
            set({ portfolios, isLoading: false });

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
            const [summaryRes, allocRes, rateRes] = await Promise.all([
                apiClient.getPortfolioSummary(portfolio.id),
                apiClient.getAllocations(portfolio.id),
                apiClient.getExchangeRates(),
            ]);
            set({
                summary: summaryRes.data,
                allocations: allocRes.data,
                exchangeRate: rateRes.data?.rates['TWD'] || 32.5,
                isLoading: false,
            });
        } catch (error) {
            set({ error: (error as Error).message, isLoading: false });
        }
    },

    setDisplayCurrency: (currency) => {
        set({ displayCurrency: currency });
    },

    refreshAll: async () => {
        const { selectedPortfolio } = get();
        if (selectedPortfolio) {
            await get().selectPortfolio(selectedPortfolio);
        }
    },
}));
