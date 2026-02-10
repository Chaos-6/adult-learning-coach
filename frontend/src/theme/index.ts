/**
 * MUI Theme configuration for the Adult Learning Coach.
 *
 * Design system:
 * - Primary: Navy blue (#1a365d) — trust, professionalism
 * - Secondary: Teal (#2d8f7b) — growth, learning
 * - Success: Green (#38a169) — strengths, achievements
 * - Warning: Amber (#d69e2e) — growth areas (not "bad", just "room to grow")
 * - Error: Red (#e53e3e) — failures, critical issues
 *
 * Why these colors? Coaching is supportive, not punitive.
 * We use "growth areas" instead of "weaknesses" and warm amber
 * instead of harsh red to signal opportunity, not failure.
 */

import { createTheme } from "@mui/material/styles";

const theme = createTheme({
  palette: {
    primary: {
      main: "#1a365d",
      light: "#2a4a7f",
      dark: "#0f2340",
      contrastText: "#ffffff",
    },
    secondary: {
      main: "#2d8f7b",
      light: "#3bb09a",
      dark: "#1e6b5a",
      contrastText: "#ffffff",
    },
    success: {
      main: "#38a169",
      light: "#68d391",
      dark: "#276749",
    },
    warning: {
      main: "#d69e2e",
      light: "#ecc94b",
      dark: "#b7791f",
    },
    error: {
      main: "#e53e3e",
      light: "#fc8181",
      dark: "#c53030",
    },
    background: {
      default: "#f7fafc",
      paper: "#ffffff",
    },
    text: {
      primary: "#1a202c",
      secondary: "#4a5568",
    },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h4: {
      fontWeight: 700,
      letterSpacing: "-0.01em",
    },
    h5: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 600,
    },
    subtitle1: {
      color: "#4a5568",
    },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)",
          border: "1px solid #e2e8f0",
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: "none",
          fontWeight: 600,
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 500,
        },
      },
    },
  },
});

export default theme;
