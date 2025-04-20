# app_globals.py
"""
Global objects shared between modules to avoid circular imports.
"""

# Initialize globals as None, will be set by app.py
mcp_manager = None
function_tools = []
mcp_tools = []
run_async_in_event_loop = None