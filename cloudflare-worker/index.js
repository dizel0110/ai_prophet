// AI Prophet — Telegram API Proxy for Hugging Face Spaces
// Cloudflare Workers free tier (100k req/day, no credit card needed)
// Deploy: Create Worker → Paste this → Save & Deploy

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const targetUrl = 'https://api.telegram.org' + url.pathname + url.search;

    const headers = new Headers(request.headers);
    headers.set('Host', 'api.telegram.org');

    const body = ['GET', 'HEAD'].includes(request.method)
      ? undefined
      : await request.text();

    return fetch(targetUrl, {
      method: request.method,
      headers,
      body,
    });
  },
};
