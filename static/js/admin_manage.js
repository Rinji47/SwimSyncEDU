// GLOBALS
//const google = window.google; // Google Maps

// MODAL UTILS
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
                    map.setCenter(marker?.getPosition() || { lat: 28.2096, lng: 83.9856 });
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

function resetModalFields(modal) {
    const form = modal.querySelector("form");
    if (form) form.reset();

    if (modal.id === "poolModal") {
        if (marker && map) {
            setDefaultLocation();
        }

        document.getElementById("coordinates").value = "";
        document.getElementById("coordDisplay").innerText = "Click on the map to select location";
    }

    if (modal.id === "classModal") {
        const cancelGroup = modal.querySelector("#cancelled_group");
        const cancelInput = modal.querySelector("#is_cancelled");
        if (cancelGroup) cancelGroup.style.display = "none";
        if (cancelInput) cancelInput.checked = false;
    }
}


// GOOGLE MAPS
let map = null;
let marker = null;

function initMap() {
    const mapDiv = document.getElementById("map");
    if (!mapDiv) return;

    const fallbackLoc = { lat: 28.2096, lng: 83.9856 }; // Pokhara

    map = new google.maps.Map(mapDiv, {
        zoom: 13,
        center: fallbackLoc,
    });

    marker = new google.maps.Marker({
        position: fallbackLoc,
        map,
        draggable: true,
    });

    map.addListener("click", (e) => {
        setMarker(e.latLng.lat(), e.latLng.lng());
    });

    marker.addListener("dragend", (e) => {
        setMarker(e.latLng.lat(), e.latLng.lng());
    });

    setDefaultLocation();
}

function setDefaultLocation() {
    if (!navigator.geolocation) return;

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
            // Keep Pokhara fallback
        },
        {
            enableHighAccuracy: true,
            timeout: 8000,
            maximumAge: 0,
        }
    );
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

        const pos = marker ? marker.getPosition() : { lat: 28.2096, lng: 83.9856 };

        map.setCenter(pos);

        const coordInput = document.getElementById('coordinates');
        const coordDisplay = document.getElementById('coordDisplay');

        if (!coordInput.value) {
            coordInput.value = `${pos.lat().toFixed(6)},${pos.lng().toFixed(6)}`;
            coordDisplay.innerText = `Selected: ${pos.lat().toFixed(6)}, ${pos.lng().toFixed(6)}`;
        }
    }, 300);
}

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
    } else {
        lat = 28.2096;
        lng = 83.9856;
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

// CLASS MODAL
function openEditClassModal(btn) {
    const modal = document.getElementById("classModal");
    if (!btn || !btn.dataset) return;

    modal.querySelector("#class_name").value = btn.dataset.className || "";
    modal.querySelector("#pool_id").value = btn.dataset.poolId || "";
    modal.querySelector("#class_type_id").value = btn.dataset.classTypeId || "";
    modal.querySelector("#user_id").value = btn.dataset.userId || "";
    modal.querySelector("#start_date").value = btn.dataset.startDate || "";
    modal.querySelector("#end_date").value = btn.dataset.endDate || "";
    modal.querySelector("#start_time").value = btn.dataset.startTime || "";
    modal.querySelector("#end_time").value = btn.dataset.endTime || "";
    modal.querySelector("#seats").value = btn.dataset.seats || "";
    modal.querySelector("#total_sessions").value = btn.dataset.totalSessions || "";

    const cancelGroup = modal.querySelector("#cancelled_group");
    const cancelInput = modal.querySelector("#is_cancelled");
    if (cancelGroup) cancelGroup.style.display = "block";
    if (cancelInput) cancelInput.checked = btn.dataset.isCancelled === "true";

    modal.querySelector("form").action = btn.dataset.url;
    modal.querySelector("h2").textContent = "Edit Class Session";

    toggleModal("classModal");
}

// CLASS TYPE MODAL
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

// POOL QUALITY MODAL
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
    modal.querySelector("form").action = modal.querySelector("form").dataset.addUrl;
    modal.querySelector("h2").textContent = "Add Quality Record";
    toggleModal("qualityModal");
}

// TRAINER MODAL

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

function openPoolViewModal(btn) {
    if (!btn || !btn.dataset || !btn.dataset.pool) return;
    const pool = JSON.parse(btn.dataset.pool);

    document.getElementById("pool_view_name").textContent = pool.name || "Pool Details";
    document.getElementById("pool_view_status").textContent = pool.status || "";
    document.getElementById("pool_view_address").textContent = pool.address || "";
    document.getElementById("pool_view_capacity").textContent = pool.capacity || "";
    document.getElementById("pool_view_coordinates").textContent = pool.coordinates || "";

    toggleModal("poolViewModal");
}

function openTrainerViewModal(btn) {
    if (!btn || !btn.dataset || !btn.dataset.trainer) return;
    const trainer = JSON.parse(btn.dataset.trainer);

    document.getElementById("trainer_view_name").textContent = trainer.full_name || trainer.username || "Trainer Details";
    document.getElementById("trainer_view_status").textContent = trainer.status || "";
    document.getElementById("trainer_view_email").textContent = trainer.email || "";
    document.getElementById("trainer_view_phone").textContent = trainer.phone || "-";
    document.getElementById("trainer_view_gender").textContent = trainer.gender || "-";
    document.getElementById("trainer_view_specialization").textContent = trainer.specialization || "-";
    document.getElementById("trainer_view_experience").textContent = trainer.experience_years ? `${trainer.experience_years} years` : "-";

    toggleModal("trainerViewModal");
}

function openMemberViewModal(btn) {
    if (!btn || !btn.dataset || !btn.dataset.member) return;
    const member = JSON.parse(btn.dataset.member);

    document.getElementById("member_view_name").textContent = member.full_name || "Member Details";
    document.getElementById("member_view_status").textContent = member.status || "";
    document.getElementById("member_view_username").textContent = member.username || "";
    document.getElementById("member_view_email").textContent = member.email || "";
    document.getElementById("member_view_phone").textContent = member.phone || "-";
    document.getElementById("member_view_gender").textContent = member.gender || "-";
    document.getElementById("member_view_dob").textContent = member.date_of_birth || "-";
    document.getElementById("member_view_joined").textContent = member.joined || "";

    toggleModal("memberViewModal");
}

function openEditMemberModal(btn) {
    if (!btn || !btn.dataset || !btn.dataset.member) return;
    const modal = document.getElementById("memberModal");
    const member = JSON.parse(btn.dataset.member);

    modal.querySelector("#member_username").value = member.username || "";
    modal.querySelector("#member_full_name").value = member.full_name || "";
    modal.querySelector("#member_email").value = member.email || "";
    modal.querySelector("#member_phone").value = member.phone || "";
    modal.querySelector("#member_gender").value = member.gender || "";
    modal.querySelector("#member_dob").value = member.date_of_birth || "";

    modal.querySelector("form").action = btn.dataset.url;
    modal.querySelector("h2").textContent = "Edit Member";

    toggleModal("memberModal");
}


function openViewModal(btnOrId) {
    if (!btnOrId || !btnOrId.dataset) return;

    const isCancelled = btnOrId.dataset.isCancelled === "true";

    document.getElementById('view_class_name').textContent = btnOrId.dataset.className || "";
    document.getElementById('view_pool').textContent = btnOrId.dataset.poolName || "";
    document.getElementById('view_trainer').textContent = btnOrId.dataset.trainerName || "";
    document.getElementById('view_type').textContent = btnOrId.dataset.classType || "";
    document.getElementById('view_dates').textContent = `${btnOrId.dataset.startDate || ""} - ${btnOrId.dataset.endDate || ""}`;
    document.getElementById('view_time').textContent = `${btnOrId.dataset.startTime || ""} - ${btnOrId.dataset.endTime || ""}`;
    document.getElementById('view_seats').textContent = btnOrId.dataset.seats || "";
    document.getElementById('view_price').textContent = btnOrId.dataset.totalPrice || "";
    document.getElementById('view_cancelled').textContent = isCancelled ? "Yes" : "No";
    document.getElementById('view_total_sessions').textContent = btnOrId.dataset.totalSessions || "";

    toggleModal('viewModal');
}
