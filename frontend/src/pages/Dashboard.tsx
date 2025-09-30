import React, { useState, useEffect } from 'react';
import {
    Grid,
    Paper,
    Typography,
    Box,
    Card,
    CardContent,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Chip,
    Button,
    Alert
} from '@mui/material';
import { format } from 'date-fns';
import { portfolioApi } from '../services/api';
import { Position, Transaction, PortfolioSummary } from '../types';

const Dashboard: React.FC = () => {
    const [portfolioSummary, setPortfolioSummary] = useState<PortfolioSummary | null>(null);
    const [activePositions, setActivePositions] = useState<Position[]>([]);
    const [recentTransactions, setRecentTransactions] = useState<Transaction[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchDashboardData();
    }, []);

    const fetchDashboardData = async () => {
        try {
            setLoading(true);
            setError(null);

            const [summary, positions, transactions] = await Promise.all([
                portfolioApi.getSummary(),
                portfolioApi.getActivePositions(),
                portfolioApi.getTransactions(10) // Get last 10 transactions
            ]);

            setPortfolioSummary(summary);
            setActivePositions(positions);
            setRecentTransactions(transactions);
        } catch (err) {
            setError('Failed to load dashboard data');
            console.error('Dashboard data fetch error:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleRefresh = () => {
        fetchDashboardData();
    };

    const formatCurrency = (value: number) => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(value);
    };

    const formatPercent = (value: number) => {
        return `${value.toFixed(2)}%`;
    };

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                <Typography>Loading dashboard...</Typography>
            </Box>
        );
    }

    if (error) {
        return (
            <Alert severity="error" action={
                <Button color="inherit" size="small" onClick={handleRefresh}>
                    Retry
                </Button>
            }>
                {error}
            </Alert>
        );
    }

    return (
        <Box sx={{ flexGrow: 1 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                <Typography variant="h4" component="h1">
                    Dashboard
                </Typography>
                <Button variant="outlined" onClick={handleRefresh}>
                    Refresh
                </Button>
            </Box>

            {/* Portfolio Summary Cards */}
            <Grid container spacing={3} mb={3}>
                <Grid item xs={12} sm={6} md={3}>
                    <Card>
                        <CardContent>
                            <Typography color="textSecondary" gutterBottom>
                                Total Value
                            </Typography>
                            <Typography variant="h5" component="div">
                                {portfolioSummary ? formatCurrency(portfolioSummary.total_market_value) : '-'}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                    <Card>
                        <CardContent>
                            <Typography color="textSecondary" gutterBottom>
                                Unrealized P&L
                            </Typography>
                            <Typography
                                variant="h5"
                                component="div"
                                color={portfolioSummary && portfolioSummary.total_unrealized_pnl >= 0 ? 'success.main' : 'error.main'}
                            >
                                {portfolioSummary ? formatCurrency(portfolioSummary.total_unrealized_pnl) : '-'}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                    <Card>
                        <CardContent>
                            <Typography color="textSecondary" gutterBottom>
                                Return %
                            </Typography>
                            <Typography
                                variant="h5"
                                component="div"
                                color={portfolioSummary && portfolioSummary.unrealized_return_pct >= 0 ? 'success.main' : 'error.main'}
                            >
                                {portfolioSummary ? formatPercent(portfolioSummary.unrealized_return_pct) : '-'}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                    <Card>
                        <CardContent>
                            <Typography color="textSecondary" gutterBottom>
                                Active Positions
                            </Typography>
                            <Typography variant="h5" component="div">
                                {portfolioSummary ? portfolioSummary.active_positions_count : '-'}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            <Grid container spacing={3}>
                {/* Active Positions */}
                <Grid item xs={12} lg={8}>
                    <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column' }}>
                        <Typography variant="h6" gutterBottom component="div">
                            Active Positions
                        </Typography>
                        <TableContainer>
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Symbol</TableCell>
                                        <TableCell align="right">Quantity</TableCell>
                                        <TableCell align="right">Avg Cost</TableCell>
                                        <TableCell align="right">Current Price</TableCell>
                                        <TableCell align="right">Market Value</TableCell>
                                        <TableCell align="right">P&L</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {activePositions.map((position) => (
                                        <TableRow key={position.id}>
                                            <TableCell component="th" scope="row">
                                                <Typography variant="body2" fontWeight="medium">
                                                    {position.symbol}
                                                </Typography>
                                            </TableCell>
                                            <TableCell align="right">{position.quantity}</TableCell>
                                            <TableCell align="right">{formatCurrency(position.average_cost)}</TableCell>
                                            <TableCell align="right">
                                                {position.current_price ? formatCurrency(position.current_price) : '-'}
                                            </TableCell>
                                            <TableCell align="right">
                                                {position.market_value ? formatCurrency(position.market_value) : '-'}
                                            </TableCell>
                                            <TableCell align="right">
                                                <Typography
                                                    color={position.unrealized_pnl && position.unrealized_pnl >= 0 ? 'success.main' : 'error.main'}
                                                >
                                                    {position.unrealized_pnl ? formatCurrency(position.unrealized_pnl) : '-'}
                                                </Typography>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                        {activePositions.length === 0 && (
                            <Box textAlign="center" py={3}>
                                <Typography color="textSecondary">
                                    No active positions
                                </Typography>
                            </Box>
                        )}
                    </Paper>
                </Grid>

                {/* Recent Transactions */}
                <Grid item xs={12} lg={4}>
                    <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column' }}>
                        <Typography variant="h6" gutterBottom component="div">
                            Recent Transactions
                        </Typography>
                        {recentTransactions.map((transaction) => (
                            <Box key={transaction.id} mb={2} p={1} border={1} borderColor="divider" borderRadius={1}>
                                <Box display="flex" justifyContent="space-between" alignItems="center">
                                    <Typography variant="body2" fontWeight="medium">
                                        {transaction.symbol}
                                    </Typography>
                                    <Chip
                                        label={transaction.transaction_type.toUpperCase()}
                                        size="small"
                                        color={transaction.transaction_type === 'buy' ? 'success' : 'error'}
                                    />
                                </Box>
                                <Typography variant="body2" color="textSecondary">
                                    {transaction.quantity} shares @ {formatCurrency(transaction.price)}
                                </Typography>
                                <Typography variant="caption" color="textSecondary">
                                    {format(new Date(transaction.executed_at), 'MMM dd, yyyy HH:mm')}
                                </Typography>
                            </Box>
                        ))}
                        {recentTransactions.length === 0 && (
                            <Box textAlign="center" py={3}>
                                <Typography color="textSecondary">
                                    No recent transactions
                                </Typography>
                            </Box>
                        )}
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    );
};

export default Dashboard;