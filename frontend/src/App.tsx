import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { AppBar, Toolbar, Typography, Container, Box } from '@mui/material';
import Navigation from './components/Navigation';
import Dashboard from './pages/Dashboard';
import Performance from './pages/Performance';
import Research from './pages/Research';
import Recommendations from './pages/Recommendations';
import Admin from './pages/Admin';

const theme = createTheme({
    palette: {
        mode: 'light',
        primary: {
            main: '#1976d2',
        },
        secondary: {
            main: '#dc004e',
        },
    },
});

function App() {
    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <Router>
                <Box sx={{ flexGrow: 1 }}>
                    <AppBar position="static">
                        <Toolbar>
                            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
                                Moda Trading
                            </Typography>
                        </Toolbar>
                    </AppBar>

                    <Navigation />

                    <Container maxWidth="xl" sx={{ mt: 2, mb: 2 }}>
                        <Routes>
                            <Route path="/" element={<Dashboard />} />
                            <Route path="/dashboard" element={<Dashboard />} />
                            <Route path="/performance" element={<Performance />} />
                            <Route path="/research" element={<Research />} />
                            <Route path="/recommendations" element={<Recommendations />} />
                            <Route path="/admin" element={<Admin />} />
                        </Routes>
                    </Container>
                </Box>
            </Router>
        </ThemeProvider>
    );
}

export default App;