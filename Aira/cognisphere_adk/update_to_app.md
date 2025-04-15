"""
Changes to add to app.py to enable AIRA integration.
Add these imports at the beginning of the file:
"""

# Add AIRA imports
from web.aira_routes import register_aira_blueprint

"""
Then add this line in the register_blueprints section:
"""

# Register the AIRA blueprint
register_aira_blueprint(app)

"""
Then add this section after initializing the orchestrator agent:
"""

# Save reference to orchestrator agent for AIRA integration
app.orchestrator_agent = orchestrator_agent

"""
Add this to the UI in the template section to enable AIRA functionality:
"""

# HTML to add to the "info-panel" div in the template
AIRA_UI_HTML = """
<div class="section">
    <h2>AIRA Network</h2>
    <div class="status">
        <div class="status-indicator" id="aira-status-indicator"></div>
        <span id="aira-status-text">Not connected</span>
    </div>
    <div id="aira-connect-form">
        <div class="form-group">
            <label for="aira-hub-url">AIRA Hub URL:</label>
            <input type="text" id="aira-hub-url" placeholder="http://localhost:8000" value="http://localhost:8000">
        </div>
        <div class="form-group">
            <label for="aira-agent-url">Agent URL (this server):</label>
            <input type="text" id="aira-agent-url" placeholder="http://localhost:5000" value="http://localhost:5000">
        </div>
        <button class="action" id="aira-connect-btn">Connect to AIRA Hub</button>
    </div>
    <div id="aira-connected-ui" style="display: none;">
        <button class="action" id="aira-disconnect-btn">Disconnect</button>
        <button class="action" id="aira-discover-btn">Discover Agents</button>
    </div>
    
    <div id="aira-discovery-results" style="display: none;">
        <h3>Discovered Agents</h3>
        <div id="aira-agents-list"></div>
    </div>
    
    <div id="aira-agent-tools" style="display: none;">
        <h3>Agent Tools</h3>
        <div id="aira-tools-list"></div>
    </div>
</div>

"""

# JavaScript to add at the end of the template
AIRA_UI_JS = """
// AIRA Network functionality
document.addEventListener('DOMContentLoaded', () => {
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
            
            const result = await response.json();
            
            if (response.ok) {
                updateAiraStatus(true, hubUrl);
                addMessageToChat('assistant', `Connected to AIRA hub at ${hubUrl}`);
            } else {
                alert(`Error connecting to AIRA hub: ${result.error}`);
                updateAiraStatus(false);
            }
        } catch (error) {
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
});
"""

# Add AIRA HTML to template
index_html = index_html.replace(
    '<div class="info-panel">',
    '<div class="info-panel">' + AIRA_UI_HTML
)

# Add AIRA JavaScript to template
index_html = index_html.replace('</script>', AIRA_UI_JS + '\n</script>')
