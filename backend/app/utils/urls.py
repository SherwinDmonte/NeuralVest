"""External URL validation (task 11.3.3).

Article links are validated when they are collected (`news_data.normalize_url`) and stored
(`financial_news` validator: must start with http/https). They are checked AGAIN here before
they are returned by the API or written into a PDF, because a stored document can be edited
outside the app. Only absolute http(s) links to a real host name are allowed: no
`javascript:`/`data:` links, no credentials, no control characters, no local addresses.
"""

import ipaddress
import re
from urllib.parse import urlsplit

MAX_URL_LENGTH = 2048
_CONTROL = re.compile(r"[\x00-\x20\x7f\\]")  # whitespace/control characters and backslashes
_LOCAL_HOSTS = {"localhost", "localhost.localdomain"}


def safe_http_url(url: str | None) -> str | None:
    """`url` when it is a safe public http(s) link, else None."""
    if not isinstance(url, str) or not url or len(url) > MAX_URL_LENGTH or _CONTROL.search(url):
        return None
    try:
        parts = urlsplit(url)
        port = parts.port  # raises ValueError for an invalid port
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        return None
    if parts.username or parts.password or (port is not None and not 0 < port < 65536):
        return None
    host = parts.hostname.lower()
    if host in _LOCAL_HOSTS or host.endswith(".local") or "." not in host.strip("[]"):
        return None
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return url  # a host name
    return url if ip.is_global else None
