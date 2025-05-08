const map = L.map('map').setView([12.2476667, 76.7153], 20);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 22,
}).addTo(map);

const triangulator = [12.2476667, 76.7153];
L.marker(triangulator).addTo(map).bindPopup("Triangulator (Laptop)");

const socket = io();
const circles = {};

socket.on("connect", () => {
    socket.emit("request_device_data");
});

socket.on("device_data", (data) => {
    const devices = data.devices;
    const baseLat = data.triangulator[0];
    const baseLng = data.triangulator[1];

    for (const [addr, info] of Object.entries(devices)) {
        const lat = baseLat + (info.distance / 111000);  // 1 deg ~ 111 km
        const lng = baseLng;

        if (circles[addr]) {
            circles[addr].setLatLng([lat, lng]).setPopupContent(`${addr}: ${info.distance}m`);
        } else {
            circles[addr] = L.circle([lat, lng], {
                radius: 0.5,
                color: 'red',
                fill: true,
                fillOpacity: 0.5
            }).addTo(map).bindPopup(`${addr}: ${info.distance}m`);
        }
    }
})