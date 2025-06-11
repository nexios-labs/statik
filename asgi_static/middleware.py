import base64
import gzip
import zlib
from typing import Any, Dict, List, Optional, Tuple, Union, Callable, cast
from .types import ASGIApp, Message, Receive, Scope, Send
from .responses import Response


class SecurityMiddleware:
    """Security middleware for static files."""
    
    def __init__(
        self,
        app: ASGIApp,
        allowed_methods: Optional[List[str]] = None,
        auth_paths: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> None:
        self.app = app
        self.allowed_methods = allowed_methods or ["GET", "HEAD"]
        self.auth_paths = auth_paths or {}

    def validate_auth(self, path: str, auth_header: Optional[str]) -> bool:
        """Validate Basic auth credentials."""
        if not self.auth_paths:
            return True

        # Find matching auth path
        auth_creds = None
        for auth_path, creds in self.auth_paths.items():
            if path.startswith(auth_path):
                auth_creds = creds
                break

        if not auth_creds:
            return True

        if not auth_header or not auth_header.startswith("Basic "):
            return False

        try:
            decoded = base64.b64decode(auth_header[6:]).decode()
            username, password = decoded.split(":", 1)
            return username in auth_creds and auth_creds[username] == password
        except (ValueError, UnicodeDecodeError):
            return False
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle ASGI request."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Check for path traversal
        path = scope["path"]
        if ".." in path or "//" in path or "\\" in path:
            response = Response(
                content="Path traversal not allowed",
                status_code=400,
                media_type="text/plain",
            )
            await response(scope, receive, send)
            return
        
        # Method check
        method = scope["method"].upper()
        if method not in self.allowed_methods:
            response = Response(
                content=f"Method {method} not allowed",
                status_code=405,
                headers={"Allow": ", ".join(self.allowed_methods)},
                media_type="text/plain",
            )
            await response(scope, receive, send)
            return
        
        # Auth check
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()
        if not self.validate_auth(path, auth_header):
                    response = Response(
                        content="Authentication required",
                        status_code=401,
                headers={"WWW-Authenticate": "Basic realm=\"Access to directory listing\""},
                        media_type="text/plain",
                    )
                    await response(scope, receive, send)
                    return
        
        await self.app(scope, receive, send)


class CacheMiddleware:
    """Cache control middleware."""
    
    def __init__(
        self,
        app: ASGIApp,
        cache_control: str = "public, max-age=3600",
        max_age: int = 3600,
    ) -> None:
        self.app = app
        self.cache_control = cache_control
        self.max_age = max_age
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle ASGI request."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Get request headers
        headers = dict(scope.get("headers", []))
        if_none_match = headers.get(b"if-none-match", b"").decode()
        if_modified_since = headers.get(b"if-modified-since", b"").decode()

        # Buffer response to check ETag
        response_started = False
        response_headers = {}
        response_status = 200
        response_body = []

        async def buffer_send(message: Message) -> None:
            nonlocal response_started, response_headers, response_status

            if message["type"] == "http.response.start":
                response_started = True
                response_headers = dict(message.get("headers", []))
                response_status = message.get("status", 200)
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if chunk:
                    response_body.append(chunk)

        # Get response
        await self.app(scope, receive, buffer_send)

        # Check for conditional request
        etag = None
        last_modified = None
        for k, v in response_headers.items():
            if k.lower() == b"etag":
                etag = v.decode()
            elif k.lower() == b"last-modified":
                last_modified = v.decode()

        if (etag and if_none_match and etag == if_none_match) or \
           (last_modified and if_modified_since and last_modified == if_modified_since):
            # Return 304 Not Modified
            headers_list = [
                (k, v) for k, v in response_headers.items()
                if k.lower() in [b"etag", b"last-modified", b"cache-control"]
            ]
            if not any(k.lower() == b"cache-control" for k, _ in headers_list):
                headers_list.append((b"cache-control", self.cache_control.encode()))

            await send({
                "type": "http.response.start",
                "status": 304,
                "headers": headers_list,
            })
            await send({
                "type": "http.response.body",
                "body": b"",
                "more_body": False,
            })
            return

        # Add cache headers
        headers_list = list(response_headers.items())
        if not any(k.lower() == b"cache-control" for k, _ in headers_list):
            headers_list.append((b"cache-control", self.cache_control.encode()))

        # Send response
        await send({
            "type": "http.response.start",
            "status": response_status,
            "headers": headers_list,
        })
        await send({
            "type": "http.response.body",
            "body": b"".join(response_body),
            "more_body": False,
        })


class CompressionMiddleware:
    """Compression middleware."""
    
    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 500,
        compression_types: Optional[List[str]] = None,
    ) -> None:
        self.app = app
        self.minimum_size = minimum_size
        self.compression_types = compression_types or ["text/", "application/json", "application/javascript"]

    def should_compress(self, headers: Dict[bytes, bytes], body_length: int) -> bool:
        """Check if response should be compressed."""
        if body_length < self.minimum_size:
            return False

        content_type = headers.get(b"content-type", b"").decode().lower().split(";")[0]
        if not content_type:
            return False
            
        return any(t.lower() in content_type for t in self.compression_types)
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle ASGI request."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Check accept-encoding header
        headers = dict(scope.get("headers", []))
        accept_encoding = headers.get(b"accept-encoding", b"").decode().lower()
        
        # If no compression supported, pass through
        if not ("gzip" in accept_encoding or "deflate" in accept_encoding):
            await self.app(scope, receive, send)
            return
        
        # Buffer response to check size and type
        response_started = False
        response_chunks = []
        response_headers = {}
        response_status = 200

        async def buffer_send(message: Message) -> None:
            nonlocal response_started, response_headers, response_status
            
            if message["type"] == "http.response.start":
                response_started = True
                response_headers = dict(message.get("headers", []))
                response_status = message.get("status", 200)
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if chunk:
                    response_chunks.append(chunk)

        # Get full response
        await self.app(scope, receive, buffer_send)

        # Check if we should compress
        body = b"".join(response_chunks)
        if not self.should_compress(response_headers, len(body)):
            # Send uncompressed
            await send({
                "type": "http.response.start",
                "status": response_status,
                "headers": list(response_headers.items()),
            })
            await send({
                "type": "http.response.body",
                "body": body,
                "more_body": False,
            })
            return
                
        # Compress body
        try:
            if "gzip" in accept_encoding:
                compressed = gzip.compress(body)
                encoding = "gzip"
            else:
                compressed = zlib.compress(body)
                encoding = "deflate"

            # Update headers
            headers_list = [
                (k, v) for k, v in response_headers.items()
                if k.lower() not in [b"content-length", b"content-encoding", b"vary"]
            ]
            headers_list.extend([
                (b"content-encoding", encoding.encode()),
                (b"content-length", str(len(compressed)).encode()),
                (b"vary", b"accept-encoding"),
            ])

            await send({
                "type": "http.response.start",
                "status": response_status,
                "headers": headers_list,
            })
            await send({
                "type": "http.response.body",
                "body": compressed,
                "more_body": False,
            })
        except Exception:
            # If compression fails, send uncompressed
            await send({
                "type": "http.response.start",
                "status": response_status,
                "headers": list(response_headers.items()),
            })
            await send({
                "type": "http.response.body",
                "body": body,
                "more_body": False,
            })