import axios from 'axios';
import {
    Position,
    Transaction,
    MLRecommendation,
    TradeSignal,
    WatchlistItem,
    PriceData,
    NewsData,
    PortfolioSummary,
    PerformanceData,
    ServiceStatus
} from '../types';

// API base URLs (update these based on your deployment)
const API_URLS = {
    portfolio: process.env.REACT_APP_PORTFOLIO_API || 'http://localhost:8080',
    mlPipeline: process.env.REACT_APP_ML_PIPELINE_API || 'http://localhost:8081',
    strategyEngine: process.env.REACT_APP_STRATEGY_ENGINE_API || 'http://localhost:8082',
    orchestrator: process.env.REACT_APP_ORCHESTRATOR_API || 'http://localhost:8083',
    alphavantage: process.env.REACT_APP_ALPHAVANTAGE_API || 'http://localhost:8084',
    finnhub: process.env.REACT_APP_FINNHUB_API || 'http://localhost:8085'
};

// Portfolio Service API
export const portfolioApi = {
    getSummary: async (): Promise<PortfolioSummary> => {
        const response = await axios.get(`${API_URLS.portfolio}/portfolio/summary`);
        return response.data;
    },

    getActivePositions: async (): Promise<Position[]> => {
        const response = await axios.get(`${API_URLS.portfolio}/positions/active`);
        return response.data.positions;
    },

    getPositionHistory: async (limit: number = 50): Promise<Position[]> => {
        const response = await axios.get(`${API_URLS.portfolio}/positions/history?limit=${limit}`);
        return response.data.positions;
    },

    getTransactions: async (limit: number = 100): Promise<Transaction[]> => {
        const response = await axios.get(`${API_URLS.portfolio}/transactions?limit=${limit}`);
        return response.data.transactions;
    },

    getWatchlist: async (): Promise<WatchlistItem[]> => {
        const response = await axios.get(`${API_URLS.portfolio}/watchlist`);
        return response.data.watchlist;
    },

    addToWatchlist: async (symbol: string, notes?: string, priority: number = 1): Promise<void> => {
        await axios.post(`${API_URLS.portfolio}/watchlist/${symbol}`, {
            added_by: 'user',
            notes,
            priority
        });
    },

    removeFromWatchlist: async (symbol: string): Promise<void> => {
        await axios.delete(`${API_URLS.portfolio}/watchlist/${symbol}`);
    },

    getHoldingsPerformance: async (): Promise<PerformanceData[]> => {
        const response = await axios.get(`${API_URLS.portfolio}/performance/holdings`);
        return response.data.holdings_performance;
    },

    updatePositionValues: async (): Promise<void> => {
        await axios.post(`${API_URLS.portfolio}/positions/update-values`);
    },

    processTradeSignals: async (): Promise<void> => {
        await axios.post(`${API_URLS.portfolio}/trades/process-signals`);
    }
};

// ML Pipeline API
export const mlApi = {
    getRecommendations: async (symbols: string[]): Promise<MLRecommendation[]> => {
        const response = await axios.post(`${API_URLS.mlPipeline}/recommend`, symbols);
        return response.data.recommendations;
    },

    trainModel: async (symbols?: string[]): Promise<void> => {
        await axios.post(`${API_URLS.mlPipeline}/train`, symbols);
    },

    getModelStatus: async (): Promise<any> => {
        const response = await axios.get(`${API_URLS.mlPipeline}/model/status`);
        return response.data;
    }
};

// Strategy Engine API
export const strategyApi = {
    processRecommendations: async (): Promise<void> => {
        await axios.post(`${API_URLS.strategyEngine}/process-recommendations`);
    },

    getActiveSignals: async (hoursBack: number = 24): Promise<TradeSignal[]> => {
        const response = await axios.get(`${API_URLS.strategyEngine}/signals/active?hours_back=${hoursBack}`);
        return response.data.signals;
    },

    getRiskStatus: async (): Promise<any> => {
        const response = await axios.get(`${API_URLS.strategyEngine}/risk/status`);
        return response.data;
    },

    generateSignal: async (symbol: string): Promise<TradeSignal | null> => {
        const response = await axios.post(`${API_URLS.strategyEngine}/signals/generate/${symbol}`);
        return response.data.signal || null;
    }
};

// Orchestrator API
export const orchestratorApi = {
    getStatus: async (): Promise<any> => {
        const response = await axios.get(`${API_URLS.orchestrator}/status`);
        return response.data;
    },

    triggerIntradayCollection: async (): Promise<void> => {
        await axios.post(`${API_URLS.orchestrator}/orchestrate/intraday`);
    },

    triggerDailyCollection: async (): Promise<void> => {
        await axios.post(`${API_URLS.orchestrator}/orchestrate/daily`);
    },

    triggerFundamentalsCollection: async (): Promise<void> => {
        await axios.post(`${API_URLS.orchestrator}/orchestrate/fundamentals`);
    },

    triggerMarketNewsCollection: async (): Promise<void> => {
        await axios.post(`${API_URLS.orchestrator}/orchestrate/market-news`);
    },

    triggerFullCollection: async (): Promise<void> => {
        await axios.post(`${API_URLS.orchestrator}/orchestrate/full`);
    }
};

// Health Check API
export const healthApi = {
    checkService: async (serviceUrl: string): Promise<ServiceStatus> => {
        try {
            const response = await axios.get(`${serviceUrl}/health`);
            return response.data;
        } catch (error) {
            return {
                service: 'unknown',
                status: 'unhealthy',
                timestamp: new Date().toISOString()
            };
        }
    },

    checkAllServices: async (): Promise<ServiceStatus[]> => {
        const services = Object.entries(API_URLS);
        const promises = services.map(([name, url]) =>
            healthApi.checkService(url).then(status => ({ ...status, service: name }))
        );

        return Promise.allSettled(promises).then(results =>
            results.map((result, index) =>
                result.status === 'fulfilled'
                    ? result.value
                    : {
                        service: services[index][0],
                        status: 'error',
                        timestamp: new Date().toISOString()
                    }
            )
        );
    }
};

// Mock data for development
export const mockApi = {
    getRecentPrices: async (symbol: string): Promise<PriceData[]> => {
        // This would normally come from Firestore via an API
        // For now, return mock data
        const mockPrices: PriceData[] = [];
        const basePrice = 100 + Math.random() * 50;

        for (let i = 30; i >= 0; i--) {
            const date = new Date();
            date.setDate(date.getDate() - i);

            const price = basePrice + (Math.random() - 0.5) * 10;
            mockPrices.push({
                symbol,
                date: date.toISOString().split('T')[0],
                open_price: price,
                high_price: price * 1.02,
                low_price: price * 0.98,
                close_price: price,
                volume: Math.floor(Math.random() * 1000000)
            });
        }

        return mockPrices;
    },

    getRecentNews: async (): Promise<NewsData[]> => {
        // Mock news data
        return [
            {
                id: '1',
                headline: 'Market sees strong gains amid positive earnings',
                summary: 'Major indices posted gains as several companies reported better-than-expected earnings.',
                url: 'https://example.com/news/1',
                published_at: new Date().toISOString(),
                symbols: ['AAPL', 'MSFT', 'GOOGL'],
                sentiment_score: 0.8,
                provider: 'mock'
            },
            {
                id: '2',
                headline: 'Tech sector leads market rally',
                summary: 'Technology stocks outperformed broader market indices today.',
                url: 'https://example.com/news/2',
                published_at: new Date(Date.now() - 3600000).toISOString(),
                symbols: ['AAPL', 'MSFT', 'AMZN'],
                sentiment_score: 0.6,
                provider: 'mock'
            }
        ];
    }
};