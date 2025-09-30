import React from 'react';
import {
    Box,
    Typography,
    Grid,
    Paper,
    Card,
    CardContent
} from '@mui/material';

const Research: React.FC = () => {
    return (
        <Box sx={{ flexGrow: 1 }}>
            <Typography variant="h4" component="h1" gutterBottom>
                Research
            </Typography>

            <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>
                            Price Data
                        </Typography>
                        <Typography color="textSecondary">
                            View historical and real-time price data from all connected data sources.
                        </Typography>
                    </Paper>
                </Grid>

                <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>
                            Fundamental Data
                        </Typography>
                        <Typography color="textSecondary">
                            Access company fundamentals, earnings, and financial ratios.
                        </Typography>
                    </Paper>
                </Grid>

                <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>
                            Company News
                        </Typography>
                        <Typography color="textSecondary">
                            Browse company-specific news and sentiment analysis.
                        </Typography>
                    </Paper>
                </Grid>

                <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>
                            Market News
                        </Typography>
                        <Typography color="textSecondary">
                            Stay updated with general market news and trends.
                        </Typography>
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    );
};

export default Research;