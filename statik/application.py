import os
import stat
from pathlib import Path
from typing import Optional, Union, Dict, List, Tuple, cast

from .config import StaticFilesConfig
from .responses import FileResponse, DirectoryResponse, Response
from .middleware import SecurityMiddleware, CacheMiddleware, CompressionMiddleware
from .types import ASGIApp, Receive, Scope, Send


class StaticFiles:
    """
    ASGI application for serving static files with advanced features:
    - Directory listing
    - Authentication
    - Caching
    - Compression
    - Security controls
    - SPA mode support
    """
    
    def __init__(
        self,
        directory: Optional[Union[str, Path]] = None,
        config: Optional[StaticFilesConfig] = None,
    ) -> None:
        if config is None and directory is None:
            raise ValueError("Either directory or config must be provided")
        
        self.config = config or StaticFilesConfig(directory=cast(Union[str, Path], directory))
        self.directory = Path(str(self.config.directory))
        
        # Verify directory exists
        if self.config.check_dir and not self.directory.exists():
            raise ValueError(f"Directory '{self.directory}' does not exist")
        
        # Create middleware stack
        self.app = self.handle_request
        
        if self.config.enable_compression:
            self.app = CompressionMiddleware(
                app=self.app,
                minimum_size=self.config.compression_min_size,
                compression_types=self.config.compression_types,
            )
        
        if self.config.cache_control or self.config.cache_max_age > 0:
            self.app = CacheMiddleware(
                app=self.app,
                cache_control=self.config.cache_control or "public, max-age=3600",
                max_age=self.config.cache_max_age,
            )
        
        self.app = SecurityMiddleware(
            app=self.app,
            allowed_methods=self.config.allowed_methods,
            auth_paths={"/": self.config.directory_listing_auth} if self.config.directory_listing_auth else None,
        )
    
    def get_file_path(self, request_path: str) -> Path:
        """Get file path from request path."""
        if not request_path or request_path == "/":
            return self.directory
        
        # Remove leading slash and normalize
        path = request_path.lstrip("/")
        path = os.path.normpath(path)
        
        # Check for path traversal
        if path.startswith("..") or "//" in path or "\\" in path:
            raise ValueError("Path traversal attempt detected")
        
        return self.directory / path
    
    def is_file_allowed(self, path: Path) -> bool:
        """Check if file access is allowed."""
        try:
            path.relative_to(self.directory)
            return True
        except ValueError:
            return False
    
    async def serve_file(self, path: Path, method: str) -> FileResponse:
        """Serve a file."""
        if not path.exists():
            if self.config.spa_mode:
                # Check if the path is an asset
                is_asset = any(path.name.endswith(ext) for ext in [".js", ".css", ".json", ".ico", ".png", ".jpg", ".gif", ".wasm"])
                if not is_asset:
                    # Try to serve index.html for non-asset paths
                    index_path = self.directory / "index.html"
                    if index_path.exists() and index_path.is_file():
                        return FileResponse(
                            path=index_path,
                            method=method,
                            chunk_size=self.config.chunk_size,
                        )
                    raise FileNotFoundError("index.html not found")
                raise FileNotFoundError("Asset not found")
            raise FileNotFoundError("File not found")
        
        if not path.is_file():
            raise IsADirectoryError("Not a file")
        
        if not self.is_file_allowed(path):
            raise PermissionError("Access denied")
        
        return FileResponse(
            path=path,
            method=method,
            chunk_size=self.config.chunk_size,
        )
    
    async def serve_directory(self, path: Path, base_url: str) -> Union[FileResponse, DirectoryResponse]:
        """Serve a directory listing."""
        if not path.is_dir():
            raise NotADirectoryError("Not a directory")
        
        if not self.is_file_allowed(path):
            raise PermissionError("Access denied")
        
        # Check for index file
        if self.config.spa_mode:
            index_path = path / "index.html"
            if index_path.is_file():
                return await self.serve_file(index_path, "GET")
        else:
            for index_file in self.config.index_files:
                index_path = path / index_file
                if index_path.is_file():
                    return await self.serve_file(index_path, "GET")
        
        # If directory listing is not allowed, return 404
        if not self.config.allow_directory_listing:
            raise FileNotFoundError("Directory listing not allowed")
        
        # Return directory listing
        return DirectoryResponse(
            path=path,
            base_url=base_url,
            html=self.config.html,
            auth_required=bool(self.config.directory_listing_auth),
        )
    
    async def handle_request(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle ASGI request."""
        if scope["type"] != "http":
            return
        
        # Get request path
        path = scope["path"]
        method = scope["method"]
        
        try:
            # Get file path
            file_path = self.get_file_path(path)
            
            # Serve file or directory
            if file_path.is_file():
                response = await self.serve_file(file_path, method)
            else:
                response = await self.serve_directory(file_path, path)
            
            await response(scope, receive, send)
        
        except (ValueError, FileNotFoundError):
            response = Response(
                content="Not found",
                status_code=404,
                media_type="text/plain",
            )
            await response(scope, receive, send)
        
        except (PermissionError, IsADirectoryError):
            response = Response(
                content="Forbidden",
                status_code=403,
                media_type="text/plain",
            )
            await response(scope, receive, send)
        
        except Exception as e:
            response = Response(
                content=str(e),
                status_code=500,
                media_type="text/plain",
            )
            await response(scope, receive, send)
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI application interface."""
        await self.app(scope, receive, send)