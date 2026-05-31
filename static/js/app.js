const urlInput = document.getElementById('urlInput');
const fetchBtn = document.getElementById('fetchBtn');
const videoPreview = document.getElementById('videoPreview');
const previewThumb = document.getElementById('previewThumb');
const previewTitle = document.getElementById('previewTitle');
const previewMeta = document.getElementById('previewMeta');
const videoQualityGrid = document.getElementById('videoQualityGrid');
const audioQualityGrid = document.getElementById('audioQualityGrid');
const downloadVideoBtn = document.getElementById('downloadVideoBtn');
const downloadAudioBtn = document.getElementById('downloadAudioBtn');
const statusDiv = document.getElementById('statusMsg');

let currentVideoFormats = [];
let currentAudioFormats = [];
let selectedVideoFormat = null;
let selectedAudioFormat = null;
let currentUrl = '';

// Invidious instances - public YouTube alternative APIs
const INVIDIOUS_INSTANCES = [
    'https://vid.puffyan.us',
    'https://inv.riverside.rocks',
    'https://iv.datura.network',
    'https://yt.artemislena.eu',
    'https://invidious.fdn.fr',
];

function setStatus(msg, type) {
    statusDiv.textContent = msg;
    statusDiv.className = 'status-msg ' + (type || '');
    statusDiv.style.display = type ? 'block' : 'none';
}

function extractVideoId(url) {
    const patterns = [
        /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)([A-Za-z0-9_-]{11})/,
        /youtube\.com\/embed\/([A-Za-z0-9_-]{11})/,
    ];
    for (const p of patterns) {
        const match = url.match(p);
        if (match) return match[1];
    }
    return null;
}

function formatDuration(seconds) {
    if (!seconds) return '';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatBytes(bytes) {
    if (!bytes) return '';
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + sizes[i];
}

function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
    document.getElementById(tab + 'Tab').classList.add('active');
}

async function tryInstances(path) {
    let lastError;
    for (const base of INVIDIOUS_INSTANCES) {
        try {
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 8000);
            const response = await fetch(base + path, { signal: controller.signal });
            clearTimeout(timeout);
            if (response.ok) {
                return await response.json();
            }
        } catch (e) {
            lastError = e;
            continue;
        }
    }
    throw lastError || new Error('All Invidious instances failed');
}

async function fetchVideoInfo() {
    const url = urlInput.value.trim();
    if (!url) {
        setStatus('נא להכניס קישור ל-YouTube', 'error');
        return;
    }

    const videoId = extractVideoId(url);
    if (!videoId) {
        setStatus('קישור לא תקין. נא להכניס קישור YouTube תקין', 'error');
        return;
    }

    currentUrl = url;
    setStatus('טוען מידע על הסרטון...', 'loading');
    fetchBtn.disabled = true;
    videoPreview.classList.remove('active');

    try {
        const data = await tryInstances(`/api/v1/videos/${videoId}`);

        previewThumb.src = data.videoThumbnails?.find(t => t.quality === 'maxres')?.url
            || data.videoThumbnails?.[0]?.url
            || '';
        previewTitle.textContent = data.title || 'סרטון ללא כותרת';

        const durationStr = data.lengthSeconds ? `משך: ${formatDuration(data.lengthSeconds)}` : '';
        const uploaderStr = data.author ? `ערוץ: ${data.author}` : '';
        previewMeta.textContent = [uploaderStr, durationStr].filter(Boolean).join(' | ');

        const videoFormats = [];
        const seenQualities = new Set();

        for (const fmt of (data.adaptiveFormats || [])) {
            if (fmt.type?.startsWith('video/')) {
                const quality = fmt.qualityLabel || fmt.resolution || 'unknown';
                if (seenQualities.has(quality)) continue;
                seenQualities.add(quality);
                videoFormats.push({
                    format_id: fmt.itag || fmt.url,
                    quality: quality,
                    resolution: fmt.resolution || quality,
                    url: fmt.url,
                    has_audio: false,
                    ext: fmt.container || 'mp4',
                });
            }
        }

        const audioFormats = [];
        const seenAudio = new Set();

        for (const fmt of (data.adaptiveFormats || [])) {
            if (fmt.type?.startsWith('audio/')) {
                const abr = fmt.bitrate ? Math.round(fmt.bitrate / 1000) : 0;
                const key = `${fmt.container}_${abr}`;
                if (seenAudio.has(key)) continue;
                seenAudio.add(key);
                audioFormats.push({
                    format_id: fmt.itag || fmt.url,
                    quality: abr ? `${abr}kbps` : 'אודיו',
                    resolution: 'audio only',
                    url: fmt.url,
                    has_audio: true,
                    ext: fmt.container || 'm4a',
                });
            }
        }

        for (const fmt of (data.formatStreams || [])) {
            if (fmt.type?.startsWith('video/')) {
                const quality = fmt.qualityLabel || fmt.resolution || 'unknown';
                if (!seenQualities.has(quality)) {
                    seenQualities.add(quality);
                    videoFormats.push({
                        format_id: fmt.itag || fmt.url,
                        quality: quality,
                        resolution: fmt.resolution || quality,
                        url: fmt.url,
                        has_audio: true,
                        ext: fmt.container || 'mp4',
                    });
                }
            }
        }

        currentVideoFormats = videoFormats;
        currentAudioFormats = audioFormats;
        renderVideoButtons();
        renderAudioButtons();

        videoPreview.classList.add('active');
        setStatus('', '');
    } catch (error) {
        console.error(error);
        setStatus('שגיאה בטעינת מידע. נסה קישור אחר או רענן את הדף.', 'error');
    } finally {
        fetchBtn.disabled = false;
    }
}

function renderVideoButtons() {
    videoQualityGrid.innerHTML = '';

    for (const fmt of currentVideoFormats) {
        const btn = document.createElement('button');
        btn.className = 'quality-btn';
        btn.textContent = fmt.quality;
        btn.dataset.url = fmt.url;

        const audioTag = fmt.has_audio ? '' : ' (וידאו בלבד)';
        btn.title = `${fmt.resolution}${audioTag}`;

        btn.addEventListener('click', () => selectVideoFormat(btn, fmt.url));
        videoQualityGrid.appendChild(btn);
    }

    if (videoQualityGrid.children.length > 0) {
        selectVideoFormat(videoQualityGrid.children[0], videoQualityGrid.children[0].dataset.url);
    }
}

function renderAudioButtons() {
    audioQualityGrid.innerHTML = '';

    for (const fmt of currentAudioFormats) {
        const btn = document.createElement('button');
        btn.className = 'quality-btn';
        btn.textContent = fmt.quality;
        btn.dataset.url = fmt.url;
        btn.title = `אודיו ${fmt.ext.toUpperCase()}`;

        btn.addEventListener('click', () => selectAudioFormat(btn, fmt.url));
        audioQualityGrid.appendChild(btn);
    }

    if (audioQualityGrid.children.length > 0) {
        selectAudioFormat(audioQualityGrid.children[0], audioQualityGrid.children[0].dataset.url);
    }
}

function selectVideoFormat(btn, url) {
    selectedVideoFormat = url;
    for (const child of videoQualityGrid.children) {
        child.classList.remove('selected');
    }
    btn.classList.add('selected');
}

function selectAudioFormat(btn, url) {
    selectedAudioFormat = url;
    for (const child of audioQualityGrid.children) {
        child.classList.remove('selected');
    }
    btn.classList.add('selected');
}

async function startDownload(type) {
    if (!currentUrl) {
        setStatus('נא לחפש סרטון תחילה', 'error');
        return;
    }

    const url = type === 'audio' ? selectedAudioFormat : selectedVideoFormat;
    const btn = type === 'audio' ? downloadAudioBtn : downloadVideoBtn;

    if (!url) {
        setStatus('לא נבחר פורמט', 'error');
        return;
    }

    setStatus('מכין הורדה...', 'loading');
    btn.disabled = true;

    try {
        const a = document.createElement('a');
        a.href = url;
        a.download = '';
        a.target = '_blank';
        document.body.appendChild(a);
        a.click();
        a.remove();
        setStatus('ההורדה החלה! לחץ "שמור" בדפדפן', 'success');
    } catch (error) {
        console.error(error);
        setStatus('שגיאה בהורדה', 'error');
    } finally {
        btn.disabled = false;
    }
}

urlInput.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        fetchVideoInfo();
    }
});
