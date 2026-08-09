"""Local graphical correction app for JTool Scanner."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from hashlib import sha256
import json
import mimetypes
from pathlib import Path
import socket
import tempfile
from typing import Any
from urllib.parse import parse_qs, urlparse
import webbrowser

from .constants import OBJECT_NAMES
from .correction import CorrectionProject, render_correction_svg
from .jmap import JMap
from .scanner import scan_png


WEB_ROOT = Path(__file__).with_name("web")
ASSET_ROOT = Path(__file__).with_name("assets")
MAX_REQUEST_BYTES = 32 * 1024 * 1024


def _source_fingerprint() -> str:
    package_root = Path(__file__).parent
    digest = sha256()
    for path in sorted(package_root.glob("*.py")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


PROCESS_SOURCE_FINGERPRINT = _source_fingerprint()


class _ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    """Reject a second app process instead of splitting requests on Windows."""

    allow_reuse_address = False

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_EXCLUSIVEADDRUSE,
                1,
            )
        super().server_bind()


def scan_image_bytes(
    content: bytes,
    filename: str = "screen.png",
    *,
    grid_step: int = 8,
    include_color_objects: bool = True,
    include_geometry: bool = True,
    start_policy: str = "auto",
    source_grid: tuple[int, int] | None = None,
    recognized_text: str | None = None,
    use_ocr: bool = True,
) -> CorrectionProject:
    """Scan uploaded PNG bytes into the existing correction-project model."""

    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("the scanner currently accepts PNG images")
    with tempfile.TemporaryDirectory(prefix="jtool-scanner-") as directory:
        path = Path(directory) / _safe_filename(filename)
        path.write_bytes(content)
        result = scan_png(
            path,
            grid_step=grid_step,
            include_color_objects=include_color_objects,
            include_geometry=include_geometry,
            source_grid=source_grid,
            recognized_text=recognized_text,
            enable_ocr=use_ocr,
        )
    return result.to_correction_project(
        filename,
        grid_step=grid_step,
        include_color_objects=include_color_objects,
        include_geometry=include_geometry,
        start_policy=start_policy,
    )


def import_jmap_text(content: str, filename: str = "map.jmap") -> CorrectionProject:
    return CorrectionProject.from_jmap(JMap.from_text(content), filename)


def preview_project(data: dict[str, Any]) -> str:
    project = CorrectionProject.from_dict(data)
    return render_correction_svg(project, Path(project.source_image or "map").name)


def export_jmap_text(data: dict[str, Any]) -> str:
    return CorrectionProject.from_dict(data).to_jmap().to_text()


def app_metadata() -> dict[str, Any]:
    return {
        "room": {"width": 800, "height": 608},
        "object_types": [
            {"id": type_id, "name": name}
            for type_id, name in sorted(OBJECT_NAMES.items())
        ],
    }


def app_health() -> dict[str, Any]:
    """Identify the exact source snapshot loaded by this app process."""

    return {"ok": True, "source_fingerprint": PROCESS_SOURCE_FINGERPRINT}


def serve_app(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    open_browser: bool = True,
) -> None:
    server = _ExclusiveThreadingHTTPServer((host, port), _AppHandler)
    url = f"http://{host}:{server.server_port}/"
    print(f"JTool Scanner app: {url}", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


class _AppHandler(BaseHTTPRequestHandler):
    server_version = "JToolScanner/1.0"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/metadata":
            self._send_json(app_metadata())
            return
        if parsed.path == "/api/health":
            self._send_json(app_health())
            return
        if parsed.path.startswith("/assets/"):
            root = ASSET_ROOT
            relative = parsed.path.removeprefix("/assets/")
        else:
            root = WEB_ROOT
            relative = "index.html" if parsed.path == "/" else parsed.path.lstrip("/")
        path = (root / relative).resolve()
        if root.resolve() not in path.parents and path != root.resolve():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._send_bytes(path.read_bytes(), content_type)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/scan":
                self._handle_scan(parse_qs(parsed.query))
            elif parsed.path == "/api/import-jmap":
                filename = self.headers.get("X-Filename", "map.jmap")
                project = import_jmap_text(self._read_body().decode("utf-8"), filename)
                self._send_json({"project": project.to_dict()})
            elif parsed.path == "/api/preview":
                self._send_bytes(
                    preview_project(self._read_json()).encode("utf-8"),
                    "image/svg+xml; charset=utf-8",
                )
            elif parsed.path == "/api/export-jmap":
                self._send_bytes(
                    export_jmap_text(self._read_json()).encode("utf-8"),
                    "text/plain; charset=utf-8",
                )
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except (ValueError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:  # pragma: no cover - last-resort API boundary
            self._send_json({"error": f"unexpected server error: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_scan(self, query: dict[str, list[str]]) -> None:
        filename = self.headers.get("X-Filename", "screen.png")
        source_grid = _parse_source_grid(_first(query, "source_grid", ""))
        project = scan_image_bytes(
            self._read_body(),
            filename,
            grid_step=int(_first(query, "grid_step", "8")),
            include_color_objects=_parse_bool(_first(query, "color", "true")),
            include_geometry=_parse_bool(_first(query, "geometry", "true")),
            start_policy=_first(query, "start_policy", "auto"),
            source_grid=source_grid,
            recognized_text=_first(query, "ocr_text", "") or None,
            use_ocr=_parse_bool(_first(query, "ocr", "true")),
        )
        self._send_json({"project": project.to_dict()})

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            raise ValueError("request body is empty")
        if length > MAX_REQUEST_BYTES:
            raise ValueError("request is larger than 32 MB")
        return self.rfile.read(length)

    def _read_json(self) -> dict[str, Any]:
        data = json.loads(self._read_body().decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        return data

    def _send_json(
        self,
        data: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        self._send_bytes(
            json.dumps(data).encode("utf-8"),
            "application/json; charset=utf-8",
            status,
        )

    def _send_bytes(
        self,
        content: bytes,
        content_type: str,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: object) -> None:
        try:
            print(f"[app] {self.address_string()} {format % args}", flush=True)
        except OSError:
            # Detached Windows launches may close the inherited console stream.
            pass


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    return name if name.lower().endswith(".png") else "screen.png"


def _first(query: dict[str, list[str]], key: str, default: str) -> str:
    values = query.get(key)
    return values[0] if values else default


def _parse_bool(value: str) -> bool:
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _parse_source_grid(value: str) -> tuple[int, int] | None:
    if not value:
        return None
    normalized = value.lower().replace(" ", "")
    left, separator, right = normalized.partition("x")
    if not separator or not left.isdigit() or not right.isdigit():
        raise ValueError("source grid must use COLSxROWS, for example 19x13")
    columns, rows = int(left), int(right)
    if columns <= 0 or rows <= 0:
        raise ValueError("source grid dimensions must be positive")
    return columns, rows


if __name__ == "__main__":
    serve_app()
