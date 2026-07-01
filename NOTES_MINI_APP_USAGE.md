# Notes Mini App - Quick Start Guide

## What You Have

A fully functional Telegram Mini App for managing your notes with:
- ✅ Rich web interface
- ✅ Search functionality
- ✅ Create, edit, and delete notes
- ✅ Telegram theme integration
- ✅ Haptic feedback
- ✅ Mobile-optimized design

## How to Use It

### Step 1: Install Dependencies

```bash
pip install flask-cors
```

### Step 2: Start the Mini App Server

Open a new terminal and run:

```bash
./start_notes_app.sh
```

Or manually:

```bash
python3 skills/notes/webapp_server.py
```

This will start the server on `http://localhost:5001`

### Step 3: Start Your Bot

In another terminal:

```bash
./start.sh
```

### Step 4: Open the Mini App

In your Telegram chat with the bot:
1. Type `/notes`
2. Click the **"📱 Open Notes App"** button
3. The mini app will open in Telegram!

## Features

### In the Mini App:
- **Create Notes**: Click the "+ New Note" button
- **Edit Notes**: Tap any note to edit it
- **Delete Notes**: Open a note and click "Delete"
- **Search**: Type in the search bar to filter notes
- **Auto-save**: All changes save automatically

### Theme Support:
- Automatically matches your Telegram theme (light/dark)
- Smooth animations and haptic feedback

## Files Created

```
skills/notes/webapp/
  ├── index.html      # Main interface
  ├── styles.css      # Telegram-themed styling
  └── app.js          # Application logic

skills/notes/webapp_server.py  # Flask API server
start_notes_app.sh             # Startup script
```

## API Endpoints

The server provides these endpoints:

- `GET /` - Serve the mini app
- `GET /api/notes?user_id={id}` - Get all notes
- `POST /api/notes` - Create a note
- `PUT /api/notes/{id}` - Update a note  
- `DELETE /api/notes/{id}` - Delete a note

## Troubleshooting

**Mini App doesn't open?**
- Make sure the webapp server is running on port 5001
- Check that your bot is running
- Try using `/notes` command again

**Notes not loading?**
- Check the webapp server terminal for errors
- Make sure your user_id is correct
- Check `data/notes/` directory has proper permissions

**Theme looks wrong?**
- The app automatically uses Telegram's theme
- Try closing and reopening the mini app

## Next Steps

For production use, you'll want to:

1. **Get a domain with HTTPS** (required by Telegram for production)
   - Use nginx or similar as reverse proxy
   - Get SSL certificate (Let's Encrypt)

2. **Update the URL** in main.py:
   ```python
   web_app=WebAppInfo(url="https://yourdomain.com")
   ```

3. **Configure in BotFather**:
   - `/setmenubutton` - Add to menu
   - `/mybots` -> Bot Settings -> Menu Button

4. **Add authentication** (optional):
   - Verify Telegram initData hash
   - Prevent unauthorized access

For now, enjoy your personal notes mini app! 🎉
