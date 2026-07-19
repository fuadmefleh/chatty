const path = require('path');
const fs = require('fs');

// Reuses the same root .env the Python backend reads (chatty_web_server.py's
// own load_dotenv() call), so pm2 doesn't need per-app env config.
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const express = require('express');
const pino = require('pino');
const qrcode = require('qrcode');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} = require('@whiskeysockets/baileys');
const {
  initDb,
  saveContact,
  lookupContactName,
  saveMessage,
  getRecentMessages,
  searchMessages,
  getContactMessages,
  getActiveContacts,
  upsertChat,
  bumpChatOnInboundMessage,
  updateChatOnOutboundMessage,
  resetUnread,
  getChats,
  getThreadByJid,
  backfillChatsFromMessages,
} = require('./db');

const PORT = process.env.WHATSAPP_BRIDGE_PORT || 8017;
const SECRET = process.env.WHATSAPP_BRIDGE_SECRET;
const AUTH_DIR = process.env.WHATSAPP_AUTH_DIR || path.join(__dirname, '..', 'data', 'whatsapp_auth');
const DB_PATH = process.env.WHATSAPP_DB_PATH || path.join(__dirname, '..', 'data', 'whatsapp_messages.db');

// This process can read every WhatsApp message and send new ones on the
// user's behalf, so an unauthenticated local HTTP API isn't good enough -
// refuse to boot without a shared secret rather than silently running open.
if (!SECRET) {
  console.error(
    "WHATSAPP_BRIDGE_SECRET is not set - refusing to start (this API can read messages and send them on the user's behalf)."
  );
  process.exit(1);
}

fs.mkdirSync(AUTH_DIR, { recursive: true });
fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });

const db = initDb(DB_PATH);
backfillChatsFromMessages(db);
const logger = pino({ level: process.env.WHATSAPP_LOG_LEVEL || 'warn' });

let sock = null;
let currentQr = null;
let connectionStatus = 'disconnected'; // 'disconnected' | 'qr_pending' | 'connected'
let connectedPhone = null;

function extractText(msg) {
  const m = msg.message;
  if (!m) return null;
  if (m.conversation) return m.conversation;
  if (m.extendedTextMessage?.text) return m.extendedTextMessage.text;
  if (m.imageMessage) return m.imageMessage.caption ? `[image] ${m.imageMessage.caption}` : '[image]';
  if (m.videoMessage) return m.videoMessage.caption ? `[video] ${m.videoMessage.caption}` : '[video]';
  if (m.documentMessage) return m.documentMessage.caption ? `[document] ${m.documentMessage.caption}` : '[document]';
  if (m.audioMessage) return '[audio]';
  if (m.stickerMessage) return '[sticker]';
  return null;
}

function recordMessage(msg, directionOverride) {
  if (!msg?.key?.remoteJid || msg.key.remoteJid === 'status@broadcast') return;
  const text = extractText(msg);
  if (!text) return;
  const jid = msg.key.remoteJid;
  const direction = directionOverride || (msg.key.fromMe ? 'out' : 'in');
  const timestamp = msg.messageTimestamp
    ? new Date(Number(msg.messageTimestamp) * 1000).toISOString()
    : new Date().toISOString();
  const contactName = lookupContactName(db, jid) || msg.pushName || jid.split('@')[0];
  saveMessage(db, { msgId: msg.key.id, jid, contactName, direction, message: text, timestamp });

  if (direction === 'in') {
    bumpChatOnInboundMessage(db, jid, contactName, text, timestamp);
  } else {
    updateChatOnOutboundMessage(db, jid, text, timestamp);
  }
}

function chatNameFromEvent(c) {
  return c.name || c.subject || c.notify || null;
}

async function startSock() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    version,
    auth: state,
    logger,
    syncFullHistory: true,
    generateHighQualityLinkPreview: false,
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      currentQr = await qrcode.toDataURL(qr);
      connectionStatus = 'qr_pending';
    }

    if (connection === 'open') {
      currentQr = null;
      connectionStatus = 'connected';
      connectedPhone = sock.user?.id ? sock.user.id.split('@')[0].split(':')[0] : null;
      logger.info('WhatsApp connected');
    } else if (connection === 'close') {
      connectionStatus = 'disconnected';
      connectedPhone = null;
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const loggedOut = statusCode === DisconnectReason.loggedOut;
      if (loggedOut) {
        logger.warn('WhatsApp logged out - clearing session, waiting for a fresh QR scan');
        fs.rmSync(AUTH_DIR, { recursive: true, force: true });
        fs.mkdirSync(AUTH_DIR, { recursive: true });
      } else {
        logger.warn({ statusCode }, 'WhatsApp connection closed, reconnecting');
      }
      startSock().catch((e) => logger.error(e, 'reconnect failed'));
    }
  });

  sock.ev.on('contacts.upsert', (contacts) => {
    for (const c of contacts) saveContact(db, c.id, c.name || c.notify || null);
  });
  sock.ev.on('contacts.update', (contacts) => {
    for (const c of contacts) if (c.id) saveContact(db, c.id, c.name || c.notify || null);
  });

  sock.ev.on('messaging-history.set', ({ messages, contacts, chats }) => {
    for (const c of contacts || []) saveContact(db, c.id, c.name || c.notify || null);
    for (const c of chats || []) {
      upsertChat(db, { jid: c.id, name: chatNameFromEvent(c), unreadCount: c.unreadCount });
    }
    for (const m of messages || []) recordMessage(m);
  });

  sock.ev.on('messages.upsert', ({ messages, type }) => {
    if (type !== 'notify' && type !== 'append') return;
    for (const m of messages) recordMessage(m);
  });

  sock.ev.on('chats.upsert', (chats) => {
    for (const c of chats) upsertChat(db, { jid: c.id, name: chatNameFromEvent(c), unreadCount: c.unreadCount });
  });
  sock.ev.on('chats.update', (chats) => {
    for (const c of chats) if (c.id) upsertChat(db, { jid: c.id, name: chatNameFromEvent(c), unreadCount: c.unreadCount });
  });
}

function toJid(to) {
  if (to.includes('@')) return to;
  const digits = to.replace(/[^0-9]/g, '');
  return `${digits}@s.whatsapp.net`;
}

const app = express();
app.use(express.json());

app.use((req, res, next) => {
  if (req.get('X-Bridge-Secret') !== SECRET) {
    return res.status(401).json({ error: 'unauthorized' });
  }
  next();
});

app.get('/status', (req, res) => {
  res.json({ status: connectionStatus, phone: connectedPhone });
});

app.get('/qr', (req, res) => {
  res.json({ qr: connectionStatus === 'qr_pending' ? currentQr : null });
});

app.post('/logout', async (req, res) => {
  try {
    if (sock) await sock.logout();
  } catch (e) {
    logger.warn(e, 'logout error (continuing)');
  }
  fs.rmSync(AUTH_DIR, { recursive: true, force: true });
  fs.mkdirSync(AUTH_DIR, { recursive: true });
  connectionStatus = 'disconnected';
  connectedPhone = null;
  currentQr = null;
  res.json({ status: 'disconnected' });
  startSock().catch((e) => logger.error(e, 'restart after manual logout failed'));
});

app.get('/messages/recent', (req, res) => {
  const limit = Math.min(parseInt(req.query.limit, 10) || 20, 200);
  const days = parseInt(req.query.days, 10) || 7;
  res.json({ messages: getRecentMessages(db, limit, days) });
});

app.get('/messages/search', (req, res) => {
  const query = String(req.query.query || '');
  const contact = req.query.contact ? String(req.query.contact) : null;
  const days = parseInt(req.query.days, 10) || 30;
  const limit = Math.min(parseInt(req.query.limit, 10) || 50, 200);
  res.json({ messages: searchMessages(db, query, contact, days, limit) });
});

app.get('/messages/contact/:name', (req, res) => {
  const limit = Math.min(parseInt(req.query.limit, 10) || 30, 200);
  const days = parseInt(req.query.days, 10) || 30;
  res.json({ messages: getContactMessages(db, req.params.name, limit, days) });
});

app.get('/contacts', (req, res) => {
  const days = parseInt(req.query.days, 10) || 30;
  res.json({ contacts: getActiveContacts(db, days) });
});

app.get('/chats', (req, res) => {
  const limit = Math.min(parseInt(req.query.limit, 10) || 200, 500);
  res.json({ chats: getChats(db, limit) });
});

app.get('/messages/thread/:jid', (req, res) => {
  const limit = Math.min(parseInt(req.query.limit, 10) || 50, 200);
  const before = req.query.before ? String(req.query.before) : null;
  res.json({ messages: getThreadByJid(db, req.params.jid, limit, before) });
});

app.post('/chats/:jid/read', async (req, res) => {
  resetUnread(db, req.params.jid);
  try {
    if (sock && connectionStatus === 'connected') {
      await sock.chatModify({ markRead: true, lastMessages: [] }, req.params.jid);
    }
  } catch (e) {
    logger.warn(e, 'mark-read on the WhatsApp side failed (local unread count still cleared)');
  }
  res.json({ success: true });
});

app.post('/send', async (req, res) => {
  const { to, message, origin } = req.body || {};
  if (!to || !message) return res.status(400).json({ error: 'to and message are required' });
  if (connectionStatus !== 'connected' || !sock) {
    return res.status(409).json({ error: 'WhatsApp is not connected' });
  }
  try {
    const jid = toJid(String(to));
    await sock.sendMessage(jid, { text: String(message) });
    recordMessage(
      {
        key: { remoteJid: jid, fromMe: true, id: `local-${Date.now()}` },
        message: { conversation: String(message) },
        messageTimestamp: Math.floor(Date.now() / 1000),
      },
      origin === 'auto' ? 'auto' : 'out'
    );
    res.json({ success: true });
  } catch (e) {
    logger.error(e, 'send failed');
    res.status(500).json({ error: String(e.message || e) });
  }
});

app.listen(PORT, '127.0.0.1', () => {
  logger.info(`whatsapp-bridge listening on 127.0.0.1:${PORT}`);
});

startSock().catch((e) => {
  logger.error(e, 'failed to start WhatsApp socket');
  process.exit(1);
});
