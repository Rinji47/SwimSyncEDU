// ---------------------- GLOBALS ----------------------
//const google = window.google; // Google Maps

// ---------------------- MODAL UTILS ----------------------
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

            if (modalId === "poolModal") {
                if (!map) {
                    initMap();
                } else {
                    google.maps.event.trigger(map, "resize");
                    map.setCenter(marker?.getPosition() || { lat: 27.7172, lng: 85.3240 });
                }
            }

        }, 300);
    }
}

// Close modal on outside click
window.addEventListener("click", (event) => {
    if (event.target.classList.contains("modal")) {
        toggleModal(event.target.id);
    }
});

// Generic function to reset any modal
function resetModalFields(modal) {
    const form = modal.querySelector("form");
    if (form) form.reset();

    // Reset marker and map only for Pool modal (Add Pool)
    if (modal.id === "poolModal") {
        const defaultLoc = { lat: 27.7172, lng: 85.3240 }; // Kathmandu default
        if (marker) marker.setPosition(defaultLoc);
        if (map) map.setCenter(defaultLoc);

        document.getElementById("coordinates").value = "";
        document.getElementById("coordDisplay").innerText = "Click on the map to select location";
    }
}


// ---------------------- GOOGLE MAPS ----------------------
let map = null;
let marker = null;

function initMap() {
    const mapDiv = document.getElementById("map");
    if (!mapDiv) return; // Wait for the modal to open or map div to exist

    const defaultLoc = { lat: 27.7172, lng: 85.3240 }; // Kathmandu

    map = new google.maps.Map(mapDiv, {
        zoom: 13,
        center: defaultLoc,
    });

    marker = new google.maps.Marker({
        position: defaultLoc,
        map,
        draggable: true,
    });

    map.addListener("click", (e) => {
        setMarker(e.latLng.lat(), e.latLng.lng());
    });

    marker.addListener("dragend", (e) => {
        setMarker(e.latLng.lat(), e.latLng.lng());
    });
}

function setMarker(lat, lng) {
    if (!marker) return;

    marker.setPosition({ lat, lng });
    document.getElementById("coordinates").value = `${lat}, ${lng}`;
    document.getElementById("coordDisplay").innerText =
        `Selected: ${lat.toFixed(6)}, ${lng.toFixed(6)}`;
}

function onPoolModalOpen() {
    setTimeout(() => {
        if (!map) return;

        google.maps.event.trigger(map, "resize");

        const pos = marker ? marker.getPosition() : { lat: 27.7172, lng: 85.3240 };

        map.setCenter(pos);

        const coordInput = document.getElementById('coordinates');
        const coordDisplay = document.getElementById('coordDisplay');

        if (!coordInput.value) {
            coordInput.value = `${pos.lat().toFixed(6)},${pos.lng().toFixed(6)}`;
            coordDisplay.innerText = `Selected: ${pos.lat().toFixed(6)}, ${pos.lng().toFixed(6)}`;
        }
    }, 300);
}

// ---------------------- POOL MODAL ----------------------

// function initMap() {
//     const defaultLoc = { lat: 27.7172, lng: 85.3240 }; // default: Kathmandu

//     map = new google.maps.Map(document.getElementById("map"), {
//         zoom: 13,
//         center: defaultLoc,
//     });

//     map.addListener("click", (e) => {
//         const lat = e.latLng.lat().toFixed(6);
//         const lng = e.latLng.lng().toFixed(6);

//         if (marker) marker.setMap(null);

//         marker = new google.maps.Marker({
//             position: e.latLng,
//             map: map
//         });

//         document.getElementById("coordinates").value = `${lat}, ${lng}`;
//         document.getElementById("coordDisplay").innerText = `Selected: ${lat}, ${lng}`;
//     });
// }

// function onPoolModalOpen() {
//     setTimeout(() => {
//         if (map) {
//             google.maps.event.trigger(map, "resize");
//             map.setCenter({ lat: 27.7172, lng: 85.3240 });
//         }
//     }, 200);
// }

function openEditPoolModal(btn) {
    const modal = document.getElementById('poolModal');
    const pool = JSON.parse(btn.dataset.pool);
    const editUrl = btn.dataset.url;

    // Fill form fields
    document.getElementById('name').value = pool.name;
    document.getElementById('address').value = pool.address;
    document.getElementById('capacity').value = pool.capacity;
    document.getElementById('coordinates').value = pool.coordinates;

    // Parse existing coordinates
    let lat, lng;
    if (pool.coordinates) {
        const parts = pool.coordinates.split(',');
        lat = parseFloat(parts[0]);
        lng = parseFloat(parts[1]);
    }

    // Initialize or update map
    const mapDiv = document.getElementById('map');
    if (!map) {
        map = new google.maps.Map(mapDiv, {
            center: { lat, lng },
            zoom: 14,
        });
        marker = new google.maps.Marker({
            position: { lat, lng },
            map,
            draggable: true,
        });

        map.addListener("click", (e) => setMarker(e.latLng.lat(), e.latLng.lng()));
        marker.addListener("dragend", (e) => setMarker(e.latLng.lat(), e.latLng.lng()));
    } else {
        marker.setPosition({ lat, lng });
        map.setCenter({ lat, lng });
        google.maps.event.trigger(map, "resize");
    }

    // Update form action
    modal.querySelector('form').action = editUrl;

    // Change modal title
    modal.querySelector('h2').textContent = "Edit Pool";

    // Show modal
    toggleModal('poolModal');
}

// ---------------------- CLASS MODAL ----------------------
function openEditClassModal(btn) {
    const modal = document.getElementById("classModal");
    const session = JSON.parse(btn.dataset.session);

    modal.querySelector("#class_name").value = session.class_name;
    modal.querySelector("#pool_id").value = session.pool_id;
    modal.querySelector("#class_type_id").value = session.class_type_id;
    modal.querySelector("#user_id").value = session.user_id;
    modal.querySelector("#start_date").value = session.start_date;
    modal.querySelector("#end_date").value = session.end_date;
    modal.querySelector("#start_time").value = session.start_time;
    modal.querySelector("#end_time").value = session.end_time;
    modal.querySelector("#seats").value = session.seats;
    modal.querySelector("#total_sessions").value = session.total_sessions;

    modal.querySelector("form").action = btn.dataset.url;
    modal.querySelector("h2").textContent = "Edit Class Session";

    toggleModal("classModal");
}

// ---------------------- CLASS TYPE MODAL ----------------------
function openEditClassTypeModal(btn) {
    const modal = document.getElementById("classTypeModal");
    const type = JSON.parse(btn.dataset.classType);

    modal.querySelector("#type_name").value = type.name;
    modal.querySelector("#cost").value = type.cost;
    modal.querySelector("#description").value = type.description;

    modal.querySelector("form").action = btn.dataset.url;
    modal.querySelector("h2").textContent = "Edit Class Type";

    toggleModal("classTypeModal");
}

// ---------------------- POOL QUALITY MODAL ----------------------
function openEditQualityModal(btn) {
    const modal = document.getElementById("qualityModal");
    const quality = JSON.parse(btn.dataset.quality);

    modal.querySelector("#quality_pool_id").value = quality.pool_id;
    modal.querySelector("#quality_date").value = quality.date;
    modal.querySelector("#cleanliness_rating").value = quality.cleanliness_rating;
    modal.querySelector("#pH_level").value = quality.pH_level || "";
    modal.querySelector("#water_temperature").value = quality.water_temperature || "";
    modal.querySelector("#chlorine_level").value = quality.chlorine_level || "";

    modal.querySelector("form").action = btn.dataset.url;
    modal.querySelector("h2").textContent = "Edit Quality Record";

    toggleModal("qualityModal");
}

function openAddQualityModal() {
    const modal = document.getElementById("qualityModal");
    resetModalFields(modal);
    // Use data attribute in HTML for URL instead of {% url %} in JS
    modal.querySelector("form").action = modal.querySelector("form").dataset.addUrl;
    modal.querySelector("h2").textContent = "Add Quality Record";
    toggleModal("qualityModal");
}

// ---------------------- TRAINER MODAL ----------------------

// Open modal for editing an existing trainer
function openEditTrainerModal(btn) {
    const modal = document.getElementById("trainerModal");
    const trainer = JSON.parse(btn.dataset.trainer);

    modal.querySelector("#username").value = trainer.username;
    modal.querySelector("#email").value = trainer.email;
    modal.querySelector("#full_name").value = trainer.full_name;
    modal.querySelector("#phone").value = trainer.phone;
    modal.querySelector("#gender").value = trainer.gender;
    modal.querySelector("#specialization").value = trainer.specialization;
    modal.querySelector("#experience_years").value = trainer.experience_years;

    // Hide password field when editing
    const passwordField = modal.querySelector("#password-field");
    if (passwordField) {
        passwordField.style.display = "none";
        modal.querySelector("#password").removeAttribute("required");
    }

    // Set form action to edit URL
    modal.querySelector("form").action = btn.dataset.url;
    modal.querySelector("h2").textContent = "Edit Trainer";

    toggleModal("trainerModal");
}

// Open modal for adding a new trainer
function openAddTrainerModal() {
    const modal = document.getElementById("trainerModal");

    // Reset all fields
    resetModalFields(modal);

    // Show password field and make it required
    const passwordField = modal.querySelector("#password-field");
    if (passwordField) {
        passwordField.style.display = "block";
        modal.querySelector("#password").setAttribute("required", "required");
    }

    // ✅ Get the Add URL from the form's data attribute
    modal.querySelector("form").action = modal.querySelector("form").dataset.addUrl;

    modal.querySelector("h2").textContent = "Add New Trainer";

    toggleModal("trainerModal");
}
