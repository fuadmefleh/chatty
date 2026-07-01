# Notes Mini App Implementation Plan

## Overview
Transform the existing notes system into a full-featured Telegram Mini App with rich UI, inline mode, and advanced features.

## Phase 1: Basic Mini App (Week 1-2)

### 1.1 Frontend Setup
**Location:** `/skills/notes/webapp/`

```
webapp/
  ├── index.html          # Main mini app interface
  ├── styles.css          # Telegram-themed styling
  ├── app.js             # Core app logic
  └── telegram-web-app.js # Telegram SDK
```

**Features:**
- List all notes with search/filter
- Create new notes with rich text editor
- Edit existing notes
- Delete notes with confirmation
- Responsive design (mobile-first)
- Dark/light theme matching Telegram

**Tech Stack:**
- Pure HTML/CSS/JS (no build step needed)
- Telegram Web Apps SDK
- Local storage for offline drafts

### 1.2 Backend API
**Location:** `/skills/notes/webapp_api.py`

**Endpoints:**
```python
# GET /api/notes?user_id={id}
# POST /api/notes (create)
# PUT /api/notes/{note_id} (update)
# DELETE /api/notes/{note_id}
# GET /api/notes/search?q={query}
```

**Integration:**
- Flask micro-service or integrate into main bot
- JWT authentication using Telegram WebApp initData
- Reuse existing NotesManager class

### 1.3 Bot Integration
**Changes to main.py:**

```python
# Add menu button configuration
async def post_init(application):
    bot = application.bot
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="📝 Notes",
            web_app=WebAppInfo(url="https://yourdomain.com/notes")
        )
    )

# Add inline keyboard to open mini app
async def notes_command(update, context):
    keyboard = [[
        InlineKeyboardButton(
            "📱 Open Notes App", 
            web_app=WebAppInfo(url="https://yourdomain.com/notes")
        )
    ]]
    await update.message.reply_text(
        "Tap below to open your notes:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
```

### 1.4 Web Server Setup
- Host webapp on subdomain (e.g., notes.yourdomain.com)
- SSL certificate required (use Let's Encrypt)
- Configure CORS for Telegram domains
- Serve static files + API endpoints

## Phase 2: Inline Mode (Week 3)

### 2.1 Enable Inline Mode in BotFather
```
/setinline - Enable inline mode
/setinlinefeedback - Enable feedback
```

### 2.2 Implement Inline Query Handler

```python
async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: @yourbot note Buy milk at 5pm
    Usage: @yourbot search meeting
    """
    query = update.inline_query.query
    user_id = str(update.inline_query.from_user.id)
    
    if not is_user_authorized(user_id):
        return
    
    results = []
    
    # Quick note creation
    if query.startswith("note "):
        content = query[5:]
        results.append(
            InlineQueryResultArticle(
                id="new_note",
                title=f"📝 Create note: {content[:50]}",
                description="Tap to save this note",
                input_message_content=InputTextMessageContent(
                    f"✅ Note saved: {content}"
                ),
                thumb_url="https://yourdomain.com/note-icon.png"
            )
        )
    
    # Search existing notes
    elif query.startswith("search "):
        search_term = query[7:]
        notes = notes_manager.search_notes(user_id, search_term)
        
        for note in notes[:10]:
            results.append(
                InlineQueryResultArticle(
                    id=note.id,
                    title=note.content[:50],
                    description=f"Created: {note.created_at}",
                    input_message_content=InputTextMessageContent(note.content)
                )
            )
    
    # List recent notes
    else:
        notes = notes_manager.get_notes(user_id)[:10]
        for note in notes:
            results.append(
                InlineQueryResultArticle(
                    id=note.id,
                    title=note.content[:50],
                    description=f"Created: {note.created_at}",
                    input_message_content=InputTextMessageContent(note.content)
                )
            )
    
    await update.inline_query.answer(results, cache_time=1)

# In main():
application.add_handler(InlineQueryHandler(inline_query))
```

### 2.3 Handle Inline Result Feedback

```python
async def chosen_inline_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save note when user selects inline result."""
    result_id = update.chosen_inline_result.result_id
    query = update.chosen_inline_result.query
    user_id = str(update.chosen_inline_result.from_user.id)
    
    if result_id == "new_note" and query.startswith("note "):
        content = query[5:]
        notes_manager.add_note(user_id, content)

application.add_handler(ChosenInlineResultHandler(chosen_inline_result))
```

## Phase 3: Advanced Features (Week 4+)

### 3.1 Attachment Menu Integration
```python
# Configure in BotFather
# /setattachmenu - Add to attachment menu
# /setattachpic - Set icon

# Users can access from paperclip menu in any chat
```

### 3.2 Rich Features in Mini App

**Categories/Folders:**
```javascript
// Add category management to webapp
categories = ['Personal', 'Work', 'Shopping', 'Ideas']
```

**Voice Notes:**
```javascript
// Use Telegram.WebApp.showPopup for recording
// Send audio to backend, convert to text via OpenAI Whisper
```

**Photo Attachments:**
```javascript
// Allow image uploads with notes
// Store in /data/notes/attachments/
```

**Location-Tagged Notes:**
```javascript
// Use Telegram.WebApp.requestLocation()
// Save coordinates with note
```

**Share to Stories:**
```javascript
// Use Telegram.WebApp.shareToStory()
// Generate beautiful note cards
```

**Reminders Integration:**
```javascript
// Link notes to reminder system
// "Remind me about this note in 2 hours"
```

### 3.3 Collaborative Features

**Share Notes:**
- Deep link: `https://t.me/yourbot?start=note_{note_id}`
- Generate shareable links to specific notes
- View-only mode for shared notes

**Group Notes:**
- Notes accessible by group members
- Collaborative shopping lists
- Meeting notes

### 3.4 Export & Backup

**Export Options:**
- JSON download
- Markdown file
- PDF generation
- Email export

## Technical Requirements

### Frontend Dependencies
```html
<script src="https://telegram.org/js/telegram-web-app.js"></script>
```

### Backend Dependencies
```python
# Add to requirements.txt
flask>=3.0.0
flask-cors>=4.0.0
pyjwt>=2.8.0
```

### Environment Variables
```bash
# Add to .env
NOTES_WEBAPP_URL=https://notes.yourdomain.com
NOTES_SECRET_KEY=your-secret-key-for-jwt
```

### Hosting Options
1. **Same server as bot** - Add Flask app to current setup
2. **Vercel/Netlify** - For static frontend only
3. **Separate VPS** - If expecting high traffic

## Security Considerations

### Authentication
```python
def verify_telegram_webapp_data(init_data: str) -> dict:
    """Verify data from Telegram WebApp is authentic."""
    data = dict(parse_qsl(init_data))
    hash_value = data.pop('hash', None)
    
    data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(
        b"WebAppData",
        config.TELEGRAM_BOT_TOKEN.encode(),
        hashlib.sha256
    ).digest()
    
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    if calculated_hash != hash_value:
        raise ValueError("Invalid hash")
    
    return json.loads(data['user'])
```

### API Security
- Verify all requests with initData validation
- Rate limiting per user
- CSRF protection
- Input sanitization

## Testing Strategy

### Unit Tests
```python
# tests/test_notes_webapp.py
def test_create_note_api()
def test_search_notes_api()
def test_telegram_data_verification()
```

### Integration Tests
- Test Mini App in Telegram Desktop
- Test Mini App in Telegram Mobile (iOS/Android)
- Test inline mode across different chat types
- Test deep linking

### User Testing
- Gather feedback from beta users
- Monitor error logs
- Track usage metrics

## Deployment Checklist

- [ ] Frontend deployed with HTTPS
- [ ] Backend API endpoints tested
- [ ] BotFather configuration complete
- [ ] Mini App previews uploaded (screenshots/video)
- [ ] Menu button configured
- [ ] Inline mode enabled and tested
- [ ] Deep linking working
- [ ] Error monitoring setup
- [ ] Backup system verified
- [ ] Documentation updated

## Success Metrics

- Notes created via mini app vs. command
- Daily active users
- Average session time in mini app
- Inline mode usage
- User retention rate
- Error rate < 1%

## Future Enhancements

### AI Features
- Smart categorization using LLM
- Note summarization
- Related notes suggestions
- Smart search with semantic similarity

### Integrations
- Sync with Google Keep
- Export to Notion/Evernote
- Calendar integration for dated notes
- Task manager integration

### Premium Features (Monetization)
- Unlimited notes (free tier: 100 notes)
- Advanced search
- Priority support
- Custom themes
- Encrypted notes
- Charge 50-100 Telegram Stars

## Resources

- [Telegram Mini Apps Documentation](https://core.telegram.org/bots/webapps)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Design Guidelines](https://core.telegram.org/bots/webapps#design-guidelines)
- [Mini Apps Examples](https://github.com/telegram-mini-apps)

## Next Steps

1. Review and approve this plan
2. Set up hosting for webapp
3. Create basic HTML/CSS/JS frontend
4. Implement Flask API endpoints
5. Test locally with ngrok
6. Deploy to production
7. Configure BotFather settings
8. Add to Mini App Store
