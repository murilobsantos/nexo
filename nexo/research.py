"""Fontes públicas por URL explícita: sem proxies, cookies ou envio de arquivos."""
import http.client
import ipaddress
import socket
import ssl
import time
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin, parse_qsl

from .files import contains_secret


class Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.title = [], []
        self.blocked = 0
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "nav", "form"}:
            self.blocked += 1
        if tag == "title":
            self.in_title = True
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "pre", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "nav", "form"}:
            self.blocked = max(0, self.blocked - 1)
        if tag == "title":
            self.in_title = False
        if tag in {"p", "div", "li", "h1", "h2", "h3", "pre"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if not self.blocked and not self.in_title:
            self.parts.append(data)

    def text(self):
        return "\n".join(" ".join(line.split()) for line in "".join(self.parts).splitlines() if line.strip())


def resolve_public(url):
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password or parts.fragment:
        raise ValueError("Use URL HTTP(S) pública, sem credencial ou fragmento")
    expected = 443 if parts.scheme == "https" else 80
    if parts.port not in {None, expected}:
        raise PermissionError("Somente portas HTTP/HTTPS padrão são permitidas")
    if any(word in key.casefold() for key, _ in parse_qsl(parts.query) for word in ("token", "password", "secret", "api_key")) or contains_secret(url):
        raise PermissionError("URL parece conter credencial")
    if len(url) > 2000 or any(ord(char) < 32 for char in url):
        raise ValueError("URL inválida ou longa demais")
    addresses = list(dict.fromkeys(info[4][0] for info in socket.getaddrinfo(parts.hostname, expected, type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise PermissionError("Endereços locais, privados ou especiais são bloqueados")
    return parts, addresses[0], expected


class PinnedConnection(http.client.HTTPConnection):
    def __init__(self, host, address, port, tls, timeout):
        super().__init__(host, port, timeout=timeout)
        self.address, self.tls = address, tls

    def connect(self):
        self.sock = socket.create_connection((self.address, self.port), self.timeout)
        if self.tls:
            self.sock = ssl.create_default_context().wrap_socket(self.sock, server_hostname=self.host)


def fetch_public(url, max_bytes=1024 * 1024):
    deadline = time.monotonic() + 20
    original = url
    for _ in range(4):
        parts, address, port = resolve_public(url)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Orçamento de pesquisa esgotado")
        connection = PinnedConnection(parts.hostname, address, port, parts.scheme == "https", min(8, remaining))
        try:
            path = parts.path or "/"
            if parts.query:
                path += "?" + parts.query
            connection.request("GET", path, headers={"Host": parts.hostname, "User-Agent": "NEXO-local/0.3", "Accept": "text/html,text/plain", "Accept-Encoding": "identity"})
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise ValueError("Redirecionamento sem destino")
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise ValueError(f"Fonte indisponível: HTTP {response.status}")
            mime = response.getheader("Content-Type", "").split(";")[0].strip().lower()
            if mime not in {"text/html", "text/plain", "application/xhtml+xml"}:
                raise ValueError("Tipo de fonte não suportado")
            if response.getheader("Content-Encoding", "identity") not in {"identity", ""}:
                raise ValueError("Fonte comprimida não suportada")
            data = bytearray()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Orçamento de pesquisa esgotado")
                if connection.sock:
                    connection.sock.settimeout(min(8, remaining))
                block = response.read1(min(8192, max_bytes + 1 - len(data)))
                if not block:
                    break
                data.extend(block)
                if len(data) > max_bytes:
                    raise ValueError("Fonte excede limite de 1 MiB")
            charset = response.headers.get_content_charset() or "utf-8"
            text = bytes(data).decode(charset, errors="replace")
            title = parts.hostname
            if mime != "text/plain":
                parser = Extractor()
                parser.feed(text)
                title = " ".join("".join(parser.title).split())[:300] or title
                text = parser.text()
            return {"source": url, "requested_url": original, "title": title, "text": text}
        finally:
            connection.close()
    raise ValueError("Redirecionamentos excedem limite")
