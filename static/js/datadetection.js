import { endpoints } from './routing.js';

// Cache for entity images
const imageCache = new Map();

// Fetch an image for detected entities
async function fetchEntityImage(label, category) {
    if (category === "text") {
        return "https://via.placeholder.com/50?text=TEXT";
    }
    const cacheKey = `${category}:${label}`;
    if (imageCache.has(cacheKey)) {
        return imageCache.get(cacheKey);
    }
    try {
        const response = await fetch(`https://en.wikipedia.org/w/api.php?action=query&titles=${encodeURIComponent(label)}&prop=pageimages&format=json&pithumbsize=100&origin=*`);
        const data = await response.json();
        const pages = data.query.pages;
        const pageId = Object.keys(pages)[0];
        const imageUrl = pages[pageId].thumbnail?.source || "https://via.placeholder.com/50?text=OBJ";
        imageCache.set(cacheKey, imageUrl);
        return imageUrl;
    } catch (error) {
        console.error("Error fetching entity image:", error);
        imageCache.set(cacheKey, "https://via.placeholder.com/50?text=OBJ");
        return "https://via.placeholder.com/50?text=OBJ";
    }
}

// Fetch and display detection data
export async function updateDetectionData() {
    try {
        // Fetch detection data
        console.log("Fetching detection data from", endpoints.inferenceData);
        const detectionResponse = await fetch(endpoints.inferenceData);
        if (!detectionResponse.ok) {
            throw new Error(`HTTP error! Status: ${detectionResponse.status}`);
        }
        const detectionData = await detectionResponse.json();

        const detectionInsights = document.getElementById("detection-insights");
        const detectionsTableBody = document.getElementById("detections-table-body");
        const detectionInsightsBox = document.getElementById("detection-insights-box");

        // Show loading spinner
        detectionInsights.innerHTML = '<div class="loading">Loading insights...</div>';
        detectionsTableBody.innerHTML = '<tr><td colspan="4" class="loading">Loading detections...</td></tr>';

        if (!Array.isArray(detectionData) || detectionData.length === 0) {
            detectionInsights.innerHTML = '<p class="error">No detections available</p>';
            detectionsTableBody.innerHTML = '<tr><td colspan="4">No detections available</td></tr>';
            detectionInsightsBox.classList.remove("highlight");
            return;
        }

        // Validate data
        const validData = detectionData.filter(d => d.category && d.label && typeof d.confidence === 'number' && d.priority);

        if (validData.length === 0) {
            detectionInsights.innerHTML = '<p class="error">Invalid detection data</p>';
            detectionsTableBody.innerHTML = '<tr><td colspan="4">Invalid detection data</td></tr>';
            detectionInsightsBox.classList.remove("highlight");
            return;
        }

        // Find highest-priority detection
        const highestPriorityDetection = validData.reduce((prev, current) =>
            (prev.priority === "high" ? prev.confidence : 0) > (current.priority === "high" ? current.confidence : 0) ? prev : current
        );

        // Highlight for high-priority targets
        if (highestPriorityDetection.priority === "high") {
            detectionInsightsBox.classList.add("highlight");
            triggerAlert(highestPriorityDetection);
        } else {
            detectionInsightsBox.classList.remove("highlight");
        }

        // Fetch image for insight card
        const imageUrl = await fetchEntityImage(highestPriorityDetection.label, highestPriorityDetection.category);

        // Create insight card with fade-in
        const timestamp = new Date().toISOString().replace('T', ' ').slice(0, 19);
        const insightCard = document.createElement('div');
        insightCard.className = `insight-card ${highestPriorityDetection.priority}`;
        insightCard.style.opacity = '0';
        insightCard.innerHTML = `
            <img src="${imageUrl}" alt="${highestPriorityDetection.label}">
            <div class="content">
                <h6>DETECTION: ${highestPriorityDetection.category.toUpperCase()} @ ${timestamp}</h6>
                <p>${highestPriorityDetection.category === 'text' ? 'Text' : 'Object'}: ${highestPriorityDetection.label}</p>
                <p>Confidence: ${Math.min(1, Math.max(0, highestPriorityDetection.confidence)).toFixed(2)}</p>
                <p>Priority: ${highestPriorityDetection.priority.toUpperCase()}</p>
            </div>
        `;

        // Update insights section
        detectionInsights.innerHTML = '';
        detectionInsights.appendChild(insightCard);
        requestAnimationFrame(() => {
            insightCard.style.transition = 'opacity 0.5s ease';
            insightCard.style.opacity = '1';
        });

        // Update detections table with fade-in
        const tableRows = validData.slice(-5).map(d => {
            const tr = document.createElement('tr');
            tr.className = d.priority;
            tr.style.opacity = '0';
            tr.innerHTML = `
                <td>${d.category}</td>
                <td class="label-small-font">${d.label}</td>
                <td>${Math.min(1, Math.max(0, d.confidence)).toFixed(2)}</td>
                <td>${d.priority.toUpperCase()}</td>
            `;
            return tr;
        });

        detectionsTableBody.innerHTML = '';
        tableRows.forEach((tr, index) => {
            detectionsTableBody.appendChild(tr);
            requestAnimationFrame(() => {
                tr.style.transition = `opacity 0.5s ease ${index * 0.1}s`;
                tr.style.opacity = '1';
            });
        });

        // Update summary counts
        const counts = {};
        validData.forEach(d => {
            const key = `${d.category}: ${d.label}`;
            counts[key] = (counts[key] || 0) + 1;
        });
        const countsList = document.createElement('ul');
        countsList.className = 'detection-counts';
        for (const [key, count] of Object.entries(counts)) {
            const li = document.createElement('li');
            li.textContent = `${key} - ${count} detection(s)`;
            countsList.appendChild(li);
        }
        detectionInsights.appendChild(countsList);
    } catch (error) {
        console.error("Error updating detection data:", error.message, error.stack);
        document.getElementById("detection-insights").innerHTML = '<p class="error">Error loading insights</p>';
        document.getElementById("detections-table-body").innerHTML = '<tr><td colspan="4" class="error">Error loading detections</td></tr>';
    }
}

// Trigger alert for high-priority targets
let activeAlert = null;
function triggerAlert(detection) {
    if (activeAlert) {
        activeAlert.remove();
        activeAlert = null;
    }
    const alertBox = document.createElement("div");
    alertBox.className = "tactical-alert";
    alertBox.innerHTML = `
        <p>HIGH-PRIORITY DETECTION</p>
        <p>${detection.category.toUpperCase()}: ${detection.label} (${Math.min(1, Math.max(0, detection.confidence)).toFixed(2)})</p>
    `;
    document.body.appendChild(alertBox);
    activeAlert = alertBox;
    setTimeout(() => {
        if (activeAlert === alertBox) {
            alertBox.style.transition = 'opacity 0.5s ease';
            alertBox.style.opacity = '0';
            setTimeout(() => {
                alertBox.remove();
                activeAlert = null;
            }, 500);
        }
    }, 5000);
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    updateDetectionData();
    setInterval(updateDetectionData, 2000); // Update every 2 seconds
});