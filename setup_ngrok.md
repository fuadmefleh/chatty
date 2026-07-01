# Setup ngrok for Local Mini App Testing

## Install ngrok

1. Download from https://ngrok.com/download
2. Or install via snap:
```bash
sudo snap install ngrok
```

## Run ngrok

In a new terminal:
```bash
ngrok http 5001
```

You'll see output like:
```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:5001
```

Copy that HTTPS URL (e.g., `https://abc123.ngrok-free.app`)

## Update the bot code

The URL changes each time you restart ngrok (unless you have a paid account).

In [src/main.py](src/main.py), update both URLs in the `/notes` command to include `/notes` path:
```python
web_app=WebAppInfo(url="https://YOUR-NGROK-URL/notes")
```

**Note:** The unified server hosts multiple mini apps:
- Notes app: `/notes`
- (Future apps will have their own paths like `/budget`, `/reminders`, etc.)

Or we can make it configurable via environment variable.
