# src/mcp/core.py

class MCPServer:
    def __init__(self, name: str):
        self.name = name
        self.tools = {}
        self.resources = {}

    def tool(self, name):
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator

    def resource(self, name):
        def decorator(fn):
            self.resources[name] = fn
            return fn

        return decorator

    async def start(self):
        print(
            f"MCPServer {self.name} started with {len(self.tools)} tools and {len(self.resources)} resources"
        )
