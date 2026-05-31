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

function setStatus(msg, type) {
    statusDiv.textContent = msg;
    statusDiv.className = 'status-msg ' + (type || '');
    statusDiv.style.display = type ? 'block' : 'none';
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

async function fetchVideoInfo() {
    const url = urlInput.value.trim();
    if (!url) {
        setStatus('נא להכניס קישור ל-YouTube', 'error');
        return;
    }

    currentUrl = url;
    setStatus('טוען מידע על הסרטון...', 'loading');
    fetchBtn.disabled = true;
    videoPreview.classList.remove('active');

    try {
        // Use server proxy to avoid CORS
        const response = await fetch('/api/proxy/info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Server error');
        }

        previewThumb.src = data.thumbnail || '';
        previewTitle.textContent = data.title || 'סרטון ללא כותרת';

        const durationStr = data.duration ? `משך: ${formatDuration(data.duration)}` : '';
        const uploaderStr = data.uploader ? `ערוץ: ${data.uploader}` : '';
        previewMeta.textContent = [uploaderStr, durationStr].filter(Boolean).join(' | ');

        currentVideoFormats = data.video_formats || [];
        currentAudioFormats = data.audio_formats || [];
        renderVideoButtons();
        renderAudioButtons();

        videoPreview.classList.add('active');
        setStatus('', '');
    } catch (error) {
        console.error('Full error:', error);
        setStatus(`שגיאה: ${error.message}`, 'error');
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
