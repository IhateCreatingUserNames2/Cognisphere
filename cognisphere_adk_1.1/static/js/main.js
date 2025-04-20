// static/js/main.js
    // Global variables
    const USER_ID = 'default_user';
    const SESSION_ID = 'default_session';
    let currentSessionId = localStorage.getItem('currentSessionId') || SESSION_ID;

    // Helper function for API calls
    async function fetchAPI(url, method = 'GET', data = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };

        if (data) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, options);
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            return { error: error.message };
        }
    }

    // Initialize the UI
    document.addEventListener('DOMContentLoaded', () => {
        const chatHistory = document.getElementById('chat-history');
        const userInput = document.getElementById('user-input');
        const sendButton = document.getElementById('send-button');
        const statusIndicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('status-text');
        const componentStatus = document.getElementById('system-status-container');
        const memoriesDiv = document.getElementById('memories-container');
        const narrativeThreadsDiv = document.getElementById('narrative-threads-container');
        const recallButton = document.getElementById('recall-memories-btn');
        currentSessionId = localStorage.getItem('currentSessionId') || SESSION_ID;
        const updateThreadsButton   = document.getElementById('update-threads-btn');
        console.log(`Restored session ID from localStorage: ${currentSessionId}`);

        // mcpIntegration
        const mcpStatusIndicator = document.getElementById('mcpIntegration-status-indicator');
        const mcpStatusText = document.getElementById('mcpIntegration-status-text');
        const mcpConfigToggle = document.getElementById('mcpIntegration-config-toggle');
        const mcpConfigPanel = document.getElementById('mcpIntegration-config-panel');
        const mcpServerList = document.getElementById('mcpIntegration-server-list');
        const mcpToolsPanel = document.getElementById('mcpIntegration-tools-panel');
        const mcpToolsList = document.getElementById('mcpIntegration-tools-list');
        const mcpAddServerBtn = document.getElementById('mcpIntegration-add-server-btn');
        const mcpCancelBtn = document.getElementById('mcpIntegration-cancel-btn');

        // Identity-related elements
        const identitySelect = document.getElementById('identity-select');
        const identitiesDiv = document.getElementById('identities');
        const currentIdentityDiv = document.getElementById('current-identity');
        const refreshIdentitiesButton = document.getElementById('refresh-identities-button');
        const createIdentityButton = document.getElementById('create-identity-button');
        const identityForm = document.getElementById('identity-form');
        const saveIdentityButton = document.getElementById('save-identity');
        const cancelIdentityButton = document.getElementById('cancel-identity');

        // Toggle MCP configuration panel
        mcpConfigToggle.addEventListener('click', () => {
            const isVisible = mcpConfigPanel.style.display !== 'none';
            mcpConfigPanel.style.display = isVisible ? 'none' : 'block';
            mcpConfigToggle.textContent = isVisible ? 'Configure MCP' : 'Hide Configuration';

            // If showing, refresh server list
            if (!isVisible) {
                refreshMcpServers();
            }
        });

        // Cancel button
        mcpCancelBtn.addEventListener('click', () => {
            mcpConfigPanel.style.display = 'none';
            mcpConfigToggle.textContent = 'Configure MCP';

            // Clear input fields
            document.getElementById('mcpIntegration-server-name').value = '';
            document.getElementById('mcpIntegration-server-command').value = '';
            document.getElementById('mcpIntegration-server-args').value = '';
            document.getElementById('mcpIntegration-server-package').value = '';
            document.getElementById('mcpIntegration-server-env').value = '';
        });

        // Add server button
        mcpAddServerBtn.addEventListener('click', async () => {
            // Get input values
            const name = document.getElementById('mcpIntegration-server-name').value.trim();
            const command = document.getElementById('mcpIntegration-server-command').value.trim();
            const argsString = document.getElementById('mcpIntegration-server-args').value.trim();
            const packageName = document.getElementById('mcpIntegration-server-package').value.trim();
            const envJson = document.getElementById('mcpIntegration-server-env').value.trim();

            // Validate required fields
            if (!command) {
                alert('Command is required');
                return;
            }

            // Parse arguments
            const args = argsString ? argsString.split(',').map(arg => arg.trim()) : [];

            // Parse environment variables
            let env = {};
            if (envJson) {
                try {
                    env = JSON.parse(envJson);
                } catch (e) {
                    alert('Invalid JSON for environment variables');
                    return;
                }
            }

            // Show loading state
            mcpAddServerBtn.disabled = true;
            mcpAddServerBtn.textContent = 'Adding Server...';

            try {

                     // First test if the MCP routes are working
                const testResponse = await fetch('/api/mcp/test');
                const testResult = await testResponse.json();

                if (!testResponse.ok) {
                    console.error("MCP routes test failed:", testResult);
                    alert(`MCP routes not working: ${testResult.error || 'Unknown error'}`);
                    return;
                }

                if (!testResult.mcp_available) {
                    alert('MCP integration is not available on the server');
                    return;
                }
                // Send request to add server
                const response = await fetch('/api/mcp/servers', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        name,
                        command,
                        args,
                        env,
                        install_package: packageName
                    })
                });

                const result = await response.json();

                if (response.ok) {
                    alert('MCP server added successfully');

                    // Clear input fields
                    document.getElementById('mcpIntegration-server-name').value = '';
                    document.getElementById('mcpIntegration-server-command').value = '';
                    document.getElementById('mcpIntegration-server-args').value = '';
                    document.getElementById('mcpIntegration-server-package').value = '';
                    document.getElementById('mcpIntegration-server-env').value = '';

                    // Refresh server list
                    refreshMcpServers();
                } else {
                    alert(`Error adding server: ${result.error || 'Unknown error'}`);
                }
            } catch (e) {
                alert(`Error adding server: ${e.message}`);
            } finally {
                // Reset button
                mcpAddServerBtn.disabled = false;
                mcpAddServerBtn.textContent = 'Add Server';
            }
        });

        // Refresh MCP servers
        async function refreshMcpServers() {
            try {
                // Fetch servers
                const response = await fetch('/api/mcp/servers');
                const data = await response.json();

                if (response.ok && data.servers) {
                    // Update MCP status
                    const serversCount = data.servers.length;
                    mcpStatusIndicator.className = `status-indicator ${serversCount > 0 ? 'status-online' : 'status-offline'}`;
                    mcpStatusText.textContent = `MCP Integration: ${serversCount} servers configured`;

                    // Update server list
                    if (serversCount === 0) {
                        mcpServerList.innerHTML = '<p>No servers configured</p>';
                    } else {
                        mcpServerList.innerHTML = '';

                        data.servers.forEach(server => {
                            const serverItem = document.createElement('div');
                            serverItem.className = 'mcpIntegration-server-item';

                            const statusClass = server.status === 'running' ? 'status-online' : 'status-offline';

                            serverItem.innerHTML = `
                                <div class="server-header">
                                    <div class="status">
                                        <div class="status-indicator ${statusClass}"></div>
                                        <h4>${server.id}</h4>
                                    </div>
                                    <div class="server-actions">
                                        <button class="action connect-server" data-id="${server.id}">
                                            ${server.status === 'running' ? 'Disconnect' : 'Connect'}
                                        </button>
                                        <button class="action remove-server" data-id="${server.id}">Remove</button>
                                    </div>
                                </div>
                                <div class="server-details">
                                    <p><strong>Command:</strong> ${server.command} ${server.args.join(' ')}</p>
                                    <p><strong>Status:</strong> ${server.status}</p>
                                    <p><strong>Created:</strong> ${new Date(server.created_at).toLocaleString()}</p>
                                </div>
                            `;

                            mcpServerList.appendChild(serverItem);
                        });

                        // Add event listeners for server actions
                        document.querySelectorAll('.connect-server').forEach(button => {
                            button.addEventListener('click', async () => {
                                const serverId = button.dataset.id;
                                const isConnected = button.textContent.trim() === 'Disconnect';

                                if (isConnected) {
                                    await disconnectServer(serverId);
                                } else {
                                    await connectServer(serverId);
                                }

                                // Refresh server list
                                refreshMcpServers();

                                // Refresh tools list
                                refreshMcpTools();
                            });
                        });

                        document.querySelectorAll('.remove-server').forEach(button => {
                            button.addEventListener('click', async () => {
                                const serverId = button.dataset.id;

                                if (confirm(`Are you sure you want to remove server ${serverId}?`)) {
                                    // First disconnect if connected
                                    try {
                                        await disconnectServer(serverId);
                                    } catch (e) {
                                        // Ignore disconnection errors during removal
                                    }

                                    // Then remove
                                    await removeServer(serverId);

                                    // Refresh server list
                                    refreshMcpServers();

                                    // Refresh tools list
                                    refreshMcpTools();
                                }
                            });
                        });
                    }
                } else {
                    mcpStatusIndicator.className = 'status-indicator status-offline';
                    mcpStatusText.textContent = 'MCP Integration: Error fetching servers';
                }
            } catch (e) {
                mcpStatusIndicator.className = 'status-indicator status-offline';
                mcpStatusText.textContent = 'MCP Integration: Error fetching servers';
                console.error('Error fetching MCP servers:', e);
            }
        }

        // Connect to an MCP server
        async function connectServer(serverId) {
            try {
                const response = await fetch(`/api/mcp/servers/${serverId}/connect`, {
                    method: 'POST'
                });

                const result = await response.json();

                if (response.ok) {
                    console.log(`Connected to server ${serverId}`);
                    console.log('Available tools:', result.tools);

                    // Show and update tools panel
                    showMcpTools(result.tools);

                    return true;
                } else {
                    alert(`Error connecting to server: ${result.error || 'Unknown error'}`);
                    return false;
                }
            } catch (e) {
                alert(`Error connecting to server: ${e.message}`);
                return false;
            }
        }

        // Disconnect from an MCP server
        async function disconnectServer(serverId) {
            try {
                const response = await fetch(`/api/mcp/servers/${serverId}/disconnect`, {
                    method: 'POST'
                });

                const result = await response.json();

                if (response.ok) {
                    console.log(`Disconnected from server ${serverId}`);
                    return true;
                } else {
                    alert(`Error disconnecting from server: ${result.error || 'Unknown error'}`);
                    return false;
                }
            } catch (e) {
                alert(`Error disconnecting from server: ${e.message}`);
                return false;
            }
        }

        // Remove an MCP server
        async function removeServer(serverId) {
            try {
                const response = await fetch(`/api/mcp/servers/${serverId}`, {
                    method: 'DELETE'
                });

                const result = await response.json();

                if (response.ok) {
                    console.log(`Removed server ${serverId}`);
                    return true;
                } else {
                    alert(`Error removing server: ${result.error || 'Unknown error'}`);
                    return false;
                }
            } catch (e) {
                alert(`Error removing server: ${e.message}`);
                return false;
            }
        }

        // Show MCP tools
        function showMcpTools(tools) {
            // Show tools panel
            mcpToolsPanel.style.display = 'block';

            // Update tools list
            if (!tools || tools.length === 0) {
                mcpToolsList.innerHTML = '<p>No MCP tools available</p>';
            } else {
                mcpToolsList.innerHTML = '';

                tools.forEach(tool => {
                    const toolItem = document.createElement('div');
                    toolItem.className = 'mcpIntegration-tool-item';

                    toolItem.innerHTML = `
                        <h4>${tool.name}</h4>
                        <p>${tool.description || 'No description available'}</p>
                        <p><small>${tool.is_long_running ? 'Long running' : 'Standard'} tool</small></p>
                    `;

                    mcpToolsList.appendChild(toolItem);
                });
            }
        }

        // Refresh MCP tools
        async function refreshMcpTools() {
            try {
                const response = await fetch('/api/mcp/tools');
                const data = await response.json();

                if (response.ok) {
                    if (data.count > 0) {
                        showMcpTools(data.tools);
                    } else {
                        mcpToolsPanel.style.display = 'none';
                    }
                }
            } catch (e) {
                console.error('Error fetching MCP tools:', e);
            }
        }

                // Session management
        const sessionsListDiv   = document.getElementById('sessions-list');
        const newSessionBtn = document.getElementById('new-session-btn');
        const refreshSessionsBtn = document.getElementById('refresh-sessions-btn');


        // Load available sessions
        async function loadSessions() {
            sessionsListDiv.innerHTML = '<div class="loading">Loading sessions...</div>';

            const result = await fetchAPI(`/api/sessions?user_id=${USER_ID}`);

            if (result.error) {
                sessionsListDiv.innerHTML = `<div class="error">Error: ${result.error}</div>`;
                return;
            }

            if (!result.sessions || result.sessions.length === 0) {
                sessionsListDiv.innerHTML = '<p>No conversation history found.</p>';
                return;
            }

            // Create sessions list
            let sessionsHTML = '';
            for (const session of result.sessions) {
                const timestamp = new Date(session.last_update * 1000).toLocaleString();
                const isActive = session.id === currentSessionId;
                const activeClass = isActive ? 'active' : '';

                sessionsHTML += `
                    <div class="session-item ${activeClass}" data-id="${session.id}">
                        <div class="session-header">
                            <span class="session-time">${timestamp}</span>
                            ${isActive ? '<span class="active-badge">Active</span>' : ''}
                        </div>
                        <div class="session-preview">${session.preview}</div>
                    </div>
                `;
            }

            sessionsListDiv.innerHTML = sessionsHTML;

            // Add click handlers
            document.querySelectorAll('.session-item').forEach(item => {
                item.addEventListener('click', () => {
                    switchToSession(item.dataset.id);
                });
            });
        }

        // Switch to a different session
        async function switchToSession(sessionId) {
            if (sessionId === currentSessionId) return;

            // Clear chat history display
            chatHistory.innerHTML = '';

            // Update global variable
            currentSessionId = sessionId;

           // Save to localStorage for persistence across page reloads
            localStorage.setItem('currentSessionId', sessionId);
            console.log(`Saved session ID to localStorage: ${sessionId}`);

            // Add loading message
            addMessageToChat('assistant', 'Loading conversation...', 'loading');

            // Load the session's messages
            await loadSessionMessages(sessionId);

            // Remove loading message
            const loadingMsg = document.querySelector('.loading');
            if (loadingMsg) chatHistory.removeChild(loadingMsg);

            // Update UI
            loadSessions(); // Refresh session list to show active session
            updateMemories();
            updateNarrativeThreads();
        }

        // Load messages for a specific session
        async function loadSessionMessages(sessionId) {
            try {
                const response = await fetchAPI(`/api/session/messages?user_id=${USER_ID}&session_id=${sessionId}`);

                if (response.error) {
                    addMessageToChat('assistant', `Error loading conversation: ${response.error}`);
                    return;
                }

                if (!response.messages || response.messages.length === 0) {
                    addMessageToChat('assistant', 'This is the beginning of a new conversation.');
                    return;
                }

                // Add all messages to chat history
                for (const message of response.messages) {
                    addMessageToChat(message.role, message.content);
                }

                // Scroll to bottom
                chatHistory.scrollTop = chatHistory.scrollHeight;

            } catch (error) {
                console.error('Error loading session messages:', error);
                addMessageToChat('assistant', 'Error loading conversation history.');
            }
        }

        // Create a new session
        async function createNewSession() {
            // Generate a unique session ID
            const newSessionId = 'session_' + Date.now();

            // Clear chat history
            chatHistory.innerHTML = '';

            // Update global variable
            currentSessionId = newSessionId;

            // Add welcome message
            addMessageToChat('assistant', 'Welcome to a new conversation! How can I help you today?');

            // Update UI
            loadSessions();
        }

        // Add event listeners
        newSessionBtn.addEventListener('click', createNewSession);
        refreshSessionsBtn.addEventListener('click', loadSessions);



        // Initial refresh
        refreshMcpServers();
        refreshMcpTools();

        // Chat functionality
        sendButton.addEventListener('click', sendMessage);
        userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        async function sendMessage() {
            const message = userInput.value.trim();
            if (!message) return;

            // Add user message to chat
            addMessageToChat('user', message);
            userInput.value = '';

            // Show thinking indicator
            addMessageToChat('assistant', 'Thinking...', 'thinking');

            // Send to backend WITH CURRENT SESSION ID
            const response = await fetchAPI('/api/chat', 'POST', {
                message,
                user_id: USER_ID,
                session_id: currentSessionId // Use the current selected session
            });

            // Remove thinking indicator and add response
            const thinkingElement = document.querySelector('.thinking');
            if (thinkingElement) {
                chatHistory.removeChild(thinkingElement);
            }

            if (response.error) {
                addMessageToChat('assistant', `Error: ${response.error}`);
            } else {
                addMessageToChat('assistant', response.response);

                // Refresh UI data after interaction
                updateMemories();
                updateNarrativeThreads();
                updateIdentities();
                loadSessions(); // Refresh session list with updated preview
            }
        }

        function addMessageToChat(role, content, className) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${role}${className ? ' ' + className : ''}`;
            messageDiv.textContent = content;
            chatHistory.appendChild(messageDiv);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }

        // System status
        async function updateSystemStatus() {
            const status = await fetchAPI('/api/status');

            if (status.error) {
                statusIndicator.className = 'status-indicator status-offline';
                statusText.textContent = 'System Offline';
                return;
            }

            statusIndicator.className = 'status-indicator status-online';
            statusText.textContent = 'System Online';

            // Update component status
            const components = status.components;
            let componentHTML = '<ul style="list-style: none; padding: 0;">';
            for (const [name, isActive] of Object.entries(components)) {
                const statusClass = isActive ? 'status-online' : 'status-offline';
                const label = name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                componentHTML += `<li style="display: flex; align-items: center; margin-bottom: 5px;">
                    <div class="status-indicator ${statusClass}" style="margin-right: 10px;"></div> ${label}
                </li>`;
            }
            componentHTML += '</ul>';
            componentStatus.innerHTML = componentHTML;
        }

        // Memories
        async function updateMemories() {
            const result = await fetchAPI(`/api/memories?user_id=${USER_ID}&session_id=${SESSION_ID}`);

            if (result.error) {
                memoriesDiv.innerHTML = `<div class="error">Error: ${result.error}</div>`;
                return;
            }

            if (!result.memories || result.memories.length === 0) {
                memoriesDiv.innerHTML = '<p>No memories recalled yet.</p>';
                return;
            }

            let memoriesHTML = '';
            for (const memory of result.memories) {
                const relevancePercent = Math.round((memory.relevance || 0) * 100);
                const identityName = memory.identity_name ? `<div class="identity">Identity: ${memory.identity_name}</div>` : '';

                memoriesHTML += `
                    <div class="memory-item">
                        <div>${memory.content}</div>
                        ${identityName}
                        <div class="relevance">Type: ${memory.type || 'unknown'}, Emotion: ${memory.emotion || 'neutral'}, Relevance: ${relevancePercent}%</div>
                    </div>
                `;
            }

            memoriesDiv.innerHTML = memoriesHTML;
        }

        // Narrative threads
        async function updateNarrativeThreads() {
            const result = await fetchAPI(`/api/narratives?user_id=${USER_ID}&session_id=${SESSION_ID}`);

            if (result.error) {
                narrativeThreadsDiv.innerHTML = `<div class="error">Error: ${result.error}</div>`;
                return;
            }

            if (!result.threads || result.threads.length === 0) {
                narrativeThreadsDiv.innerHTML = '<p>No active narrative threads.</p>';
                return;
            }

            let threadsHTML = '';
            for (const thread of result.threads) {
                const lastUpdated = new Date(thread.last_updated).toLocaleString();

                // Get linked identities if available
                let identitiesHTML = '';
                if (thread.linked_identity_names && thread.linked_identity_names.length > 0) {
                    identitiesHTML = `<div><strong>Linked Identities:</strong> ${thread.linked_identity_names.join(', ')}</div>`;
                }

                // Get last event if available
                let lastEventText = 'No events yet';
                if (thread.events && thread.events.length > 0) {
                    const lastEvent = thread.events[thread.events.length - 1];
                    lastEventText = lastEvent.content || 'Event with no content';
                }

                threadsHTML += `
                    <div class="thread-item">
                        <h3>${thread.title}</h3>
                        <div>${thread.description}</div>
                        <div><strong>Theme:</strong> ${thread.theme}</div>
                        ${identitiesHTML}
                        <div><strong>Latest:</strong> ${lastEventText}</div>
                        <div><strong>Last updated:</strong> ${lastUpdated}</div>
                    </div>
                `;
            }

            narrativeThreadsDiv.innerHTML = threadsHTML;
        }

        // Identity Management Functions
        async function updateIdentities() {
            const result = await fetchAPI(`/api/identities?user_id=${USER_ID}&session_id=${SESSION_ID}`);

            if (result.error) {
                identitiesDiv.innerHTML = `<div class="error">Error: ${result.error}</div>`;
                identitySelect.innerHTML = '<option value="">Error loading</option>';
                return;
            }

            if (!result.identities || result.identities.length === 0) {
                identitiesDiv.innerHTML = '<p>No identities created yet.</p>';
                identitySelect.innerHTML = '<option value="">No identities</option>';
                return;
            }

            // Update identities list
            let identitiesHTML = '';
            identitySelect.innerHTML = ''; // Clear previous options

            for (const identity of result.identities) {
                const isActive = identity.is_active;
                const activeClass = isActive ? 'active' : '';
                const activeText = isActive ? ' (Active)' : '';

                // Add to dropdown
                const option = document.createElement('option');
                option.value = identity.id;
                option.textContent = identity.name + activeText;
                option.selected = isActive;
                identitySelect.appendChild(option);

                // Add to identities section
                identitiesHTML += `
                    <div class="identity-item ${activeClass}">
                        <h3>${identity.name}${activeText}</h3>
                        <div>${identity.description || 'No description'}</div>
                        <div><strong>Type:</strong> ${identity.type}</div>
                        <div class="identity-actions">
                            ${!isActive ?
                                `<button class="action switch-identity" data-id="${identity.id}">Switch to this identity</button>` :
                                '<span>Current identity</span>'}
                        </div>
                    </div>
                `;
            }

            identitiesDiv.innerHTML = identitiesHTML;

            // Update current identity display
            const activeIdentity = result.identities.find(i => i.is_active);
            if (activeIdentity) {
                currentIdentityDiv.innerHTML = `
                    <div class="identity-item active">
                        <h3>${activeIdentity.name}</h3>
                        <div>${activeIdentity.description || 'No description'}</div>
                        <div><strong>Type:</strong> ${activeIdentity.type}</div>
                    </div>
                `;
            } else {
                currentIdentityDiv.innerHTML = '<p>No active identity</p>';
            }

            // Add event listeners to switch identity buttons
            document.querySelectorAll('.switch-identity').forEach(button => {
                button.addEventListener('click', async () => {
                    const identityId = button.dataset.id;
                    await switchIdentity(identityId);
                });
            });
        }

        async function switchIdentity(identityId) {
            // Show loading state
            currentIdentityDiv.innerHTML = '<div class="loading">Switching identity...</div>';

            // Request identity switch
            const result = await fetchAPI('/api/identities/switch', 'POST', {
                user_id: USER_ID,
                session_id: SESSION_ID,
                identity_id: identityId
            });

            // Handle response
            if (result.error) {
                currentIdentityDiv.innerHTML = `<div class="error">Error: ${result.error}</div>`;
                return;
            }

            // Add system message about identity switch
            addMessageToChat('assistant', `Switched to identity: ${result.active_identity_name}`);

            // Refresh identities
            updateIdentities();

            // Also refresh memories and narratives as they may be filtered by identity
            updateMemories();
            updateNarrativeThreads();
        }

        // Identity creation form
        createIdentityButton.addEventListener('click', () => {
            identityForm.classList.add('active');
        });

        cancelIdentityButton.addEventListener('click', () => {
            identityForm.classList.remove('active');
            // Clear form fields
            document.getElementById('identity-name').value = '';
            document.getElementById('identity-description').value = '';
            document.getElementById('identity-personality').value = '';
        });

        saveIdentityButton.addEventListener('click', async () => {
            const name = document.getElementById('identity-name').value.trim();
            const description = document.getElementById('identity-description').value.trim();
            const tone = document.getElementById('identity-tone').value;
            const personality = document.getElementById('identity-personality').value.trim();

            if (!name) {
                alert('Please provide a name for the identity');
                return;
            }

            // Construct message to create identity
            const message = `Create a new identity with these details:
                Name: ${name}
                Description: ${description}
                Tone: ${tone}
                Personality: ${personality}`;

            // Show thinking indicator
            addMessageToChat('assistant', 'Creating identity...', 'thinking');

            // Send to backend
            const response = await fetchAPI('/api/chat', 'POST', {
                message,
                user_id: USER_ID,
                session_id: SESSION_ID
            });

            // Remove thinking indicator
            const thinkingElement = document.querySelector('.thinking');
            if (thinkingElement) {
                chatHistory.removeChild(thinkingElement);
            }

            if (response.error) {
                addMessageToChat('assistant', `Error: ${response.error}`);
            } else {
                addMessageToChat('assistant', response.response);

                // Reset and hide form
                identityForm.classList.remove('active');
                document.getElementById('identity-name').value = '';
                document.getElementById('identity-description').value = '';
                document.getElementById('identity-personality').value = '';

                // Refresh identities
                updateIdentities();
            }
        });

// AIRA Network functionality

    const airaStatusIndicator = document.getElementById('aira-status-indicator');
    const airaStatusText = document.getElementById('aira-status-text');
    const airaConnectForm = document.getElementById('aira-connect-form');
    const airaConnectedUI = document.getElementById('aira-connected-ui');
    const airaHubUrlInput = document.getElementById('aira-hub-url');
    const airaAgentUrlInput = document.getElementById('aira-agent-url');
    const airaConnectBtn = document.getElementById('aira-connect-btn');
    const airaDisconnectBtn = document.getElementById('aira-disconnect-btn');
    const airaDiscoverBtn = document.getElementById('aira-discover-btn');
    const airaDiscoveryResults = document.getElementById('aira-discovery-results');
    const airaAgentsList = document.getElementById('aira-agents-list');
    const airaAgentTools = document.getElementById('aira-agent-tools');
    const airaToolsList = document.getElementById('aira-tools-list');

    // Check AIRA status on load
    checkAiraStatus();

    // Connect to AIRA hub
    airaConnectBtn.addEventListener('click', async () => {
        const hubUrl = airaHubUrlInput.value.trim();
        const agentUrl = airaAgentUrlInput.value.trim();

        if (!hubUrl || !agentUrl) {
            alert('Please enter both the AIRA Hub URL and Agent URL');
            return;
        }

        try {
          console.log("Attempting to connect to AIRA hub:", hubUrl);
            airaConnectBtn.disabled = true;
            airaConnectBtn.textContent = 'Connecting...';

            const response = await fetch('/api/aira/connect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    hub_url: hubUrl,
                    agent_url: agentUrl
                })
            });
            console.log("AIRA connection response status:", response.status);
            const result = await response.json();
            console.log("AIRA connection result:", result);
            if (response.ok) {
                updateAiraStatus(true, hubUrl);
                addMessageToChat('assistant', `Connected to AIRA hub at ${hubUrl}`);
            } else {
                console.error("Error connecting to AIRA hub:", result.error);
                alert(`Error connecting to AIRA hub: ${result.error}`);
                updateAiraStatus(false);
            }
        } catch (error) {
            console.error("Exception in AIRA connection:", error);
            alert(`Error: ${error.message}`);
            updateAiraStatus(false);
        } finally {
            airaConnectBtn.disabled = false;
            airaConnectBtn.textContent = 'Connect to AIRA Hub';
        }
    });

    // Disconnect from AIRA hub
    airaDisconnectBtn.addEventListener('click', async () => {
        try {
            airaDisconnectBtn.disabled = true;

            const response = await fetch('/api/aira/disconnect', {
                method: 'POST'
            });

            const result = await response.json();

            if (response.ok) {
                updateAiraStatus(false);
                airaDiscoveryResults.style.display = 'none';
                airaAgentTools.style.display = 'none';
                addMessageToChat('assistant', 'Disconnected from AIRA hub');
            } else {
                alert(`Error disconnecting from AIRA hub: ${result.error}`);
            }
        } catch (error) {
            alert(`Error: ${error.message}`);
        } finally {
            airaDisconnectBtn.disabled = false;
        }
    });

    // Discover AIRA agents
    airaDiscoverBtn.addEventListener('click', async () => {
        try {
            airaDiscoverBtn.disabled = true;
            airaDiscoverBtn.textContent = 'Discovering...';

            const response = await fetch('/api/aira/discover/agents');

            const result = await response.json();

            if (response.ok) {
                displayAgents(result.agents);
                airaDiscoveryResults.style.display = 'block';
                addMessageToChat('assistant', `Discovered ${result.agents.length} agents on the AIRA network`);
            } else {
                alert(`Error discovering agents: ${result.error}`);
            }
        } catch (error) {
            alert(`Error: ${error.message}`);
        } finally {
            airaDiscoverBtn.disabled = false;
            airaDiscoverBtn.textContent = 'Discover Agents';
        }
    });

    // Check AIRA status
    async function checkAiraStatus() {
        try {
            const response = await fetch('/api/aira/status');
            const result = await response.json();

            updateAiraStatus(result.connected, result.hub_url);
        } catch (error) {
            console.error('Error checking AIRA status:', error);
            updateAiraStatus(false);
        }
    }

    // Update AIRA status UI
    function updateAiraStatus(connected, hubUrl = '') {
        if (connected) {
            airaStatusIndicator.className = 'status-indicator status-online';
            airaStatusText.textContent = `Connected to ${hubUrl}`;
            airaConnectForm.style.display = 'none';
            airaConnectedUI.style.display = 'block';
        } else {
            airaStatusIndicator.className = 'status-indicator status-offline';
            airaStatusText.textContent = 'Not connected';
            airaConnectForm.style.display = 'block';
            airaConnectedUI.style.display = 'none';
            airaDiscoveryResults.style.display = 'none';
            airaAgentTools.style.display = 'none';
        }
    }

    // Display discovered agents
    function displayAgents(agents) {
        airaAgentsList.innerHTML = '';

        if (agents.length === 0) {
            airaAgentsList.innerHTML = '<p>No agents found</p>';
            return;
        }

        for (const agent of agents) {
            const agentItem = document.createElement('div');
            agentItem.className = 'agent-item';

            agentItem.innerHTML = `
                <h4>${agent.name}</h4>
                <p>${agent.description || 'No description'}</p>
                <button class="action discover-tools-btn" data-url="${agent.url}">Discover Tools</button>
            `;

            airaAgentsList.appendChild(agentItem);
        }

        // Add event listeners for discover tools buttons
        document.querySelectorAll('.discover-tools-btn').forEach(button => {
            button.addEventListener('click', async () => {
                const agentUrl = button.dataset.url;

                try {
                    button.disabled = true;
                    button.textContent = 'Discovering...';

                    const response = await fetch(`/api/aira/discover/tools?agent_url=${encodeURIComponent(agentUrl)}`);

                    const result = await response.json();

                    if (response.ok) {
                        displayTools(result.tools, agentUrl, result.agent_name);
                        airaAgentTools.style.display = 'block';
                    } else {
                        alert(`Error discovering tools: ${result.error}`);
                    }
                } catch (error) {
                    alert(`Error: ${error.message}`);
                } finally {
                    button.disabled = false;
                    button.textContent = 'Discover Tools';
                }
            });
        });
    }

    // Display agent tools
    function displayTools(tools, agentUrl, agentName) {
        airaToolsList.innerHTML = '';

        if (tools.length === 0) {
            airaToolsList.innerHTML = `<p>No tools found for ${agentName}</p>`;
            return;
        }

        airaToolsList.innerHTML = `<h4>Tools from ${agentName}</h4>`;

        for (const tool of tools) {
            const toolItem = document.createElement('div');
            toolItem.className = 'tool-item';

            // Create parameters display
            let paramsHtml = '';
            if (tool.parameters && Object.keys(tool.parameters).length > 0) {
                paramsHtml = '<div class="tool-params">';
                for (const [key, value] of Object.entries(tool.parameters)) {
                    paramsHtml += `<div class="param-item">
                        <label>${key}:</label>
                        <input type="text" class="param-input" data-param="${key}">
                    </div>`;
                }
                paramsHtml += '</div>';
            }

            toolItem.innerHTML = `
                <h5>${tool.name}</h5>
                <p>${tool.description || 'No description'}</p>
                ${paramsHtml}
                <button class="action invoke-tool-btn" data-agent-url="${agentUrl}" data-tool-name="${tool.name}">Invoke Tool</button>
            `;

            airaToolsList.appendChild(toolItem);
        }

        // Add event listeners for invoke tool buttons
        document.querySelectorAll('.invoke-tool-btn').forEach(button => {
            button.addEventListener('click', async () => {
                const agentUrl = button.dataset.agentUrl;
                const toolName = button.dataset.toolName;

                // Get parameters
                const paramInputs = button.parentElement.querySelectorAll('.param-input');
                const parameters = {};

                paramInputs.forEach(input => {
                    parameters[input.dataset.param] = input.value.trim();
                });

                try {
                    button.disabled = true;
                    button.textContent = 'Invoking...';

                    const response = await fetch('/api/aira/invoke', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            agent_url: agentUrl,
                            tool_name: toolName,
                            parameters: parameters
                        })
                    });

                    const result = await response.json();

                    if (response.ok) {
                        // Add the result to the chat
                        const resultText = typeof result.result === 'object'
                            ? JSON.stringify(result.result, null, 2)
                            : result.result;

                        addMessageToChat('assistant', `Tool result from ${toolName}:\n\n${resultText}`);
                    } else {
                        alert(`Error invoking tool: ${result.error}`);
                    }
                } catch (error) {
                    alert(`Error: ${error.message}`);
                } finally {
                    button.disabled = false;
                    button.textContent = 'Invoke Tool';
                }
            });
        });
    }

        // Identity dropdown change handler
        identitySelect.addEventListener('change', async () => {
            const selectedId = identitySelect.value;
            if (selectedId) {
                await switchIdentity(selectedId);
            }
        });

        // Button handlers
        recallButton.addEventListener('click', () => {
            memoriesDiv.innerHTML = '<div class="loading">Recalling memories...</div>';
            updateMemories();
        });

        getThreadsButton.addEventListener('click', () => {
            narrativeThreadsDiv.innerHTML = '<div class="loading">Updating threads...</div>';
            updateNarrativeThreads();
        });

        refreshIdentitiesButton.addEventListener('click', () => {
            identitiesDiv.innerHTML = '<div class="loading">Refreshing identities...</div>';
            updateIdentities();
        });

        // Initial data load
        updateSystemStatus();
        updateMemories();
        updateNarrativeThreads();
        updateIdentities();



        // Add a welcome message
        addMessageToChat('assistant', 'Welcome to Cognisphere ADK! How can I help you today?');

        // Refresh status every minute
        setInterval(updateSystemStatus, 60000);
    });
