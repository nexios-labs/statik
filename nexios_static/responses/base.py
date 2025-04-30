from typing import Any, Dict, List, Optional, Tuple, Union

from ..types import Headers, Scope, Receive, Send


class MutableHeaders:
    """Mutable headers container."""
    
    def __init__(self, raw: Optional[List[Tuple[bytes, bytes]]] = None) -> None:
        self._list = raw or []
    
    def __setitem__(self, key: str, value: str) -> None:
        """Set header value."""
        key_lower = key.lower()
        found = False
        for i, (k, v) in enumerate(self._list):
            if k.decode("latin1").lower() == key_lower:
                self._list[i] = (key.encode("latin1"), str(value).encode("latin1"))
                found = True
                break
        if not found:
            self._list.append((key.encode("latin1"), str(value).encode("latin1")))
    
    def __getitem__(self, key: str) -> str:
        """Get header value."""
        key_lower = key.lower()
        for k, v in self._list:
            if k.decode("latin1").lower() == key_lower:
                return v.decode("latin1")
        raise KeyError(key)
    
    def __delitem__(self, key: str) -> None:
        """Delete header."""
        key_lower = key.lower()
        found = False
        for i, (k, v) in enumerate(self._list):
            if k.decode("latin1").lower() == key_lower:
                del self._list[i]
                found = True
                break
        if not found:
            raise KeyError(key)
    
    def __contains__(self, key: str) -> bool:
        """Check if header exists."""
        key_lower = key.lower()
        for k, v in self._list:
            if k.decode("latin1").lower() == key_lower:
                return True
        return False
    
    def __iter__(self):
        """Iterate over headers."""
        for k, v in self._list:
            yield k.decode("latin1"), v.decode("latin1")
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get header value with default."""
        try:
            return self[key]
        except KeyError:
            return default
    
    def update(self, other: Dict[str, str]) -> None:
        """Update headers from dict."""
        for key, value in other.items():
            if value is not None:
                self[key] = value
    
    @property
    def raw(self) -> List[Tuple[bytes, bytes]]:
        """Get raw headers list."""
        return self._list


class Response:
    """Base class for all responses."""
    
    media_type = None
    charset = "utf-8"
    
    def __init__(
        self,
        content: Union[str, bytes] = b"",
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        media_type: Optional[str] = None,
    ) -> None:
        self.status_code = status_code
        self.body = self.render(content)
        self.headers = MutableHeaders()
        
        if headers:
            self.headers.update(headers)
        
        if media_type is not None:
            self.media_type = media_type
        
        self.set_content_type()
        self.set_content_length()
    
    def render(self, content: Union[str, bytes]) -> bytes:
        """Convert content to bytes."""
        if content is None:
            return b""
        if isinstance(content, bytes):
            return content
        if isinstance(content, str):
            return content.encode(self.charset)
        return str(content).encode(self.charset)
    
    def set_content_length(self) -> None:
        """Set Content-Length header."""
        if "content-length" not in self.headers:
            self.headers["content-length"] = str(len(self.body))
    
    def set_content_type(self) -> None:
        """Set Content-Type header."""
        if self.media_type is not None and "content-type" not in self.headers:
            content_type = self.media_type
            if "charset=" not in content_type and content_type.startswith(("text/", "application/json", "application/javascript", "application/xml")):
                content_type = f"{content_type}; charset={self.charset}"
            self.headers["content-type"] = content_type
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Send response."""
        await send({
            "type": "http.response.start",
            "status": self.status_code,
            "headers": self.headers.raw,
        })
        
        if scope["method"] != "HEAD":
            await send({
                "type": "http.response.body",
                "body": self.body,
                "more_body": False,
            })
        else:
            await send({
                "type": "http.response.body",
                "body": b"",
                "more_body": False,
            })


class StreamingResponse(Response):
    """Response that streams content."""
    
    def __init__(
        self,
        content: Any,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        media_type: Optional[str] = None,
        chunk_size: int = 64 * 1024,
    ) -> None:
        self.content = content
        self.status_code = status_code
        self.headers = MutableHeaders()
        self.chunk_size = chunk_size
        
        if headers:
            self.headers.update(headers)
        
        if media_type is not None:
            self.media_type = media_type
        
        self.set_content_type()
    
    async def stream_response(self, send: Send, method: str) -> None:
        """Stream response content."""
        if method == "HEAD":
            await send({
                "type": "http.response.body",
                "body": b"",
                "more_body": False,
            })
            return

        if hasattr(self.content, "__aiter__"):
            async for chunk in self.content:
                chunk = self.render(chunk)
                await send({
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True,
                })
        else:
            for chunk in self.content:
                chunk = self.render(chunk)
                await send({
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True,
                })
        
        await send({
            "type": "http.response.body",
            "body": b"",
            "more_body": False,
        })
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Send streaming response."""
        await send({
            "type": "http.response.start",
            "status": self.status_code,
            "headers": self.headers.raw,
        })
        
        await self.stream_response(send, scope["method"])


class HTMLResponse(Response):
    """HTML response."""
    media_type = "text/html"


class JSONResponse(Response):
    """JSON response."""
    media_type = "application/json"
    
    def render(self, content: Any) -> bytes:
        """Convert content to JSON bytes."""
        import json
        return json.dumps(content).encode("utf-8")


class PlainTextResponse(Response):
    """Plain text response."""
    media_type = "text/plain"


class RedirectResponse(Response):
    """Redirect response."""
    
    def __init__(
        self,
        url: str,
        status_code: int = 307,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(
            content=b"",
            status_code=status_code,
            headers=headers,
        )
        self.headers["location"] = url 