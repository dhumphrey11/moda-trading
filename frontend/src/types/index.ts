// Types for the trading application

export interface Position {
    id: string;
    symbol: string;
    quantity: number;
    average_cost: number;
    current_price?: number;
    market_value?: number;
    unrealized_pnl?: number;
    status: 'active' | 'closed';
    opened_at: string;
    closed_at?: string;
}

export interface Transaction {
    id: string;
    symbol: string;
    transaction_type: 'buy' | 'sell';
    quantity: number;
    price: number;
    total_amount: number;
    fees: number;
    executed_at: string;
    order_id?: string;
}

export interface MLRecommendation {
    id: string;
    symbol: string;
    recommendation: 'buy' | 'hold' | 'sell';
    confidence_score: number;
    price_target?: number;
    stop_loss?: number;
    model_version: string;
    features_used: Record<string, any>;
    created_at: string;
}

export interface TradeSignal {
    id: string;
    symbol: string;
    signal_type: 'buy' | 'hold' | 'sell';
    quantity: number;
    price_limit?: number;
    stop_loss?: number;
    take_profit?: number;
    confidence: number;
    reasoning: string;
    expires_at?: string;
    created_at: string;
}

export interface WatchlistItem {
    id: string;
    symbol: string;
    added_by: string;
    notes?: string;
    priority: number;
    created_at: string;
}

export interface PriceData {
    symbol: string;
    date: string;
    open_price: number;
    high_price: number;
    low_price: number;
    close_price: number;
    volume: number;
    adjusted_close?: number;
}

export interface NewsData {
    id: string;
    headline: string;
    summary: string;
    url: string;
    published_at: string;
    symbols: string[];
    sentiment_score?: number;
    provider: string;
}

export interface PortfolioSummary {
    active_positions_count: number;
    total_market_value: number;
    total_cost_basis: number;
    total_unrealized_pnl: number;
    unrealized_return_pct: number;
    recent_transactions_count: number;
    last_updated: string;
}

export interface PerformanceData {
    symbol: string;
    quantity: number;
    average_cost: number;
    current_price?: number;
    market_value?: number;
    unrealized_pnl: number;
    return_pct: number;
}

export interface ServiceStatus {
    service: string;
    status: string;
    timestamp: string;
    version?: string;
}