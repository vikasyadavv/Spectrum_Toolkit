// ============================================================
//  SETTINGS: change these values, then click Deploy
// ============================================================
const SETTINGS = {
  // Where the Spectrum Toolkit service lives (your VM, through the Cloudflare Tunnel)
  API_ORIGIN: 'https://stkapi.cheminations.com',

  // Websites allowed to use the toolkit (pages on these sites may send files and settings)
  ALLOWED_SITES: [
    'https://cheminations.com',
    'https://www.cheminations.com'
  ],

  // Allow opening a toolkit address directly in the browser's address bar (handy for testing).
  // Keep false normally, so only your web pages can use it.
  ALLOW_DIRECT_VISITS: false,

  // The requests the website may make, and how. Remove a line to switch that request off.
  //   GET:  the page asks for something    POST: the page sends a file or settings
  ALLOWED_REQUESTS: {
    'health': 'GET',          // is the toolkit running? (and its version)
    'options': 'GET',         // every method and plot setting, to build the page's forms
    'example': 'GET',         // three example spectra, before a file is loaded
    'load': 'POST',           // a data file -> its spectra
    'process': 'POST',        // spectra + processing steps -> processed spectra
    'process-file': 'POST',   // a data file + processing steps in one go
    'figure': 'POST',         // spectra + plot settings -> a picture (png, tiff, pdf, ...)
    'groups': 'POST',         // propose or set which sample each spectrum belongs to
    'style-check': 'POST'     // check a saved style before it is used
  },

  // Largest file or request the page may send, in MB (Cloudflare's free plan stops at 100 MB)
  MAX_UPLOAD_MB: 95,

  // How long Cloudflare keeps an answer that is the same for everyone, in minutes
  // (only these GET requests are kept; files and settings sent by visitors never are)
  CACHE_MINUTES: { options: 60, example: 60 },

  // If your VM can't be reached, a kept answer is served if it is younger than this many days
  KEEP_IF_OFFLINE_DAYS: 7,

  // How long a visitor's browser may reuse a kept answer, in minutes
  BROWSER_CACHE_MINUTES: 5,

  // Give up waiting for your VM after this many seconds (big files and 1200 dpi pictures take a while;
  // Cloudflare itself stops waiting at 100 s)
  API_TIMEOUT_SECONDS: 90,

  // Short-term limit: requests per IP within this many seconds. The live preview asks for a picture
  // after each change, so this is higher than for the Spectrum Explorer. Each Cloudflare location
  // counts on its own, so it is a rough first line of defence.
  RATE_LIMIT_REQUESTS: 120,
  RATE_LIMIT_WINDOW_SECONDS: 60
};
// ============================================================
//  Needs one secret on this Worker (Settings > Variables and Secrets > Add > Secret):
//    STK_API_KEY = the contents of ~/stk-secrets/api_key.txt on the VM
//  Route: cheminations.com/api/stk/*
// ============================================================


// ---- Small helpers --------------------------------------------------------------------------

// Headers of the toolkit's answers that the page needs, passed on as they are
const PASS_ON = ['Content-Type', 'Content-Disposition', 'X-Warning'];

// Remembers, per visitor IP, how many requests were made in the current window.
// Lives only in this Worker's memory, so it resets when Cloudflare restarts the Worker.
const recentRequests = new Map();

// Build an answer with the headers every answer gets. Errors are JSON {"detail": "..."},
// the same form the toolkit itself uses, so the page reads every message the same way.
function reply(body, status, extraHeaders = {}) {
  // Text, a picture (bytes) or a stream goes out as it is; anything else (an error message) becomes JSON
  const asIs = typeof body === 'string' || body === null || body instanceof ArrayBuffer || body instanceof ReadableStream;
  return new Response(asIs ? body : JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',         // JSON unless the toolkit says otherwise
      'X-Content-Type-Options': 'nosniff',                      // browsers must not guess another type
      'X-Robots-Tag': 'noindex',                                // search engines: don't list toolkit answers
      'Cache-Control': 'no-store',                              // answers to a visitor's own data are never kept
      ...extraHeaders
    }
  });
}

// True if the request comes from a page on one of ALLOWED_SITES
function fromOurSite(request) {
  const fetchSite = request.headers.get('Sec-Fetch-Site');      // set by modern browsers: who is asking
  const referer = request.headers.get('Referer') || '';         // the page that made the request
  const refererOk = SETTINGS.ALLOWED_SITES.some(site => referer.startsWith(site + '/'));
  if (fetchSite === 'none') return SETTINGS.ALLOW_DIRECT_VISITS; // typed into the address bar
  if (fetchSite === 'same-origin') return true;                 // a page on the same site
  if (fetchSite === 'same-site') return refererOk;              // e.g. www.cheminations.com
  if (fetchSite) return false;                                  // 'cross-site': another website
  return refererOk;                                             // older browsers: trust the Referer
}

// True if this IP made too many requests in the current window
function tooMany(ip) {
  const now = Date.now();
  const windowMs = SETTINGS.RATE_LIMIT_WINDOW_SECONDS * 1000;
  const entry = recentRequests.get(ip);
  if (!entry || now - entry.start > windowMs) {                 // first request, or the window is over
    recentRequests.set(ip, { start: now, count: 1 });
    if (recentRequests.size > 5000) {                           // keep memory small: forget old windows
      for (const [key, value] of recentRequests) {
        if (now - value.start > windowMs) recentRequests.delete(key);
      }
    }
    return false;
  }
  entry.count += 1;
  return entry.count > SETTINGS.RATE_LIMIT_REQUESTS;
}

// Turn the website's address into the toolkit's, or null if it isn't an allowed request.
// Website: /api/stk/figure   ->   toolkit: /figure
function apiPath(url) {
  const parts = url.pathname.replace(/^\/api\/stk\/?/, '').split('/').filter(Boolean);
  if (parts.length !== 1 || !(parts[0] in SETTINGS.ALLOWED_REQUESTS)) return null;
  return { kind: parts[0], method: SETTINGS.ALLOWED_REQUESTS[parts[0]], path: '/' + parts[0] };
}

// What the page may send with each POST: a file upload (form) for load and process-file, JSON for the rest
function rightBodyType(kind, contentType) {
  const form = kind === 'load' || kind === 'process-file';
  return form ? contentType.startsWith('multipart/form-data') : contentType.startsWith('application/json');
}

// Ask the VM, giving up if it has not started to answer after API_TIMEOUT_SECONDS. A sent file or
// settings go straight through (streamed, never held in the Worker's memory); only the headers the
// toolkit needs are passed on.
async function askApi(target, request, env) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), SETTINGS.API_TIMEOUT_SECONDS * 1000);
  const headers = { 'X-STK-Key': env.STK_API_KEY };             // the secret the toolkit checks
  if (target.method === 'POST') {
    headers['Content-Type'] = request.headers.get('Content-Type');      // includes the form's boundary
    headers['Content-Length'] = request.headers.get('Content-Length');
  }
  try {
    return await fetch(SETTINGS.API_ORIGIN + target.path, {
      method: target.method,
      headers,
      body: target.method === 'POST' ? request.body : undefined,
      signal: controller.signal
    });
  } finally {
    clearTimeout(timer);
  }
}

// The toolkit's answer, passed on with its own type, file name and font warning.
// body: the answer's bytes when they were read already, else it streams straight to the visitor.
function passOn(answer, extraHeaders = {}, body = answer.body) {
  const headers = { ...extraHeaders };
  for (const name of PASS_ON) {
    const value = answer.headers.get(name);
    if (value) headers[name] = value;
  }
  return reply(body, answer.status, headers);
}


// ---- The Worker -----------------------------------------------------------------------------

export default {
  async fetch(request, env, ctx) {
    // 1. Only pages on your website may ask
    if (!fromOurSite(request)) return reply({ detail: 'Not available' }, 403);

    // 2. Too many requests from one visitor in a short time
    const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
    if (tooMany(ip)) return reply({ detail: 'Too many requests, please wait a minute' }, 429);

    // 3. Only the allowed requests, each with its own method, ever reach your VM
    const url = new URL(request.url);
    const target = apiPath(url);
    if (!target) return reply({ detail: 'Not found' }, 404);
    if (request.method !== target.method) {
      return reply({ detail: 'Method not allowed' }, 405, { 'Allow': target.method });
    }

    // 4. Sent files and settings: the right kind, and not too big
    if (target.method === 'POST') {
      const contentType = request.headers.get('Content-Type') || '';
      if (!rightBodyType(target.kind, contentType)) {
        return reply({ detail: 'Wrong kind of request: send a file as a form, settings as JSON' }, 415);
      }
      const length = Number(request.headers.get('Content-Length'));
      if (!length) return reply({ detail: 'The size of the request is missing' }, 411);
      if (length > SETTINGS.MAX_UPLOAD_MB * 1024 * 1024) {
        return reply({ detail: `File larger than ${SETTINGS.MAX_UPLOAD_MB} MB` }, 413);
      }
    }

    // 5. Answers that are the same for everyone (options, example): is there a fresh saved copy here?
    const keep = SETTINGS.CACHE_MINUTES[target.kind];
    const cache = caches.default;
    const cacheKey = new Request(`${url.origin}/api/stk-cache${target.path}`);   // one entry per answer
    const saved = keep ? await cache.match(cacheKey) : null;
    const savedAt = saved ? Number(saved.headers.get('X-Saved-At') || 0) : 0;
    if (saved && Date.now() - savedAt < keep * 60 * 1000) {
      return reply(await saved.text(), 200, {
        'X-Cache': 'HIT', 'Cache-Control': `public, max-age=${SETTINGS.BROWSER_CACHE_MINUTES * 60}`
      });
    }

    // 6. Ask your VM
    let answer = null;
    try {
      answer = await askApi(target, request, env);
    } catch (e) {
      answer = null;                                            // VM unreachable or too slow
    }

    // 7. A good answer to options or example: save it (in the background) and pass it on
    if (answer && answer.status === 200 && keep) {
      const body = await answer.arrayBuffer();                  // small (under 200 KB): read it once, use it twice
      const keepSeconds = SETTINGS.KEEP_IF_OFFLINE_DAYS * 24 * 3600;
      ctx.waitUntil(cache.put(cacheKey, new Response(body.slice(0), {
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Cache-Control': `public, max-age=${keepSeconds}`,     // Cloudflare may keep it this long
          'X-Saved-At': String(Date.now())                       // so we know how old it is
        }
      })));
      return passOn(answer, {
        'X-Cache': 'MISS', 'Cache-Control': `public, max-age=${SETTINGS.BROWSER_CACHE_MINUTES * 60}`
      }, body);
    }

    // 8. Every other answer from the toolkit (results, pictures, and its clear messages about wrong
    //    files or settings: 413, 422, 500) goes back as it is. 401 means the key is wrong: that is
    //    our setup, not the visitor's fault, so it is treated like the VM being down.
    if (answer && answer.status !== 401 && answer.status < 502) return passOn(answer);

    // 9. The VM is down or failing: use the saved answer if there is one and it isn't too old
    if (saved && Date.now() - savedAt < SETTINGS.KEEP_IF_OFFLINE_DAYS * 24 * 3600 * 1000) {
      return reply(await saved.text(), 200, { 'X-Cache': 'STALE' });
    }
    return reply({ detail: 'The Spectrum Toolkit is temporarily unavailable, please try again in a minute' }, 503);
  }
};
