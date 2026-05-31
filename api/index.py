"""Vercel serverless handler for YouTube Downloader"""
import os
import sys
import re
import json
import traceback

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    """Vercel serverless request handler"""

    def do_GET(self):
        """Handle GET requests for static files and pages"""
        try:
            path = self.path

            if path.startswith('/static/'):
                self._serve_static(path)
                return

            if path in ('/', '/index.html', '/blog', '/blog.html'):
                self._serve_html(path)
                return

            self._serve_html('/index.html')
        except Exception as e:
            self._send_error(str(e))

    def _send_error(self, msg):
        """Send error response"""
        self.send_response(500)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(f'Error: {msg}'.encode('utf-8'))

    def do_POST(self):
        """Handle POST requests for API endpoints"""
        try:
            path = self.path

            if path == '/api/info':
                self._handle_info()
            elif path == '/download':
                self._handle_download()
            else:
                self._send_json({'error': 'Not found'}, 404)
        except Exception as e:
            self._send_error(str(e))

    def _serve_static(self, path):
        """Serve CSS/JS static files"""
        base_dir = os.path.dirname(os.path.dirname(__file__))
        file_path = os.path.join(base_dir, path.lstrip('/'))

        if not os.path.exists(file_path):
            self._send_status(404)
            return

        content_type = 'text/css' if path.endswith('.css') else 'application/javascript'
        self._send_file(file_path, content_type)

    def _serve_html(self, path):
        """Serve HTML pages from public folder"""
        base_dir = os.path.dirname(os.path.dirname(__file__))
        file_name = 'index.html' if path in ('/', '/index.html') else 'blog.html'
        file_path = os.path.join(base_dir, 'public', file_name)

        if not os.path.exists(file_path):
            self._send_status(404)
            return

        self._send_file(file_path, 'text/html; charset=utf-8')

    def _send_file(self, file_path, content_type):
        """Read and send file content"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def _handle_info(self):
        """Extract video info using yt-dlp"""
        try:
            data = self._read_json_body()
            url = data.get('url', '').strip()

            if not url or not _validate_youtube_url(url):
                self._send_json({'error': 'Invalid or missing YouTube URL'}, 400)
                return

            import yt_dlp
            info = _extract_video_info(url)
            self._send_json(info)

        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    def _handle_download(self):
        """Return direct stream URL (Vercel can't serve files)"""
        try:
            data = self._read_json_body()
            url = data.get('url', '').strip()
            fmt_id = data.get('format_id', 'best')

            if not url or not _validate_youtube_url(url):
                self._send_json({'error': 'Invalid URL'}, 400)
                return

            import yt_dlp
            opts = {'quiet': True, 'no_warnings': True, 'format': fmt_id}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                direct_url = info.get('url')
                if not direct_url and info.get('formats'):
                    direct_url = info['formats'][0].get('url')

            if not direct_url:
                self._send_json({'error': 'No direct URL found'}, 500)
                return

            self._send_json({
                'redirect_url': direct_url,
                'filename': _safe_filename(info.get('title', 'video')),
                'message': 'Use this direct link to download'
            })

        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    def _read_json_body(self):
        """Parse JSON from request body"""
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        body = self.rfile.read(length)
        return json.loads(body.decode('utf-8'))

    def _send_json(self, data, status=200):
        """Send JSON response with CORS"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _send_status(self, status):
        """Send empty response with status code"""
        self.send_response(status)
        self.end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def _validate_youtube_url(url):
    """Validate YouTube URL format"""
    pattern = r'https?://(www\.)?(youtube|youtu)\.\w+/(watch\?v=|embed/|shorts/|v/)?[\w\-]+'
    return bool(re.match(pattern, url))


def _safe_filename(title):
    """Create filesystem-safe filename"""
    safe = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')[:50]
    return safe or 'video'


def _extract_video_info(url):
    """Extract video metadata using yt-dlp"""
    import yt_dlp

    opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = info.get('formats', [])
    seen_qualities = set()
    video_formats = []

    for fmt in formats:
        if fmt.get('vcodec') == 'none' or fmt.get('acodec') == 'none':
            continue
        q = fmt.get('quality_label') or fmt.get('format_note', 'unknown')
        if q in seen_qualities:
            continue
        seen_qualities.add(q)
        video_formats.append({
            'format_id': fmt['format_id'],
            'ext': fmt['ext'],
            'quality': q,
            'resolution': fmt.get('resolution', 'unknown'),
            'type': 'video',
            'has_audio': True,
        })

    seen_audio = set()
    audio_formats = []
    for fmt in formats:
        if fmt.get('vcodec') != 'none' or fmt.get('acodec') == 'none':
            continue
        abr = fmt.get('abr', 0) or 0
        key = f"{fmt.get('ext', 'm4a')}_{int(abr)}"
        if key in seen_audio:
            continue
        seen_audio.add(key)
        audio_formats.append({
            'format_id': fmt['format_id'],
            'ext': fmt['ext'],
            'quality': f"{int(abr)}kbps" if abr else 'audio',
            'resolution': 'audio only',
            'type': 'audio',
            'has_audio': True,
        })

    return {
        'title': info.get('title', 'video'),
        'duration': info.get('duration'),
        'thumbnail': info.get('thumbnail', ''),
        'uploader': info.get('uploader', ''),
        'video_formats': video_formats,
        'audio_formats': audio_formats,
    }
