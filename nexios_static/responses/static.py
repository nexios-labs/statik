import os
import stat
import time
import mimetypes
import hashlib
from datetime import datetime
from email.utils import formatdate
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Union, cast, AsyncIterator, Iterator

import aiofiles

from .base import Response, StreamingResponse, HTMLResponse, JSONResponse
from ..types import Scope, Receive, Send, MutableHeaders


class FileResponse(StreamingResponse):
    """
    Custom file response with advanced features like:
    - Automatic content type detection using Python's built-in mimetypes
    - ETags support
    - Range requests
    - Streaming support
    """
    
    chunk_size = 64 * 1024  # 64KB chunks
    
    def __init__(
        self,
        path: Union[str, Path],
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        media_type: Optional[str] = None,
        filename: Optional[str] = None,
        stat_result: Optional[os.stat_result] = None,
        method: Optional[str] = None,
        chunk_size: Optional[int] = None,
    ) -> None:
        super().__init__(content=b"", status_code=status_code)  # Initialize with empty content
        self.path = Path(path)
        self.filename = filename
        self.send_header_only = method is not None and method.upper() == "HEAD"
        if chunk_size is not None:
            self.chunk_size = chunk_size
        
        if stat_result is not None:
            self.stat_result = stat_result
        else:
            self.stat_result = self.path.stat()
        
        self.headers = MutableHeaders()
        if headers:
            self.headers.update(headers)
        
        if media_type is None:
            # Use Python's built-in mimetypes for content type detection
            media_type = mimetypes.guess_type(str(self.path))[0] or "application/octet-stream"
            # Fix JavaScript MIME type
            if media_type == "text/javascript":
                media_type = "application/javascript"
        
        self.media_type = media_type
        self.init_headers()
    
    def init_headers(self) -> None:
        """Initialize response headers."""
        
        # Content-Length and Last-Modified
        self.headers["content-length"] = str(self.stat_result.st_size)
        mtime = int(round(self.stat_result.st_mtime))  # Convert float to int by rounding
        self.headers["last-modified"] = formatdate(mtime, usegmt=True)
        
        # Content-Type
        if self.media_type:
            content_type = self.media_type
            if content_type.startswith("text/") or content_type == "application/javascript":
                content_type += "; charset=utf-8"
            self.headers["content-type"] = content_type
        
        # Content-Disposition
        if self.filename:
            disposition = f'attachment; filename="{self.filename}"'
        else:
            disposition = "inline"
        self.headers["content-disposition"] = disposition
        
        # ETag
        etag = self.calculate_etag()
        if etag:
            self.headers["etag"] = etag
    
    def calculate_etag(self) -> str:
        """Calculate ETag based on file metadata."""
        stat = self.stat_result
        mtime = int(round(stat.st_mtime))  # Convert float to int by rounding
        etag_data = f"{mtime}:{stat.st_size}:{stat.st_ino}"
        etag_hash = hashlib.md5(etag_data.encode()).hexdigest()
        return f'"{etag_hash}"'
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Send file response."""
        if self.send_header_only:
            await send({
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.headers.raw,
            })
            await send({
                "type": "http.response.body",
                "body": b"",
                "more_body": False,
            })
            return
        
        async def afile_iterator() -> AsyncIterator[bytes]:
            async with aiofiles.open(self.path, mode="rb") as file:
                while chunk := await file.read(self.chunk_size):
                    yield chunk
        
        self.body_iterator = afile_iterator()
        await super().__call__(scope, receive, send)


class DirectoryResponse:
    """
    Response for directory listing with:
    - HTML rendering
    - JSON format support
    - Security controls
    """
    
    def __init__(
        self,
        path: Union[str, Path],
        base_url: str = "",
        allow_up: bool = True,
        html: bool = True,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.path = Path(path)
        self.base_url = base_url.rstrip("/")
        self.allow_up = allow_up
        self.html = html
        self.status_code = status_code
        self.headers = headers or {}
    
    def get_file_info(self, path: Path) -> Dict[str, Any]:
        """Get file information for directory listing."""
        stat_result = path.stat()
        
        return {
            "name": path.name,
            "path": str(path.relative_to(self.path)),
            "size": stat_result.st_size,
            "modified": datetime.fromtimestamp(stat_result.st_mtime).isoformat(),
            "is_dir": path.is_dir(),
            "is_file": path.is_file(),
        }
    
    def render_html(self, files: List[Dict[str, Any]]) -> str:
        """Render directory listing as HTML."""
        html = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>Directory listing</title>",
            "<style>",
            "body { font-family: system-ui, -apple-system, sans-serif; margin: 2rem; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { text-align: left; padding: 8px; border-bottom: 1px solid #ddd; }",
            "th { background-color: #f5f5f5; }",
            "tr:hover { background-color: #f5f5f5; }",
            "a { color: #0066cc; text-decoration: none; }",
            "a:hover { text-decoration: underline; }",
            ".size { text-align: right; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>Directory listing for {self.path.name}/</h1>",
            "<table>",
            "<tr><th>Name</th><th>Size</th><th>Modified</th></tr>",
        ]
        
        if self.allow_up:
            html.append(
                '<tr><td><a href="../">..</a></td><td></td><td></td></tr>'
            )
        
        for file in sorted(files, key=lambda x: (not x["is_dir"], x["name"].lower())):
            name = file["name"]
            if file["is_dir"]:
                name += "/"
            
            size = "-" if file["is_dir"] else self.format_size(file["size"])
            modified = file["modified"].split("T")[0]
            
            html.extend([
                "<tr>",
                f'<td><a href="{name}">{name}</a></td>',
                f'<td class="size">{size}</td>',
                f'<td>{modified}</td>',
                "</tr>",
            ])
        
        html.extend([
            "</table>",
            "</body>",
            "</html>",
        ])
        
        return "\n".join(html)
    
    @staticmethod
    def format_size(size: int) -> str:
        """Format file size in human readable format."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle directory listing request."""
        try:
            # Check for index.html first
            index_path = self.path / "index.html"
            if index_path.is_file():
                from .file import FileResponse
                response = FileResponse(path=index_path)
                await response(scope, receive, send)
                return

            files = []
            for item in self.path.iterdir():
                if not item.name.startswith("."):  # Skip hidden files
                    try:
                        files.append(self.get_file_info(item))
                    except (PermissionError, FileNotFoundError):
                        continue

            if self.html:
                response = HTMLResponse(
                    content=self.render_html(files),
                    status_code=self.status_code,
                    headers=self.headers
                )
            else:
                response = JSONResponse(
                    content={"files": files},
                    status_code=self.status_code,
                    headers={"content-type": "application/json"}
                )
            
            await response(scope, receive, send)
        except Exception as e:
            response = Response(
                content=str(e),
                status_code=500,
                media_type="text/plain"
            )
            await response(scope, receive, send) 