# Chatty

## Git commit conventions

When creating git commits, use "Chatty" as the co-author instead of Claude. Use this trailer format:

```
Co-Authored-By: Chatty <noreply@infineray.com>
```

Do not include a `Claude-Session` link line.

## Reloading after changes

Whenever you make code changes (backend or frontend), reload the running
services afterward so the changes take effect — don't wait to be asked.

**Frontend (`order_explorer_site/frontend/`) — `order-explorer-frontend`
runs `vite preview`, which serves the static prebuilt `dist/` folder, NOT
a live dev server.** A plain `pm2 restart` just re-serves the same stale
build — it does nothing for source changes. You MUST rebuild first:

```
cd order_explorer_site/frontend && npm run build
pm2 restart order-explorer-frontend
```

Verify the new bundle actually shipped before declaring success — check
the built JS filename changed (`grep -o 'src="[^"]*\.js"' <(curl -s
http://localhost:5173/)`) and/or grep the new `dist/assets/*.js` for a
string unique to your change. Do NOT just restart and assume it worked.

**Backend:**

```
pm2 restart chatty-web-server
```

Only restart `order-explorer-backend` too if you actually touched
`order_explorer_site/backend/`. After restarting, verify it came back up
cleanly (e.g. `curl http://localhost:8016/api/chatty/health`, check
`pm2 logs chatty-web-server --lines 20 --nostream` for errors) instead of
assuming success.
