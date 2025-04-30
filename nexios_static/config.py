from pathlib import Path
from typing import Dict, List, Optional, Union


class StaticFilesConfig:
    """Configuration for static files handler."""
    
    def __init__(
        self,
        directory: Union[str, Path],
        html: bool = True,
        check_dir: bool = True,
        follow_symlinks: bool = False,
        allow_directory_listing: bool = False,
        directory_listing_auth: Optional[Dict[str, str]] = None,
        index_files: Optional[List[str]] = None,
        chunk_size: int = 64 * 1024,  # 64KB chunks
        enable_compression: bool = False,
        compression_min_size: int = 1024,  # 1KB minimum
        compression_types: Optional[List[str]] = None,
        cache_control: Optional[str] = None,
        cache_max_age: int = 3600,  # 1 hour
        allowed_methods: Optional[List[str]] = None,
        spa_mode: bool = False,
    ) -> None:
        # Convert directory to Path
        self.directory = Path(str(directory))
        
        # Directory options
        self.html = html
        self.check_dir = check_dir
        self.follow_symlinks = follow_symlinks
        self.allow_directory_listing = allow_directory_listing
        self.directory_listing_auth = directory_listing_auth
        self.index_files = index_files or ["index.html"]
        self.chunk_size = chunk_size
        
        # Compression options
        self.enable_compression = enable_compression
        self.compression_min_size = compression_min_size
        self.compression_types = compression_types or [
            "text/",
            "application/javascript",
            "application/json",
            "application/xml",
            "application/wasm",
        ]
        
        # Cache options
        self.cache_control = cache_control
        self.cache_max_age = cache_max_age
        
        # Security options
        self.allowed_methods = allowed_methods or ["GET", "HEAD"]
        
        # SPA mode
        self.spa_mode = spa_mode

        # Additional checks
        if not self.allowed_methods:
            raise ValueError("allowed_methods cannot be empty")
        
        if self.cache_max_age < 0:
            raise ValueError("cache_max_age must be non-negative")
        
        if self.compression_min_size < 0:
            raise ValueError("compression_min_size must be non-negative")
        
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive") 