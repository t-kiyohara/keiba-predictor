/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    screens: {
      sp: { max: '599px' },
      tablet: { min: '600px', max: '959px' },
      desktop: '960px',
    },
    extend: {
      colors: {
        primary: '#0077c7',
        danger: '#e01e5a',
        warning: '#ffcc17',
        link: '#0071c1',
        orange: '#ff9900',
        'text-black': '#23221e',
        'text-grey': '#706d65',
        'text-disabled': '#c1bdb7',
        'stone-01': '#f8f7f6',
        'stone-02': '#edebe8',
        'stone-03': '#aaa69f',
        'stone-04': '#4e4c49',
        border: '#d6d3d0',
        surface: '#ffffff',
        'over-bg': '#f2f1f0',
      },
      fontFamily: {
        sans: [
          'AdjustedYuGothic',
          '"Yu Gothic"',
          'YuGothic',
          '"Hiragino Sans"',
          'sans-serif',
        ],
      },
      fontSize: {
        xxs: ['0.667rem', { lineHeight: '1.5' }],
        xs: ['0.75rem', { lineHeight: '1.5' }],
        sm: ['0.857rem', { lineHeight: '1.5' }],
        base: ['1rem', { lineHeight: '1.5' }],
        lg: ['1.2rem', { lineHeight: '1.25' }],
        xl: ['1.5rem', { lineHeight: '1.25' }],
        '2xl': ['2rem', { lineHeight: '1.25' }],
      },
      borderRadius: {
        DEFAULT: '6px',
      },
      boxShadow: {
        sm: '0 2px 4px rgba(0,0,0,0.1)',
        md: '0 4px 8px rgba(0,0,0,0.15)',
      },
    },
  },
  plugins: [],
};
