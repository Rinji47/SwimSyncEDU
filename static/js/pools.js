const requestLocationBtn = document.getElementById("requestLocationBtn");
function requestLocation() {
    if (!navigator.geolocation) {
        window.location.href = window.location.pathname;
        return;
    }
    navigator.geolocation.getCurrentPosition(
        (position) => {
            const { latitude, longitude } = position.coords;
            const url = new URL(window.location.href);
            url.searchParams.set("lat", latitude.toFixed(6));
            url.searchParams.set("lng", longitude.toFixed(6));
            window.location.href = url.toString();
        },
        () => {
            window.location.href = window.location.pathname;
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
