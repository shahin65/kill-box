/**
 * Kill Box Telegram reverse proxy.
 * Forwards Django -> this Worker -> https://api.telegram.org
 *
 * Bind Worker secret PROXY_SECRET. Django sends the same value as
 * X-Killbox-Proxy-Secret. Only /bot... and /file/bot... paths are proxied.
 */
const TELEGRAM_ORIGIN = 'https://api.telegram.org';
const HOP = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
  'host',
  'cf-connecting-ip',
  'cf-ipcountry',
  'cf-ray',
  'cf-visitor',
  'cdn-loop',
  'x-forwarded-for',
  'x-forwarded-proto',
  'x-real-ip',
  'x-killbox-proxy-secret',
]);

function allowedPath(pathname) {
  return pathname.startsWith('/bot') || pathname.startsWith('/file/bot');
}

export default {
  async fetch(request, env) {
    const expected = String(env.PROXY_SECRET || '');
    if (!expected) {
      return new Response('Proxy is not configured.', { status: 500 });
    }
    const got = request.headers.get('X-Killbox-Proxy-Secret') || '';
    if (got !== expected) {
      return new Response('Forbidden', { status: 403 });
    }

    const incoming = new URL(request.url);
    if (!allowedPath(incoming.pathname)) {
      return new Response('Not found', { status: 404 });
    }

    const target = new URL(incoming.pathname + incoming.search, TELEGRAM_ORIGIN);
    const headers = new Headers();
    for (const [key, value] of request.headers.entries()) {
      if (!HOP.has(key.toLowerCase())) {
        headers.set(key, value);
      }
    }

    const init = {
      method: request.method,
      headers,
      redirect: 'follow',
    };
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      init.body = request.body;
    }

    return fetch(target, init);
  },
};
