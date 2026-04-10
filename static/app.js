document.addEventListener('DOMContentLoaded', () => {
    // --- Elements ---
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const docList = document.getElementById('doc-list');
    const docCount = document.getElementById('doc-count');
    const uploadStatus = document.getElementById('upload-status');
    const uploadText = document.getElementById('upload-text');
    
    const chatForm = document.getElementById('chat-form');
    const queryInput = document.getElementById('query-input');
    const messagesContainer = document.getElementById('messages');
    const sendBtn = document.getElementById('send-btn');
    const clearHistoryBtn = document.getElementById('clear-history-btn');
    const clearCacheBtn = document.getElementById('clear-cache-btn');

    let uploadedDocumentsCount = 0;
    
    // --- WebSocket Setup ---
    let ws = null;
    let isConnected = false;
    let currentBotMsgElement = null;

    function connectWebSocket() {
        if (ws && isConnected) {
            console.log('WebSocket already connected');
            return;
        }

        console.log('Attempting to connect WebSocket...');
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/ask`;
        
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            isConnected = true;
            console.log('WebSocket connected');
        };
        
        ws.onclose = () => {
            isConnected = false;
            console.log('WebSocket disconnected. Reconnecting in 3s...');
            setTimeout(connectWebSocket, 3000);
        };
        
        ws.onerror = (err) => {
            console.error('WebSocket Error:', err);
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('WebSocket message received:', data);
            
            if (data.error) {
                appendSystemMessage(`Error: ${data.error}`);
                enableInput();
                return;
            }
            
            if (data.answer && typeof data.answer === 'string') {
                // Non-streaming fallback or explicit answer
                if (!currentBotMsgElement) {
                    currentBotMsgElement = createBotMessage();
                }
                currentBotMsgElement.innerHTML = parseMarkdown(data.answer);
            }

            if (data.chunk) {
                if (!currentBotMsgElement) {
                    currentBotMsgElement = createBotMessage();
                }
                currentBotMsgElement.dataset.rawText = (currentBotMsgElement.dataset.rawText || '') + data.chunk;
                currentBotMsgElement.innerHTML = parseMarkdown(currentBotMsgElement.dataset.rawText);
                scrollToBottom();
            }
            
            if (data.done) {
                const fullText = (currentBotMsgElement.dataset.rawText || data.answer || '').trim();
                const isUnknown = fullText.includes("I don't know based on the provided documents") || fullText.includes("No relevant information found");

                appendResponseBadge(currentBotMsgElement, data.cached === true);
                if (data.sources && data.sources.length > 0 && !isUnknown) {
                    appendSources(currentBotMsgElement, data.sources);
                }
                enableInput();
                currentBotMsgElement = null;
                scrollToBottom();
            }
        };
    }

    connectWebSocket();

    // --- File Upload Logic ---
    
    // Click to upload
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFiles(e.target.files);
        }
    });

    // Drag and Drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('dragover');
        }, false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleFiles(files);
        }
    });

    async function handleFiles(files) {
        const formData = new FormData();
        const pendingRows = Array.from(files).map(file => {
            formData.append('files', file);
            return addDocumentToList(file.name, { pending: true });
        });

        uploadStatus.classList.remove('hidden');
        uploadText.textContent = `Uploading ${files.length} file(s)...`;
        
        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            
            const results = await response.json();
            
            if (response.ok) {
                results.forEach((result, index) => {
                    updateDocumentListItem(
                        pendingRows[index],
                        result.filename || files[index].name,
                        result.document_id,
                        result.message
                    );
                });
                uploadText.textContent = 'Upload complete!';
                setTimeout(() => {
                    uploadStatus.classList.add('hidden');
                }, 3000);
            } else {
                pendingRows.forEach(removeDocumentListItem);
                uploadText.textContent = `Error: ${results.detail || 'Upload failed'}`;
                setTimeout(() => uploadStatus.classList.add('hidden'), 5000);
            }
        } catch (err) {
            console.error('Upload error:', err);
            pendingRows.forEach(removeDocumentListItem);
            uploadText.textContent = 'Network error during upload.';
            setTimeout(() => uploadStatus.classList.add('hidden'), 5000);
        }
    }

    function addDocumentToList(filename, options = {}) {
        if (uploadedDocumentsCount === 0) {
            docList.innerHTML = '';
        }
        
        uploadedDocumentsCount++;
        docCount.textContent = uploadedDocumentsCount;
        
        const li = document.createElement('li');
        li.className = 'doc-item';
        if (options.pending) {
            li.classList.add('pending');
        }
        li.innerHTML = `
            <input type="checkbox" class="doc-select" title="Use this document for answers" aria-label="Use ${escapeHTML(filename)} for answers" ${options.pending ? 'disabled' : 'checked'}>
            <svg class="doc-icon" viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            <span class="doc-name"></span>
            <span class="doc-status">${options.pending ? 'Uploading...' : ''}</span>
            <div class="doc-actions">
                <button type="button" class="doc-action-btn remove-list-btn" title="Remove from list" aria-label="Remove ${escapeHTML(filename)} from list">
                    List
                </button>
                <button type="button" class="doc-action-btn remove-vector-btn" title="Remove from vector DB" aria-label="Remove ${escapeHTML(filename)} from vector database" ${options.pending ? 'disabled' : ''}>
                    Vector DB
                </button>
            </div>
        `;
        li.querySelector('.doc-name').textContent = filename;
        docList.appendChild(li);
        return li;
    }

    function updateDocumentListItem(li, filename, documentId, statusText = '') {
        if (!li) return;
        li.dataset.documentId = documentId;
        li.classList.remove('pending');
        li.querySelector('.doc-name').textContent = filename;
        li.querySelector('.doc-status').textContent = '';
        const checkbox = li.querySelector('.doc-select');
        checkbox.disabled = !documentId;
        checkbox.checked = Boolean(documentId);
        checkbox.setAttribute('aria-label', `Use ${filename} for answers`);
        li.querySelector('.doc-status').textContent = '';
        const listButton = li.querySelector('.remove-list-btn');
        listButton.setAttribute('aria-label', `Remove ${filename} from list`);
        const vectorButton = li.querySelector('.remove-vector-btn');
        vectorButton.disabled = !documentId;
        vectorButton.setAttribute('aria-label', `Remove ${filename} from vector database`);
    }

    function removeDocumentListItem(li) {
        if (!li || !li.parentElement) return;
        li.remove();
        uploadedDocumentsCount = Math.max(0, uploadedDocumentsCount - 1);
        docCount.textContent = uploadedDocumentsCount;
        if (uploadedDocumentsCount === 0) {
            docList.innerHTML = '<li class="empty-state">No documents uploaded yet</li>';
        }
    }

    docList.addEventListener('click', async (event) => {
        const listButton = event.target.closest('.remove-list-btn');
        if (listButton) {
            const li = listButton.closest('li');
            removeDocumentListItem(li);
            return;
        }

        const button = event.target.closest('.remove-vector-btn');
        if (!button) return;

        const li = button.closest('li');
        const documentId = li?.dataset.documentId;
        const filename = li?.querySelector('.doc-name')?.textContent || 'this document';
        if (!documentId) return;

        if (!confirm(`Remove "${filename}" from vector database?`)) {
            return;
        }

        button.disabled = true;
        li.classList.add('deleting');
        li.querySelector('.doc-status').textContent = 'Removing from vector DB...';

        try {
            const response = await fetch(`/api/files/${encodeURIComponent(documentId)}/vector`, {
                method: 'DELETE'
            });
            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || result.error || 'Delete failed');
            }

            appendSystemMessage(`Removed "${filename}" from vector database.`, 'notice');
            removeDocumentListItem(li);
        } catch (err) {
            console.error('Delete error:', err);
            li.classList.remove('deleting');
            li.querySelector('.doc-status').textContent = 'Vector remove failed';
            button.disabled = false;
            appendSystemMessage(`Could not remove "${filename}" from vector database.`, 'error');
        }
    });

    function getSelectedDocumentIds() {
        return Array.from(docList.querySelectorAll('.doc-item'))
            .filter(item => item.querySelector('.doc-select')?.checked)
            .map(item => item.dataset.documentId)
            .filter(Boolean);
    }

    // --- Chat Logic ---

    clearHistoryBtn.addEventListener('click', () => {
        currentBotMsgElement = null;
        messagesContainer.innerHTML = '';
        enableInput();
        const readyMessage = appendSystemMessage('Ready for a fresh chat...', 'notice temporary');
        setTimeout(() => {
            readyMessage.classList.add('fade-out');
            readyMessage.addEventListener('animationend', () => readyMessage.remove(), { once: true });
        }, 2500);
    });

    clearCacheBtn.addEventListener('click', async () => {
        clearCacheBtn.disabled = true;

        try {
            const response = await fetch('/api/clear_cache', { method: 'POST' });
            const data = await response.json();

            if (!response.ok || data.status !== 'success') {
                throw new Error(data.detail || 'Failed to clear cache.');
            }

            const count = data.cleared_count || 0;
            const label = count === 1 ? 'cached response' : 'cached responses';
            appendSystemMessage(`Cleared ${count} ${label}.`, 'notice');
        } catch (err) {
            console.error('Clear cache error:', err);
            appendSystemMessage('Failed to clear cache.', 'error');
        } finally {
            clearCacheBtn.disabled = false;
        }
    });

    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const query = queryInput.value.trim();
        if (!query) return;

        const selectedDocIds = getSelectedDocumentIds();
        if (uploadedDocumentsCount > 0 && selectedDocIds.length === 0) {
            appendSystemMessage('Select at least one document to ask from.', 'error');
            return;
        }

        appendUserMessage(query);
        queryInput.value = '';
        disableInput();

        if (isConnected) {
            currentBotMsgElement = createBotMessage();
            currentBotMsgElement.innerHTML = '<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>';
            
            ws.send(JSON.stringify({
                question: query,
                doc_ids: selectedDocIds.length ? selectedDocIds : null
            }));
        } else {
            // Fallback to fetch
            fetchAnswer(query, selectedDocIds);
        }
    });

    async function fetchAnswer(query, selectedDocIds = []) {
        currentBotMsgElement = createBotMessage();
        currentBotMsgElement.innerHTML = '<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>';
        
        try {
            const response = await fetch('/api/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question: query,
                    doc_ids: selectedDocIds.length ? selectedDocIds : null
                })
            });
            const data = await response.json();
            
            currentBotMsgElement.innerHTML = parseMarkdown(data.answer);
            appendResponseBadge(currentBotMsgElement, data.cached === true);
            const fullText = (data.answer || '').trim();
            const isUnknown = fullText.includes("I don't know based on the provided documents") || fullText.includes("No relevant information found");
            
            if (data.sources && data.sources.length > 0 && !isUnknown) {
                appendSources(currentBotMsgElement, data.sources);
            }
        } catch (err) {
            currentBotMsgElement.innerHTML = `Error: ${err.message}`;
        } finally {
            enableInput();
            currentBotMsgElement = null;
            scrollToBottom();
        }
    }

    function appendUserMessage(text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message user';
        msgDiv.innerHTML = `
            <div class="avatar">
                <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            </div>
            <div class="msg-content">${escapeHTML(text)}</div>
        `;
        messagesContainer.appendChild(msgDiv);
        scrollToBottom();
    }

    function createBotMessage() {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message bot';
        
        const avatar = `<div class="avatar">
            <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none"><path d="M12 2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2h0a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"></path><path d="M12 8a6 6 0 0 0-6 6v2a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-2a6 6 0 0 0-6-6z"></path><path d="M8 22h8"></path><line x1="12" y1="18" x2="12" y2="22"></line><line x1="9" y1="12" x2="9.01" y2="12"></line><line x1="15" y1="12" x2="15.01" y2="12"></line></svg>
        </div>`;
        
        const content = document.createElement('div');
        content.className = 'msg-content';
        content.dataset.rawText = ''; // To accumulate markdown text
        
        msgDiv.innerHTML = avatar;
        msgDiv.appendChild(content);
        messagesContainer.appendChild(msgDiv);
        scrollToBottom();
        
        return content;
    }

    function appendSystemMessage(text, variant = '') {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message system ${variant}`.trim();
        msgDiv.innerHTML = `
            <div class="msg-content">${escapeHTML(text)}</div>
        `;
        messagesContainer.appendChild(msgDiv);
        scrollToBottom();
        return msgDiv;
    }

    function appendSources(contentDiv, sources) {
        const sourceNames = uniqueSourceNames(sources);
        if (sourceNames.length === 0) return;

        const sourceLine = document.createElement('p');
        sourceLine.className = 'source-line';
        sourceLine.innerHTML = `<strong>Sources:</strong> ${sourceNames.map(escapeHTML).join(', ')}`;
        contentDiv.appendChild(sourceLine);
    }

    function appendResponseBadge(contentDiv, isCached) {
        const existingBadge = contentDiv.querySelector('.response-badge');
        if (existingBadge) {
            existingBadge.remove();
        }

        const badge = document.createElement('div');
        badge.className = `response-badge ${isCached ? 'cache' : 'llm'}`;
        badge.textContent = isCached ? 'From cache' : 'From LLM';
        contentDiv.prepend(badge);
    }

    function uniqueSourceNames(sources) {
        const names = [];
        const seen = new Set();

        sources.forEach(source => {
            const rawName = typeof source === 'string'
                ? source
                : source?.filename || source?.doc_name || source?.doc_id || source?.source;
            if (!rawName) return;

            const name = rawName.split(/[\\/]/).pop().trim();
            if (!name || looksInternalId(name)) return;

            const key = name.toLowerCase();
            if (seen.has(key)) return;

            seen.add(key);
            names.push(name);
        });

        return names;
    }

    function looksInternalId(value) {
        const compact = value.replace(/-/g, '');
        return compact.length >= 16 && /^[a-f0-9]+$/i.test(compact);
    }

    function disableInput() {
        queryInput.disabled = true;
        sendBtn.disabled = true;
    }

    function enableInput() {
        queryInput.disabled = false;
        sendBtn.disabled = false;
        queryInput.focus();
    }

    function scrollToBottom() {
        requestAnimationFrame(() => {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        });
    }

    function escapeHTML(str) {
        return str.replace(/[&<>'"]/g, 
            tag => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                "'": '&#39;',
                '"': '&quot;'
            }[tag])
        );
    }
    
    function parseMarkdown(text) {
        // Very basic markdown parser for simple bold and paragraphs.
        if (!text) return '';
        let html = escapeHTML(text);
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
        html = html.replace(/\n\n/g, '</p><p>');
        html = html.replace(/\n/g, '<br/>');
        return `<p>${html}</p>`;
    }
});
