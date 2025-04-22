🔧 MCP Server Setup: The Big Picture

MCP is a protocol for dynamically connecting to and using computational services
Servers can be local tools, specialized computation engines, or external services
Designed to make it easy to discover, connect to, and use different computational resources

📦 Server Environment Setup

Uses a shared environment managed by MCPSharedEnvironment
Handles installation of Node.js packages for MCP servers
Ensures packages are installed in a centralized, reusable location
Works across different platforms (Windows, macOS, Linux)

🚀 How to Add an MCP Server

Configuration Methods:

Through the UI (in index.html)
Programmatically using MCPServerManager


Required Information:

Server Name (optional)
Command to launch (required)
Arguments
Optional environment variables
Optional package to install


Example UI Addition:
Server Name: filesystem
Command: npx
Arguments: -y,@modelcontextprotocol/server-filesystem

Programmatic Addition:
pythonserver_manager.add_server(
    name="my_server",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem"],
    env={"API_KEY": "your_key"}
)


🔌 Server Connection Process

Server Discovery

Scans for installed MCP server packages
Checks global and local npm installations
Creates a list of available servers


Connection Steps:

Validate server configuration
Create an isolated environment
Optional: Install specific packages
Launch server process
Establish communication channel



🛠 Invoking MCP Tools

Discovery

List available tools on a server

python# Discover tools for a specific server
tools = mcp_manager.list_tools(server_id)

Tool Execution
python# Call a specific tool
result = mcp_manager.call_tool(
    server_id="filesystem",
    tool_name="list_files",
    arguments={
        "path": "/home/user/documents"
    }
)


🌐 Advanced Features

Supports different server types (stdio, HTTP, WebSocket)
Dynamic tool discovery
Secure, isolated environments
Cross-platform compatibility

⚠️ Key Limitations

Requires Node.js and npm
Server packages must be MCP-compatible
Some setup complexity for complex servers

🔍 Example Workflow

Install a server package
bashnpm install -g @modelcontextprotocol/server-filesystem

Add to Cognisphere
python# In Python
server_manager.add_server(
    name="my_files",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem"]
)

Use the tool
python# List files in a directory
result = mcp_manager.call_tool(
    server_id="my_files", 
    tool_name="list_files",
    arguments={"path": "/home/user/documents"}
)
