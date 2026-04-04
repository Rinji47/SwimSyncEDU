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
                if (!window.google || !window.google.maps) {
                    return;
                }

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
    if (form) {
        form.reset();
        const defaultAction = form.dataset.defaultAction;
        if (defaultAction) {
            form.action = defaultAction;
        }
    }

    if (modal.id === "poolModal") {
        if (marker && map) {
            setDefaultLocation();
        }

        document.getElementById("coordinates").value = "";
        document.getElementById("coordDisplay").innerText = "Click on the map to select location";
        const existingImagesWrap = document.getElementById("existingPoolImages");
        const existingImagesList = document.getElementById("existingPoolImagesList");
        if (existingImagesWrap) existingImagesWrap.style.display = "none";
        if (existingImagesList) existingImagesList.innerHTML = "";
        const title = modal.querySelector("h2");
        if (title) title.textContent = "Add New Pool";
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
    if (!mapDiv || !window.google || !window.google.maps) return;

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
    if (!window.google || !window.google.maps) {
        alert("Google Maps is unavailable. Set GOOGLE_MAPS_API_KEY before editing pool coordinates.");
        return;
    }

    const modal = document.getElementById('poolModal');
    const pool = JSON.parse(btn.dataset.pool);
    const editUrl = btn.dataset.url;

    // Fill form fields
    document.getElementById('name').value = pool.name;
    document.getElementById('address').value = pool.address;
    document.getElementById('capacity').value = pool.capacity;
    document.getElementById('coordinates').value = pool.coordinates;
    renderExistingPoolImages(pool.images || []);

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

function renderExistingPoolImages(images) {
    const existingImagesWrap = document.getElementById("existingPoolImages");
    const existingImagesList = document.getElementById("existingPoolImagesList");
    if (!existingImagesWrap || !existingImagesList) return;

    if (!images || images.length === 0) {
        existingImagesWrap.style.display = "none";
        existingImagesList.innerHTML = "";
        return;
    }

    existingImagesWrap.style.display = "block";
    existingImagesList.innerHTML = images
        .map((image) => `
            <label style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.5rem;">
                <input type="checkbox" name="delete_image_ids" value="${image.id}">
                <img src="${image.url}" alt="${image.caption || 'Pool image'}" style="width:64px;height:64px;object-fit:cover;border-radius:8px;border:1px solid #e2e8f0;">
                <span>${image.caption || "Pool image"}</span>
            </label>
        `)
        .join("");
}

// CLASS MODAL
// openEditClassModal removed: class session editing is not handled here

// CLASS TYPE MODAL
function openAddClassTypeModal() {
    const modal = document.getElementById("classTypeModal");
    const form = modal.querySelector("form");
    const note = modal.querySelector("#class_type_duration_note");

    form.action = "";
    form.reset();
    modal.querySelector("#duration_days").value = 0;
    modal.querySelector("h2").textContent = "Add Class Type";
    note.textContent = "This duration is used when creating future class sessions.";

    toggleModal("classTypeModal");
}

function openEditClassTypeModal(btn) {
    const modal = document.getElementById("classTypeModal");
    const type = JSON.parse(btn.dataset.classType);
    const note = modal.querySelector("#class_type_duration_note");

    modal.querySelector("#type_name").value = type.name;
    modal.querySelector("#cost").value = type.cost;
    modal.querySelector("#duration_days").value = type.duration_days || 0;
    modal.querySelector("#description").value = type.description;

    modal.querySelector("form").action = btn.dataset.url;
    modal.querySelector("h2").textContent = "Edit Class Type";
    note.textContent = "Changing duration updates this class type for future class sessions. Existing sessions keep their current dates.";

    toggleModal("classTypeModal");
}

function parseClassTypeMeta(selectEl) {
    if (!selectEl) return { durationDays: 0, isGroup: false };
    const option = selectEl.options[selectEl.selectedIndex];
    if (!option) return { durationDays: 0, isGroup: false };

    const durationDays = parseInt(option.dataset.durationDays || "0", 10);
    const isGroup = option.dataset.isGroup === "true";

    return {
        durationDays: Number.isNaN(durationDays) ? 0 : durationDays,
        isGroup,
    };
}

function updateEndDateFromType() {
    const classTypeSelect = document.getElementById("class_type_id");
    const startDateInput = document.getElementById("start_date");
    const endDateInput = document.getElementById("end_date");

    if (!classTypeSelect || !startDateInput || !endDateInput) return;

    const { durationDays, isGroup } = parseClassTypeMeta(classTypeSelect);
    
    // Auto-calculate end date for group classes
    if (!isGroup || durationDays <= 0 || !startDateInput.value) return;

    const startDate = new Date(`${startDateInput.value}T00:00:00`);
    if (Number.isNaN(startDate.getTime())) return;

    const endDate = new Date(startDate);
    endDate.setDate(endDate.getDate() + durationDays - 1);

    const year = endDate.getFullYear();
    const month = String(endDate.getMonth() + 1).padStart(2, "0");
    const day = String(endDate.getDate()).padStart(2, "0");
    endDateInput.value = `${year}-${month}-${day}`;
}

function validateClassTimes() {
    const startTimeInput = document.getElementById("start_time");
    const endTimeInput = document.getElementById("end_time");
    
    if (!startTimeInput || !endTimeInput) return true;
    if (!startTimeInput.value || !endTimeInput.value) return true;
    
    const [startHour, startMin] = startTimeInput.value.split(':').map(Number);
    const [endHour, endMin] = endTimeInput.value.split(':').map(Number);
    const startMinutes = startHour * 60 + startMin;
    const endMinutes = endHour * 60 + endMin;
    const durationMinutes = endMinutes - startMinutes;
    
    if (durationMinutes <= 0) {
        alert("End time must be after start time.");
        endTimeInput.value = "";
        return false;
    }
    
    if (durationMinutes > 180) { // 3 hours = 180 minutes
        alert("Class duration cannot exceed 3 hours.");
        endTimeInput.value = "";
        return false;
    }
    
    return true;
}

document.addEventListener("DOMContentLoaded", () => {
    const classTypeSelect = document.getElementById("class_type_id");
    const startDateInput = document.getElementById("start_date");
    const startTimeInput = document.getElementById("start_time");
    const endTimeInput = document.getElementById("end_time");
    const classForm = document.querySelector("#classModal form");

    if (classTypeSelect) {
        classTypeSelect.addEventListener("change", updateEndDateFromType);
    }

    if (startDateInput) {
        startDateInput.addEventListener("change", updateEndDateFromType);
    }
    
    if (startTimeInput) {
        startTimeInput.addEventListener("change", validateClassTimes);
    }
    
    if (endTimeInput) {
        endTimeInput.addEventListener("change", validateClassTimes);
        endTimeInput.addEventListener("blur", validateClassTimes);
    }
    
    if (classForm) {
        classForm.addEventListener("submit", (e) => {
            if (!validateClassTimes()) {
                e.preventDefault();
            }
        });
    }
});

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
    const signatureInput = modal.querySelector("#digital_signature");
    const signaturePreview = modal.querySelector("#digitalSignaturePreview");

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

    if (signatureInput) {
        signatureInput.required = false;
        signatureInput.value = "";
    }

    if (signaturePreview) {
        if (trainer.digital_signature && trainer.digital_signature !== "null") {
            signaturePreview.src = trainer.digital_signature;
            signaturePreview.style.display = "block";
        } else {
            signaturePreview.removeAttribute("src");
            signaturePreview.style.display = "none";
        }
    }

    // Set form action to edit URL
    modal.querySelector("form").action = btn.dataset.url;
    modal.querySelector("h2").textContent = "Edit Trainer";

    toggleModal("trainerModal");
}

// Open modal for adding a new trainer
function openAddTrainerModal() {
    const modal = document.getElementById("trainerModal");
    const signatureInput = modal.querySelector("#digital_signature");
    const signaturePreview = modal.querySelector("#digitalSignaturePreview");

    // Reset all fields
    resetModalFields(modal);

    // Show password field and make it required
    const passwordField = modal.querySelector("#password-field");
    if (passwordField) {
        passwordField.style.display = "block";
        modal.querySelector("#password").setAttribute("required", "required");
    }

    if (signatureInput) {
        signatureInput.setAttribute("required", "required");
    }

    if (signaturePreview) {
        signaturePreview.removeAttribute("src");
        signaturePreview.style.display = "none";
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
    const signatureImg = document.getElementById("trainer_view_signature");
    const signatureEmpty = document.getElementById("trainer_view_signature_empty");

    document.getElementById("trainer_view_name").textContent = trainer.full_name || trainer.username || "Trainer Details";
    document.getElementById("trainer_view_status").textContent = trainer.status || "";
    document.getElementById("trainer_view_email").textContent = trainer.email || "";
    document.getElementById("trainer_view_phone").textContent = trainer.phone || "-";
    document.getElementById("trainer_view_gender").textContent = trainer.gender || "-";
    document.getElementById("trainer_view_specialization").textContent = trainer.specialization || "-";
    document.getElementById("trainer_view_experience").textContent = trainer.experience_years ? `${trainer.experience_years} years` : "-";

    if (signatureImg && signatureEmpty) {
        if (trainer.digital_signature && trainer.digital_signature !== "null") {
            signatureImg.src = trainer.digital_signature;
            signatureImg.style.display = "block";
            signatureEmpty.style.display = "none";
        } else {
            signatureImg.removeAttribute("src");
            signatureImg.style.display = "none";
            signatureEmpty.style.display = "inline";
        }
    }

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
    document.getElementById('view_bookings').textContent = btnOrId.dataset.totalBookings || "0";
    document.getElementById('view_cancelled').textContent = isCancelled ? "Yes" : "No";

    toggleModal('viewModal');
}
