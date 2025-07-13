let currentPage = 1;
let zoomLevel = 1;
let lastLogLength = 0;

async function updateSnapshots(page = 1) {
    try {
        console.log(`Fetching snapshots for page ${page}`);
        const response = await fetch(`/snapshots?page=${page}`);
        console.log(`Snapshots response status: ${response.status}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        console.log('Snapshots data:', data);
        const list = document.getElementById('snapshot-list');
        const count = document.getElementById('snapshot-count');
        const loadMoreBtn = document.getElementById('load-more');

        if (page === 1) list.innerHTML = '';
        count.textContent = data.total || 0;

        data.snapshots.forEach(snapshot => {
            const img = document.createElement('img');
            img.src = `/snapshots/${snapshot}`;
            img.className = 'snapshot-img';
            img.alt = snapshot;
            img.addEventListener('click', () => showSnapshotPreview(`/snapshots/${snapshot}`));
            list.appendChild(img);
        });

        loadMoreBtn.style.display = data.has_more ? 'block' : 'none';
        if (data.has_more) currentPage = page;
    } catch (error) {
        console.error('Error fetching snapshots:', error);
        document.getElementById('snapshot-list').innerHTML = '<p class="error">Failed to load snapshots. Check server connection.</p>';
    }
}

async function clearSnapshots() {
    if (confirm('Are you sure you want to delete all snapshots? This cannot be undone.')) {
        try {
            console.log('Clearing snapshots');
            const response = await fetch('/clear_snapshots', { method: 'POST' });
            const result = await response.json();
            console.log('Clear snapshots result:', result);
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
    console.log('Showing snapshot preview:', url);
    const img = document.getElementById('snapshot-preview');
    img.src = url;
    zoomLevel = 1;
    img.style.transform = `scale(${zoomLevel})`;
    const modal = new bootstrap.Modal(document.getElementById('snapshot-modal'));
    modal.show();
}

function handleZoom(event) {
    event.preventDefault();
    const img = document.getElementById('snapshot-preview');
    const delta = event.deltaY > 0 ? -0.1 : 0.1;
    zoomLevel = Math.max(0.5, Math.min(zoomLevel + delta, 3));
    img.style.transform = `scale(${zoomLevel})`;
}

async function updateLogs() {
    try {
        console.log('Fetching logs');
        const response = await fetch('/logs');
        console.log(`Logs response status: ${response.status}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const logs = await response.json();
        console.log('Logs data:', logs);
        if (logs.length !== lastLogLength) {
            const logList = document.getElementById('log-list');
            logList.innerHTML = '';
            logs.forEach(log => {
                const li = document.createElement('li');
                li.textContent = log;
                logList.appendChild(li);
            });
            lastLogLength = logs.length;
        }
    } catch (error) {
        console.error('Error fetching logs:', error);
        document.getElementById('log-list').innerHTML = '<li class="error">Error loading logs</li>';
    }
}

async function updateDetections() {
    try {
        console.log('Fetching detections');
        const response = await fetch('/inference_data');
        console.log(`Detections response status: ${response.status}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const detections = await response.json();
        console.log('Detections data:', detections);
        const list = document.getElementById('detections-list');
        list.innerHTML = '';
        detections.forEach(d => {
            const li = document.createElement('li');
            li.className = 'detection-item';
            const timestamp = new Date().toISOString().replace('T', ' ').slice(0, 19);
            li.textContent = `${timestamp}: ${d.category} - ${d.label} (${d.confidence.toFixed(2)})`;
            list.appendChild(li);
        });
        if (detections.length === 0) {
            list.innerHTML = '<li>No detections available</li>';
        }
    } catch (error) {
        console.error('Error fetching detections:', error);
        document.getElementById('detections-list').innerHTML = '<li class="error">Error loading detections. Check server connection.</li>';
    }
}

async function runDiagnostics() {
    try {
        console.log('Running diagnostics');
        const response = await fetch('/diagnostics');
        console.log(`Diagnostics response status: ${response.status}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        console.log('Diagnostics data:', data);
        const diagnosticsDiv = document.getElementById('diagnostics');
        diagnosticsDiv.innerHTML = '<h5>Diagnostics</h5>';
        for (const [key, value] of Object.entries(data.diagnostics)) {
            const p = document.createElement('p');
            p.textContent = `${key}: ${value}`;
            diagnosticsDiv.appendChild(p);
        }
        if (data.suggestions && data.suggestions.length > 0) {
            diagnosticsDiv.innerHTML += '<h5>Suggestions</h5>';
            const ul = document.createElement('ul');
            data.suggestions.forEach(s => {
                const li = document.createElement('li');
                li.textContent = s;
                ul.appendChild(li);
            });
            diagnosticsDiv.appendChild(ul);
        }
    } catch (error) {
        console.error('Error running diagnostics:', error);
        document.getElementById('diagnostics').innerHTML = `<p class="error">Error: ${error.message}</p>`;
    }
}

async function loadCameraParams() {
    try {
        console.log('Loading camera parameters');
        const response = await fetch('/camera_params');
        console.log(`Camera params response status: ${response.status}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        console.log('Camera params data:', data);
        const resolutionSelect = document.getElementById('resolution');
        resolutionSelect.value = `${data.width}x${data.height}` || '640x480';
        document.getElementById('fps').value = data.fps || 30;
        document.getElementById('motion_threshold').value = data.motion_threshold || 25;
        document.getElementById('min_motion_area').value = data.min_motion_area || 500;
    } catch (error) {
        console.error('Error loading camera params:', error);
        document.getElementById('camera-params-form').innerHTML += `<p class="error">Error loading parameters</p>`;
    }
}

async function updateCurrentTiltAngle() {
    try {
        console.log('Fetching current tilt angle');
        const response = await fetch('/get_tilt');
        console.log(`Get tilt response status: ${response.status}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        console.log('Get tilt data:', data);
        const currentTiltSpan = document.getElementById('current-tilt-angle');
        if (data.angle !== undefined) {
            currentTiltSpan.textContent = data.angle.toFixed(1);
            currentTiltSpan.style.color = 'black';
        } else {
            currentTiltSpan.textContent = 'error';
            currentTiltSpan.style.color = 'red';
        }
    } catch (error) {
        console.error('Error fetching tilt angle:', error);
        document.getElementById('current-tilt-angle').textContent = 'error';
        document.getElementById('current-tilt-angle').style.color = 'red';
    }
}

function toggleFullScreen() {
    const videoContainer = document.getElementById('video-feed-container');
    const toggleButton = document.getElementById('fullscreen-toggle');

    if (!document.fullscreenElement) {
        videoContainer.requestFullscreen().then(() => {
            toggleButton.textContent = 'Exit Full Screen';
        }).catch(err => {
            console.error(`Error enabling full-screen: ${err.message}`);
        });
    } else {
        document.exitFullscreen().then(() => {
            toggleButton.textContent = 'Full Screen';
        }).catch(err => {
            console.error(`Error exiting full-screen: ${err.message}`);
        });
    }
}

function updateVideoFeed() {
    const mode = document.getElementById('video-mode').value;
    const colormap = document.getElementById('colormap').value;
    const depthObjectDetection = document.getElementById('depth-object-detection').checked;
    const trackingEnabled = document.getElementById('tracking-enabled').checked;
    const videoFeed = document.getElementById('video-feed');
    const newSrc = `/video_feed?mode=${mode}&colormap=${colormap}&depth_object_detection=${depthObjectDetection}&tracking_enabled=${trackingEnabled}`;
    
    console.log('Updating video feed with src:', newSrc);
    videoFeed.onerror = () => {
        videoFeed.src = '';
        videoFeed.alt = 'Camera Offline';
        videoFeed.style.display = 'none';
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        errorDiv.textContent = 'Camera Offline';
        videoFeed.parentElement.appendChild(errorDiv);
    };

    videoFeed.onload = () => {
        videoFeed.style.display = 'block';
        const errorDiv = videoFeed.parentElement.querySelector('.error');
        if (errorDiv) errorDiv.remove();
    };

    videoFeed.src = newSrc;
}

async function setTiltAngle() {
    const angle = document.getElementById('tilt-angle').value;
    const currentTiltSpan = document.getElementById('current-tilt-angle');
    try {
        console.log('Setting tilt angle:', angle);
        const response = await fetch('/set_tilt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ angle: parseFloat(angle) })
        });
        const result = await response.json();
        console.log('Set tilt result:', result);
        if (!response.ok) {
            alert(result.error || 'Failed to set tilt angle');
            currentTiltSpan.style.color = 'red';
        } else {
            currentTiltSpan.style.color = 'black';
            updateCurrentTiltAngle();
        }
    } catch (error) {
        console.error('Error setting tilt angle:', error);
        alert('Failed to set tilt angle: Network or server error');
        currentTiltSpan.style.color = 'red';
    }
}

async function startTimeLapse() {
    const interval = parseFloat(document.getElementById('timelapse-interval').value);
    const numImages = parseInt(document.getElementById('timelapse-num-images').value, 10);
    const mode = document.getElementById('video-mode').value;
    const colormap = document.getElementById('colormap').value;
    const startBtn = document.getElementById('start-timelapse-btn');
    const stopBtn = document.getElementById('stop-timelapse-btn');

    if (interval <= 0 || numImages <= 0) {
        alert('Interval and number of images must be positive');
        return;
    }

    try {
        console.log('Starting time-lapse:', { interval, numImages, mode, colormap });
        startBtn.disabled = true;
        stopBtn.disabled = false;
        const response = await fetch('/start_time_lapse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ interval, num_images: numImages, mode, colormap })
        });
        const result = await response.json();
        console.log('Start time-lapse result:', result);
        if (!response.ok) {
            alert(result.message || 'Failed to start time-lapse');
            startBtn.disabled = false;
            stopBtn.disabled = true;
        } else {
            alert(result.message || 'Time-lapse started');
        }
    } catch (error) {
        console.error('Error starting time-lapse:', error);
        alert('Failed to start time-lapse');
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }
}

async function stopTimeLapse() {
    const startBtn = document.getElementById('start-timelapse-btn');
    const stopBtn = document.getElementById('stop-timelapse-btn');
    try {
        console.log('Stopping time-lapse');
        const response = await fetch('/stop_time_lapse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const result = await response.json();
        console.log('Stop time-lapse result:', result);
        if (!response.ok) {
            alert(result.message || 'Failed to stop time-lapse');
        } else {
            alert(result.message || 'Time-lapse stopped');
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }
    } catch (error) {
        console.error('Error stopping time-lapse:', error);
        alert('Failed to stop time-lapse');
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }
}

document.getElementById('camera-params-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const resolution = document.getElementById('resolution').value.split('x');
    const formData = {
        width: parseInt(resolution[0], 10),
        height: parseInt(resolution[1], 10),
        fps: parseInt(document.getElementById('fps').value, 10),
        motion_threshold: parseInt(document.getElementById('motion_threshold').value, 10),
        min_motion_area: parseInt(document.getElementById('min_motion_area').value, 10)
    };
    try {
        console.log('Submitting camera params:', formData);
        const response = await fetch('/camera_params', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        const result = await response.json();
        console.log('Camera params update result:', result);
        alert(result.message || 'Parameters updated');
        updateVideoFeed();
    } catch (error) {
        console.error('Error updating camera params:', error);
        alert('Failed to update parameters');
    }
});

document.getElementById('clear-snapshots').addEventListener('click', clearSnapshots);
document.getElementById('diagnostics-btn').addEventListener('click', runDiagnostics);
document.getElementById('video-mode').addEventListener('change', updateVideoFeed);
document.getElementById('colormap').addEventListener('change', updateVideoFeed);
document.getElementById('depth-object-detection').addEventListener('change', updateVideoFeed);
document.getElementById('tracking-enabled').addEventListener('change', updateVideoFeed);
document.getElementById('tilt-angle').addEventListener('input', setTiltAngle);
document.getElementById('start-timelapse-btn').addEventListener('click', startTimeLapse);
document.getElementById('stop-timelapse-btn').addEventListener('click', stopTimeLapse);
document.getElementById('snapshot-modal').addEventListener('wheel', handleZoom);
document.getElementById('load-more').addEventListener('click', () => updateSnapshots(currentPage + 1));
document.getElementById('fullscreen-toggle').addEventListener('click', toggleFullScreen);

// Initialize video feed with error handling
function initializeVideoFeed() {
    const videoFeed = document.getElementById('video-feed');
    videoFeed.onerror = () => {
        videoFeed.src = '';
        videoFeed.alt = 'Camera Offline';
        videoFeed.style.display = 'none';
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        errorDiv.textContent = 'Camera Offline';
        videoFeed.parentElement.appendChild(errorDiv);
    };
    videoFeed.onload = () => {
        videoFeed.style.display = 'block';
        const errorDiv = videoFeed.parentElement.querySelector('.error');
        if (errorDiv) errorDiv.remove();
    };
    updateVideoFeed();
}

// Initialize tooltips
document.addEventListener('DOMContentLoaded', () => {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggerList.forEach(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    document.getElementById('stop-timelapse-btn').disabled = true; // Disable stop button initially
});

// Periodic updates
setInterval(() => updateSnapshots(1), 10000);
setInterval(updateLogs, 5000);
setInterval(updateDetections, 2000);
setInterval(updateCurrentTiltAngle, 5000);

// Initial load
initializeVideoFeed();
updateSnapshots(1);
updateLogs();
loadCameraParams();
updateDetections();
updateCurrentTiltAngle();

export function init() {
    console.log("Scripts loaded");
}