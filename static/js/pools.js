const requestLocationBtn = document.getElementById("requestLocationBtn");
const poolsStatus = document.getElementById("poolsStatus");
function requestLocation() {
    if (!navigator.geolocation) {
        window.location.href = window.location.pathname;
        return;
    }

    if (poolsStatus) {
        poolsStatus.textContent = "Finding pools near you...";
    }
    navigator.geolocation.getCurrentPosition(
        (position) => {
            const { latitude, longitude } = position.coords;
            const url = new URL(window.location.href);
            const radiusInput = document.getElementById("radiusInput");
            const radiusValue = radiusInput ? radiusInput.value : "";
            url.searchParams.set("lat", latitude.toFixed(6));
            url.searchParams.set("lng", longitude.toFixed(6));
            if (radiusValue) {
                url.searchParams.set("radius", radiusValue);
            }
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

document.querySelectorAll("[data-carousel]").forEach((carousel) => {
    const slides = Array.from(carousel.querySelectorAll("[data-slide]"));
    const prevBtn = carousel.querySelector("[data-prev]");
    const nextBtn = carousel.querySelector("[data-next]");
    const indicator = carousel.querySelector("[data-indicator]");

    if (slides.length <= 1) return;

    let currentIndex = 0;
    const render = () => {
        slides.forEach((slide, idx) => {
            slide.classList.toggle("active", idx === currentIndex);
        });
        if (indicator) {
            indicator.textContent = `${currentIndex + 1} / ${slides.length}`;
        }
    };

    if (prevBtn) {
        prevBtn.addEventListener("click", () => {
            currentIndex = (currentIndex - 1 + slides.length) % slides.length;
            render();
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener("click", () => {
            currentIndex = (currentIndex + 1) % slides.length;
            render();
        });
    }
});
