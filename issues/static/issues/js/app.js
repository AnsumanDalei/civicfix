// Optional, user-controlled AI suggestions for the report description.
document.addEventListener("DOMContentLoaded", function () {
  const panel = document.getElementById("ai-assist");
  if (!panel) return;

  const description = document.getElementById("id_description");
  const category = document.getElementById("id_category");
  const resultPanel = panel.querySelector(".ai-result");
  const resultText = panel.querySelector(".ai-result-text");
  const status = panel.querySelector("[data-ai-status]");
  const applyButton = panel.querySelector("[data-ai-apply]");
  const buttons = [...panel.querySelectorAll("[data-ai-action]")];
  let suggestion = null;

  buttons.forEach(function (button) {
    button.addEventListener("click", async function () {
      const text = description.value.trim();
      if (!text) {
        status.textContent = "Enter an issue description before asking for help.";
        description.focus();
        return;
      }

      buttons.forEach((item) => { item.disabled = true; });
      status.textContent = "Getting a suggestion…";
      resultPanel.hidden = true;
      applyButton.hidden = true;
      suggestion = null;

      try {
        const csrf = document.querySelector('#issue-form [name="csrfmiddlewaretoken"]')?.value;
        const response = await fetch(panel.dataset.url, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf || "" },
          body: JSON.stringify({ action: button.dataset.aiAction, description: text }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "AI assistance is currently unavailable.");

        suggestion = { action: button.dataset.aiAction, value: data.result, category: data.category };
        resultText.textContent = data.result;
        resultPanel.hidden = false;
        applyButton.hidden = suggestion.action === "summary";
        status.textContent = "Review the suggestion. It will not be used unless you apply it.";
      } catch (error) {
        status.textContent = error.message || "AI assistance is currently unavailable. Continue manually.";
      } finally {
        buttons.forEach((item) => { item.disabled = false; });
      }
    });
  });

  applyButton.addEventListener("click", function () {
    if (!suggestion) return;
    if (suggestion.action === "improve") {
      description.value = suggestion.value;
      description.dispatchEvent(new Event("input", { bubbles: true }));
    } else if (suggestion.action === "category" && category) {
      category.value = suggestion.category;
      category.dispatchEvent(new Event("change", { bubbles: true }));
    }
    status.textContent = "Suggestion applied. You can edit it before submitting.";
    applyButton.hidden = true;
  });
});

document.addEventListener("DOMContentLoaded", function () {
  const mapEl = document.getElementById("map");
  if (!mapEl) return;

  const latInput = document.getElementById("id_latitude");
  const lngInput = document.getElementById("id_longitude");
  const locateBtn = document.getElementById("locate-btn");
  const locationStatus = document.getElementById("location-status");

  const configuredLat = Number(mapEl.dataset.defaultLat);
  const configuredLng = Number(mapEl.dataset.defaultLng);
  const configuredZoom = Number(mapEl.dataset.defaultZoom);
  const defaultLat = Number.isFinite(configuredLat) ? configuredLat : 20.5937;
  const defaultLng = Number.isFinite(configuredLng) ? configuredLng : 78.9629;
  const defaultZoom = Number.isFinite(configuredZoom) ? configuredZoom : 5;

  const map = L.map("map").setView([defaultLat, defaultLng], defaultZoom);
  window.reportMap = map;
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
  maxZoom: 19,
  }).addTo(map);

  let marker = L.marker([defaultLat, defaultLng], { draggable: true }).addTo(map);
  window.reportMarker = marker;

  function setCoords(lat, lng) {
    latInput.value = lat.toFixed(6);
    lngInput.value = lng.toFixed(6);
    marker.setLatLng([lat, lng]);
    map.panTo([lat, lng]);
    if (locationStatus) locationStatus.textContent = `Location set to ${lat.toFixed(5)}, ${lng.toFixed(5)}. Drag the pin to adjust it.`;
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

  if (latInput.value && lngInput.value) {
    marker.setLatLng([Number(latInput.value), Number(lngInput.value)]);
    map.setView([Number(latInput.value), Number(lngInput.value)], Math.max(defaultZoom, 14));
    if (locationStatus) locationStatus.textContent = mapEl.dataset.editing === "true" ? "Current issue location. Drag the pin or click the map to move it." : "Location restored. Drag the pin or click the map to move it.";
  } else {
    latInput.value = "";
    lngInput.value = "";
  }
});
