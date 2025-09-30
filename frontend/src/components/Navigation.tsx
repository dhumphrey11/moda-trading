import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
    Drawer,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    ListItemButton,
    Box,
    Toolbar
} from '@mui/material';
import {
    Dashboard as DashboardIcon,
    TrendingUp as PerformanceIcon,
    Search as ResearchIcon,
    Lightbulb as RecommendationsIcon,
    Settings as AdminIcon
} from '@mui/icons-material';

const drawerWidth = 240;

const menuItems = [
    { text: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard' },
    { text: 'Performance', icon: <PerformanceIcon />, path: '/performance' },
    { text: 'Research', icon: <ResearchIcon />, path: '/research' },
    { text: 'Recommendations', icon: <RecommendationsIcon />, path: '/recommendations' },
    { text: 'Admin', icon: <AdminIcon />, path: '/admin' },
];

const Navigation: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();

    return (
        <Drawer
            variant="permanent"
            sx={{
                width: drawerWidth,
                flexShrink: 0,
                '& .MuiDrawer-paper': {
                    width: drawerWidth,
                    boxSizing: 'border-box',
                },
            }}
        >
            <Toolbar />
            <Box sx={{ overflow: 'auto' }}>
                <List>
                    {menuItems.map((item) => (
                        <ListItem key={item.text} disablePadding>
                            <ListItemButton
                                selected={location.pathname === item.path}
                                onClick={() => navigate(item.path)}
                            >
                                <ListItemIcon>
                                    {item.icon}
                                </ListItemIcon>
                                <ListItemText primary={item.text} />
                            </ListItemButton>
                        </ListItem>
                    ))}
                </List>
            </Box>
        </Drawer>
    );
};

export default Navigation;