const puppeteer = require('puppeteer');

(async () => {
    const browser = await puppeteer.launch({ headless: 'new' });
    const page = await browser.newPage();

    // 捕捉 Console Logs 與 Errors
    page.on('console', msg => {
        console.log(`[Browser Console]: ${msg.type()} - ${msg.text()}`);
    });
    page.on('pageerror', error => {
        console.log(`[Browser Error]: ${error.message}`);
    });
    page.on('requestfailed', request => {
        console.log(`[Request Failed]: ${request.url()} - ${request.failure()?.errorText}`);
    });

    try {
        console.log('Navigating to Vercel app...');
        await page.goto('https://wealth-tracker-web-brown.vercel.app', { waitUntil: 'networkidle2' });
        console.log('Page loaded. Waiting 3 seconds for hydration and React errors to surface...');
        await new Promise(r => setTimeout(r, 3000));
        console.log('Done.');
    } catch (error) {
        console.error(`[Puppeteer Error]: ${error.message}`);
    } finally {
        await browser.close();
    }
})();
