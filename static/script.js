const API_BASE = '/api';

// DOM elements
const chatbotIcon = document.getElementById('chatbotIcon');
const chatbox = document.getElementById('chatbox');
const closeChat = document.getElementById('closeChat');
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const fileList = document.getElementById('fileList');
const documentViewer = document.getElementById('documentViewer');
const uploadBtn = document.getElementById('uploadBtn');
const fileInput = document.getElementById('fileInput');
const references = document.getElementById('references');

// State
let currentReferences = [];
let currentDocument = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadDocuments();
    setupEventListeners();
});

// Event Listeners
function setupEventListeners() {
    chatbotIcon.addEventListener('click', () => {
        chatbox.classList.add('open');
        chatbotIcon.classList.add('hidden');
    });

    closeChat.addEventListener('click', () => {
        chatbox.classList.remove('open');
        chatbotIcon.classList.remove('hidden');
    });

    sendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    uploadBtn.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', handleFileUpload);
}

// Load documents list
async function loadDocuments() {
    try {
        const response = await fetch(`${API_BASE}/documents`);
        const data = await response.json();
        displayDocuments(data.documents);
    } catch (error) {
        console.error('Error loading documents:', error);
        fileList.innerHTML = '<div class="loading">Error loading documents</div>';
    }
}

// Display documents in sidebar
function displayDocuments(documents) {
    if (documents.length === 0) {
        fileList.innerHTML = '<div class="loading">No documents found</div>';
        return;
    }

    fileList.innerHTML = documents.map(doc => `
        <div class="file-item" data-filename="${escapeAttribute(doc.filename)}">
            <svg class="file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                ${doc.filename.endsWith('.pdf')
            ? '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline>'
            : '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line>'
        }
            </svg>
            <span class="file-name">${escapeHtml(doc.filename)}</span>
            <button class="delete-file-btn" title="Delete file" data-delete="${escapeAttribute(doc.filename)}">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
            </button>
        </div>
    `).join('');

    // Add click handlers for file selection
    document.querySelectorAll('.file-item').forEach(item => {
        item.addEventListener('click', (e) => {
            // If delete button was clicked, ignore
            if (e.target.closest('.delete-file-btn')) return;

            document.querySelectorAll('.file-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            loadDocument(item.dataset.filename);
        });
    });

    // Add click handlers for delete buttons
    document.querySelectorAll('.delete-file-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const filename = btn.dataset.delete;
            deleteFile(e, filename);
        });
    });
}

// Delete file
async function deleteFile(event, filename) {
    event.stopPropagation(); // Prevent clicking the file item
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) return;

    try {
        const response = await fetch(`${API_BASE}/documents/${encodeURIComponent(filename)}`, {
            method: 'DELETE',
        });

        if (response.ok) {
            loadDocuments();
            if (currentDocument === filename) {
                documentViewer.innerHTML = '<div class="empty-state"><p>Document deleted</p></div>';
                currentDocument = null;
            }
        } else {
            console.error('Error deleting file');
            alert('Error deleting file');
        }
    } catch (error) {
        console.error('Error deleting file:', error);
        alert('Error deleting file');
    }
}

// Load document content
async function loadDocument(filename) {
    try {
        currentDocument = filename;
        const response = await fetch(`${API_BASE}/documents/${encodeURIComponent(filename)}`);

        if (filename.endsWith('.pdf')) {
            // For PDFs, open in new tab or embed
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            documentViewer.innerHTML = `
                <div class="document-content">
                    <h1>${filename}</h1>
                    <iframe src="${url}" width="100%" height="800px" style="border: none;"></iframe>
                </div>
            `;
        } else {
            // For text files
            const data = await response.json();
            documentViewer.innerHTML = `
                <div class="document-content">
                    <h1>${data.filename}</h1>
                    <pre>${escapeHtml(data.content)}</pre>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading document:', error);
        documentViewer.innerHTML = '<div class="empty-state"><p>Error loading document</p></div>';
    }
}

// Send message
async function sendMessage() {
    const question = chatInput.value.trim();
    if (!question) return;

    // Add user message
    addMessage(question, 'user');
    chatInput.value = '';
    sendBtn.disabled = true;

    // Show typing indicator
    const typingId = addTypingIndicator();

    try {
        const response = await fetch(`${API_BASE}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ question, k: 4 }),
        });

        const data = await response.json();

        // Remove typing indicator
        removeTypingIndicator(typingId);

        // Add bot response
        addMessage(data.answer, 'bot', true); // Enable HTML rendering

        // Display references
        if (data.references && data.references.length > 0) {
            currentReferences = data.references;
            displayReferences(data.references);
        } else {
            references.innerHTML = '';
        }

    } catch (error) {
        removeTypingIndicator(typingId);
        addMessage('Sorry, I encountered an error. Please try again.', 'bot');
        console.error('Error:', error);
    } finally {
        sendBtn.disabled = false;
    }
}

// Add message to chat
function addMessage(text, type, isHtml = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;

    let content = text;
    if (type === 'bot' && isHtml) {
        // Allow raw HTML content
        // Remove markdown code blocks if present (sometimes LLMs wrap HTML in ```html ... ```)
        content = text.replace(/```html/g, '').replace(/```/g, '');
    } else {
        content = escapeHtml(text);
    }

    messageDiv.innerHTML = `
        <div class="message-content">
            ${type === 'bot' && isHtml ? content : `<p>${content}</p>`}
        </div>
    `;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Handle inline reference click
window.handleReferenceClick = function (event, filename) {
    event.preventDefault();
    const fileItem = document.querySelector(`[data-filename="${filename}"]`);
    if (fileItem) {
        fileItem.click();
    } else {
        console.warn(`Document ${filename} not found in sidebar list`);
        // Fallback: try to load it anyway
        loadDocument(filename);
    }
};

// Add typing indicator
function addTypingIndicator() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message bot-message typing-indicator';
    typingDiv.id = 'typing-indicator';
    typingDiv.innerHTML = `
        <div class="message-content">
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    chatMessages.appendChild(typingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return 'typing-indicator';
}

// Remove typing indicator
function removeTypingIndicator(id) {
    const indicator = document.getElementById(id);
    if (indicator) {
        indicator.remove();
    }
}

// Display references
function displayReferences(refs) {
    if (!refs || refs.length === 0) {
        references.innerHTML = '';
        return;
    }

    references.innerHTML = refs.map(ref => `
        <a href="#" class="reference-item" data-source="${ref.source}" data-filename="${ref.filename}">
            ${ref.filename}${ref.page ? ` (Page ${ref.page})` : ''}
        </a>
    `).join('');

    // Add click handlers
    document.querySelectorAll('.reference-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const filename = item.dataset.filename;
            // Find and select the document in sidebar
            const fileItem = document.querySelector(`[data-filename="${filename}"]`);
            if (fileItem) {
                fileItem.click();
            }
        });
    });
}

// Handle file upload
async function handleFileUpload(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch(`${API_BASE}/upload`, {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();
            console.log('File uploaded:', data);

            // Reload documents list
            loadDocuments();

            // Show success message
            addMessage(`File "${file.name}" uploaded and indexed successfully!`, 'bot');
        } catch (error) {
            console.error('Error uploading file:', error);
            addMessage(`Error uploading "${file.name}"`, 'bot');
        }
    }

    // Reset input
    fileInput.value = '';
}

// Utility function
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeAttribute(text) {
    return text.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

