from typing import Any, Awaitable, Callable, Dict, List, MutableMapping, Optional, Tuple, Union
from typing_extensions import Protocol, TypedDict, Required

# ASGI Types
class ASGIScope(TypedDict, total=False):
    """ASGI scope with required fields marked."""
    type: Required[str]
    method: Required[str]
    path: Required[str]
    headers: Required[List[Tuple[bytes, bytes]]]
    asgi: Dict[str, str]
    http_version: str
    scheme: str
    raw_path: bytes
    query_string: bytes
    root_path: str
    client: Optional[Tuple[str, int]]
    server: Optional[Tuple[str, Optional[int]]]
    state: Dict[str, Any]

class HTTPResponseStart(TypedDict):
    """HTTP response start with required fields."""
    type: Required[str]  # Always "http.response.start"
    status: Required[int]
    headers: Required[List[Tuple[bytes, bytes]]]

class HTTPResponseBody(TypedDict):
    """HTTP response body with required fields."""
    type: Required[str]  # Always "http.response.body"
    body: Required[bytes]
    more_body: Required[bool]

Message = MutableMapping[str, Any]
Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

# Headers Types
class MutableHeaders(Protocol):
    """Mutable headers protocol."""
    def __setitem__(self, key: str, value: str) -> None: ...
    def __getitem__(self, key: str) -> str: ...
    def __delitem__(self, key: str) -> None: ...
    def __contains__(self, key: str) -> bool: ...
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]: ...
    def update(self, other: Dict[str, str]) -> None: ...
    @property
    def raw(self) -> List[Tuple[bytes, bytes]]: ...

# HTTP types
HTTPResponseStart = Dict[str, Union[int, List[Tuple[bytes, bytes]]]]
HTTPResponseBody = Dict[str, Union[bytes, bool]]

# Headers type
Headers = List[Tuple[bytes, bytes]]
MutableHeaders = Dict[str, str]

# Auth types
AuthCredentials = Dict[str, str]

# File types
FileMode = str
FileSize = int
FileTime = float
FileStat = Any  # os.stat_result

# Response types
ResponseContent = Union[str, bytes]
ResponseStatus = int
ResponseHeaders = Dict[str, str]
ResponseBody = Union[str, bytes]

# Middleware types
MiddlewareCallable = Callable[[Scope, Receive, Send], Awaitable[None]] 