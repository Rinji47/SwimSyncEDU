const poolsStatus = document.getElementById("poolsStatus");
const requestLocationBtn = document.getElementById("requestLocationBtn");
const showAllPoolsBtn = document.getElementById("showAllPoolsBtn");
const poolCards = Array.from(document.querySelectorAll(".pool-card"));

function parseCoordinates(raw) {
    if (!raw) return null;
    const cleaned = raw.replace(/\s+/g, "");
    const parts = cleaned.split(",");
    if (parts.length !== 2) return null;
    const lat = Number(parts[0]);
    const lng = Number(parts[1]);
    if (Number.isNaN(lat) || Number.isNaN(lng)) return null;
    return { lat, lng };
}

function haversineKm(lat1, lon1, lat2, lon2) {
    const toRad = (value) => (value * Math.PI) / 180;
    const r = 6371;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a =
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return r * c;
}

function showAll(message) {
    if (poolsStatus) {
        poolsStatus.textContent = message;
    }
    poolCards.forEach((card) => {
        card.style.display = "";
    });
}

function showNearby(lat, lng) {
    let nearbyCount = 0;

    poolCards.forEach((card) => {
        const coords = parseCoordinates(card.dataset.coordinates);
        if (!coords) {
            card.style.display = "none";
            return;
        }
        const distance = haversineKm(lat, lng, coords.lat, coords.lng);
        if (distance <= 10) {
            card.style.display = "";
            nearbyCount += 1;
        } else {
            card.style.display = "none";
        }
    });

    if (nearbyCount === 0) {
        showAll("No pools within 10 km. Showing all pools instead.");
    } else if (poolsStatus) {
        poolsStatus.textContent = `Showing ${nearbyCount} pool${nearbyCount === 1 ? "" : "s"} within 10 km.`;
    }
}

function requestLocation() {
    if (!navigator.geolocation) {
        showAll("Location is not supported by your browser. Showing all pools.");
        return;
    }

    poolsStatus.textContent = "Finding pools near you...";

    navigator.geolocation.getCurrentPosition(
        (position) => {
            showNearby(position.coords.latitude, position.coords.longitude);
        },
        () => {
            showAll("We could not access your location. Showing all pools.");
        },
        {
            enableHighAccuracy: true,
            timeout: 8000,
            maximumAge: 0,
        }
    );
}

if (requestLocationBtn) {
    requestLocationBtn.addEventListener("click", requestLocation);
}

if (showAllPoolsBtn) {
    showAllPoolsBtn.addEventListener("click", () => {
        showAll("Showing all pools.");
    });
}

if (poolCards.length) {
    requestLocation();
} else if (poolsStatus) {
    poolsStatus.textContent = "No pools available yet.";
}
