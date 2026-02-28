import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {
      colors: {
        bg: '#070f1f',
        panel: '#0d1728',
        panel2: '#111f34',
        text: '#e7efff',
        muted: '#9bb2d3',
        accent: '#4ea1ff'
      }
    }
  },
  plugins: []
};

export default config;
