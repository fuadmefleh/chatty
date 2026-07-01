// Initialize Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand();
tg.enableClosingConfirmation();

// Apply Telegram theme
document.documentElement.style.setProperty('--tg-theme-bg-color', tg.themeParams.bg_color || '#ffffff');
document.documentElement.style.setProperty('--tg-theme-text-color', tg.themeParams.text_color || '#000000');
document.documentElement.style.setProperty('--tg-theme-hint-color', tg.themeParams.hint_color || '#999999');
document.documentElement.style.setProperty('--tg-theme-link-color', tg.themeParams.link_color || '#2481cc');
document.documentElement.style.setProperty('--tg-theme-button-color', tg.themeParams.button_color || '#2481cc');
document.documentElement.style.setProperty('--tg-theme-button-text-color', tg.themeParams.button_text_color || '#ffffff');
document.documentElement.style.setProperty('--tg-theme-secondary-bg-color', tg.themeParams.secondary_bg_color || '#f4f4f5');

// State
let notes = [];
let currentNoteId = null;
let searchTerm = '';

// API Base URL - will use relative path since served from same server
const API_BASE = '/api/notes';

// Get user ID from Telegram
const userId = tg.initDataUnsafe?.user?.id || 'test_user';

// DOM Elements
const notesList = document.getElementById('notesList');
const searchInput = document.getElementById('searchInput');
const addNoteBtn = document.getElementById('addNoteBtn');
const noteEditorModal = document.getElementById('noteEditorModal');
const modalTitle = document.getElementById('modalTitle');
const noteContent = document.getElementById('noteContent');
const saveNoteBtn = document.getElementById('saveNoteBtn');
const deleteNoteBtn = document.getElementById('deleteNoteBtn');
const closeModal = document.getElementById('closeModal');
const emptyState = document.getElementById('emptyState');

// Initialize
loadNotes();

// Event Listeners
addNoteBtn.addEventListener('click', openNewNoteModal);
closeModal.addEventListener('click', closeNoteModal);
saveNoteBtn.addEventListener('click', saveNote);
deleteNoteBtn.addEventListener('click', deleteNote);
searchInput.addEventListener('input', handleSearch);

// Click outside modal to close
noteEditorModal.addEventListener('click', (e) => {
    if (e.target === noteEditorModal) {
        closeNoteModal();
    }
});

// Functions
async function loadNotes() {
    try {
        notesList.innerHTML = '<div class="loading">Loading notes...</div>';
        
        const response = await fetch(`${API_BASE}?user_id=${userId}`);
        const data = await response.json();
        
        if (data.success) {
            notes = data.notes || [];
            renderNotes();
        } else {
            throw new Error(data.error || 'Failed to load notes');
        }
    } catch (error) {
        console.error('Error loading notes:', error);
        tg.showAlert('Failed to load notes: ' + error.message);
        notesList.innerHTML = '<div class="loading">Error loading notes</div>';
    }
}

function renderNotes() {
    const filteredNotes = filterNotes(notes, searchTerm);
    
    if (filteredNotes.length === 0) {
        notesList.innerHTML = '';
        emptyState.style.display = 'block';
        if (searchTerm) {
            emptyState.querySelector('h3').textContent = 'No matching notes';
            emptyState.querySelector('p').textContent = 'Try a different search term';
        } else {
            emptyState.querySelector('h3').textContent = 'No notes yet';
            emptyState.querySelector('p').textContent = 'Tap the "+ New Note" button to create your first note!';
        }
        return;
    }
    
    emptyState.style.display = 'none';
    
    notesList.innerHTML = filteredNotes.map(note => {
        const content = highlightSearch(truncateText(note.content, 200), searchTerm);
        const date = formatDate(note.created_at);
        
        return `
            <div class="note-card" data-note-id="${note.id}">
                <div class="note-content preview">${content}</div>
                <div class="note-meta">
                    <span class="note-date">🕒 ${date}</span>
                </div>
            </div>
        `;
    }).join('');
    
    // Add click listeners to notes
    document.querySelectorAll('.note-card').forEach(card => {
        card.addEventListener('click', () => {
            const noteId = card.getAttribute('data-note-id');
            openEditNoteModal(noteId);
        });
    });
}

function filterNotes(notesList, term) {
    if (!term) return notesList;
    
    const lowerTerm = term.toLowerCase();
    return notesList.filter(note => 
        note.content.toLowerCase().includes(lowerTerm)
    );
}

function highlightSearch(text, term) {
    if (!term) return escapeHtml(text);
    
    const escapedText = escapeHtml(text);
    const escapedTerm = escapeHtml(term);
    const regex = new RegExp(`(${escapedTerm})`, 'gi');
    
    return escapedText.replace(regex, '<span class="highlight">$1</span>');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function truncateText(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) {
        return 'Today ' + date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
    } else if (days === 1) {
        return 'Yesterday';
    } else if (days < 7) {
        return days + ' days ago';
    } else {
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }
}

function openNewNoteModal() {
    currentNoteId = null;
    modalTitle.textContent = 'New Note';
    noteContent.value = '';
    deleteNoteBtn.style.display = 'none';
    noteEditorModal.style.display = 'flex';
    noteContent.focus();
    
    // Haptic feedback
    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred('light');
    }
}

function openEditNoteModal(noteId) {
    const note = notes.find(n => n.id === noteId);
    if (!note) return;
    
    currentNoteId = noteId;
    modalTitle.textContent = 'Edit Note';
    noteContent.value = note.content;
    deleteNoteBtn.style.display = 'block';
    noteEditorModal.style.display = 'flex';
    noteContent.focus();
    
    // Haptic feedback
    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred('light');
    }
}

function closeNoteModal() {
    noteEditorModal.style.display = 'none';
    currentNoteId = null;
    
    // Haptic feedback
    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred('light');
    }
}

async function saveNote() {
    const content = noteContent.value.trim();
    
    if (!content) {
        tg.showAlert('Please enter some text for your note');
        return;
    }
    
    // Haptic feedback
    if (tg.HapticFeedback) {
        tg.HapticFeedback.notificationOccurred('success');
    }
    
    try {
        const url = currentNoteId 
            ? `${API_BASE}/${currentNoteId}`
            : API_BASE;
        
        const method = currentNoteId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: userId,
                note_content: content
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            closeNoteModal();
            await loadNotes();
            tg.showPopup({
                title: 'Success',
                message: currentNoteId ? 'Note updated!' : 'Note saved!',
                buttons: [{type: 'ok'}]
            });
        } else {
            throw new Error(data.error || 'Failed to save note');
        }
    } catch (error) {
        console.error('Error saving note:', error);
        tg.showAlert('Failed to save note: ' + error.message);
    }
}

async function deleteNote() {
    if (!currentNoteId) return;
    
    tg.showPopup({
        title: 'Delete Note',
        message: 'Are you sure you want to delete this note?',
        buttons: [
            {id: 'delete', type: 'destructive', text: 'Delete'},
            {type: 'cancel'}
        ]
    }, async (buttonId) => {
        if (buttonId === 'delete') {
            try {
                const response = await fetch(`${API_BASE}/${currentNoteId}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        user_id: userId
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // Haptic feedback
                    if (tg.HapticFeedback) {
                        tg.HapticFeedback.notificationOccurred('success');
                    }
                    
                    closeNoteModal();
                    await loadNotes();
                } else {
                    throw new Error(data.error || 'Failed to delete note');
                }
            } catch (error) {
                console.error('Error deleting note:', error);
                tg.showAlert('Failed to delete note: ' + error.message);
            }
        }
    });
}

function handleSearch(e) {
    searchTerm = e.target.value.trim();
    renderNotes();
}

// Handle back button
tg.BackButton.onClick(() => {
    if (noteEditorModal.style.display === 'flex') {
        closeNoteModal();
    } else {
        tg.close();
    }
});

// Show back button when modal is open
const originalDisplay = noteEditorModal.style.display;
const observer = new MutationObserver(() => {
    if (noteEditorModal.style.display === 'flex') {
        tg.BackButton.show();
    } else {
        tg.BackButton.hide();
    }
});
observer.observe(noteEditorModal, { attributes: true, attributeFilter: ['style'] });
