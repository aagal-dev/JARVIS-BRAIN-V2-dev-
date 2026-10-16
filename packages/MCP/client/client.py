from __future__ import annotations
import asyncio
from contextlib import AsyncExitStack
from typing import Any, Iterable
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ..common.config import MCPServerConfig, StdioTransport, StreamableHTTPTransport
from ..common.exceptions import *
from .result import MCPResult, _json_value, normalize
from .runtime import AsyncRuntime


class ServerClient:
    """Server-scoped view; tools are addressed without the namespace."""
    def __init__(self, client: "MCPClient", name: str): self._client, self.name = client, name
    def tools(self): return self._client.tools(self.name)
    def resources(self): return self._client.resources(self.name)
    def prompts(self): return self._client.prompts(self.name)
    def call_tool(self, name: str, arguments: dict[str, Any] | None = None): return self._client.call_tool(f"{self.name}__{name}", arguments)
    def read_resource(self, uri: str): return self._client.read_resource(uri, self.name)
    def get_prompt(self, name: str, arguments: dict[str, str] | None = None): return self._client.get_prompt(name, arguments, self.name)


class MCPClient:
    def __init__(self, servers: Iterable[MCPServerConfig], *, timeout: float = 30.0):
        self._configs = list(servers); self._timeout = timeout; self._runtime: AsyncRuntime | None = None
        self._sessions: dict[str, ClientSession] = {}; self._stack: AsyncExitStack | None = None; self._connected = False
        names = [c.name for c in self._configs]
        if len(names) != len(set(names)): raise MCPValidationError("duplicate server names")
        if timeout <= 0: raise MCPValidationError("timeout must be positive")

    def connect(self) -> "MCPClient":
        if self._connected: return self
        self._runtime = AsyncRuntime()
        try:
            self._runtime.call(self._connect(), self._timeout); self._connected = True; return self
        except Exception as exc:
            self._cleanup_failed()
            if isinstance(exc, MCPError): raise
            raise MCPConnectionError("could not connect MCP server(s)") from exc

    async def _connect(self) -> None:
        self._stack = AsyncExitStack()
        for config in self._configs:
            transport = config.transport
            if isinstance(transport, StdioTransport):
                params = StdioServerParameters(command=transport.command, args=list(transport.args), env=dict(transport.env) if transport.env else None, cwd=transport.cwd)
                streams = await self._stack.enter_async_context(stdio_client(params))
            elif isinstance(transport, StreamableHTTPTransport):
                streams = await self._stack.enter_async_context(transport.factory(timeout=config.timeout))
            else:
                streams = await self._stack.enter_async_context(transport.factory())
            session = await self._stack.enter_async_context(ClientSession(*streams, read_timeout_seconds=config.timeout))
            await asyncio.wait_for(session.initialize(), config.timeout)
            self._sessions[config.name] = session

    def _require_connected(self) -> AsyncRuntime:
        if not self._connected or not self._runtime: raise MCPLifecycleError("client is not connected; call connect() first")
        return self._runtime
    def _cleanup_failed(self) -> None:
        if self._runtime:
            try: self._runtime.call(self._close_async(), min(2, self._timeout))
            except Exception: pass
            self._runtime.close()
        self._sessions.clear(); self._stack = None; self._runtime = None
    def close(self) -> None:
        if not self._runtime: return
        try: self._runtime.call(self._close_async(), self._timeout)
        finally:
            self._connected = False; self._sessions.clear(); self._stack = None; runtime, self._runtime = self._runtime, None; runtime.close()
    async def _close_async(self) -> None:
        if self._stack: await self._stack.aclose()
    def __enter__(self): return self.connect()
    def __exit__(self, *_): self.close()
    def server(self, name: str) -> ServerClient:
        self._require_connected()
        if name not in self._sessions: raise MCPValidationError(f"unknown server: {name}")
        return ServerClient(self, name)
    def tools(self, server: str | None = None): return self._list("list_tools", "tools", server)
    def resources(self, server: str | None = None): return self._list("list_resources", "resources", server)
    def prompts(self, server: str | None = None): return self._list("list_prompts", "prompts", server)
    def _list(self, method: str, attr: str, server: str | None):
        runtime = self._require_connected()
        names = [server] if server else list(self._sessions)
        if server and server not in self._sessions: raise MCPValidationError(f"unknown server: {server}")
        async def go():
            result = {}
            for name in names:
                reply = await getattr(self._sessions[name], method)()
                result[name] = list(getattr(reply, attr, []))
            if attr == "tools":
                if server:
                    return {tool.name: self._tool_schema(tool, tool.name) for tool in result[server]}
                return {f"{name}__{tool.name}": self._tool_schema(tool, f"{name}__{tool.name}") for name, tools in result.items() for tool in tools}
            return result[server] if server else {f"{n}__{t.name}": t for n, ts in result.items() for t in ts}
        try:
            return runtime.call(go(), self._timeout)
        except MCPError:
            raise
        except Exception as exc:
            target = f" for server {server}" if server else ""
            raise MCPTransportError(f"could not list {attr}{target}") from exc
    
    @staticmethod
    def _tool_schema(tool: Any, name: str) -> dict[str, Any]:
        """Return only the information an agent needs to make a valid tool call."""
        schema = {
            "name": name,
            "description": (getattr(tool, "description", None) or "").strip(),
            "input_schema": _json_value(getattr(tool, "input_schema", {})),
        }
        output_schema = getattr(tool, "output_schema", None)
        if output_schema is not None:
            schema["output_schema"] = _json_value(output_schema)
        return schema

    def _route(self, name: str) -> tuple[str, str]:
        if "__" not in name: raise MCPValidationError("tool name must be namespaced: server__tool")
        server, tool = name.split("__", 1)
        if not server or not tool or server not in self._sessions: raise MCPValidationError(f"unknown namespaced tool: {name}")
        return server, tool
    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> MCPResult:
        if arguments is not None and not isinstance(arguments, dict): raise MCPValidationError("arguments must be a dict or None")
        runtime = self._require_connected(); server, tool = self._route(name)
        async def go(): return await self._sessions[server].call_tool(tool, arguments, read_timeout_seconds=self._timeout)
        try: return normalize(runtime.call(go(), self._timeout))
        except MCPError: raise
        except Exception as exc: raise MCPTransportError("tool request failed") from exc
    def read_resource(self, uri: str, server: str | None = None): return self._call_scoped("read_resource", uri, None, server, MCPResourceError)
    def get_prompt(self, name: str, arguments: dict[str, str] | None = None, server: str | None = None): return self._call_scoped("get_prompt", name, arguments, server, MCPPromptError)
    def _call_scoped(self, method: str, name: str, arguments: Any, server: str | None, error: type[MCPError]):
        runtime = self._require_connected()
        if server is None:
            if len(self._sessions) != 1: raise MCPValidationError(f"server is required for {method} with multiple servers")
            server = next(iter(self._sessions))
        if server not in self._sessions: raise MCPValidationError(f"unknown server: {server}")
        async def go():
            fn = getattr(self._sessions[server], method)
            return await (fn(name, arguments) if arguments is not None else fn(name))
        try: return runtime.call(go(), self._timeout)
        except MCPError: raise
        except Exception as exc: raise error(f"{method} failed") from exc
