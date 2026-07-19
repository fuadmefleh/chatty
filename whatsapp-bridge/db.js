const Database = require('better-sqlite3');

function initDb(dbPath) {
  const db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.exec(`
    CREATE TABLE IF NOT EXISTS messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      msg_id TEXT UNIQUE,
      jid TEXT NOT NULL,
      contact_name TEXT,
      direction TEXT NOT NULL,
      message TEXT NOT NULL,
      timestamp TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
    CREATE INDEX IF NOT EXISTS idx_messages_jid ON messages(jid);

    CREATE TABLE IF NOT EXISTS contacts (
      jid TEXT PRIMARY KEY,
      name TEXT
    );

    CREATE TABLE IF NOT EXISTS chats (
      jid TEXT PRIMARY KEY,
      name TEXT,
      unread_count INTEGER NOT NULL DEFAULT 0,
      last_message TEXT,
      last_message_ts TEXT
    );
  `);
  return db;
}

function saveContact(db, jid, name) {
  if (!jid || !name) return;
  db.prepare(
    `INSERT INTO contacts (jid, name) VALUES (?, ?)
     ON CONFLICT(jid) DO UPDATE SET name = excluded.name`
  ).run(jid, name);
}

function lookupContactName(db, jid) {
  const row = db.prepare('SELECT name FROM contacts WHERE jid = ?').get(jid);
  return row?.name || null;
}

function saveMessage(db, { msgId, jid, contactName, direction, message, timestamp }) {
  db.prepare(
    `INSERT INTO messages (msg_id, jid, contact_name, direction, message, timestamp)
     VALUES (?, ?, ?, ?, ?, ?)
     ON CONFLICT(msg_id) DO NOTHING`
  ).run(msgId || null, jid, contactName, direction, message, timestamp);
}

function getRecentMessages(db, limit, days) {
  const cutoff = new Date(Date.now() - days * 86400000).toISOString();
  return db
    .prepare(
      `SELECT jid, contact_name, direction, message, timestamp
       FROM messages WHERE timestamp >= ?
       ORDER BY timestamp DESC LIMIT ?`
    )
    .all(cutoff, limit);
}

function searchMessages(db, query, contact, days, limit) {
  const cutoff = new Date(Date.now() - days * 86400000).toISOString();
  const params = [cutoff, `%${query}%`];
  let sql = `SELECT jid, contact_name, direction, message, timestamp
             FROM messages WHERE timestamp >= ? AND message LIKE ?`;
  if (contact) {
    sql += ' AND contact_name LIKE ?';
    params.push(`%${contact}%`);
  }
  sql += ' ORDER BY timestamp DESC LIMIT ?';
  params.push(limit);
  return db.prepare(sql).all(...params);
}

function getContactMessages(db, contact, limit, days) {
  const cutoff = new Date(Date.now() - days * 86400000).toISOString();
  return db
    .prepare(
      `SELECT jid, contact_name, direction, message, timestamp
       FROM messages WHERE timestamp >= ? AND contact_name LIKE ?
       ORDER BY timestamp DESC LIMIT ?`
    )
    .all(cutoff, `%${contact}%`, limit);
}

// Baileys' chats.upsert/chats.update events (and the `chats` array bundled
// into messaging-history.set) often only carry a partial patch - COALESCE
// keeps whatever we already knew about a chat when a given event doesn't
// mention it, instead of clobbering it with null/undefined.
function upsertChat(db, { jid, name, unreadCount }) {
  if (!jid) return;
  db.prepare(
    `INSERT INTO chats (jid, name, unread_count) VALUES (?, ?, COALESCE(?, 0))
     ON CONFLICT(jid) DO UPDATE SET
       name = COALESCE(excluded.name, chats.name),
       unread_count = COALESCE(?, chats.unread_count)`
  ).run(jid, name || null, unreadCount ?? null, unreadCount ?? null);
}

function bumpChatOnInboundMessage(db, jid, name, message, timestamp) {
  db.prepare(
    `INSERT INTO chats (jid, name, unread_count, last_message, last_message_ts)
     VALUES (?, ?, 1, ?, ?)
     ON CONFLICT(jid) DO UPDATE SET
       name = COALESCE(excluded.name, chats.name),
       unread_count = chats.unread_count + 1,
       last_message = excluded.last_message,
       last_message_ts = excluded.last_message_ts`
  ).run(jid, name || null, message, timestamp);
}

function updateChatOnOutboundMessage(db, jid, message, timestamp) {
  db.prepare(
    `INSERT INTO chats (jid, last_message, last_message_ts) VALUES (?, ?, ?)
     ON CONFLICT(jid) DO UPDATE SET last_message = excluded.last_message, last_message_ts = excluded.last_message_ts`
  ).run(jid, message, timestamp);
}

function resetUnread(db, jid) {
  db.prepare('UPDATE chats SET unread_count = 0 WHERE jid = ?').run(jid);
}

function getChats(db, limit = 200) {
  return db
    .prepare(
      `SELECT jid, name, unread_count, last_message, last_message_ts
       FROM chats ORDER BY last_message_ts DESC LIMIT ?`
    )
    .all(limit);
}

// Returns messages in chronological (ascending) order, ready to render
// top-to-bottom - `before` pages further back in history.
function getThreadByJid(db, jid, limit, before) {
  const params = [jid];
  let sql = `SELECT msg_id, jid, contact_name, direction, message, timestamp
             FROM messages WHERE jid = ?`;
  if (before) {
    sql += ' AND timestamp < ?';
    params.push(before);
  }
  sql += ' ORDER BY timestamp DESC LIMIT ?';
  params.push(limit);
  const rows = db.prepare(sql).all(...params);
  return rows.reverse();
}

// One-time backfill for chats that already had messages before the `chats`
// table existed (or a session that was already linked before this bridge
// version shipped) - chats.upsert/chats.update only fire for live activity,
// so a pre-existing conversation with no new traffic would otherwise never
// show up in /chats. Never overwrites a row chats.upsert already populated.
function backfillChatsFromMessages(db) {
  db.exec(`
    INSERT INTO chats (jid, name, last_message, last_message_ts)
    SELECT m.jid, m.contact_name, m.message, m.timestamp
    FROM messages m
    JOIN (SELECT jid, MAX(timestamp) AS max_ts FROM messages GROUP BY jid) latest
      ON latest.jid = m.jid AND latest.max_ts = m.timestamp
    WHERE m.jid NOT IN (SELECT jid FROM chats)
  `);
}

function getActiveContacts(db, days) {
  const cutoff = new Date(Date.now() - days * 86400000).toISOString();
  return db
    .prepare(
      `SELECT contact_name, jid, COUNT(*) as message_count, MAX(timestamp) as last_message_date
       FROM messages WHERE timestamp >= ?
       GROUP BY jid ORDER BY message_count DESC`
    )
    .all(cutoff);
}

module.exports = {
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
};
