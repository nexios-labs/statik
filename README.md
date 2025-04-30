# Statik

<div align="center">
<svg width="100" height="100" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="45" fill="#3498db" stroke="#2980b9" stroke-width="2"/>
  <path d="M30 50 L70 50 M50 30 L50 70" stroke="white" stroke-width="8" stroke-linecap="round"/>
  <text x="50" y="90" text-anchor="middle" font-family="Arial" font-size="24" fill="#2c3e50">Statik</text>
</svg>

A minimalist, high-performance static file server for ASGI applications.

[![Python Version](https://img.shields.io/pypi/pyversions/statik.svg)](https://pypi.org/project/statik/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
</div>

## Overview

Statik is a high-performance static file server designed for ASGI applications. It provides efficient file serving capabilities with minimal dependencies, making it ideal for production environments where performance and security are critical.

## Core Features

- **High Performance**: Optimized for serving static files with minimal overhead and maximum throughput
- **Minimal Dependencies**: Core functionality requires only `anyio` and `typing-extensions`
- **Security Features**: Built-in protection against path traversal and configurable authentication
- **Compression Support**: Automatic gzip and deflate compression for supported content types
- **Caching System**: ETag support and configurable cache control headers
- **Streaming Support**: Efficient large file handling with configurable chunk sizes
- **SPA Mode**: Built-in Single Page Application support
- **Directory Listings**: Optional HTML/JSON directory listings with authentication
- **Range Requests**: Support for partial content and resume downloads

## Installation

```bash
pip install statik
```

## Basic Usage

```python
from statik import StaticFiles

# Basic static file server
app = StaticFiles(directory="static")

# Run with any ASGI server
# Example with uvicorn:
# uvicorn myapp:app
```

## Configuration Guide

### Basic Configuration

```python
from statik import StaticFiles, StaticFilesConfig

# Simple static file server
app = StaticFiles(directory="static")

# Advanced configuration
config = StaticFilesConfig(
    directory="static",
    chunk_size=32 * 1024,  # 32KB chunks
    follow_symlinks=False,
    check_dir=True
)
app = StaticFiles(config=config)
```

### Security Configuration

```python
config = StaticFilesConfig(
    directory="static",
    allowed_methods=["GET", "HEAD"],
    directory_listing_auth={
        "admin": "secret"  # Basic auth for directory listing
    },
    follow_symlinks=False,
    check_dir=True
)
```

### Caching and Compression

```python
config = StaticFilesConfig(
    directory="static",
    enable_compression=True,
    compression_min_size=1024,  # 1KB minimum
    compression_types=[
        "text/",
        "application/javascript",
        "application/json",
        "application/xml"
    ],
    cache_control="public, max-age=3600",
    cache_max_age=3600
)
```

### Single Page Application (SPA) Configuration

```python
config = StaticFilesConfig(
    directory="static",
    spa_mode=True,
    index_files=["index.html"],
    cache_control="public, max-age=3600"
)
```

## Framework Integration

### FastAPI Integration

```python
from fastapi import FastAPI
from statik import StaticFiles, StaticFilesConfig

app = FastAPI()

# Basic static files
app.mount("/static", StaticFiles(directory="static"))

# Advanced configuration
config = StaticFilesConfig(
    directory="static/assets",
    enable_compression=True,
    compression_min_size=1024,
    cache_control="public, max-age=3600",
    spa_mode=False
)

# Mount multiple static directories
app.mount("/assets", StaticFiles(config=config))
app.mount("/public", StaticFiles(directory="public"))

# Protected static files with basic auth
protected_config = StaticFilesConfig(
    directory="protected",
    directory_listing_auth={
        "admin": "secret123"
    },
    allow_directory_listing=True
)
app.mount("/protected", StaticFiles(config=protected_config))

# Example route using static files
@app.get("/")
async def read_root():
    return {"message": "Static files are served at /static, /assets, and /protected"}
```

### Starlette Integration

```python
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.responses import JSONResponse
from statik import StaticFiles, StaticFilesConfig

routes = [
    # Basic static files
    Mount("/static", StaticFiles(directory="static")),
    
    # SPA configuration
    Mount("/app", StaticFiles(
        config=StaticFilesConfig(
            directory="spa",
            spa_mode=True,
            index_files=["index.html"],
            cache_control="public, max-age=3600"
        )
    )),
    
    # Media files with compression
    Mount("/media", StaticFiles(
        config=StaticFilesConfig(
            directory="media",
            enable_compression=True,
            compression_types=[
                "image/svg+xml",
                "application/json",
                "text/css",
                "application/javascript"
            ]
        )
    ))
]

app = Starlette(routes=routes)

@app.route("/")
async def homepage(request):
    return JSONResponse({
        "static_routes": [
            "/static",
            "/app",
            "/media"
        ]
    })
```

### Nexios Integration

```python
from nexios import NexiosApp
from statik import StaticFiles, StaticFilesConfig

app = NexiosApp()

# Basic static file serving
app.register(StaticFiles(directory="static"),"/static")



@app.get("/api/status")
async def status(req, res):
    return {
        "status": "running",
        "static_mounts": [
            "/",  # SPA
            "/docs",
            "/media"
        ]
    }

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Common Integration Patterns

### Serving Multiple Directories

```python
from fastapi import FastAPI
from statik import StaticFiles, StaticFilesConfig

app = FastAPI()

# Structure:
# /static
#   /css
#   /js
#   /images
# /uploads
# /public

# Serve different directories with different configurations
app.mount("/static", StaticFiles(
    config=StaticFilesConfig(
        directory="static",
        enable_compression=True,
        cache_control="public, max-age=3600"
    )
))

app.mount("/uploads", StaticFiles(
    config=StaticFilesConfig(
        directory="uploads",
        chunk_size=256 * 1024,  # Larger chunks for uploads
        enable_compression=False  # Don't compress already compressed files
    )
))

app.mount("/public", StaticFiles(directory="public"))
```

### SPA with API Backend

```python
from fastapi import FastAPI
from statik import StaticFiles, StaticFilesConfig

app = FastAPI()

# Serve SPA from /app
spa_config = StaticFilesConfig(
    directory="frontend/dist",
    spa_mode=True,
    enable_compression=True,
    cache_control="public, max-age=3600"
)
app.mount("/app", StaticFiles(config=spa_config))

# API routes
@app.get("/api/data")
async def get_data():
    return {"data": "example"}

# Serve API documentation
docs_config = StaticFilesConfig(
    directory="docs",
    allow_directory_listing=True
)
app.mount("/docs", StaticFiles(config=docs_config))
```

### Protected Media Server

```python
from fastapi import FastAPI
from statik import StaticFiles, StaticFilesConfig

app = FastAPI()

# Protected media files with authentication
media_config = StaticFilesConfig(
    directory="media",
    directory_listing_auth={
        "admin": "secure_password",
        "user": "user_password"
    },
    allow_directory_listing=True,
    chunk_size=128 * 1024,
    compression_types=[
        "image/svg+xml",
        "text/plain",
        "application/json"
    ]
)

app.mount("/media", StaticFiles(config=media_config))

# Optional: Add route to check auth status
@app.get("/media-status")
async def media_status():
    return {
        "status": "available",
        "auth_required": True
    }
```

These examples demonstrate common use cases and best practices for integrating Statik with various frameworks. Each example includes appropriate configuration for the specific use case, such as:

- Compression settings for appropriate file types
- Caching strategies
- Authentication for protected resources
- SPA mode configuration
- Large file handling
- Multiple directory mounting

Choose and adapt these examples based on your specific requirements.

## Configuration Reference

### StaticFilesConfig Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `directory` | `str\|Path` | Required | Base directory for serving files |
| `check_dir` | `bool` | `True` | Verify directory exists on startup |
| `follow_symlinks` | `bool` | `False` | Allow following symbolic links |
| `allow_directory_listing` | `bool` | `False` | Enable directory listing feature |
| `directory_listing_auth` | `dict` | `None` | Basic auth credentials for directory listing |
| `allowed_methods` | `list` | `["GET", "HEAD"]` | Allowed HTTP methods |
| `cache_control` | `str` | `None` | Cache-Control header value |
| `cache_max_age` | `int` | `3600` | Cache max age in seconds |
| `enable_compression` | `bool` | `False` | Enable compression support |
| `compression_min_size` | `int` | `1024` | Minimum file size for compression |
| `compression_types` | `list` | See below | MIME types to compress |
| `chunk_size` | `int` | `64 * 1024` | File streaming chunk size |
| `spa_mode` | `bool` | `False` | Enable SPA mode |
| `index_files` | `list` | `["index.html"]` | List of index file names |

### Default Compression Types
```python
DEFAULT_COMPRESSION_TYPES = [
    "text/",
    "application/javascript",
    "application/json",
    "application/xml",
    "application/wasm"
]
```

## Performance Optimization

### Chunk Size Configuration
- Larger chunks (128KB+): Better for high-bandwidth scenarios
- Smaller chunks (32KB): Better for memory-constrained environments
- Default (64KB): Good balance for most use cases

```python
config = StaticFilesConfig(
    directory="static",
    chunk_size=128 * 1024  # 128KB chunks
)
```

### Compression Guidelines
1. Enable compression only for text-based files
2. Set appropriate minimum file size (typically 1KB+)
3. Configure supported MIME types carefully

### Caching Strategy
1. Set appropriate cache-control headers
2. Enable ETag support for client-side caching
3. Configure cache max age based on content update frequency

### Security Best Practices
1. Keep `follow_symlinks=False` unless specifically needed
2. Implement authentication for sensitive directories
3. Use allowed_methods to restrict HTTP methods
4. Validate file paths against directory traversal

## Error Handling

The server handles various error conditions with appropriate HTTP status codes:

- 404 Not Found: File or directory not found
- 403 Forbidden: Access denied or directory traversal attempt
- 401 Unauthorized: Failed authentication
- 405 Method Not Allowed: Invalid HTTP method
- 500 Internal Server Error: Unexpected server errors

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/improvement`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/improvement`)
5. Create a Pull Request

For major changes, please open an issue first to discuss the proposed changes.

## License

This project is licensed under the MIT License. See the LICENSE file for details. 