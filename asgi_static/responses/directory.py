from typing import Union, Optional, Dict, List
import os
from pathlib import Path
import json
from datetime import datetime
from .base import Response

class DirectoryResponse(Response):
    """Directory listing response class."""

    def __init__(
        self,
        path: Union[str, Path],
        base_url: str,
        html: bool = True,
        auth_required: bool = False,
    ) -> None:
        self.path = Path(path)
        self.base_url = base_url.rstrip("/")
        self.html = html

        # Get directory contents
        entries = []
        for entry in sorted(self.path.iterdir()):
            is_dir = entry.is_dir()
            name = entry.name
            size = entry.stat().st_size if not is_dir else None
            mtime = entry.stat().st_mtime
            entries.append({
                "name": name,
                "is_dir": is_dir,
                "size": size,
                "mtime": mtime,
            })

        # Generate response content
        if html:
            content = self.generate_html(entries)
            media_type = "text/html"
        else:
            content = json.dumps(entries)
            media_type = "application/json"

        # Set headers
        headers = {}
        if auth_required:
            headers["www-authenticate"] = "Basic realm=\"Directory listing\""

        # Initialize response
        super().__init__(
            content=content,
            status_code=401 if auth_required else 200,
            headers=headers,
            media_type=media_type,
        )

    def generate_html(self, entries: List[Dict]) -> str:
        """Generate HTML directory listing."""
        html = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>Directory listing</title>",
            "<style>",
            "body { font-family: sans-serif; margin: 2em; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { text-align: left; padding: 8px; border-bottom: 1px solid #ddd; }",
            "th { background-color: #f2f2f2; }",
            "tr:hover { background-color: #f5f5f5; }",
            "a { text-decoration: none; color: #0366d6; }",
            "a:hover { text-decoration: underline; }",
            ".dir { font-weight: bold; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Directory listing</h1>",
            "<table>",
            "<tr><th>Name</th><th>Size</th><th>Last Modified</th></tr>",
        ]

        if str(self.path) != ".":
            parent = str(Path(self.base_url).parent)
            html.append(f'<tr><td><a href="{parent}">..</a></td><td></td><td></td></tr>')

        for entry in entries:
            name = entry["name"]
            size = entry["size"]
            mtime = entry["mtime"]

            # Format size
            if size is not None:
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size/1024:.1f} KB"
                else:
                    size_str = f"{size/(1024*1024):.1f} MB"
            else:
                size_str = "-"

            # Format time
            mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

            # Generate row
            path = f"{self.base_url}/{name}"
            if entry["is_dir"]:
                html.append(
                    f'<tr><td><a href="{path}" class="dir">{name}/</a></td>'
                    f'<td>{size_str}</td><td>{mtime_str}</td></tr>'
                )
            else:
                html.append(
                    f'<tr><td><a href="{path}">{name}</a></td>'
                    f'<td>{size_str}</td><td>{mtime_str}</td></tr>'
                )

        html.extend([
            "</table>",
            "</body>",
            "</html>",
        ])

        return "\n".join(html) 