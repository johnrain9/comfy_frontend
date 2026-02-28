import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: 'index.html'
    }),
    // V2 is served under /v2 by FastAPI.
    paths: {
      base: '/v2'
    },
    alias: {
      $lib: 'src/lib'
    }
  }
};

export default config;
