import os
import re
import shutil
from datetime import datetime
from flask import Flask, render_template, request, send_file, jsonify
import yt_dlp

app = Flask(__name__)
DOWNLOAD_FOLDER = "downloads"
STATIC_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

YOUTUBE_REGEX = re.compile(
    r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|shorts/|v/)?(?P<id>[A-Za-z0-9\-_]+)"
)

COMMON_YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'referer': 'https://www.youtube.com/',
    'headers': {
        'Accept-Language': 'en-US,en;q=0.9',
    },
}


def validate_url(url):
    return YOUTUBE_REGEX.match(url)


def cleanup_old_downloads(folder=DOWNLOAD_FOLDER, max_age_hours=2):
    now = datetime.now()
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        if os.path.isfile(filepath):
            file_age = now - datetime.fromtimestamp(os.path.getmtime(filepath))
            if file_age.total_seconds() > max_age_hours * 3600:
                os.remove(filepath)


def get_video_info(url):
    ydl_opts = {**COMMON_YDL_OPTS, 'listformats': False}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
        # 1. Video+Audio merged formats (pre-merged by YouTube)
        merged_video_formats = []
        for f in info.get('formats', []):
            if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                merged_video_formats.append(f)
        
        # 2. Video-only streams (will be merged with audio)
        video_only_map = {}
        for f in info.get('formats', []):
            if f.get('vcodec') == 'none' or f.get('acodec') != 'none':
                continue
            q = f.get('quality_label') or f.get('format_note', 'unknown')
            res = f.get('width', 0) or 0
            if q not in video_only_map or res > video_only_map[q].get('width', 0):
                video_only_map[q] = f
        
        # 3. Audio-only formats
        audio_formats = []
        best_audio = None
        for f in info.get('formats', []):
            if f.get('vcodec') != 'none' or f.get('acodec') == 'none':
                continue
            # Track best audio for merging
            abr = f.get('abr', 0) or 0
            if best_audio is None or abr > (best_audio.get('abr', 0) or 0):
                best_audio = f
            audio_formats.append(f)
        
        # Build response categories
        video_formats = []
        
        # Add merged formats first (ready to use)
        seen_qualities = set()
        for f in sorted(merged_video_formats, key=lambda x: x.get('height', 0) or 0, reverse=True):
            q = f.get('quality_label') or f.get('format_note', 'unknown')
            if q not in seen_qualities:
                seen_qualities.add(q)
                video_formats.append({
                    'format_id': f['format_id'],
                    'ext': f['ext'],
                    'quality': q,
                    'resolution': f.get('resolution', 'unknown'),
                    'filesize': f.get('filesize') or f.get('filesize_approx'),
                    'type': 'video',
                    'has_audio': True,
                })
        
        # Add video-only streams (higher qualities that need audio merge)
        for q, f in sorted(video_only_map.items(), key=lambda x: x[1].get('width', 0), reverse=True):
            if q not in seen_qualities:
                seen_qualities.add(q)
                video_formats.append({
                    'format_id': f['format_id'],
                    'ext': f['ext'],
                    'quality': q,
                    'resolution': f.get('resolution', 'unknown'),
                    'filesize': f.get('filesize') or f.get('filesize_approx'),
                    'type': 'video',
                    'has_audio': False,
                    'audio_format_id': best_audio['format_id'] if best_audio else None,
                })
        
        # Audio formats
        audio_list = []
        seen_audio = set()
        for f in sorted(audio_formats, key=lambda x: x.get('abr', 0) or 0, reverse=True):
            abr = f.get('abr', 0)
            key = f"{f.get('ext', 'm4a')}_{abr}"
            if key not in seen_audio:
                seen_audio.add(key)
                audio_list.append({
                    'format_id': f['format_id'],
                    'ext': f['ext'],
                    'quality': f"{int(abr)}kbps" if abr else 'audio',
                    'resolution': 'audio only',
                    'filesize': f.get('filesize') or f.get('filesize_approx'),
                    'type': 'audio',
                    'has_audio': True,
                })
        
        return {
            'title': info.get('title', 'video'),
            'duration': info.get('duration'),
            'thumbnail': info.get('thumbnail', ''),
            'uploader': info.get('uploader', ''),
            'video_formats': video_formats,
            'audio_formats': audio_list,
        }


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/blog', methods=['GET'])
def blog():
    return render_template('blog.html')


@app.route('/api/info', methods=['POST'])
def video_info():
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url or not validate_url(url):
        return jsonify({'error': 'Invalid or missing YouTube URL'}), 400
    try:
        info = get_video_info(url)
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download', methods=['POST'])
def download_video():
    data = request.get_json()
    url = data.get('url', '').strip()
    format_id = data.get('format_id', 'best')
    download_type = data.get('type', 'video')

    if not url or not validate_url(url):
        return jsonify({'error': 'Invalid or missing YouTube URL'}), 400

    cleanup_old_downloads()

    try:
        info_opts = {**COMMON_YDL_OPTS}
        with yt_dlp.YoutubeDL(info_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        title = info.get('title', 'video')
        safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')[:50]
        if not safe_title:
            safe_title = 'video'

        if download_type == 'audio':
            output_path = os.path.join(DOWNLOAD_FOLDER, f"{safe_title}_{format_id}.mp3")
            ydl_opts = {
                **COMMON_YDL_OPTS,
                'format': format_id if format_id != 'best' else 'bestaudio',
                'outtmpl': output_path,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            }
            download_name = f"{safe_title}.mp3"
        else:
            output_path = os.path.join(DOWNLOAD_FOLDER, f"{safe_title}_{format_id}.mp4")
            fmt = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            if format_id and format_id != 'best':
                fmt = f"{format_id}+bestaudio[ext=m4a]/{format_id}/best"
            ydl_opts = {
                **COMMON_YDL_OPTS,
                'format': fmt,
                'outtmpl': output_path,
                'merge_output_format': 'mp4',
            }
            download_name = f"{safe_title}.mp4"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if os.path.exists(output_path):
            return send_file(output_path, as_attachment=True, download_name=download_name)
        return jsonify({'error': 'Download failed, file not found'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
