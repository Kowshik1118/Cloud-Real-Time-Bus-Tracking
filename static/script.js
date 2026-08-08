let map;
let markers = {};
let allBuses = [];

function initializeMap() {
    map = L.map("map").setView([12.9716, 77.5946], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors"
    }).addTo(map);
}

async function loadBuses() {
    try {
        const response = await fetch("/api/buses", {cache: "no-store"});
        allBuses = await response.json();

        document.getElementById("totalBuses").innerText = allBuses.length;
        document.getElementById("activeBuses").innerText =
            allBuses.filter(b => b.status === "Active").length;
        document.getElementById("lastUpdated").innerText =
            new Date().toLocaleTimeString();

        updateBusList(allBuses);
        updateMarkers(allBuses);
    } catch (error) {
        document.getElementById("gpsStatus").innerText = "OFFLINE";
        console.error(error);
    }
}

function updateBusList(buses) {
    const list = document.getElementById("busList");
    list.innerHTML = "";

    buses.forEach(bus => {
        const card = document.createElement("div");
        card.className = "bus-card";
card.innerHTML = `
    <h3>🚌 ${bus.bus_number}</h3>

    <p>
        <strong>Route:</strong>
        ${bus.route}
    </p>

    <p>
        <strong>Speed:</strong>
        ${bus.speed} km/h
    </p>

    <p>
        <strong>GPS:</strong>
        ${Number(bus.latitude).toFixed(5)},
        ${Number(bus.longitude).toFixed(5)}
    </p>

    <p>
        <strong>Status:</strong>
        <span class="${bus.status === 'Active' ? 'status-active' : 'status-inactive'}">
            ${bus.status}
        </span>
    </p>

    <p>
        <strong>Next change:</strong>
        ${bus.remaining_seconds} seconds
    </p>
`;
        card.onclick = () => {
            map.setView([bus.latitude, bus.longitude], 16);
            if (markers[bus.id]) markers[bus.id].openPopup();
        };
        list.appendChild(card);
    });
}

function updateMarkers(buses) {
    buses.forEach(bus => {
        const position = [bus.latitude, bus.longitude];

        if (!markers[bus.id]) {
            markers[bus.id] = L.marker(position).addTo(map);
        } else {
            markers[bus.id].setLatLng(position);
        }

        markers[bus.id].setPopupContent(createPopup(bus));
    });
}

function createPopup(bus) {
    return `
        <div>
            <h3>🚌 ${bus.bus_number}</h3>
            <p><strong>Route:</strong> ${bus.route}</p>
            <p><strong>Speed:</strong> ${bus.speed} km/h</p>
            <p><strong>GPS:</strong><br>${Number(bus.latitude).toFixed(5)}, ${Number(bus.longitude).toFixed(5)}</p>
            <p><strong>Status:</strong> ${bus.status}</p>
        </div>
    `;
}

function filterBuses() {
    const query = document.getElementById("searchBox").value.toLowerCase();
    updateBusList(allBuses.filter(bus =>
        bus.bus_number.toLowerCase().includes(query) ||
        bus.route.toLowerCase().includes(query)
    ));
}

initializeMap();
loadBuses();
setInterval(loadBuses, 2000);
