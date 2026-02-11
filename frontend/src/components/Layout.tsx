/**
 * Application shell — sidebar navigation + main content area.
 *
 * This is the persistent frame around every page. It provides:
 * 1. A sidebar with navigation links
 * 2. A top bar with the app title
 * 3. A content area where pages render via React Router's <Outlet>
 *
 * Why a sidebar layout? Coaching dashboards need quick navigation
 * between uploading, reviewing reports, and tracking progress.
 * A sidebar keeps all navigation visible without eating into content space.
 */

import React, { useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import {
  AppBar,
  Box,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import DashboardIcon from "@mui/icons-material/Dashboard";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import CompareArrowsIcon from "@mui/icons-material/CompareArrows";
import SchoolIcon from "@mui/icons-material/School";

const DRAWER_WIDTH = 240;

const navItems = [
  { label: "Dashboard", path: "/", icon: <DashboardIcon /> },
  { label: "Upload Video", path: "/upload", icon: <CloudUploadIcon /> },
  { label: "Compare Videos", path: "/comparisons/new", icon: <CompareArrowsIcon /> },
];

export default function Layout() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const handleNav = (path: string) => {
    navigate(path);
    if (isMobile) setMobileOpen(false);
  };

  const drawerContent = (
    <Box sx={{ mt: 2 }}>
      {/* Brand mark */}
      <Box sx={{ px: 2, pb: 2, display: "flex", alignItems: "center", gap: 1 }}>
        <SchoolIcon sx={{ color: "primary.main", fontSize: 28 }} />
        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: "primary.main" }}>
          Learning Coach
        </Typography>
      </Box>

      <List>
        {navItems.map((item) => (
          <ListItemButton
            key={item.path}
            selected={location.pathname === item.path}
            onClick={() => handleNav(item.path)}
            sx={{
              mx: 1,
              borderRadius: 1,
              "&.Mui-selected": {
                backgroundColor: "primary.main",
                color: "white",
                "&:hover": { backgroundColor: "primary.dark" },
                "& .MuiListItemIcon-root": { color: "white" },
              },
            }}
          >
            <ListItemIcon sx={{ minWidth: 36 }}>{item.icon}</ListItemIcon>
            <ListItemText primary={item.label} />
          </ListItemButton>
        ))}
      </List>
    </Box>
  );

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      {/* App Bar — only visible on mobile as a hamburger menu trigger */}
      {isMobile && (
        <AppBar position="fixed" sx={{ zIndex: theme.zIndex.drawer + 1 }}>
          <Toolbar>
            <IconButton
              color="inherit"
              edge="start"
              onClick={() => setMobileOpen(!mobileOpen)}
              sx={{ mr: 2 }}
            >
              <MenuIcon />
            </IconButton>
            <Typography variant="h6" noWrap>
              Adult Learning Coach
            </Typography>
          </Toolbar>
        </AppBar>
      )}

      {/* Sidebar */}
      <Box component="nav" sx={{ width: { md: DRAWER_WIDTH }, flexShrink: 0 }}>
        {isMobile ? (
          <Drawer
            variant="temporary"
            open={mobileOpen}
            onClose={() => setMobileOpen(false)}
            ModalProps={{ keepMounted: true }}
            sx={{ "& .MuiDrawer-paper": { width: DRAWER_WIDTH } }}
          >
            {drawerContent}
          </Drawer>
        ) : (
          <Drawer
            variant="permanent"
            sx={{
              "& .MuiDrawer-paper": {
                width: DRAWER_WIDTH,
                borderRight: "1px solid #e2e8f0",
              },
            }}
            open
          >
            {drawerContent}
          </Drawer>
        )}
      </Box>

      {/* Main content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          mt: isMobile ? 8 : 0,
          backgroundColor: "background.default",
          minHeight: "100vh",
        }}
      >
        <Outlet />
      </Box>
    </Box>
  );
}
