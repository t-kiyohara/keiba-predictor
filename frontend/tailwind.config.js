/** @type {import('tailwindcss').Config} */
/* DESIGN.md「重賞スコープ」§2/§3/§9 のトークン。ライト固定・角丸なし・影なし。
   色の定義元は src/index.css の :root(CSS 変数)。ここはその参照に留める。 */
const colors = {
  paper: 'var(--paper)',
  'paper-inset': 'var(--paper-inset)',
  ink: 'var(--ink)',
  'ink-weak': 'var(--ink-weak)',
  rule: 'var(--rule)',
  shu: 'var(--shu)',
  ai: 'var(--ai)',
  white: '#FFFFFF',
  transparent: 'transparent',
  current: 'currentColor',
};

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    // 地の色数を最小限に保つため、パレットは全面差し替え(Tailwind 既定色は使わない)
    colors,
    borderColor: { ...colors, DEFAULT: colors.rule },
    // 角丸は使わない(DESIGN.md §1)
    borderRadius: { none: '0' },
    extend: {
      screens: {
        // 馬柱の縦組み→横テーブルのフォールバック境界(DESIGN.md §4)
        sp: { max: '767px' },
      },
      fontFamily: {
        // 題字・レース名・日付見出しのみ明朝
        mincho: ['"Shippori Mincho B1"', 'serif'],
        sans: ['"IBM Plex Sans JP"', '"Hiragino Sans"', 'sans-serif'],
      },
      fontSize: {
        // DESIGN.md §3 のスケール
        caption: ['12px', { lineHeight: '1.5' }],
        data: ['13px', { lineHeight: '1.5' }],
        body: ['14px', { lineHeight: '1.7' }],
        heading: ['18px', { lineHeight: '1.4' }],
        'race-name': ['26px', { lineHeight: '1.3' }],
        logo: ['28px', { lineHeight: '1.2' }],
        figure: ['34px', { lineHeight: '1.1' }],
      },
      maxWidth: {
        page: '1080px',
      },
      transitionDuration: {
        // hover の背景遷移のみ(DESIGN.md §6)
        DEFAULT: '100ms',
      },
    },
  },
  corePlugins: {
    // 紙面に影は使わない(DESIGN.md §1)
    boxShadow: false,
    boxShadowColor: false,
    ringWidth: false,
    ringColor: false,
    ringOffsetWidth: false,
    ringOffsetColor: false,
  },
  plugins: [],
};
