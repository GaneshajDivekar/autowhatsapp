const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
require('dotenv').config();

const FASTAPI_URL = process.env.FASTAPI_URL || 'http://localhost:8000';

// Find Chrome on Railway or local
const CHROME_PATH = process.env.CHROME_PATH ||
  '/nix/store/*/bin/chromium' ||
  '/usr/bin/chromium-browser' ||
  '/usr/bin/chromium' ||
  undefined;

const client = new Client({
  authStrategy: new LocalAuth({
    clientId: 'tharoor',
    dataPath: '/tmp/.wwebjs_auth'
  }),
  puppeteer: {
    headless: true,
    executablePath: CHROME_PATH,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--no-zygote',
      '--single-process',
      '--disable-extensions',
      '--disable-background-networking',
      '--disable-default-apps',
      '--disable-sync',
      '--disable-translate',
      '--no-first-run',
      '--safebrowsing-disable-auto-update'
    ]
  }
});

client.on('qr', (qr) => {
  console.log('\n📱 QR CODE — scan with WhatsApp:\n');
  qrcode.generate(qr, { small: true });
  console.log('\n⚠️  Check Railway logs to see this QR code!');
  console.log('Go to: Railway Dashboard → Your service → Logs\n');
});

client.on('loading_screen', (percent, message) => {
  console.log('⏳ Loading...', percent, '%', message);
});

client.on('authenticated', () => {
  console.log('🔐 Authenticated!');
});

client.on('auth_failure', (msg) => {
  console.error('❌ Auth failed:', msg);
});

client.on('ready', () => {
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('✅ WhatsApp Bot is LIVE!');
  console.log('👤 Individual chats only');
  console.log('🚫 Groups ignored');
  console.log('🧠 Gender + Emotion ON');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━\n');
});

client.on('message', async (msg) => {
  if (msg.fromMe) return;
  if (msg.isStatus) return;
  if (!msg.body.trim()) return;

  const chat = await msg.getChat();
  if (chat.isGroup) {
    console.log(`⏭️  Skipping group: "${chat.name}"`);
    return;
  }

  const contact = await msg.getContact();
  const senderName = contact.pushname || contact.number || 'Friend';

  console.log(`\n📨 From ${senderName}: ${msg.body}`);

  try {
    await chat.sendStateTyping();

    const res = await fetch(`${FASTAPI_URL}/reply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: msg.from,
        sender_name: senderName,
        message: msg.body
      })
    });

    const data = await res.json();

    if (!data.reply) {
      console.log('⚠️  No reply — bot may be disabled');
      return;
    }

    console.log(`👤 Gender: ${data.gender_detected} | Mood: ${data.mood_detected}`);

    const delay = 1500 + Math.random() * 1500;
    await new Promise(r => setTimeout(r, delay));

    await msg.reply(data.reply);
    console.log(`✉️  Sent: ${data.reply.substring(0, 60)}...`);

  } catch (err) {
    console.error('❌ Error:', err.message);
  }
});

client.on('disconnected', (reason) => {
  console.log('⚠️  Disconnected:', reason);
  console.log('🔄 Reconnecting in 5 seconds...');
  setTimeout(() => client.initialize(), 5000);
});

console.log('🚀 Starting WhatsApp Bot on Railway...');
console.log('📡 FastAPI URL:', FASTAPI_URL);
console.log('⏳ Loading browser — wait 60 seconds for QR...\n');

client.initialize();
