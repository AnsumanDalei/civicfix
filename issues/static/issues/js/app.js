// CivicFix — report form map interaction
document.addEventListener("DOMContentLoaded", function () {
  const mapEl = document.getElementById("map");
  if (!mapEl) return;

  const latInput = document.getElementById("id_latitude");
  const lngInput = document.getElementById("id_longitude");
  const locateBtn = document.getElementById("locate-btn");

  // Default view comes from the server (settings.DEFAULT_MAP_LAT/LNG/ZOOM,
  // configurable via .env — not hardcoded to any one city or country).
  // Falls back to a neutral world view if the attributes are missing.
  const defaultLat = parseFloat(mapEl.dataset.defaultLat) || 20.0;
  const defaultLng = parseFloat(mapEl.dataset.defaultLng) || 0.0;
  const defaultZoom = parseInt(mapEl.dataset.defaultZoom, 10) || 2;

  const map = L.map("map").setView([defaultLat, defaultLng], defaultZoom);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  let marker = L.marker([defaultLat, defaultLng], { draggable: true }).addTo(map);

  function setCoords(lat, lng) {
    latInput.value = lat.toFixed(6);
    lngInput.value = lng.toFixed(6);
    marker.setLatLng([lat, lng]);
    map.panTo([lat, lng]);
  }

  marker.on("dragend", function () {
    const pos = marker.getLatLng();
    setCoords(pos.lat, pos.lng);
  });

  map.on("click", function (e) {
    setCoords(e.latlng.lat, e.latlng.lng);
  });

  locateBtn.addEventListener("click", function () {
    if (!navigator.geolocation) {
      alert("Geolocation isn't supported by this browser. Click the map to set the pin instead.");
      return;
    }
    locateBtn.textContent = "Locating...";
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        setCoords(pos.coords.latitude, pos.coords.longitude);
        map.setView([pos.coords.latitude, pos.coords.longitude], 16);
        locateBtn.textContent = "📍 Use my current location";
      },
      function () {
        alert("Couldn't get your location. Click the map to set the pin manually.");
        locateBtn.textContent = "📍 Use my current location";
      }
    );
  });

  // Set initial default values so the form is valid even without interaction
  setCoords(defaultLat, defaultLng);
});
