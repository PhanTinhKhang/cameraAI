const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  
  page.on('pageerror', err => {
    console.log('PAGE ERROR:', err.toString());
  });
  
  page.on('console', msg => {
    if(msg.type() === 'error') console.log('CONSOLE ERROR:', msg.text());
  });

  console.log("Navigating to dashboard...");
  await page.goto('http://localhost:5173', {waitUntil: 'networkidle2'});

  try {
    console.log("Clicking the first alert...");
    const listItems = await page.$$('.ant-list-item');
    if (listItems.length > 0) {
      await listItems[0].click();
      await new Promise(r => setTimeout(r, 1000));
      
      console.log("Looking for 'Theo dõi' button...");
      const buttons = await page.$$('.ant-btn-dashed');
      for (let btn of buttons) {
        const text = await page.evaluate(el => el.textContent, btn);
        if (text && text.includes('Theo')) {
          console.log("Clicking 'Theo dõi' button...");
          await btn.click();
          break;
        }
      }
      await new Promise(r => setTimeout(r, 2000));
    } else {
      console.log("No alerts found in the list.");
    }
  } catch(e) {
    console.error("Test execution failed:", e);
  }

  await browser.close();
  console.log("Done.");
})();
