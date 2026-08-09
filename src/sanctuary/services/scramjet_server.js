import http from 'node:http';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import express from 'express';
import { scramjetPath } from '@mercuryworkshop/scramjet/path';
import { createBareServer } from '@tomphttp/bare-server-node';
import { server as wispServer } from '@mercuryworkshop/wisp-js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = parseInt(process.argv[2] || process.env.PORT || process.env.SCRAMJET_PORT || '7860', 10);
const HOST = '0.0.0.0';

const app = express();
const server = http.createServer();
const bare = createBareServer('/bare/');

app.use((req, res, next) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', '*');
    res.setHeader('Access-Control-Allow-Headers', '*');
    res.removeHeader('X-Frame-Options');
    res.removeHeader('Content-Security-Policy');
    next();
});

// Locate public directory across standard deployment layouts
const publicDirCandidates = [
    path.resolve(process.cwd(), 'public'),
    path.resolve(__dirname, 'public'),
    path.resolve(__dirname, '../../public'),
    path.resolve(__dirname, '../public')
];

let publicDir = publicDirCandidates.find(dir => fs.existsSync(dir)) || publicDirCandidates[0];

// 1. Serve Scramjet's built-in WASM and JS client files
app.use('/scramjet/', express.static(scramjetPath));
app.use('/proxy/scramjet/', express.static(scramjetPath));

// 2. Service Worker routes
app.get(['/sw.js', '/proxy/sw.js'], (req, res) => {
    const swPath = path.join(publicDir, 'sw.js');
    if (fs.existsSync(swPath)) {
        res.setHeader('Service-Worker-Allowed', '/');
        res.setHeader('Content-Type', 'application/javascript');
        res.sendFile(swPath);
    } else {
        res.status(404).send('sw.js not found');
    }
});

// Health check endpoint
app.get('/proxy/health', (req, res) => res.json({ status: 'ok', service: 'scramjet', engine: 'wasm', protocols: ['bare', 'wisp'] }));

// 3. Serve frontend HTML & static assets
app.use(express.static(publicDir));
app.use('/proxy', express.static(publicDir));

app.use('/proxy/gateway', (req, res) => {
    const indexPath = path.join(publicDir, 'index.html');
    if (fs.existsSync(indexPath)) {
        res.sendFile(indexPath);
    } else {
        res.status(404).send('Proxy gateway index.html not found');
    }
});

app.get(['/', '/proxy', '/proxy/'], (req, res) => {
    const indexPath = path.join(publicDir, 'index.html');
    if (fs.existsSync(indexPath)) {
        res.sendFile(indexPath);
    } else {
        res.status(404).send('Proxy gateway index.html not found');
    }
});

// 4. Route standard HTTP requests through Bare Server & Express
server.on('request', (req, res) => {
    if (bare.shouldRoute(req)) {
        bare.routeRequest(req, res);
    } else {
        app(req, res);
    }
});

// 5. Route WebSocket upgrades for Bare & Wisp protocol
server.on('upgrade', (req, socket, head) => {
    if (req.url.startsWith('/wisp')) {
        wispServer.routeRequest(req, socket, head);
    } else if (bare.shouldRoute(req)) {
        bare.routeUpgrade(req, socket, head);
    } else {
        socket.end();
    }
});

server.listen(PORT, HOST, () => {
    console.log(`[SCRAMJET] Upgraded WASM & Wisp Engine active on http://${HOST}:${PORT}`);
});
