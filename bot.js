const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
require('dotenv').config();

const FASTAPI_URL = process.env.FASTAPI_URL || 'http://localhost:8000';

const client = new Client({
  authStrategy: new LocalAuth({ clientId: 'tharoor' }),
  puppeteer: {
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--no-zygote',
      '--single-process'
    ]
  }
});

client.on('qr', (qr) => {
  console.log('\n📱 Scan this QR code with WhatsApp:\n');
  qrcode.generate(qr, { small: true });
  console.log('\n⏰ Scan quickly before it expires!\n');
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
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('✅ WhatsApp Bot is LIVE!');
  console.log('👤 Only replying to individual chats');
  console.log('🚫 Group messages ignored');
  console.log('🧠 Gender + Emotion detection ON');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
});

client.on('message', async (msg) => {
  if (msg.fromMe) return;
  if (msg.isStatus) return;
  if (!msg.body.trim()) return;

  const chat = await msg.getChat();

  // Skip group messages
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

    console.log(`👤 Gender: ${data.gender_detected}`);

    // Human-like delay 1.5 to 3 seconds
    const delay = 1500 + Math.random() * 1500;
    await new Promise(r => setTimeout(r, delay));

    await msg.reply(data.reply);
    console.log(`✉️  Sent: ${data.reply.substring(0, 70)}...`);

  } catch (err) {
    console.error('❌ Error:', err.message);
    console.error('💡 Make sure FastAPI is running on port 8000');
  }
});

client.on('disconnected', (reason) => {
  console.log('⚠️  Disconnected:', reason);
  console.log('🔄 Reconnecting in 5 seconds...');
  setTimeout(() => client.initialize(), 5000);
});

console.log('🚀 Starting WhatsApp Bot...');
console.log('📡 FastAPI URL:', FASTAPI_URL);
console.log('⏳ Loading browser — please wait 30-60 seconds...\n');

client.initialize();
