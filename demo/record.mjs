import { chromium } from 'playwright';
import { execSync, spawn } from 'child_process';
import { readdirSync, writeFileSync, existsSync, mkdirSync, renameSync } from 'fs';
import { join, resolve } from 'path';

const ROOT = resolve(import.meta.dirname, '..');
const RAW = join(import.meta.dirname, 'raw-scenes');
const OUTPUT = join(import.meta.dirname, 'openEDUdata-demo.mp4');
const VIEWPORT = { width: 1280, height: 720 };
const VITE_URL = process.env.VITE_URL || 'http://[::1]:5180';

// ─── Mock data ──────────────────────────────────────────────────────────────

const DASHBOARD_DATA = {
  gevonden: true,
  laatste_jaar: '2023',
  ingeschrevenen: { '2019': 34500, '2020': 35100, '2021': 35891, '2022': 36234, '2023': 37012 },
  eerstejaars: { '2019': 7800, '2020': 8012, '2021': 8234, '2022': 8567, '2023': 8891 },
  gediplomeerden: { '2019': 6200, '2020': 6450, '2021': 6700, '2022': 6890, '2023': 7100 },
  sectoren: {
    ECONOMIE: 8500, GEZONDHEIDSZORG: 7200, TECHNIEK: 6100,
    ONDERWIJS: 5400, GEDRAG_EN_MAATSCHAPPIJ: 4800, TAAL_EN_CULTUUR: 2100, SECTOROVERSTIJGEND: 2912,
  },
  geslacht: { VROUW: 21500, MAN: 15512 },
};

const MODELS_CONFIG = {
  models: [
    { id: 'claude-sonnet-4-6', name: 'Claude Sonnet 4.6', description: 'Snel en nauwkeurig' },
    { id: 'gpt-4o', name: 'GPT-4o', description: 'OpenAI' },
  ],
  default_model: 'claude-sonnet-4-6',
};

// ─── WebSocket mock script (injected via addInitScript) ─────────────────────

const WS_MOCK_SCRIPT = `
(function() {
  const OrigWS = window.WebSocket;
  window.__wsMocks = [];

  window.WebSocket = function(url, protocols) {
    // Let Vite HMR WebSocket through
    if (!url.includes('/api/chat')) {
      return new OrigWS(url, protocols);
    }

    const mock = {
      url, readyState: 0,
      CONNECTING: 0, OPEN: 1, CLOSED: 3,
      onopen: null, onclose: null, onmessage: null, onerror: null,
      _listeners: {},
      addEventListener(type, fn) {
        this._listeners[type] = this._listeners[type] || [];
        this._listeners[type].push(fn);
      },
      removeEventListener(type, fn) {
        if (this._listeners[type]) this._listeners[type] = this._listeners[type].filter(f => f !== fn);
      },
      send(data) {
        window.__wsLastSent = JSON.parse(data);
        window.__wsOnSend?.(window.__wsLastSent);
      },
      close() { this.readyState = 3; },
      _emit(event) {
        const msg = { data: JSON.stringify(event) };
        if (this.onmessage) this.onmessage(msg);
        (this._listeners['message'] || []).forEach(fn => fn(msg));
      },
    };

    window.__wsMocks.push(mock);
    window.__wsMock = mock;

    setTimeout(() => {
      mock.readyState = 1;
      if (mock.onopen) mock.onopen({});
      (mock._listeners['open'] || []).forEach(fn => fn({}));
    }, 100);

    return mock;
  };
  // Copy static properties
  window.WebSocket.CONNECTING = 0;
  window.WebSocket.OPEN = 1;
  window.WebSocket.CLOSING = 2;
  window.WebSocket.CLOSED = 3;
})();
`;

// ─── Helpers ────────────────────────────────────────────────────────────────

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

async function setupMocks(page) {
  await page.addInitScript(WS_MOCK_SCRIPT);

  await page.route('**/api/auth/status', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ required: false }) })
  );
  await page.route('**/api/settings/config', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MODELS_CONFIG) })
  );
  await page.route('**/api/dashboard/instroom**', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(DASHBOARD_DATA) })
  );
  await page.route('**/api/starters', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })
  );
}

async function seedSettings(page, opts = {}) {
  const settings = {
    instelling: opts.instelling || 'Hogeschool Utrecht',
    functie: opts.functie || 'Beleidsmedewerker',
    mode: opts.mode || 'light',
  };
  await page.addInitScript(({ settings }) => {
    localStorage.setItem('openEDUdata_settings', JSON.stringify(settings));
    localStorage.setItem('openEDUdata_onboarded', '1');
    localStorage.removeItem('openEDUdata_conversations');
    localStorage.removeItem('openEDUdata_current_chat');
    localStorage.removeItem('edudata_workbooks');
    localStorage.removeItem('edudata_dc_messages');
    localStorage.removeItem('edudata_dc_figures');
  }, { settings });
}

async function showAnnotation(page, text, position = 'bottom-center', durationMs = 2500) {
  const posStyles = {
    'bottom-center': 'bottom:80px;left:50%;transform:translateX(-50%);',
    'top-center': 'top:80px;left:50%;transform:translateX(-50%);',
    'top-right': 'top:80px;right:24px;',
    'top-left': 'top:80px;left:24px;',
    'center': 'top:50%;left:50%;transform:translate(-50%,-50%);',
    'bottom-right': 'bottom:100px;right:24px;',
    'bottom-left': 'bottom:100px;left:24px;',
  };
  await page.evaluate(({ text, style }) => {
    const el = document.createElement('div');
    el.className = '__demo-annotation';
    el.textContent = text;
    el.setAttribute('style',
      `position:fixed;z-index:99999;pointer-events:none;` +
      `background:rgba(37,99,235,0.92);color:white;` +
      `padding:14px 28px;border-radius:14px;` +
      `font-size:17px;font-weight:700;font-family:Inter,system-ui,sans-serif;` +
      `box-shadow:0 6px 28px rgba(0,0,0,0.2);` +
      `animation:fadeInAnnotation .3s ease;` + style
    );
    if (!document.querySelector('#__demo-anim-style')) {
      const s = document.createElement('style');
      s.id = '__demo-anim-style';
      s.textContent = '@keyframes fadeInAnnotation{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}';
      document.head.appendChild(s);
    }
    document.body.appendChild(el);
  }, { text, style: posStyles[position] || posStyles['bottom-center'] });
  await delay(durationMs);
  await page.evaluate(() => document.querySelectorAll('.__demo-annotation').forEach(e => e.remove()));
}

async function clearAnnotations(page) {
  await page.evaluate(() => document.querySelectorAll('.__demo-annotation').forEach(e => e.remove()));
}

async function emitWs(page, event) {
  await page.evaluate((ev) => {
    if (window.__wsMock) window.__wsMock._emit(ev);
  }, event);
}

async function streamText(page, text, chunkSize = 8, delayMs = 30) {
  for (let i = 0; i < text.length; i += chunkSize) {
    const chunk = text.slice(i, i + chunkSize);
    await emitWs(page, { type: 'text_delta', content: chunk });
    await delay(delayMs);
  }
}

async function typeText(page, selector, text, delayMs = 40) {
  await page.click(selector);
  for (const char of text) {
    await page.keyboard.type(char, { delay: delayMs });
  }
}

// ─── Scene recordings ───────────────────────────────────────────────────────

async function recordScene(browser, name, sceneFn, opts = {}) {
  console.log(`  Recording scene: ${name}...`);
  const context = await browser.newContext({
    viewport: VIEWPORT,
    recordVideo: { dir: RAW, size: VIEWPORT },
    colorScheme: opts.colorScheme || 'light',
  });
  const page = await context.newPage();
  await setupMocks(page);
  if (opts.seedSettings !== false) {
    await seedSettings(page, opts.settings || {});
  }
  await page.goto(VITE_URL, { waitUntil: 'networkidle' });
  await delay(600);

  try {
    await sceneFn(page);
  } catch (err) {
    console.error(`  Error in scene ${name}:`, err.message);
  }

  await delay(500);
  const videoPath = await page.video().path();
  await context.close();

  const dest = join(RAW, `${name}.webm`);
  renameSync(videoPath, dest);
  console.log(`  Saved: ${dest}`);
  return dest;
}

// ─── SCENE 1: Home Page ─────────────────────────────────────────────────────

async function sceneHome(page) {
  await delay(800);
  await showAnnotation(page, 'Home — direct toegang tot chat en dashboards', 'bottom-center', 2500);
  await delay(500);

  // Scroll to features
  await page.evaluate(() => {
    document.querySelector('.section')?.scrollIntoView({ behavior: 'smooth' });
  });
  await delay(1500);
  await showAnnotation(page, 'Vraag in gewone taal, dashboards zonder BI-kennis', 'top-center', 2500);
  await delay(500);

  // Scroll to benefits
  await page.evaluate(() => {
    const sections = document.querySelectorAll('.section');
    if (sections[1]) sections[1].scrollIntoView({ behavior: 'smooth' });
  });
  await delay(1500);
  await showAnnotation(page, 'Direct inzichten, altijd dezelfde data', 'top-center', 2000);
  await delay(500);

  // Open data sources modal
  await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }));
  await delay(1000);
  const sourcesBtn = page.locator('button.sources-link');
  if (await sourcesBtn.isVisible()) {
    await sourcesBtn.click();
    await delay(800);
    await showAnnotation(page, 'CBS, RIO en DUO — 120+ open datasets', 'top-center', 2500);
    await delay(500);
    // Close modal
    await page.keyboard.press('Escape');
    await page.evaluate(() => {
      document.querySelectorAll('[style*="position: fixed"]').forEach(el => {
        if (el.textContent.includes('CBS') || el.textContent.includes('Databronnen')) el.remove();
      });
    });
  }
  await delay(500);
}

// ─── SCENE 2: Settings Onboarding ───────────────────────────────────────────

async function sceneSettings(page) {
  // Click the settings button (top right)
  await delay(500);
  const settingsBtn = page.locator('nav.navbar button[title="Instellingen"]');
  await settingsBtn.waitFor({ state: 'visible', timeout: 5000 });
  await settingsBtn.click();
  await delay(1200);

  // Wait for the modal to be visible
  await page.waitForSelector('input[placeholder="Naam van je instelling"]', { state: 'visible', timeout: 5000 });
  await delay(500);
  await showAnnotation(page, 'Stel je profiel in — instelling, rol en weergave', 'top-right', 2500);
  await delay(500);

  // Clear and retype institution name for the demo
  const input = page.locator('input[placeholder="Naam van je instelling"]');
  await input.click();
  await input.fill('');
  await delay(300);
  await typeText(page, 'input[placeholder="Naam van je instelling"]', 'Hogeschool Utrecht', 50);
  await delay(800);

  // Click a function
  await page.click('text=Beleidsmedewerker');
  await delay(600);
  await showAnnotation(page, 'Rol bepaalt gepersonaliseerde suggesties', 'top-right', 2000);
  await delay(500);

  // Show mode options
  await showAnnotation(page, 'Kies lichte, donkere of systeemweergave', 'top-right', 2000);
  await delay(500);

  // Click save
  await page.click('text=Opslaan');
  await delay(1000);
}

// ─── SCENE 3: Chat ──────────────────────────────────────────────────────────

async function sceneChat(page) {
  // Navigate to chat
  await page.click('text=Chat');
  await delay(1000);

  // Show welcome
  await showAnnotation(page, 'Gepersonaliseerde begroeting met je instelling en rol', 'bottom-center', 2500);
  await delay(500);

  // Open "Instroom" category in sidebar
  const instroomBtn = page.locator('button.suggested-category-btn', { hasText: 'Instroom' });
  if (await instroomBtn.isVisible()) {
    await instroomBtn.click();
    await delay(800);
    await showAnnotation(page, 'Suggestievragen per thema — gepersonaliseerd', 'bottom-left', 2000);
    await delay(500);
  }

  // Click a suggested question
  const suggestedQ = page.locator('button.suggested-btn', { hasText: 'voltijdonderwijs' });
  if (await suggestedQ.count() > 0) {
    await suggestedQ.first().click();
  } else {
    // Fallback: type a question manually
    await page.fill('.chat-input', 'Hoe heeft de deelname aan voltijdonderwijs bij Hogeschool Utrecht zich ontwikkeld?');
    await page.click('.send-btn');
  }
  await delay(500);

  // Wait for WS mock to be ready, then simulate response
  await delay(300);
  await emitWs(page, { type: 'message_start' });
  await delay(400);

  // Tool steps
  const tools = [
    { name: 'search_catalog', label: 'Catalogus doorzoeken...' },
    { name: 'query_duo_1', label: 'DUO data ophalen: voltijdinschrijvingen (p01hoinges)...' },
    { name: 'query_duo_2', label: 'DUO data ophalen: eerstejaars voltijd (p02ho1ejrs)...' },
  ];
  for (const tool of tools) {
    await emitWs(page, { type: 'tool_start', name: tool.name, label: tool.label });
    await delay(800);
    await emitWs(page, { type: 'tool_end', name: tool.name });
    await delay(200);
  }

  await showAnnotation(page, 'Automatisch de juiste databronnen gevonden', 'bottom-right', 2000);
  await delay(300);

  // Stream the response in blocks: prose is streamed char-by-char, tables sent as one chunk
  // so ReactMarkdown can render them properly
  const blocks = [
    { type: 'stream', text: `## Voltijdonderwijs Hogeschool Utrecht\n\nDe deelname aan voltijdonderwijs bij Hogeschool Utrecht laat een **stijgende trend** zien over de afgelopen jaren:\n\n` },
    { type: 'block', text: `| Jaar | Voltijd ingeschrevenen | Eerstejaars voltijd |\n|------|----------------------|---------------------|\n| 2019 | 28.450 | 6.820 |\n| 2020 | 29.100 | 7.015 |\n| 2021 | 29.890 | 7.234 |\n| 2022 | 30.540 | 7.567 |\n| 2023 | 31.200 | 7.891 |\n\n` },
    { type: 'stream', text: `De totale voltijdpopulatie groeide met **9,7%** in vijf jaar. De instroom van eerstejaars steeg met **15,7%**, wat wijst op een toenemende aantrekkingskracht.\n\nDe sterkste groei is zichtbaar in de sectoren **Techniek** (+18%) en **Gezondheidszorg** (+14%).` },
  ];

  for (const block of blocks) {
    if (block.type === 'block') {
      await emitWs(page, { type: 'text_delta', content: block.text });
      await delay(300);
    } else {
      await streamText(page, block.text, 12, 20);
    }
  }
  await delay(300);
  await emitWs(page, { type: 'message_end' });
  await delay(800);

  await showAnnotation(page, 'Markdown met tabellen — direct bruikbaar', 'bottom-center', 2500);
  await delay(500);

  // Now emit clarification options
  await emitWs(page, {
    type: 'clarification',
    vraag: 'Wil je verder inzoomen op deze data?',
    opties: [
      { label: 'Voltijd vs. deeltijd vergelijken', aanbevolen: true, beschrijving: 'Beide vormen naast elkaar' },
      { label: 'Per sector uitsplitsen', beschrijving: 'Instroom per CROHO-sector' },
      { label: 'Vergelijk met regio', beschrijving: 'Hogeschool Utrecht vs. regio Utrecht' },
    ],
  });
  await delay(1000);
  await showAnnotation(page, 'Slimme vervolgvragen — klik om dieper in te zoomen', 'bottom-center', 2500);
  await delay(500);

  // Show the "Maak dashboard" button
  await showAnnotation(page, 'Eén klik: gesprek wordt een dashboard', 'bottom-left', 2000);
  await delay(800);
}

// ─── SCENE 4: Dashboard ─────────────────────────────────────────────────────

async function sceneDashboard(page) {
  // Navigate to dashboard
  await page.click('text=Dashboard');
  await delay(1200);

  await showAnnotation(page, 'Dashboard-galerij met voorgebouwde en eigen dashboards', 'top-center', 2500);
  await delay(500);

  // Click built-in dashboard
  const builtinCard = page.locator('.wb-card').first();
  await builtinCard.click();
  await delay(2000);

  // Wait for charts to render
  await page.waitForSelector('canvas', { state: 'visible', timeout: 5000 }).catch(() => {});
  await delay(1500);

  await showAnnotation(page, 'Live KPI\'s en grafieken — automatisch bijgewerkt', 'top-center', 2500);
  await delay(500);

  // Scroll down to see more charts
  await page.evaluate(() => {
    document.querySelector('.wb-viewer-content')?.scrollBy({ top: 300, behavior: 'smooth' });
  });
  await delay(1500);
  await showAnnotation(page, 'Sectorverdeling, instroom en diplomering in één overzicht', 'bottom-center', 2500);
  await delay(500);

  // Go back
  await page.click('.wb-back-btn');
  await delay(800);

  // Click "Nieuw dashboard" (first one, skip DEV-only test button)
  const newBtn = page.locator('.wb-new-card').first();
  await newBtn.click();
  await delay(1000);

  await showAnnotation(page, 'Beschrijf in woorden welk dashboard je wilt', 'top-center', 2500);
  await delay(800);

  // Type in the creator textarea
  const dcInput = page.locator('.dc-textarea');
  await dcInput.click();
  await typeText(page, '.dc-textarea', 'Vergelijk de instroom per sector bij Hogeschool Utrecht', 35);
  await delay(800);
}

// ─── SCENE 5: Dark Mode ─────────────────────────────────────────────────────

async function sceneDarkMode(page) {
  // Navigate to chat to show content
  await page.click('text=Chat');
  await delay(800);

  // Open settings
  const settingsBtn = page.locator('nav.navbar button[title="Instellingen"]');
  if (await settingsBtn.isVisible()) {
    await settingsBtn.click();
  } else {
    await page.click('text=Hogeschool Utrecht');
  }
  await delay(800);

  // Click "Donker"
  await page.click('text=Donker');
  await delay(400);

  await showAnnotation(page, 'Donkere modus voor comfortabel werken', 'top-center', 2000);
  await delay(500);

  // Save
  await page.click('text=Opslaan');
  await delay(1500);

  // Show the dark mode result
  await showAnnotation(page, 'Alle pagina\'s en grafieken passen zich aan', 'bottom-center', 2500);
  await delay(500);

  // Navigate to dashboard to show dark mode there too
  await page.click('text=Dashboard');
  await delay(1200);

  const builtinCard = page.locator('.wb-card').first();
  await builtinCard.click();
  await delay(2000);
  await page.waitForSelector('canvas', { state: 'visible', timeout: 5000 }).catch(() => {});
  await delay(1500);
  await showAnnotation(page, 'Dashboard in dark mode', 'top-center', 2000);
  await delay(800);
}

// ─── Main ───────────────────────────────────────────────────────────────────

async function main() {
  console.log('openEDUdata+ Demo Video Recorder');
  console.log('=================================\n');

  // Ensure raw dir exists
  if (!existsSync(RAW)) mkdirSync(RAW, { recursive: true });

  // Check Vite is running
  try {
    const res = await fetch(VITE_URL, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  } catch {
    console.error(`ERROR: Vite dev server not running at ${VITE_URL}`);
    console.error('Start it first: cd frontend && npx vite --port 5173');
    process.exit(1);
  }

  const browser = await chromium.launch({ headless: true });

  const scenes = [
    ['scene-01-home', sceneHome],
    ['scene-02-settings', sceneSettings],
    ['scene-03-chat', sceneChat],
    ['scene-04-dashboard', sceneDashboard],
    ['scene-05-darkmode', sceneDarkMode, { settings: { mode: 'light' } }],
  ];

  const videoPaths = [];
  for (const [name, fn, opts] of scenes) {
    const path = await recordScene(browser, name, fn, opts || {});
    videoPaths.push(path);
  }

  await browser.close();
  console.log('\nAll scenes recorded. Stitching with ffmpeg...\n');

  // Scene titles for ffmpeg overlay
  const sceneTitles = [
    '1. Home',
    '2. Instellingen',
    '3. Chat met AI-assistent',
    '4. Dashboards',
    '5. Donkere modus',
  ];

  // Convert each WebM to MP4 with title overlay
  const mp4Paths = [];
  for (let i = 0; i < videoPaths.length; i++) {
    const mp4 = videoPaths[i].replace('.webm', '.mp4');
    const title = sceneTitles[i];
    const drawtext = `drawtext=text='${title}':fontsize=26:fontcolor=white:` +
      `box=1:boxcolor=black@0.55:boxborderw=14:x=36:y=36:` +
      `enable='lt(t\\,3.5)':font=sans`;
    try {
      execSync(
        `ffmpeg -y -i "${videoPaths[i]}" -vf "${drawtext}" -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p -an "${mp4}" 2>&1`,
        { stdio: 'pipe', timeout: 60000 }
      );
    } catch (err) {
      // Fallback without drawtext (font issues)
      console.log(`  Title overlay failed for scene ${i+1}, converting without overlay...`);
      execSync(
        `ffmpeg -y -i "${videoPaths[i]}" -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p -an "${mp4}" 2>&1`,
        { stdio: 'pipe', timeout: 60000 }
      );
    }
    mp4Paths.push(mp4);
    console.log(`  Converted: ${mp4}`);
  }

  // Create concat file
  const concatFile = join(RAW, 'concat.txt');
  writeFileSync(concatFile, mp4Paths.map(p => `file '${p}'`).join('\n'));

  // Concatenate all scenes
  execSync(
    `ffmpeg -y -f concat -safe 0 -i "${concatFile}" -c:v libx264 -preset fast -crf 22 -pix_fmt yuv420p -movflags +faststart "${OUTPUT}" 2>&1`,
    { stdio: 'pipe', timeout: 120000 }
  );

  console.log(`\nDone! Output: ${OUTPUT}`);

  // Print file size
  const stat = execSync(`ls -lh "${OUTPUT}"`).toString().trim();
  console.log(stat);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
