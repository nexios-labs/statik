import os
import mimetypes
from pathlib import Path
from typing import Optional, Union
from email.utils import formatdate

from .base import StreamingResponse


class FileResponse(StreamingResponse):
    """File response class for nexios_static."""

    def __init__(
        self,
        path: Union[str, Path],
        filename: Optional[str] = None,
        stat_result: Optional[os.stat_result] = None,
        method: Optional[str] = None,
        chunk_size: Optional[int] = None,
    ) -> None:
        self.path = Path(path)
        self.filename = filename or self.path.name
        self.stat_result = stat_result or self.path.stat()
        self.method = method
        self.chunk_size = chunk_size or 64 * 1024  # 64KB chunks

        # Initialize mimetypes
        mimetypes.init()
        mimetypes.add_type("application/javascript", ".js")
        mimetypes.add_type("application/wasm", ".wasm")

        # Set content type
        content_type, encoding = mimetypes.guess_type(str(self.path))
        if content_type is None:
            content_type = "application/octet-stream"

        # Add charset for text files
        if content_type.startswith(("text/", "application/json", "application/javascript", "application/xml")):
            content_type += "; charset=utf-8"

        # Calculate ETag
        mtime = int(self.stat_result.st_mtime)
        size = self.stat_result.st_size
        etag = f'"{mtime}:{size}"'

        # Set headers
        headers = {
            "content-type": content_type,
            "content-length": str(self.stat_result.st_size),
            "last-modified": formatdate(self.stat_result.st_mtime, usegmt=True),
            "etag": etag,
            "cache-control": "public, max-age=3600",
        }

        # Add content disposition if filename is provided
        if self.filename:
            headers["content-disposition"] = f"inline; filename={self.filename}"

        # Initialize streaming response
        super().__init__(
            content=self.file_iterator(),
            status_code=200,
            headers=headers,
            media_type=content_type,
            chunk_size=self.chunk_size,
        )

    async def file_iterator(self):
        """Yield file contents in chunks."""
        if self.method == "HEAD":
            return

        with open(self.path, "rb") as file:
            while True:
                chunk = file.read(self.chunk_size)
                if not chunk:
                    break
                yield chunk 