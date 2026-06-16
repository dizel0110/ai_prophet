// AI Prophet — Telegram API Proxy + R2 Video Storage
// Deploy: wrangler deploy (or Cloudflare Dashboard → Paste → Save & Deploy)

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // ── R2 Upload ──
    if (url.pathname === '/r2/upload' && request.method === 'POST') {
      try {
        const formData = await request.formData();
        const file = formData.get('file');
        if (!file) return new Response('Missing file', { status: 400 });

        const filename = Date.now() + '_' + (file.name || 'video.mp4');
        await env.VIDEOS_BUCKET.put(filename, file.stream(), {
          httpMetadata: { contentType: file.type || 'video/mp4' },
        });

        const publicUrl = url.origin + '/r2/file/' + filename;
        return new Response(publicUrl, { status: 200 });
      } catch (e) {
        return new Response('Upload error: ' + e.message, { status: 500 });
      }
    }

    // ── R2 Serve (public files) ──
    if (url.pathname.startsWith('/r2/file/')) {
      const filename = url.pathname.replace('/r2/file/', '');
      const object = await env.VIDEOS_BUCKET.get(filename);
      if (!object) return new Response('Not found', { status: 404 });

      const headers = new Headers();
      object.writeHttpMetadata(headers);
      headers.set('ETag', object.httpEtag);
      headers.set('Accept-Ranges', 'bytes');
      headers.set('Access-Control-Allow-Origin', '*');
      headers.set('Cache-Control', 'public, max-age=3600');

      const range = request.headers.get('range');
      if (range) {
        // Byte-range support for video streaming
        const size = object.size;
        const parts = range.replace(/bytes=/, '').split('-');
        const start = parseInt(parts[0], 10);
        const end = parts[1] ? parseInt(parts[1], 10) : size - 1;
        const chunkSize = end - start + 1;
        headers.set('Content-Range', `bytes ${start}-${end}/${size}`);
        headers.set('Content-Length', chunkSize);
        const stream = object.body.slice(start, end + 1);
        return new Response(stream, { status: 206, headers });
      }

      headers.set('Content-Length', object.size);
      return new Response(object.body, { status: 200, headers });
    }

    // ── R2 Delete ──
    if (url.pathname === '/r2/delete' && request.method === 'POST') {
      try {
        const body = await request.json();
        const filename = body.filename;
        if (!filename) return new Response('Missing filename', { status: 400 });
        await env.VIDEOS_BUCKET.delete(filename);
        return new Response('OK', { status: 200 });
      } catch (e) {
        return new Response('Delete error: ' + e.message, { status: 500 });
      }
    }

    // ── Default: Telegram API Proxy ──
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
