import os
import pytest
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Tuple, Union, Any, Awaitable, Callable, cast

from nexios.testing import Client
from nexios_static import StaticFiles, StaticFilesConfig
from nexios import NexiosApp
from nexios.types import Message
from nexios_static.types import Scope, Receive, Send


class StaticFilesWrapper(NexiosApp):
    """Wrapper to make StaticFiles work with Nexios test client."""
    
    def __init__(self, static_app: StaticFiles) -> None:
        super().__init__()
        self.static_app = static_app
    
    async def __call__(
        self,
        scope: Dict[str, Any],
        receive: Callable[[], Awaitable[Message]],
        send: Callable[[Message], Awaitable[None]]
    ) -> None:
        """Handle ASGI request."""
        if scope["type"] == "lifespan":
            await super().__call__(scope, receive, send)
        else:
            # Cast to appropriate types for StaticFiles
            static_scope = cast(Scope, scope)
            static_receive = cast(Receive, receive)
            static_send = cast(Send, send)
            await self.static_app(static_scope, static_receive, static_send)


@pytest.fixture
def temp_static_dir(tmp_path):
    """Create a temporary directory with test files."""
    # Create test files
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    
    # Create test.txt
    test_file = static_dir / "test.txt"
    test_file.write_text("Hello, World!")
    
    # Create index.html
    index_file = static_dir / "index.html"
    index_file.write_text("<html><body>Index Page</body></html>")
    
    # Create subdirectory with files
    sub_dir = static_dir / "subdir"
    sub_dir.mkdir()
    sub_file = sub_dir / "sub.txt"
    sub_file.write_text("Sub file content")
    
    return static_dir


@pytest.fixture
async def client(temp_static_dir):
    """Create test client."""
    app = StaticFiles(directory=temp_static_dir)
    app = StaticFilesWrapper(app)
    async with Client(app) as client:
        yield client


async def test_serve_file(client, temp_static_dir):
    """Test serving a simple file."""
    response = await client.get("/test.txt")
    assert response.status_code == 200
    assert response.text == "Hello, World!"
    assert "text/plain" in response.headers["content-type"]


async def test_serve_index(client, temp_static_dir):
    """Test serving index.html."""
    response = await client.get("/")
    assert response.status_code == 200
    assert response.text == "<html><body>Index Page</body></html>"
    assert "text/html" in response.headers["content-type"]


async def test_protected_directory(client, temp_static_dir):
    """Test protected directory with authentication."""
    config = StaticFilesConfig(
        directory=temp_static_dir,
        allow_directory_listing=True,
        directory_listing_auth={"admin": "secret"}
    )
    app = StaticFiles(config=config)
    app = StaticFilesWrapper(app)
    async with Client(app) as client:
        # Test with correct auth
        import base64
        auth = base64.b64encode(b"admin:secret").decode()
        response = await client.get(
            "/",
            headers={"authorization": f"Basic {auth}"}
        )
        assert response.status_code == 200


async def test_compression(client, temp_static_dir):
    """Test response compression."""
    config = StaticFilesConfig(
        directory=temp_static_dir,
        enable_compression=True,
        compression_min_size=1  # Set small size for testing
    )
    app = StaticFiles(config=config)
    app = StaticFilesWrapper(app)
    async with Client(app) as client:
        # Test with gzip
        response = await client.get(
            "/test.txt",
            headers={"accept-encoding": "gzip"}
        )
        assert response.status_code == 200
        assert response.headers.get("content-encoding") == "gzip"
        
        # Test with deflate
        response = await client.get(
            "/test.txt",
            headers={"accept-encoding": "deflate"}
        )
        assert response.status_code == 200
        assert response.headers.get("content-encoding") == "deflate"


async def test_caching(client, temp_static_dir):
    """Test caching headers."""
    config = StaticFilesConfig(
        directory=temp_static_dir,
        cache_max_age=3600
    )
    app = StaticFiles(config=config)
    app = StaticFilesWrapper(app)
    async with Client(app) as client:
        response = await client.get("/test.txt")
        assert response.status_code == 200
        assert "public, max-age=3600" in response.headers["cache-control"]
        assert "etag" in response.headers
        
        # Test conditional request
        etag = response.headers["etag"]
        response = await client.get(
            "/test.txt",
            headers={"if-none-match": etag}
        )
        assert response.status_code == 304


async def test_content_types(temp_static_dir):
    """Test correct content type detection."""
    # Create test files
    files = {
        "text.txt": "Hello, World!",
        "script.js": "console.log('Hello');",
        "style.css": "body { color: blue; }",
        "data.json": '{"hello": "world"}',
        "index.html": "<html><body>Welcome</body></html>",
    }
    
    for name, content in files.items():
        (temp_static_dir / name).write_text(content)
    
    app = StaticFiles(directory=temp_static_dir)
    app = StaticFilesWrapper(app)
    
    async with Client(app=app, base_url="http://testserver") as client:
        type_map = {
            "/text.txt": "text/plain",
            "/script.js": "application/javascript",
            "/style.css": "text/css",
            "/data.json": "application/json",
            "/index.html": "text/html",
        }
        
        for path, expected_type in type_map.items():
            response = await client.get(path)
            assert response.status_code == 200
            assert expected_type in response.headers["content-type"]


async def test_streaming_performance(temp_static_dir):
    """Test streaming performance with different chunk sizes."""
    # Create a large file
    large_file = temp_static_dir / "large.bin"
    large_file.write_bytes(os.urandom(1024 * 1024))  # 1MB file
    
    chunk_sizes = [8192, 32768, 65536]  # Test different chunk sizes
    
    for chunk_size in chunk_sizes:
        config = StaticFilesConfig(
            directory=temp_static_dir,
            chunk_size=chunk_size
        )
        
        static_app = StaticFiles(config=config)
        app = StaticFilesWrapper(static_app)
        
        async with Client(app=app, base_url="http://testserver") as test_client:
            response = await test_client.get("/large.bin")
            assert response.status_code == 200
            assert len(response.content) == 1024 * 1024  # Full file received 