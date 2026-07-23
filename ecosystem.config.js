module.exports = {
  apps: [
    {
      name: 'chatty-bot',
      script: './start.sh',
      interpreter: '/bin/bash',
      cwd: '/home/edgeworks-server/chatty',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production'
      },
      error_file: './logs/pm2-error.log',
      out_file: './logs/pm2-out.log',
      log_file: './logs/pm2-combined.log',
      time: true,
      merge_logs: true,
      kill_timeout: 5000,
      wait_ready: false,
      listen_timeout: 10000
    },
    {
      // Atlas Web API - REST + WebSocket backend for the dashboard
      name: 'chatty-web-server',
      script: './venv/bin/python',
      args: 'chatty_web_server.py',
      cwd: '/home/edgeworks-server/chatty',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      error_file: './logs/chatty-web-error.log',
      out_file: './logs/chatty-web-out.log',
      time: true,
      merge_logs: true,
      kill_timeout: 5000,
    },
    {
      // Order Explorer FastAPI backend
      name: 'order-explorer-backend',
      script: '/home/edgeworks-server/chatty/venv/bin/uvicorn',
      args: 'main:app --host 0.0.0.0 --port 8015',
      cwd: '/home/edgeworks-server/chatty/order_explorer_site/backend',
      interpreter: 'none',
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      error_file: '/home/edgeworks-server/chatty/logs/order-backend-error.log',
      out_file: '/home/edgeworks-server/chatty/logs/order-backend-out.log',
      time: true,
      merge_logs: true,
    },
    {
      // Order Explorer React + Vite frontend (production build served via vite preview)
      // Run `npm run build` in order_explorer_site/frontend before starting
      name: 'order-explorer-frontend',
      script: 'npx',
      args: 'vite preview --host 0.0.0.0 --port 5173',
      cwd: '/home/edgeworks-server/chatty/order_explorer_site/frontend',
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      max_memory_restart: '256M',
      error_file: '/home/edgeworks-server/chatty/logs/order-frontend-error.log',
      out_file: '/home/edgeworks-server/chatty/logs/order-frontend-out.log',
      time: true,
      merge_logs: true,
    },
    {
      // WhatsApp bridge - holds the live Baileys/WhatsApp Web session and
      // exposes it to the Python backend over a localhost HTTP API secured
      // by WHATSAPP_BRIDGE_SECRET (read from ../.env via dotenv in index.js)
      name: 'whatsapp-bridge',
      script: 'index.js',
      cwd: '/home/edgeworks-server/chatty/whatsapp-bridge',
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      max_memory_restart: '256M',
      error_file: '/home/edgeworks-server/chatty/logs/whatsapp-bridge-error.log',
      out_file: '/home/edgeworks-server/chatty/logs/whatsapp-bridge-out.log',
      time: true,
      merge_logs: true,
    }
  ]
};
