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

    let uploadedDocumentsCount = 0;
    
    // --- WebSocket Setup ---
    let ws = null;
    let isConnected = false;
    let currentBotMsgElement = null;

    function connectWebSocket() {
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
                // Formatting sources
                const fullText = (currentBotMsgElement.dataset.rawText || data.answer || '').trim();
                const isUnknown = fullText.includes("I don't know based on the provided documents") || fullText.includes("No relevant information found");

                if (data.sources && data.sources.length > 0 && !isUnknown) {
                    appendSources(currentBotMsgElement.parentElement, data.sources);
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
        Array.from(files).forEach(file => {
            formData.append('files', file);
            addDocumentToList(file.name, true);
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
                uploadText.textContent = 'Upload complete!';
                setTimeout(() => {
                    uploadStatus.classList.add('hidden');
                }, 3000);
            } else {
                uploadText.textContent = `Error: ${results.detail || 'Upload failed'}`;
                setTimeout(() => uploadStatus.classList.add('hidden'), 5000);
            }
        } catch (err) {
            console.error('Upload error:', err);
            uploadText.textContent = 'Network error during upload.';
            setTimeout(() => uploadStatus.classList.add('hidden'), 5000);
        }
    }

    function addDocumentToList(filename, isNew = false) {
        if (uploadedDocumentsCount === 0) {
            docList.innerHTML = '';
        }
        
        uploadedDocumentsCount++;
        docCount.textContent = uploadedDocumentsCount;
        
        const li = document.createElement('li');
        li.innerHTML = `
            <svg class="doc-icon" viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${filename}</span>
        `;
        docList.appendChild(li);
    }

    // --- Chat Logic ---

    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const query = queryInput.value.trim();
        if (!query) return;

        appendUserMessage(query);
        queryInput.value = '';
        disableInput();

        if (isConnected) {
            currentBotMsgElement = createBotMessage();
            currentBotMsgElement.innerHTML = '<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>';
            
            ws.send(JSON.stringify({
                question: query
                // doc_ids: [] optional payload
            }));
        } else {
            // Fallback to fetch
            fetchAnswer(query);
        }
    });

    async function fetchAnswer(query) {
        currentBotMsgElement = createBotMessage();
        currentBotMsgElement.innerHTML = '<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>';
        
        try {
            const response = await fetch('/api/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: query })
            });
            const data = await response.json();
            
            currentBotMsgElement.innerHTML = parseMarkdown(data.answer);
            const fullText = (data.answer || '').trim();
            const isUnknown = fullText.includes("I don't know based on the provided documents") || fullText.includes("No relevant information found");
            
            if (data.sources && data.sources.length > 0 && !isUnknown) {
                appendSources(currentBotMsgElement.parentElement, data.sources);
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

    function appendSystemMessage(text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message system';
        msgDiv.innerHTML = `
            <div class="msg-content">${escapeHTML(text)}</div>
        `;
        messagesContainer.appendChild(msgDiv);
        scrollToBottom();
    }

    function appendSources(messageDiv, sources) {
        if (!sources || sources.length === 0) return;
        const srcDiv = document.createElement('div');
        srcDiv.className = 'sources';

        let html = '<h4>📚 Sources</h4><ul>';
        // Display up to top 5 sources for better accuracy
        const topSources = sources.slice(0, 5);
        topSources.forEach((src, index) => {
            const snippet = src.text.substring(0, 120).replace(/\n/g, ' ') + '...';
            const docName = src.doc_name || src.doc_id || 'Unknown Document';
            const relevance = src.score > 0.8 ? 'High' : src.score > 0.6 ? 'Medium' : 'Low';
            html += `<li><strong>${docName}</strong><br><span class="source-text">"${escapeHTML(snippet)}"</span><br><small>Relevance: ${relevance} (${src.score.toFixed(3)})</small></li>`;
        });
        html += '</ul>';
        srcDiv.innerHTML = html;
        messageDiv.appendChild(srcDiv);
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
