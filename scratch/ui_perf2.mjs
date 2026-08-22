import puppeteer from 'puppeteer-core';
const browser = await puppeteer.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: 'new',
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900 });
await page.goto('file:///C:/oosc/ui/index.html');
await page.waitForSelector('tbody tr');
const out = await page.evaluate(async () => {
  const f = document.querySelector('#filter');
  const handlerTimes = [];
  const paintTimes = [];
  for (let i = 0; i < 30; i++) {
    const q = ['c','ca','can','m','mo','e','ex','r','re','g'][i % 10] + i;
    const t0 = performance.now();
    f.value = q;
    f.dispatchEvent(new Event('input', { bubbles: true }));
    handlerTimes.push(performance.now() - t0);
    await new Promise((r) => requestAnimationFrame(r));
    paintTimes.push(performance.now() - t0);
  }
  return {
    handlerMax: Math.max(...handlerTimes).toFixed(1),
    handlerAvg: (handlerTimes.reduce((a,b)=>a+b,0)/handlerTimes.length).toFixed(1),
    paintMax: Math.max(...paintTimes).toFixed(1),
    paintAvg: (paintTimes.reduce((a,b)=>a+b,0)/paintTimes.length).toFixed(1),
  };
});
console.log(JSON.stringify(out, null, 1));
await browser.close();
