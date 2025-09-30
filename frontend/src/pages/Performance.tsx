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
    Button,
    Alert
} from '@mui/material';
import { portfolioApi } from '../services/api';
import { PerformanceData } from '../types';

const Performance: React.FC = () => {
    const [performanceData, setPerformanceData] = useState<PerformanceData[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchPerformanceData();
    }, []);

    const fetchPerformanceData = async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await portfolioApi.getHoldingsPerformance();
            setPerformanceData(data);
        } catch (err) {
            setError('Failed to load performance data');
            console.error('Performance data fetch error:', err);
        } finally {
            setLoading(false);
        }
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
                <Typography>Loading performance data...</Typography>
            </Box>
        );
    }

    if (error) {
        return (
            <Alert severity="error" action={
                <Button color="inherit" size="small" onClick={fetchPerformanceData}>
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
                    Performance
                </Typography>
                <Button variant="outlined" onClick={fetchPerformanceData}>
                    Refresh
                </Button>
            </Box>

            <Grid container spacing={3}>
                <Grid item xs={12}>
                    <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column' }}>
                        <Typography variant="h6" gutterBottom component="div">
                            Holdings Performance
                        </Typography>
                        <TableContainer>
                            <Table>
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Symbol</TableCell>
                                        <TableCell align="right">Quantity</TableCell>
                                        <TableCell align="right">Avg Cost</TableCell>
                                        <TableCell align="right">Current Price</TableCell>
                                        <TableCell align="right">Market Value</TableCell>
                                        <TableCell align="right">P&L</TableCell>
                                        <TableCell align="right">Return %</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {performanceData.map((holding) => (
                                        <TableRow key={holding.symbol}>
                                            <TableCell component="th" scope="row">
                                                <Typography variant="body2" fontWeight="medium">
                                                    {holding.symbol}
                                                </Typography>
                                            </TableCell>
                                            <TableCell align="right">{holding.quantity}</TableCell>
                                            <TableCell align="right">{formatCurrency(holding.average_cost)}</TableCell>
                                            <TableCell align="right">
                                                {holding.current_price ? formatCurrency(holding.current_price) : '-'}
                                            </TableCell>
                                            <TableCell align="right">
                                                {holding.market_value ? formatCurrency(holding.market_value) : '-'}
                                            </TableCell>
                                            <TableCell align="right">
                                                <Typography
                                                    color={holding.unrealized_pnl >= 0 ? 'success.main' : 'error.main'}
                                                >
                                                    {formatCurrency(holding.unrealized_pnl)}
                                                </Typography>
                                            </TableCell>
                                            <TableCell align="right">
                                                <Typography
                                                    color={holding.return_pct >= 0 ? 'success.main' : 'error.main'}
                                                >
                                                    {formatPercent(holding.return_pct)}
                                                </Typography>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                        {performanceData.length === 0 && (
                            <Box textAlign="center" py={3}>
                                <Typography color="textSecondary">
                                    No performance data available
                                </Typography>
                            </Box>
                        )}
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    );
};

export default Performance;