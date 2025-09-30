import React, { useState, useEffect } from 'react';
import {
    Box,
    Typography,
    Grid,
    Paper,
    Card,
    CardContent,
    Button,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Chip,
    Alert,
    TextField,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions
} from '@mui/material';
import { orchestratorApi, healthApi, portfolioApi } from '../services/api';
import { ServiceStatus } from '../types';

const Admin: React.FC = () => {
    const [serviceStatuses, setServiceStatuses] = useState<ServiceStatus[]>([]);
    const [loading, setLoading] = useState(false);
    const [orchestratorStatus, setOrchestratorStatus] = useState<any>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [newSymbol, setNewSymbol] = useState('');

    useEffect(() => {
        checkServiceHealth();
        getOrchestratorStatus();
    }, []);

    const checkServiceHealth = async () => {
        try {
            setLoading(true);
            const statuses = await healthApi.checkAllServices();
            setServiceStatuses(statuses);
        } catch (error) {
            console.error('Error checking service health:', error);
        } finally {
            setLoading(false);
        }
    };

    const getOrchestratorStatus = async () => {
        try {
            const status = await orchestratorApi.getStatus();
            setOrchestratorStatus(status);
        } catch (error) {
            console.error('Error getting orchestrator status:', error);
        }
    };

    const handleDataCollection = async (type: string) => {
        try {
            switch (type) {
                case 'intraday':
                    await orchestratorApi.triggerIntradayCollection();
                    break;
                case 'daily':
                    await orchestratorApi.triggerDailyCollection();
                    break;
                case 'fundamentals':
                    await orchestratorApi.triggerFundamentalsCollection();
                    break;
                case 'market-news':
                    await orchestratorApi.triggerMarketNewsCollection();
                    break;
                case 'full':
                    await orchestratorApi.triggerFullCollection();
                    break;
            }
            alert(`${type} collection triggered successfully`);
        } catch (error) {
            alert(`Failed to trigger ${type} collection`);
        }
    };

    const handleAddToWatchlist = async () => {
        if (!newSymbol.trim()) return;

        try {
            await portfolioApi.addToWatchlist(newSymbol.toUpperCase());
            setNewSymbol('');
            setDialogOpen(false);
            alert(`${newSymbol} added to watchlist`);
        } catch (error) {
            alert(`Failed to add ${newSymbol} to watchlist`);
        }
    };

    const getStatusColor = (status: string) => {
        switch (status.toLowerCase()) {
            case 'healthy':
                return 'success';
            case 'unhealthy':
                return 'error';
            default:
                return 'warning';
        }
    };

    return (
        <Box sx={{ flexGrow: 1 }}>
            <Typography variant="h4" component="h1" gutterBottom>
                Admin Dashboard
            </Typography>

            <Grid container spacing={3}>
                {/* Service Health */}
                <Grid item xs={12}>
                    <Paper sx={{ p: 2 }}>
                        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                            <Typography variant="h6">
                                Service Health
                            </Typography>
                            <Button variant="outlined" onClick={checkServiceHealth} disabled={loading}>
                                {loading ? 'Checking...' : 'Refresh'}
                            </Button>
                        </Box>
                        <TableContainer>
                            <Table>
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Service</TableCell>
                                        <TableCell>Status</TableCell>
                                        <TableCell>Last Check</TableCell>
                                        <TableCell>Version</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {serviceStatuses.map((service) => (
                                        <TableRow key={service.service}>
                                            <TableCell>{service.service}</TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={service.status}
                                                    color={getStatusColor(service.status)}
                                                    size="small"
                                                />
                                            </TableCell>
                                            <TableCell>{new Date(service.timestamp).toLocaleString()}</TableCell>
                                            <TableCell>{service.version || '-'}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </Paper>
                </Grid>

                {/* Data Collection Controls */}
                <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>
                            Data Collection
                        </Typography>
                        <Grid container spacing={2}>
                            <Grid item xs={12} sm={6}>
                                <Button
                                    fullWidth
                                    variant="contained"
                                    onClick={() => handleDataCollection('intraday')}
                                >
                                    Trigger Intraday
                                </Button>
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <Button
                                    fullWidth
                                    variant="contained"
                                    onClick={() => handleDataCollection('daily')}
                                >
                                    Trigger Daily
                                </Button>
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <Button
                                    fullWidth
                                    variant="contained"
                                    onClick={() => handleDataCollection('fundamentals')}
                                >
                                    Trigger Fundamentals
                                </Button>
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <Button
                                    fullWidth
                                    variant="contained"
                                    onClick={() => handleDataCollection('market-news')}
                                >
                                    Trigger Market News
                                </Button>
                            </Grid>
                            <Grid item xs={12}>
                                <Button
                                    fullWidth
                                    variant="contained"
                                    color="primary"
                                    onClick={() => handleDataCollection('full')}
                                >
                                    Trigger Full Collection
                                </Button>
                            </Grid>
                        </Grid>
                    </Paper>
                </Grid>

                {/* Orchestrator Status */}
                <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>
                            Orchestrator Status
                        </Typography>
                        {orchestratorStatus ? (
                            <Grid container spacing={2}>
                                <Grid item xs={6}>
                                    <Card>
                                        <CardContent>
                                            <Typography color="textSecondary" gutterBottom>
                                                Active Positions
                                            </Typography>
                                            <Typography variant="h5">
                                                {orchestratorStatus.active_positions_count || 0}
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>
                                <Grid item xs={6}>
                                    <Card>
                                        <CardContent>
                                            <Typography color="textSecondary" gutterBottom>
                                                Watchlist Count
                                            </Typography>
                                            <Typography variant="h5">
                                                {orchestratorStatus.watchlist_count || 0}
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>
                            </Grid>
                        ) : (
                            <Typography color="textSecondary">
                                Loading orchestrator status...
                            </Typography>
                        )}
                    </Paper>
                </Grid>

                {/* Watchlist Management */}
                <Grid item xs={12}>
                    <Paper sx={{ p: 2 }}>
                        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                            <Typography variant="h6">
                                Watchlist Management
                            </Typography>
                            <Button variant="contained" onClick={() => setDialogOpen(true)}>
                                Add Symbol
                            </Button>
                        </Box>
                        <Typography color="textSecondary">
                            Manage symbols in your trading watchlist. These symbols will be monitored for data collection and ML recommendations.
                        </Typography>
                    </Paper>
                </Grid>
            </Grid>

            {/* Add Symbol Dialog */}
            <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)}>
                <DialogTitle>Add Symbol to Watchlist</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        margin="dense"
                        label="Stock Symbol"
                        type="text"
                        fullWidth
                        variant="outlined"
                        value={newSymbol}
                        onChange={(e) => setNewSymbol(e.target.value)}
                        placeholder="e.g., AAPL"
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
                    <Button onClick={handleAddToWatchlist} variant="contained">
                        Add
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default Admin;