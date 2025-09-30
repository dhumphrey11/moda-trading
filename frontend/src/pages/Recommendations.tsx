import React, { useState, useEffect } from 'react';
import {
    Grid,
    Paper,
    Typography,
    Box,
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
import { mlApi } from '../services/api';
import { MLRecommendation } from '../types';

const Recommendations: React.FC = () => {
    const [recommendations, setRecommendations] = useState<MLRecommendation[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchRecommendations = async () => {
        try {
            setLoading(true);
            setError(null);
            // For demo purposes, using mock symbols
            const mockSymbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA'];
            const data = await mlApi.getRecommendations(mockSymbols);
            setRecommendations(data);
        } catch (err) {
            setError('Failed to load recommendations');
            console.error('Recommendations fetch error:', err);
        } finally {
            setLoading(false);
        }
    };

    const getRecommendationColor = (recommendation: string) => {
        switch (recommendation) {
            case 'buy':
                return 'success';
            case 'sell':
                return 'error';
            default:
                return 'default';
        }
    };

    const formatCurrency = (value: number) => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(value);
    };

    return (
        <Box sx={{ flexGrow: 1 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                <Typography variant="h4" component="h1">
                    AI/ML Recommendations
                </Typography>
                <Button
                    variant="contained"
                    onClick={fetchRecommendations}
                    disabled={loading}
                >
                    {loading ? 'Loading...' : 'Generate Recommendations'}
                </Button>
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 3 }}>
                    {error}
                </Alert>
            )}

            <Grid container spacing={3}>
                <Grid item xs={12}>
                    <Paper sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>
                            Latest Recommendations
                        </Typography>
                        <TableContainer>
                            <Table>
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Symbol</TableCell>
                                        <TableCell>Recommendation</TableCell>
                                        <TableCell align="right">Confidence</TableCell>
                                        <TableCell align="right">Price Target</TableCell>
                                        <TableCell align="right">Stop Loss</TableCell>
                                        <TableCell>Model Version</TableCell>
                                        <TableCell>Created</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {recommendations.map((rec) => (
                                        <TableRow key={rec.id}>
                                            <TableCell component="th" scope="row">
                                                <Typography variant="body2" fontWeight="medium">
                                                    {rec.symbol}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={rec.recommendation.toUpperCase()}
                                                    color={getRecommendationColor(rec.recommendation)}
                                                    size="small"
                                                />
                                            </TableCell>
                                            <TableCell align="right">
                                                {rec.confidence_score.toFixed(1)}%
                                            </TableCell>
                                            <TableCell align="right">
                                                {rec.price_target ? formatCurrency(rec.price_target) : '-'}
                                            </TableCell>
                                            <TableCell align="right">
                                                {rec.stop_loss ? formatCurrency(rec.stop_loss) : '-'}
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="caption">
                                                    {rec.model_version}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="caption">
                                                    {format(new Date(rec.created_at), 'MMM dd, HH:mm')}
                                                </Typography>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                        {recommendations.length === 0 && !loading && (
                            <Box textAlign="center" py={4}>
                                <Typography color="textSecondary">
                                    No recommendations available. Click "Generate Recommendations" to get AI predictions.
                                </Typography>
                            </Box>
                        )}
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    );
};

export default Recommendations;