function toggleModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    if (modal.classList.contains("show")) {
        modal.classList.remove("show");

        setTimeout(() => {
            modal.style.display = "none";
            resetModalFields(modal);
        }, 300);
    } else {
        modal.style.display = "block";

        setTimeout(() => {
            modal.classList.add("show");
        }, 300);
    }
}

window.addEventListener("click", (event) => {
    if (event.target.classList.contains("modal")) {
        toggleModal(event.target.id);
    }
});

function resetModalFields(modal) {
    const form = modal.querySelector("form");
    if (!form) return;

    form.reset();
    const defaultAction = form.dataset.defaultAction;
    if (defaultAction) {
        form.action = defaultAction;
    }
}

let map = null;
let marker = null;

function initMap() {
    const mapDiv = document.getElementById("map");
    if (!mapDiv || !window.google || !window.google.maps) {
        return;
    }

    const coordInput = document.getElementById("coordinates");
    const rawCoord = coordInput ? coordInput.value.trim() : "";

    const fallbackLoc = { lat: 28.2096, lng: 83.9856 };
    let initialLoc = fallbackLoc;

    if (rawCoord) {
        const parts = rawCoord.split(",");
        if (parts.length === 2) {
            const lat = parseFloat(parts[0]);
            const lng = parseFloat(parts[1]);
            if (!Number.isNaN(lat) && !Number.isNaN(lng)) {
                initialLoc = { lat, lng };
            }
        }
    }

    map = new google.maps.Map(mapDiv, {
        zoom: 13,
        center: initialLoc,
    });

    marker = new google.maps.Marker({
        position: initialLoc,
        map,
        draggable: true,
    });

    map.addListener("click", (e) => {
        setMarker(e.latLng.lat(), e.latLng.lng());
    });

    marker.addListener("dragend", (e) => {
        setMarker(e.latLng.lat(), e.latLng.lng());
    });

    if (!rawCoord) {
        setDefaultLocation();
    }
}

function setDefaultLocation() {
    if (!navigator.geolocation || !map || !marker) return;

    navigator.geolocation.getCurrentPosition(
        (position) => {
            const currentLoc = {
                lat: position.coords.latitude,
                lng: position.coords.longitude,
            };
            map.setCenter(currentLoc);
            marker.setPosition(currentLoc);
        },
        () => {
        },
        {
            enableHighAccuracy: true,
            timeout: 8000,
            maximumAge: 0,
        }
    );
}

function setMarker(lat, lng) {
    if (!marker) {
        return;
    }

    marker.setPosition({ lat, lng });

    const coordInput = document.getElementById("coordinates");
    const coordDisplay = document.getElementById("coordDisplay");

    if (coordInput) {
        coordInput.value = `${lat}, ${lng}`;
    }

    if (coordDisplay) {
        coordDisplay.innerText = `Selected: ${lat.toFixed(6)}, ${lng.toFixed(6)}`;
    }
}
