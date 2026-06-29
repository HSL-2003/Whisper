/**
 * WhisperX Meeting Transcriber — Frontend Application Logic
 * Handles URL detection, file upload, SSE progress, transcript rendering, and MD export.
 */

// ══════════════════════════════════════════════════════════════
// State
// ══════════════════════════════════════════════════════════════
const state = {
    currentJobId: null,
    result: null,
    selectedFile: null,
    activeTab: 'url',
    eventSource: null,
};

// ══════════════════════════════════════════════════════════════
// DOM References
// ══════════════════════════════════════════════════════════════
const $ = (id) => document.getElementById(id);

const DOM = {
    urlInput: $('url-input'),
    urlDetect: $('url-detect'),
    btnTranscribe: $('btn-transcribe'),
    btnContent: null,
    btnLoader: null,
    dropZone: $('drop-zone'),
    fileInput: $('file-input'),
    selectedFile: $('selected-file'),
    fileName: $('file-name'),
    fileSize: $('file-size'),
    btnRemoveFile: $('btn-remove-file'),
    progressSection: $('progress-section'),
    progressFill: $('progress-fill'),
    progressPercent: $('progress-percent'),
    progressMessage: $('progress-message'),
    progressBar: $('progress-bar'),
    inputSection: $('input-section'),
    resultsSection: $('results-section'),
    errorSection: $('error-section'),
    errorMessage: $('error-message'),
    timeline: $('transcript-timeline'),
    searchInput: $('search-input'),
    filterSpeaker: $('filter-speaker'),
    btnDownloadMd: $('btn-download-md'),
    btnDownloadSrt: $('btn-download-srt'),
    btnDownloadVtt: $('btn-download-vtt'),
    btnDownloadTxt: $('btn-download-txt'),
    btnCopyAll: $('btn-copy-all'),
    speakerLegend: $('speaker-legend'),
    statDuration: $('stat-duration'),
    statSpeakers: $('stat-speakers'),
    statSegments: $('stat-segments'),
    statLanguage: $('stat-language'),
    optDiarize: $('opt-diarize'),
    optMaxSpeakers: $('opt-max-speakers'),
    optHfToken: $('opt-hf-token'),
    optCookiesFile: $('opt-cookies-file'),
    optTranslateLang: $('opt-translate-lang'),
    warningBanner: $('warning-banner'),
    warningMessageText: $('warning-message-text'),
};

// ══════════════════════════════════════════════════════════════
// URL Detection Patterns
// ══════════════════════════════════════════════════════════════
const URL_PATTERNS = [
    { name: 'Zoom', pattern: /zoom\.us\// },
    { name: 'Google Drive', pattern: /drive\.google\.com\// },
    { name: 'YouTube', pattern: /(youtube\.com\/(watch|shorts|live)|youtu\.be\/)/ },
    { name: 'TikTok', pattern: /tiktok\.com\// },
    { name: 'Vimeo', pattern: /vimeo\.com\// },
    { name: 'Direct URL', pattern: /^https?:\/\/.+\.(mp4|mov|mp3|wav|webm|m4a)/i },
];

function detectUrl(url) {
    if (!url || url.length < 8) return null;
    for (const p of URL_PATTERNS) {
        if (p.pattern.test(url)) return p.name;
    }
    if (/^https?:\/\//.test(url)) return 'URL';
    return null;
}

// ══════════════════════════════════════════════════════════════
// Tab Switching
// ══════════════════════════════════════════════════════════════
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        state.activeTab = tab;
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        $(`tab-content-${tab}`).classList.add('active');
        updateTranscribeButton();
    });
});

// ══════════════════════════════════════════════════════════════
// URL Input
// ══════════════════════════════════════════════════════════════
DOM.urlInput.addEventListener('input', () => {
    const url = DOM.urlInput.value.trim();
    const detected = detectUrl(url);
    if (detected) {
        DOM.urlDetect.textContent = `✓ ${detected}`;
        DOM.urlDetect.classList.add('visible');
    } else {
        DOM.urlDetect.classList.remove('visible');
    }
    updateTranscribeButton();
});

// Paste handler
DOM.urlInput.addEventListener('paste', (e) => {
    setTimeout(() => {
        DOM.urlInput.dispatchEvent(new Event('input'));
    }, 50);
});

// ══════════════════════════════════════════════════════════════
// File Upload & Drag/Drop
// ══════════════════════════════════════════════════════════════
DOM.dropZone.addEventListener('click', () => DOM.fileInput.click());

DOM.dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    DOM.dropZone.classList.add('dragover');
});
DOM.dropZone.addEventListener('dragleave', () => DOM.dropZone.classList.remove('dragover'));
DOM.dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    DOM.dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) handleFileSelect(e.dataTransfer.files[0]);
});

DOM.fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) handleFileSelect(e.target.files[0]);
});

DOM.btnRemoveFile.addEventListener('click', () => {
    state.selectedFile = null;
    DOM.selectedFile.style.display = 'none';
    DOM.dropZone.style.display = '';
    DOM.fileInput.value = '';
    updateTranscribeButton();
});

function handleFileSelect(file) {
    const maxSize = 500 * 1024 * 1024;
    if (file.size > maxSize) {
        alert('File too large. Maximum 500MB.');
        return;
    }
    const validExts = ['.mp4', '.mov', '.mp3', '.wav', '.m4a', '.webm', '.ogg', '.flac'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!validExts.includes(ext)) {
        alert(`Unsupported format: ${ext}\nAllowed: ${validExts.join(', ')}`);
        return;
    }

    state.selectedFile = file;
    DOM.fileName.textContent = file.name;
    DOM.fileSize.textContent = formatFileSize(file.size);
    DOM.selectedFile.style.display = 'flex';
    DOM.dropZone.style.display = 'none';
    updateTranscribeButton();
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ══════════════════════════════════════════════════════════════
// Transcribe Button
// ══════════════════════════════════════════════════════════════
function updateTranscribeButton() {
    const hasUrl = state.activeTab === 'url' && DOM.urlInput.value.trim().length > 8;
    const hasFile = state.activeTab === 'file' && state.selectedFile;
    DOM.btnTranscribe.disabled = !(hasUrl || hasFile);
}

DOM.btnTranscribe.addEventListener('click', startTranscription);

async function startTranscription() {
    const btnContent = DOM.btnTranscribe.querySelector('.btn-content');
    const btnLoader = DOM.btnTranscribe.querySelector('.btn-loader');

    DOM.btnTranscribe.disabled = true;
    btnContent.style.display = 'none';
    btnLoader.style.display = 'flex';

    // Show progress
    DOM.progressSection.style.display = '';
    DOM.resultsSection.style.display = 'none';
    DOM.errorSection.style.display = 'none';

    // Scroll to progress
    DOM.progressSection.scrollIntoView({ behavior: 'smooth', block: 'center' });

    const formData = new FormData();

    if (state.activeTab === 'url') {
        formData.append('url', DOM.urlInput.value.trim());
    } else if (state.selectedFile) {
        formData.append('file', state.selectedFile);
    }

    formData.append('enable_diarization', DOM.optDiarize.checked);
    formData.append('max_speakers', DOM.optMaxSpeakers.value);

    const hfTokenVal = DOM.optHfToken.value.trim();
    if (hfTokenVal) {
        formData.append('hf_token', hfTokenVal);
    }

    if (DOM.optCookiesFile.files.length > 0) {
        formData.append('cookies_file', DOM.optCookiesFile.files[0]);
    }

    const translateLangVal = DOM.optTranslateLang.value;
    if (translateLangVal) {
        formData.append('translate_lang', translateLangVal);
    }

    try {
        const resp = await fetch('/api/transcribe', { method: 'POST', body: formData });
        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Server error');
        }
        const data = await resp.json();
        state.currentJobId = data.jobId;
        startSSEStream(data.jobId);
    } catch (err) {
        showError(err.message);
        btnContent.style.display = 'flex';
        btnLoader.style.display = 'none';
        DOM.btnTranscribe.disabled = false;
    }
}

// ══════════════════════════════════════════════════════════════
// SSE Progress Stream
// ══════════════════════════════════════════════════════════════
function startSSEStream(jobId) {
    if (state.eventSource) state.eventSource.close();

    const es = new EventSource(`/api/transcribe/${jobId}/stream`);
    state.eventSource = es;

    es.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateProgress(data);

        if (data.status === 'done') {
            es.close();
            state.eventSource = null;
            state.result = data.result;
            showResults(data.result);
        } else if (data.status === 'error') {
            es.close();
            state.eventSource = null;
            showError(data.error || data.message);
        }
    };

    es.onerror = () => {
        es.close();
        state.eventSource = null;
        // Try to fetch result directly
        fetchResultFallback(jobId);
    };
}

async function fetchResultFallback(jobId) {
    try {
        await new Promise(r => setTimeout(r, 2000));
        const resp = await fetch(`/api/transcribe/${jobId}/result`);
        const data = await resp.json();
        if (data.segments) {
            state.result = data;
            showResults(data);
        } else if (data.status === 'error') {
            showError(data.message || 'Unknown error');
        } else {
            showError('Connection lost. Please try again.');
        }
    } catch {
        showError('Connection lost. Please try again.');
    }
}

// ══════════════════════════════════════════════════════════════
// Progress UI
// ══════════════════════════════════════════════════════════════
const STEP_THRESHOLDS = [
    { id: 'step-download', min: 0, max: 27 },
    { id: 'step-transcribe', min: 28, max: 57 },
    { id: 'step-align', min: 58, max: 77 },
    { id: 'step-diarize', min: 78, max: 97 },
    { id: 'step-done', min: 98, max: 100 },
];

function updateProgress(data) {
    const pct = data.progress || 0;
    DOM.progressFill.style.width = pct + '%';
    DOM.progressPercent.textContent = Math.round(pct) + '%';
    DOM.progressMessage.textContent = data.message || '';
    DOM.progressBar.classList.add('active');

    // Update step indicators
    STEP_THRESHOLDS.forEach(step => {
        const el = $(step.id);
        if (pct >= step.max) {
            el.classList.remove('active');
            el.classList.add('completed');
        } else if (pct >= step.min) {
            el.classList.add('active');
            el.classList.remove('completed');
        } else {
            el.classList.remove('active', 'completed');
        }
    });
}

// ══════════════════════════════════════════════════════════════
// Results Rendering
// ══════════════════════════════════════════════════════════════
function showResults(result) {
    // Reset button
    const btnContent = DOM.btnTranscribe.querySelector('.btn-content');
    const btnLoader = DOM.btnTranscribe.querySelector('.btn-loader');
    btnContent.style.display = 'flex';
    btnLoader.style.display = 'none';
    DOM.btnTranscribe.disabled = false;

    DOM.progressSection.style.display = 'none';
    DOM.resultsSection.style.display = '';
    DOM.errorSection.style.display = 'none';

    const meta = result.metadata || {};
    const speakers = result.speakers || [];
    const segments = result.segments || [];

    // Show/hide diarization warning banner
    if (meta.diarizationError) {
        DOM.warningMessageText.textContent = meta.diarizationError;
        DOM.warningBanner.style.display = 'flex';
    } else {
        DOM.warningBanner.style.display = 'none';
    }

    // Stats
    DOM.statDuration.textContent = meta.totalDurationFormatted || '--';
    DOM.statSpeakers.textContent = meta.totalSpeakers || 0;
    DOM.statSegments.textContent = meta.totalSegments || 0;
    DOM.statLanguage.textContent = (meta.language || '--').toUpperCase();

    // Speaker legend
    DOM.speakerLegend.innerHTML = '';
    DOM.filterSpeaker.innerHTML = '<option value="">All Speakers</option>';
    speakers.forEach(s => {
        const chip = document.createElement('div');
        chip.className = 'speaker-chip';
        chip.innerHTML = `
            <span class="speaker-dot" style="background:${s.color}"></span>
            <span>${s.emoji} ${s.id}</span>
            <span class="speaker-chip-duration">${formatDuration(s.totalDuration)}</span>
        `;
        chip.addEventListener('click', () => {
            DOM.filterSpeaker.value = s.id;
            filterTranscript();
        });
        DOM.speakerLegend.appendChild(chip);

        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = `${s.emoji} ${s.id}`;
        DOM.filterSpeaker.appendChild(opt);
    });

    // Render transcript
    renderTranscript(segments);

    // Scroll to results
    DOM.resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderTranscript(segments, searchTerm = '', speakerFilter = '') {
    DOM.timeline.innerHTML = '';

    let filtered = segments;

    if (speakerFilter) {
        filtered = filtered.filter(s => s.speaker === speakerFilter);
    }
    if (searchTerm) {
        const term = searchTerm.toLowerCase();
        filtered = filtered.filter(s => s.text.toLowerCase().includes(term));
    }

    if (filtered.length === 0) {
        DOM.timeline.innerHTML = '<div class="no-results">No matching segments found.</div>';
        return;
    }

    filtered.forEach((seg, i) => {
        const div = document.createElement('div');
        div.className = 'segment';
        div.style.animationDelay = `${Math.min(i * 20, 500)}ms`;

        const initials = seg.speaker.replace('SPEAKER_', 'S');

        let textHtml = '';
        if (seg.words && seg.words.length > 0) {
            textHtml = seg.words.map(w => {
                const wordEscaped = escapeHtml(w.word);
                const isSearchMatch = searchTerm && w.word.toLowerCase().includes(searchTerm.toLowerCase());
                const highlightedWord = isSearchMatch ? `<mark>${wordEscaped}</mark>` : wordEscaped;
                
                const startFmt = formatTimeCode(w.start);
                const endFmt = formatTimeCode(w.end);
                const tooltip = `${startFmt} → ${endFmt}`;
                
                return `<span class="word-span" title="${tooltip}">${highlightedWord}</span>`;
            }).join(' ');
        } else {
            textHtml = escapeHtml(seg.text);
            if (searchTerm) {
                const re = new RegExp(`(${escapeRegExp(searchTerm)})`, 'gi');
                textHtml = textHtml.replace(re, '<mark>$1</mark>');
            }
        }

        div.innerHTML = `
            <div class="segment-speaker">
                <div class="segment-avatar" style="background:${seg.speakerColor}">${initials}</div>
                <span class="segment-speaker-label">${seg.speaker}</span>
            </div>
            <div class="segment-content">
                <div class="segment-time">${seg.startFormatted} → ${seg.endFormatted}</div>
                <div class="segment-text">${textHtml}</div>
            </div>
            <button class="segment-copy" title="Copy text" onclick="copySegment(${seg.id})">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
            </button>
        `;
        DOM.timeline.appendChild(div);
    });
}

// ══════════════════════════════════════════════════════════════
// Search & Filter
// ══════════════════════════════════════════════════════════════
let searchDebounce = null;
DOM.searchInput.addEventListener('input', () => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(filterTranscript, 250);
});
DOM.filterSpeaker.addEventListener('change', filterTranscript);

function filterTranscript() {
    if (!state.result) return;
    renderTranscript(
        state.result.segments,
        DOM.searchInput.value.trim(),
        DOM.filterSpeaker.value
    );
}

// ══════════════════════════════════════════════════════════════
// Export & Copy
// ══════════════════════════════════════════════════════════════
DOM.btnDownloadMd.addEventListener('click', () => {
    if (!state.currentJobId) return;
    window.open(`/api/transcribe/${state.currentJobId}/download`, '_blank');
});

DOM.btnDownloadSrt.addEventListener('click', () => {
    if (!state.currentJobId) return;
    window.open(`/api/transcribe/${state.currentJobId}/download/srt`, '_blank');
});

DOM.btnDownloadVtt.addEventListener('click', () => {
    if (!state.currentJobId) return;
    window.open(`/api/transcribe/${state.currentJobId}/download/vtt`, '_blank');
});

DOM.btnDownloadTxt.addEventListener('click', () => {
    if (!state.currentJobId) return;
    window.open(`/api/transcribe/${state.currentJobId}/download/txt`, '_blank');
});

DOM.btnCopyAll.addEventListener('click', () => {
    if (!state.result) return;
    const segments = state.result.segments || [];
    const text = segments.map(s =>
        `[${s.startFormatted}] ${s.speaker}: ${s.text}`
    ).join('\n');
    navigator.clipboard.writeText(text).then(() => {
        DOM.btnCopyAll.textContent = '✓ Copied!';
        setTimeout(() => {
            DOM.btnCopyAll.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>Copy All`;
        }, 2000);
    });
});

window.copySegment = function(segId) {
    if (!state.result) return;
    const seg = state.result.segments.find(s => s.id === segId);
    if (seg) {
        navigator.clipboard.writeText(seg.text);
    }
};

// ══════════════════════════════════════════════════════════════
// Error & Reset
// ══════════════════════════════════════════════════════════════
function showError(message) {
    const btnContent = DOM.btnTranscribe.querySelector('.btn-content');
    const btnLoader = DOM.btnTranscribe.querySelector('.btn-loader');
    btnContent.style.display = 'flex';
    btnLoader.style.display = 'none';
    DOM.btnTranscribe.disabled = false;

    DOM.progressSection.style.display = 'none';
    DOM.resultsSection.style.display = 'none';
    DOM.errorSection.style.display = '';
    DOM.errorMessage.textContent = message;
}

window.resetApp = function() {
    state.currentJobId = null;
    state.result = null;
    if (state.eventSource) { state.eventSource.close(); state.eventSource = null; }

    DOM.progressSection.style.display = 'none';
    DOM.resultsSection.style.display = 'none';
    DOM.warningBanner.style.display = 'none';
    DOM.errorSection.style.display = 'none';
    DOM.progressFill.style.width = '0%';
    DOM.progressPercent.textContent = '0%';

    document.querySelectorAll('.step').forEach(s => s.classList.remove('active', 'completed'));

    DOM.optCookiesFile.value = '';
    DOM.optTranslateLang.value = '';
    DOM.inputSection.scrollIntoView({ behavior: 'smooth' });
};

// ══════════════════════════════════════════════════════════════
// Helpers
// ══════════════════════════════════════════════════════════════
function formatDuration(seconds) {
    if (!seconds || seconds < 0) return '0s';
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function formatTimeCode(seconds) {
    if (seconds === null || seconds === undefined || seconds < 0) return '00:00.000';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);
    
    const pad = (num, len = 2) => String(num).padStart(len, '0');
    
    if (h > 0) {
        return `${pad(h)}:${pad(m)}:${pad(s)}.${pad(ms, 3)}`;
    }
    return `${pad(m)}:${pad(s)}.${pad(ms, 3)}`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeRegExp(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ══════════════════════════════════════════════════════════════
// Init: fetch health to set badges
// ══════════════════════════════════════════════════════════════
fetch('/api/health').then(r => r.json()).then(data => {
    $('badge-device').querySelector('span:last-child') || null;
    const deviceText = data.device === 'cuda' ? 'GPU Mode' : 'CPU Mode';
    $('badge-device').innerHTML = `<span class="badge-dot"></span>${deviceText}`;
    $('badge-model').textContent = `${data.model} model`;
}).catch(() => {});
