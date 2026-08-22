import puppeteer from 'puppeteer-core';

const browser = await puppeteer.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: 'new',
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900 });
await page.goto('file:///C:/oosc/ui/index.html');
await page.waitForSelector('tbody tr');

// 1) interaction latency: filter typing + row select + tab switch (input->paint via rAF)
async function latency(fn) {
  return page.evaluate(async (fnSrc) => {
    const fn = eval(`(${fnSrc})`);
    const times = [];
    for (let i = 0; i < 20; i++) {
      const t0 = performance.now();
      fn(i);
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      times.push(performance.now() - t0);
    }
    return { max: Math.max(...times), avg: times.reduce((a, b) => a + b, 0) / times.length };
  }, fn.toString());
}

const typeLat = await latency((i) => {
  const f = document.querySelector('#filter');
  f.value = 'gen-00' + (i % 9);
  f.dispatchEvent(new Event('input', { bubbles: true }));
});

const selLat = await latency((i) => {
  const rows = document.querySelectorAll('#runs-body tr');
  rows[i % rows.length].click();
});

const tabLat = await latency((i) => {
  const btns = document.querySelectorAll('#tabs button');
  btns[i % btns.length].click();
});

// clear filter
await page.evaluate(() => {
  const f = document.querySelector('#filter');
  f.value = '';
  f.dispatchEvent(new Event('input', { bubbles: true }));
});

// 2) fps while a transform animation runs with full data on screen
const fpsResult = await page.evaluate(() => new Promise((resolve) => {
  let frames = 0; const start = performance.now(); let last = 0;
  const el = document.createElement('div');
  Object.assign(el.style, {
    position: 'fixed', top: '0', left: '0', width: '120px', height: '4px',
    background: '#f2c94c', willChange: 'transform', zIndex: 99,
  });
  document.body.appendChild(el);
  function loop(t) {
    frames++;
    el.style.transform = `translateX(${(t / 12) % 1400}px)`;
    if ((t % 500) < 17) last = t;
    if (t - start < 2000) requestAnimationFrame(loop);
    else resolve({ frames, ms: t - start });
  }
  requestAnimationFrame(loop);
}));

console.log(JSON.stringify({
  interaction_latency_ms: {
    filter_typing: { max: +typeLat.max.toFixed(1), avg: +typeLat.avg.toFixed(1) },
    row_select: { max: +selLat.max.toFixed(1), avg: +selLat.avg.toFixed(1) },
    tab_switch: { max: +tabLat.max.toFixed(1), avg: +tabLat.avg.toFixed(1) },
  },
  animation: {
    frames: fpsResult.frames,
    duration_ms: fpsResult.ms,
    fps: +(fpsResult.frames / (fpsResult.ms / 1000)).toFixed(1),
  },
}, null, 1));

await browser.close();
