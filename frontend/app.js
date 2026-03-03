document.addEventListener('DOMContentLoaded', () => {
    const downloadBtn = document.getElementById('download-btn');
    const urlInput = document.getElementById('video-url');
    const statusMsg = document.getElementById('status-message');
    const btnLoader = document.getElementById('btn-loader');
    const btnText = downloadBtn.querySelector('.btn-text');
    const btnIcon = downloadBtn.querySelector('.btn-icon');
    const resultCard = document.getElementById('result-container');
    const saveLink = document.getElementById('save-link');
    const videoTitle = document.getElementById('video-title');

    const cookieBanner = document.getElementById('cookie-banner');
    const cookieStatusText = document.getElementById('cookie-status-text');
    const cookieFileInput = document.getElementById('cookie-file');
    const uploadLabelText = document.getElementById('upload-label-text');
    const uploadBtn = document.getElementById('upload-btn');
    const cookieMsg = document.getElementById('cookie-msg');

    // ── Cookie status banner ─────────────────────────────────────────────────
    async function checkCookieStatus() {
        try {
            const res = await fetch('/api/cookies-status');
            const data = await res.json();
            if (data.loaded) {
                cookieBanner.className = 'cookie-banner success';
                cookieStatusText.textContent =
                    `✅ Cookies loaded (${(data.size_bytes / 1024).toFixed(1)} KB) — Downloads ready!`;
            } else {
                cookieBanner.className = 'cookie-banner warn';
                cookieStatusText.textContent =
                    '⚠️ No cookies uploaded yet. Use the "Setup Login Cookies" section below to enable downloads.';
            }
            cookieBanner.classList.remove('hidden');
        } catch (e) {
            console.warn('Cookie status check failed:', e);
        }
    }

    checkCookieStatus();

    // ── File picker → show upload button ────────────────────────────────────
    cookieFileInput.addEventListener('change', () => {
        const file = cookieFileInput.files[0];
        if (file) {
            uploadLabelText.innerHTML = `📄 <strong>${file.name}</strong>`;
            uploadBtn.classList.remove('hidden');
        }
    });

    // ── Upload cookies.txt ───────────────────────────────────────────────────
    if (uploadBtn) {
        uploadBtn.addEventListener('click', async () => {
            const file = cookieFileInput.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);
            uploadBtn.textContent = 'Uploading...';
            uploadBtn.disabled = true;

            try {
                const res = await fetch('/api/upload-cookies', { method: 'POST', body: formData });
                const data = await res.json();
                if (res.ok) {
                    cookieMsg.textContent = '✅ ' + data.message;
                    cookieMsg.className = 'cookie-msg success';
                    await checkCookieStatus();
                } else {
                    throw new Error(data.detail || 'Upload failed');
                }
            } catch (e) {
                cookieMsg.textContent = '❌ ' + e.message;
                cookieMsg.className = 'cookie-msg error';
            } finally {
                uploadBtn.textContent = 'Upload Cookies File';
                uploadBtn.disabled = false;
            }
        });
    }

    // ── Loading state helpers ────────────────────────────────────────────────
    function setStatus(msg, type = 'info') {
        statusMsg.textContent = msg;
        statusMsg.className = `status-message ${msg ? type : ''}`;
    }

    function setLoading(on) {
        downloadBtn.disabled = on;
        btnLoader.style.display = on ? 'block' : 'none';
        btnText.style.display = on ? 'none' : 'block';
        if (btnIcon) btnIcon.style.display = on ? 'none' : 'block';
        if (!on && resultCard) resultCard.classList.remove('hidden');
    }

    // ── Main download handler ────────────────────────────────────────────────
    async function handleDownload() {
        const url = urlInput.value.trim();

        if (!url) {
            setStatus('Please paste an Instagram URL first.', 'error');
            return;
        }
        if (!url.includes('instagram.com')) {
            setStatus('Please enter a valid Instagram link.', 'error');
            return;
        }

        setLoading(true);
        if (resultCard) resultCard.classList.add('hidden');
        setStatus('Fetching video info… this may take 5–15 seconds.', 'info');

        try {
            const formData = new FormData();
            formData.append('url', url);

            const response = await fetch('/api/download', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                let errMsg = 'Download failed. Please check the URL and try again.';
                try {
                    const errData = await response.json();
                    errMsg = errData.detail || errMsg;
                } catch (_) { }
                throw new Error(errMsg);
            }

            // Stream the blob
            const blob = await response.blob();
            const downloadUrl = URL.createObjectURL(blob);

            // Parse filename from Content-Disposition
            const cd = response.headers.get('Content-Disposition') || '';
            let filename = 'instagram_video.mp4';
            const fmatch = cd.match(/filename\*?=(?:UTF-8'')?["']?([^"';\n]+)["']?/i);
            if (fmatch && fmatch[1]) {
                try { filename = decodeURIComponent(fmatch[1].trim()); }
                catch (_) { filename = fmatch[1].trim(); }
            }
            if (!filename.toLowerCase().endsWith('.mp4')) filename += '.mp4';

            // ── Auto-trigger download via dynamic anchor (most reliable) ───────
            const tempLink = document.createElement('a');
            tempLink.href = downloadUrl;
            tempLink.download = filename;
            tempLink.style.display = 'none';
            document.body.appendChild(tempLink);
            tempLink.click();
            document.body.removeChild(tempLink);
            // Revoke blob URL after delay to free memory
            setTimeout(() => URL.revokeObjectURL(downloadUrl), 10000);

            setStatus('✅ Your video is downloading as: ' + filename, 'success');
            if (videoTitle) videoTitle.textContent = filename;
            // Keep save-link as backup
            if (saveLink) {
                saveLink.href = downloadUrl;
                saveLink.setAttribute('download', filename);
            }

            if (resultCard) {
                resultCard.classList.remove('hidden');
                setTimeout(() => resultCard.scrollIntoView({ behavior: 'smooth', block: 'center' }), 100);
            }
        } catch (err) {
            console.error('[InstaSnap] Download error:', err);
            setStatus(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }

    downloadBtn.addEventListener('click', handleDownload);
    urlInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handleDownload();
    });
});
