let currentPage = 1;

async function updateSnapshots(page = 1) {
    try {
        const response = await fetch(`/snapshots?page=${page}`);
        const data = await response.json();
        const list = document.getElementById('snapshot-list');
        const count = document.getElementById('snapshot-count');
        const loadMoreBtn = document.getElementById('load-more');

        if (page === 1) list.innerHTML = '';
        count.textContent = data.total;

        data.snapshots.forEach(snapshot => {
            const li = document.createElement('li');
            const link = document.createElement('a');
            link.href = '#';
            link.textContent = snapshot;
            link.className = 'link';
            link.addEventListener('click', (e) => {
                e.preventDefault();
                showSnapshotPreview(`/snapshots/${snapshot}`);
            });
            li.appendChild(link);
            list.appendChild(li);
        });

        loadMoreBtn.style.display = data.has_more ? 'block' : 'none';
        if (data.has_more) currentPage = page;
    } catch (error) {
        console.error('Error fetching snapshots:', error);
        alert('Failed to fetch snapshots');
    }
}

async function clearSnapshots() {
    if (confirm('Are you sure you want to delete all snapshots? This cannot be undone.')) {
        try {
            const response = await fetch('/clear_snapshots', { method: 'POST' });
            const result = await response.json();
            if (response.ok) {
                alert(result.message || 'All snapshots deleted');
                updateSnapshots(1);
            } else {
                alert(result.message || 'Failed to delete snapshots');
            }
        } catch (error) {
            console.error('Error deleting snapshots:', error);
            alert('Failed to delete snapshots');
        }
    }
}

function showSnapshotPreview(url) {
    const img = document.getElementById('snapshot-preview');
    img.src = url;
    const modal = new bootstrap.Modal(document.getElementById('snapshot-modal'));
    modal.show();
}

async function updateLogs() {
    try {
        const response = await fetch('/logs');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const logs = await response.json();
        const logList = document.getElementById('log-list');
        logList.innerHTML = '';
        logs.forEach(log => {
            const li = document.createElement('li');
            li.textContent = log;
            logList.appendChild(li);
        });
    } catch (error) {
        console.error('Error fetching logs:', error);
        document.getElementById('log-list').innerHTML = '<li>Error loading logs</li>';
    }
}

async function updateMetadata() {
    try {
        const response = await fetch('/camera_metadata');
        const data = await response.json();
        document.getElementById('meta-resolution').textContent = data.resolution || 'N/A';
        document.getElementById('meta-timestamp').textContent = data.timestamp || 'N/A';
        document.getElementById('meta-fps').textContent = data.frame_rate || 'N/A';
    } catch (error) {
        console.error('Error fetching metadata:', error);
        alert('Failed to fetch camera metadata');
    }
}

async function loadCameraParams() {
    try {
        const response = await fetch('/camera_params');
        const data = await response.json();
        document.getElementById('resolution').value = data.resolution || '640x480';
        document.getElementById('fps').value = data.fps;
        document.getElementById('motion_threshold').value = data.motion_threshold;
        document.getElementById('min_motion_area').value = data.min_motion_area;
    } catch (error) {
        console.error('Error loading camera params:', error);
        alert('Failed to load camera parameters');
    }
}

async function updateCameraControls(retries = 3, delay = 1000) {
    const form = document.getElementById('camera-controls-form');
    let loadingDiv = document.getElementById('controls-loading');
    if (!loadingDiv) {
        loadingDiv = document.createElement('div');
        loadingDiv.id = 'controls-loading';
        loadingDiv.className = 'text-muted';
        loadingDiv.textContent = 'Loading controls...';
        form.parentNode.insertBefore(loadingDiv, form);
    }

    for (let attempt = 1; attempt <= retries; attempt++) {
        try {
            const response = await fetch('/camera_controls');
            if (!response.ok) throw new Error(`HTTP error ${response.status}`);
            const data = await response.json();
            form.innerHTML = '';
            loadingDiv.style.display = 'none';

            if (data.error) {
                form.innerHTML = `<p class="error">${data.error}</p>`;
                return;
            }

            data.controls.forEach(control => {
                const div = document.createElement('div');
                div.className = 'control-group';

                const label = document.createElement('label');
                label.htmlFor = control.name;
                label.textContent = `${control.name} (Default: ${control.default})`;

                let input;
                if (control.type === 'int') {
                    const controlGroup = document.createElement('div');
                    controlGroup.className = 'slider-group';

                    input = document.createElement('input');
                    input.type = 'range';
                    input.id = control.name;
                    input.name = control.name;
                    input.min = control.min;
                    input.max = control.max;
                    input.step = control.step || 1;
                    input.value = control.value;

                    const numberDisplay = document.createElement('span');
                    numberDisplay.id = `${control.name}-value`;
                    numberDisplay.className = 'value-display';
                    numberDisplay.textContent = control.value;

                    input.addEventListener('input', () => {
                        numberDisplay.textContent = input.value;
                    });

                    controlGroup.appendChild(input);
                    controlGroup.appendChild(numberDisplay);
                    div.appendChild(label);
                    div.appendChild(controlGroup);
                } else if (control.type === 'bool') {
                    input = document.createElement('input');
                    input.type = 'checkbox';
                    input.id = control.name;
                    input.name = control.name;
                    input.checked = control.value === '1' || control.value === 1;

                    const checkDiv = document.createElement('div');
                    checkDiv.className = 'form-check';
                    checkDiv.appendChild(input);
                    checkDiv.appendChild(label.cloneNode(true));
                    label.style.display = 'none';
                    div.appendChild(checkDiv);
                }

                if (input) {
                    div.appendChild(label);
                    form.appendChild(div);
                }
            });

            const submitBtn = document.createElement('button');
            submitBtn.type = 'submit';
            submitBtn.className = 'app-btn btn-primary btn-sm';
            submitBtn.textContent = 'Apply';
            form.appendChild(submitBtn);

            const resetBtn = document.createElement('button');
            resetBtn.type = 'button';
            resetBtn.className = 'app-btn btn-outline btn-sm';
            resetBtn.textContent = 'Reset to Default';
            resetBtn.addEventListener('click', async () => {
                try {
                    const response = await fetch('/reset_camera_params', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    const result = await response.json();
                    if (response.ok) {
                        alert(result.message || 'Camera parameters reset');
                        await updateCameraControls();
                        await loadCameraParams();
                    } else {
                        alert(result.message || 'Failed to reset parameters');
                    }
                } catch (error) {
                    console.error('Error resetting camera params:', error);
                    alert('Failed to reset camera parameters');
                }
            });
            form.appendChild(resetBtn);

            const nightVisionBtn = document.createElement('button');
            nightVisionBtn.type = 'button';
            nightVisionBtn.className = 'app-btn btn-primary btn-sm';
            nightVisionBtn.textContent = 'Night Vision';
            nightVisionBtn.addEventListener('click', async () => {
                try {
                    const response = await fetch('/night_vision', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    const result = await response.json();
                    if (response.ok) {
                        alert(result.message || 'Night vision settings applied');
                        await updateCameraControls();
                    } else {
                        alert(result.message || 'Failed to apply night vision');
                    }
                } catch (error) {
                    console.error('Error applying night vision:', error);
                    alert('Failed to apply night vision settings');
                }
            });
            form.appendChild(nightVisionBtn);

            return;
        } catch (error) {
            console.error(`Attempt ${attempt}/${retries} failed: ${error.message}`);
            if (attempt === retries) {
                form.innerHTML = `<p class="error">Failed to load controls after ${retries} attempts: ${error.message}</p>`;
                loadingDiv.style.display = 'none';
            } else {
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }
    }
}

document.getElementById('video-feed').addEventListener('click', () => {
    const videoContainer = document.getElementById('video-feed-container');
    if (!document.fullscreenElement) {
        videoContainer.requestFullscreen().catch(err => {
            console.error(`Error enabling full-screen: ${err.message}`);
        });
    } else {
        document.exitFullscreen().catch(err => {
            console.error(`Error exiting full-screen: ${err.message}`);
        });
    }
});

document.getElementById('camera-params-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = {
        resolution: document.getElementById('resolution').value,
        fps: parseInt(document.getElementById('fps').value),
        motion_threshold: parseInt(document.getElementById('motion_threshold').value),
        min_motion_area: parseInt(document.getElementById('min_motion_area').value)
    };
    if (Object.values(formData).some(v => !v || (typeof v === 'number' && v <= 0))) {
        alert('All values must be valid and positive');
        return;
    }
    try {
        const response = await fetch('/camera_params', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        const result = await response.json();
        alert(result.message || 'Parameters updated');
        updateMetadata();
    } catch (error) {
        console.error('Error updating camera params:', error);
        alert('Failed to update parameters');
    }
});

document.getElementById('camera-controls-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = new FormData(document.getElementById('camera-controls-form'));
    const formData = {};
    form.forEach((value, key) => {
        const input = document.getElementById(key);
        formData[key] = input.type === 'checkbox' ? (input.checked ? 1 : 0) : parseInt(value, 10);
    });
    try {
        const response = await fetch('/camera_controls', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        const result = await response.json();
        if (response.ok) {
            alert(result.message || 'Controls updated successfully');
            await updateCameraControls();
        } else {
            alert(result.message || 'Failed to update controls');
        }
    } catch (error) {
        console.error('Error updating camera controls:', error);
        alert('Failed to update camera controls: ' + error.message);
    }
});

document.getElementById('clear-snapshots').addEventListener('click', clearSnapshots);

const toggle = document.getElementById('timelapse-toggle');
const settings = document.getElementById('timelapse-settings');
const status = document.getElementById('timelapse-status');

toggle.addEventListener('change', async () => {
    const interval = parseFloat(document.getElementById('interval').value);
    const num_images = parseInt(document.getElementById('num_images').value);

    if (interval <= 0 || num_images <= 0) {
        alert('Interval and number of images must be positive');
        toggle.checked = false;
        return;
    }

    if (toggle.checked) {
        settings.classList.remove('hidden');
        const response = await fetch('/start_time_lapse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ interval, num_images })
        });
        const result = await response.json();
        status.textContent = result.message;
        if (!response.ok) {
            toggle.checked = false;
            settings.classList.add('hidden');
        }
    } else {
        settings.classList.add('hidden');
        const response = await fetch('/stop_time_lapse', { method: 'POST' });
        const result = await response.json();
        status.textContent = result.message;
    }
});

document.getElementById('load-more').addEventListener('click', () => {
    updateSnapshots(currentPage + 1);
});

setInterval(() => updateSnapshots(1), 5000);
setInterval(updateLogs, 5000);
setInterval(updateMetadata, 5000);
updateSnapshots(1);
updateLogs();
updateMetadata();
loadCameraParams();
updateCameraControls();