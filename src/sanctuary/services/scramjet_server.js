import http from 'node:http';
import express from 'express';
import { scramjetPath } from '@mercuryworkshop/scramjet/path';
import { createBareServer } from '@tomphttp/bare-server-node';

const PORT = parseInt(process.argv[2] || process.env.PORT || process.env.SCRAMJET_PORT || '7860', 10);
const HOST = '0.0.0.0';

const app = express();
const server = http.createServer();
const bare = createBareServer('/bare/');

// 1. Serve Scramjet's built-in WASM and JS client files under /scramjet/
app.use('/scramjet/', express.static(scramjetPath));
app.use('/proxy/scramjet/', express.static(scramjetPath));

// Health check endpoint
app.get('/proxy/health', (req, res) => res.json({ status: 'ok', service: 'scramjet', engine: 'wasm' }));

// 2. Serve frontend HTML & Service Worker from public/ directory or fallback UI
app.use(express.static('public'));
app.use('/proxy', express.static('public'));

// 3. Route standard HTTP requests through Bare Server & Express
server.on('request', (req, res) => {
    if (bare.shouldRoute(req)) {
        bare.routeRequest(req, res);
    } else {
        app(req, res);
    }
});

// 4. Route WebSocket upgrades (Required for YouTube, Discord, WebSockets)
server.on('upgrade', (req, socket, head) => {
    if (bare.shouldRoute(req)) {
        bare.routeUpgrade(req, socket, head);
    } else {
        socket.end();
    }
});

server.listen(PORT, HOST, () => {
    console.log(`[SCRAMJET] Real WASM Proxy Engine active on http://${HOST}:${PORT}`);
});
