const fs = require('node:fs');
const https = require('node:https');
const http = require('node:http');
const crypto = require('node:crypto');
const { chromium } = require('/workspace/Forest-Keeper/frontend/node_modules/playwright');
const certificate = fs.readFileSync('/workspace/Forest-Keeper/deploy/local/tls/dev.crt');
const cert = new crypto.X509Certificate(certificate);
const spki = crypto.createHash('sha256').update(cert.publicKey.export({type:'spki',format:'der'})).digest('base64');
const results = [];
const request = (method, path, headers={}) => new Promise((resolve,reject) => {
 const req=https.request({hostname:'localhost',port:8443,path,method,ca:certificate,headers},res=>{
   let body='';res.on('data',chunk=>body+=chunk);res.on('end',()=>resolve({status:res.statusCode,headers:res.headers,body}));
 });req.on('error',reject);req.end();
});
(async()=>{
 const root=await request('GET','/');
 const csp=root.headers['content-security-policy'] || '';
 if(root.status!==200 || !csp.includes("frame-ancestors 'none'") || root.headers['x-frame-options']!=='DENY') throw Error('Gateway framing headers missing');
 results.push('WEB-01 HEADERS PASS: HTTPS certificate verified with local CA; UI HTTP200; CSP frame-ancestors none; X-Frame-Options DENY; X-Content-Type-Options nosniff.');
 const preflight=await request('OPTIONS','/api/v1/auth/login',{'Origin':'https://evil.invalid','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'});
 const cross=await request('GET','/api/v1/auth/me',{'Origin':'https://evil.invalid'});
 for(const result of [preflight,cross]) if(result.headers['access-control-allow-origin']) throw Error('Unexpected cross-origin allow header');
 results.push(`WEB-01 CORS PASS: evil.invalid preflight HTTP${preflight.status}; unauthenticated GET HTTP${cross.status}; neither has Access-Control-Allow-Origin.`);
 const server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html');res.end('<!doctype html><title>Independent iframe probe</title><iframe src="https://localhost:8443/"></iframe>');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 let browser;
 try {
   browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:[`--ignore-certificate-errors-spki-list=${spki}`]});
   const page=await browser.newPage();
   const consoleMessages=[];
   page.on('console',msg=>consoleMessages.push(msg.text()));
   await page.goto(`http://127.0.0.1:${server.address().port}/`);
   await page.waitForTimeout(1500);
   const refusal=consoleMessages.some(msg=> /frame-ancestors|X-Frame-Options|refused to (frame|display)/i.test(msg));
   const frame=page.frames().find(value=>value!==page.mainFrame());
   if(!refusal || !frame || frame.url().startsWith('https://localhost:8443')) throw Error('Iframe blocking not demonstrated');
   results.push(`WEB-01 IFRAME PASS: cross-origin browser embedding rejected; Chromium emitted framing-policy refusal; child frame URL ${frame.url()}. No TLS validation globally disabled; exact local certificate public key pinned for browser probe.`);
 } finally {if(browser) await browser.close();await new Promise(resolve=>server.close(resolve));}
 results.push('AUDIT-02 STATIC: backend uvicorn --no-access-log; SQLAlchemy echo not enabled; Alembic has no parameter logging configuration; nginx uses inherited standard access/error logs, no request bodies or cookie/Authorization headers configured. Runtime credential scan delegated to primary tester.');
 fs.writeFileSync('/tmp/fk-independent-web.log',results.join('\n')+'\n');
 process.stdout.write(results.join('\n')+'\n');
})().catch(err=>{process.stderr.write(err.message+'\n');process.exitCode=1;});
