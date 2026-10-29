import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './views/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Indian Institutional Palette (Repo 1)
        'court-maroon': '#881337',
        'ashoka-navy': '#0F172A',
        'statutory-green': '#065F46',
        'saffron-deep': '#C2410C',

        // Beige palette (Repo 2 Canvas & Surfaces)
        beige: {
          50: '#FBF9F5',
          100: '#F5F0E6',
          200: '#EBE3D3',
          300: '#DCD0B8',
          800: '#4A4438',
          900: '#2C271E',
        },
        // Very Light Saffron palette (Repo 2 Primary Brand & Highlights)
        saffron: {
          50: '#FFF9F0',
          100: '#FFF3E0',
          200: '#FFE0B2',
          300: '#FFCC80',
          500: '#FF9933',
          700: '#D97706',
        },
        // Very Light Blue palette (Repo 2 Secondary Accents & Highlights)
        iceblue: {
          50: '#F4F8FC',
          100: '#EBF5FF',
          200: '#D6E8FA',
          300: '#B5D8F8',
          600: '#2563EB',
          800: '#1E40AF',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
};

export default config;
