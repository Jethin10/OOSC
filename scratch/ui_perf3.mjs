import puppeteer from 'puppeteer-core';
const browser = await puppeteer.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: 'new' });
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900 });
await page.goto('file:///C:/oosc/ui/index.html');
await page.waitForSelector('tbody tr');
// warm up: 5 throwaway interactions
await page.evaluate(async () => {
  const f = document.querySelector('#filter');
  for (let i = 0; i < 5; i++) { f.value = 'w' + i; f.dispatchEvent(new Event('input', { bubbles: true })); await new Promise(r=>requestAnimationFrame(r)); }
});
const out = await page.evaluate(async () => {
  const f = document.querySelector('#filter');
  const paintTimes = [];
  for (let i = 0; i < 40; i++) {
    f.value = 'gen-00' + (i % 10);
    f.dispatchEvent(new Event('input', { bubbles: true }));
    const t0 = performance.now();
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    paintTimes.push(performance.now() - t0);
  }
  return { max: Math.max(...paintTimes).toFixed(1), avg: (paintTimes.reduce((a,b)=>a+b,0)/paintTimes.length).toFixed(1) };
});
console.log('steady-state filter latency ms:', JSON.stringify(out));
await browser.close();
