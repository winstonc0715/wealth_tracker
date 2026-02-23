'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';

type Theme = 'default' | 'obsidian' | 'forest' | 'cyber';

interface ThemeContextType {
    theme: Theme;
    setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
    const [theme, setThemeState] = useState<Theme>('default');
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
        const savedTheme = localStorage.getItem('wt_theme') as Theme;
        if (savedTheme) {
            setThemeState(savedTheme);
            if (savedTheme !== 'default') {
                document.documentElement.setAttribute('data-theme', savedTheme);
            } else {
                document.documentElement.removeAttribute('data-theme');
            }
        }
    }, []);

    const setTheme = (newTheme: Theme) => {
        setThemeState(newTheme);
        localStorage.setItem('wt_theme', newTheme);
        if (newTheme !== 'default') {
            document.documentElement.setAttribute('data-theme', newTheme);
        } else {
            document.documentElement.removeAttribute('data-theme');
        }
    };

    return (
        <ThemeContext.Provider value={{ theme, setTheme }}>
            {children}
        </ThemeContext.Provider>
    );
}

export const useTheme = () => {
    const context = useContext(ThemeContext);
    if (context === undefined) {
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
};
