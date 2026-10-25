let chromium;
try {
  chromium = require('playwright').chromium;
} catch (e) {
  try {
    chromium = require('C:/Users/Choijay/AppData/Local/Programs/Python/Python311/Lib/site-packages/playwright/driver/package').chromium;
  } catch (e2) {
    throw new Error('Playwright not found: ' + e.message + '; ' + e2.message);
  }
}
const path = require('path');
const fs = require('fs');
(async()=>{
  const root=path.resolve(__dirname,'../../..');
  const file=process.argv[2] ? path.resolve(process.argv[2]) : path.join(root,'static/reports/blog-search-insights-20261022.html');
  const qa=path.join(root,'static/reports/_qa');fs.mkdirSync(qa,{recursive:true});
  const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  const page=await browser.newPage({viewport:{width:1440,height:1050}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('file:///'+file.replace(/\\/g,'/'));
  const total=13;
  if(await page.locator('.slide').count()!==total)throw new Error('Expected '+total+' pages');
  await page.locator('.toc-group a').first().click();
  if(await page.locator('#count').textContent()!=='2 / '+total)throw new Error('Contents link failed');
  await page.locator('#toc').click();
  await page.locator('#next').click();
  if(await page.locator('#count').textContent()!=='2 / '+total)throw new Error('Next failed');
  await page.locator('#jump').selectOption('3');
  await page.screenshot({path:path.join(qa,'blog-insights-page-04.png'),fullPage:true});
  await page.locator('#all').click();
  if(await page.locator('.slide:visible').count()!==total)throw new Error('All pages failed');
  await page.emulateMedia({media:'print'});
  const printBounds=await page.locator('.slide').evaluateAll(nodes=>nodes.map((n,i)=>({page:i+1,height:n.clientHeight,scrollHeight:n.scrollHeight,overflow:n.scrollHeight>n.clientHeight+2,footerOverflow:n.querySelector('footer').getBoundingClientRect().bottom>n.getBoundingClientRect().bottom-15})));
  await page.emulateMedia({media:'screen'});await page.locator('#all').click();
  await page.setViewportSize({width:390,height:844});await page.locator('#jump').selectOption('0');
  const mobile=await page.evaluate(()=>({viewport:innerWidth,documentWidth:document.documentElement.scrollWidth}));
  await page.setViewportSize({width:1440,height:1050});
  for(const n of [1,2,3,4,5,6,7,8,9,10,11,12,13]){await page.locator('#jump').selectOption(String(n-1));await page.screenshot({path:path.join(qa,`blog-insights-page-${n}.png`),fullPage:true})}
  const aggregateHeaders=await page.locator('th').allTextContents();
  if(aggregateHeaders.some(h=>/합산점|점수 합계|제품평균/.test(h)))throw new Error('Removed aggregate metric still has a column');
  const titles=await page.locator('.slide h1').allTextContents();
  if(titles.some(t=>/합산점|점수 합계|제품평균/.test(t)))throw new Error('Removed aggregate chart still published');
  const top10=await page.locator('.expanded-top10').evaluateAll(tables=>tables.map(table=>[...table.querySelectorAll('thead th')].map((h,column)=>({header:h.textContent,ranks:[...table.querySelectorAll('tbody tr')].flatMap(row=>[...row.cells[column].querySelectorAll('.rank-pill')].map(p=>parseInt(p.textContent,10))).filter(n=>n<=10).sort((a,b)=>a-b)})).filter(x=>/^(Logitech|HP Poly)/.test(x.header))));
  if(top10.length!==4||top10.flat().length!==9||top10.flat().some(x=>x.ranks.join(',')!=='1,2,3,4,5,6,7,8,9,10'))throw new Error('Logitech / Poly top 10 incomplete');
  if(await page.locator('.top5-audit tbody tr').count()!==35)throw new Error('Top 5 audit rows missing');
  const tableCount=await page.locator('table').count();const comparisonCount=await page.locator('.comparison').count();
  if(comparisonCount<tableCount)throw new Error('Missing table comparison guidance');
  const report={pages:total,errors,printBounds,mobile};fs.writeFileSync(path.join(qa,'blog-insights-check.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify({pages:total,errors,printOverflowPages:printBounds.filter(x=>x.overflow||x.footerOverflow),mobile}));await browser.close();
  if(errors.length||printBounds.some(x=>x.overflow||x.footerOverflow)||mobile.documentWidth>mobile.viewport+2)process.exitCode=1;
})().catch(e=>{console.error(e.message);process.exitCode=1});

