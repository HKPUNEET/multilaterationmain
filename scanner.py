import asyncio
from bleak import BleakScanner
import json
from datetime import datetime
from collections import deque
import socket
from datetime import datetime
from collections import deque
import socketio
import numpy as np

class BleScanner:
    def __init__(self, triangulator_position=(0, 0), window_size=5, kalman_q=0.01, kalman_r=0.8,main_node_url="http://localhost:5050"):
        self.triangulator_position = triangulator_position
        self.window_size = window_size
        self.kalman_q = kalman_q
        self.kalman_r = kalman_r
        self.devices_seen = {}
        self.filtered_rssi_buffer = {}
        self.kalman_state = {}
        self.kalman_covariance = {}
        self.triangulator_position = triangulator_position
        self.main_node_url = main_node_url
        self.sio = socketio.AsyncClient()
        self.rssi_history= {}


    def send_data_to_app(self, data):
        """
        Send updated device data to the app via a socket connection
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.host, self.port))
            s.sendall(data.encode())
    def estimate_distance(self, rssi, tx_power=-59, n=2.7):
        """
        Estimate distance from RSSI using the Log-distance Path Loss Model.
        """
        return round(10 ** ((tx_power - rssi) / (10 * n)), 2)

    def moving_average(self, address, new_rssi):
        """
        Apply moving average filtering to smooth the RSSI.
        """
        buffer = self.filtered_rssi_buffer.setdefault(address, deque(maxlen=self.window_size))
        buffer.append(new_rssi)
        return sum(buffer) / len(buffer)

    def kalman_filter(self, address, measured_rssi):
        """
        Apply the Kalman filter for noise reduction in RSSI.
        """
        x = self.kalman_state.get(address, measured_rssi)
        p = self.kalman_covariance.get(address, 1)

        # Predict
        x_pred = x
        p_pred = p + self.kalman_q

        # Update
        k = p_pred / (p_pred + self.kalman_r)
        x_new = x_pred + k * (measured_rssi - x_pred)
        p_new = (1 - k) * p_pred

        self.kalman_state[address] = x_new
        self.kalman_covariance[address] = p_new

        return x_new
    def moving_average(self, address, new_rssi):
        buffer = self.filtered_rssi_buffer.setdefault(address, deque(maxlen=self.window_size))
        buffer.append(new_rssi)

        history = self.rssi_history.setdefault(address, deque(maxlen=10))
        history.append(new_rssi)
        variance = np.var(history) if len(history) > 1 else 1.0  # Safe fallback
        return sum(buffer) / len(buffer), variance
    
    async def callback(self, device, advertisement_data):
        """
        Callback function to handle received BLE advertisements.
        """
        # Try to get payload from manufacturer_data, fallback to local_name or service_data
        payload = None

        if advertisement_data.manufacturer_data:
            for _, v in advertisement_data.manufacturer_data.items():
                payload = v.decode("utf-8", errors="ignore").strip()
        elif advertisement_data.local_name:
            payload = advertisement_data.local_name.strip()
        elif advertisement_data.service_data:
            for _, v in advertisement_data.service_data.items():
                payload = v.decode("utf-8", errors="ignore").strip()

        # Skip if no usable payload found
        if not payload:
            return

        try:
            raw_rssi = device.rssi

            # Filtered RSSI
            filtered_rssi = self.kalman_filter(device.address, raw_rssi)
            smoothed_rssi, variance = self.moving_average(device.address, filtered_rssi)

            # Adaptive path-loss exponent
            n = 2.0 if smoothed_rssi > -65 else 3.2 if smoothed_rssi < -80 else 2.7
            distance = self.estimate_distance(smoothed_rssi, n=n)

            self.devices_seen[device.address] = {
                "payload": payload,
                "rssi": round(smoothed_rssi, 2),
                "distance": distance,
                "last_seen": datetime.now().isoformat()
            }
            smoothed_rssi, variance = self.moving_average(device.address, filtered_rssi)



            await self.sio.emit("distance_data", {
                "from": "side_node",
                "coords": self.triangulator_position,
                "device": device.address,
                "payload": payload,
                "rssi": round(smoothed_rssi, 2),
                "distance": distance,
                "variance": variance # ✨ Added
})


            # Save the updated dictionary to a JSON file
            with open("ble_devices.json", "w") as f:
                json.dump(self.devices_seen, f, indent=2)

            print(
                f"🛰 {device.address} | RSSI: {raw_rssi} → {smoothed_rssi:.2f} | Distance: {distance}m | Payload: {payload}")

        except Exception as e:
            print(f"Error parsing device {device.address}: {e}")

    async def run_scanner(self):

            print("Connecting to main node...")
            await self.connect_to_main_node()

            # Wait until connected
            while not self.sio.connected:
                print("Waiting for connection...")
                await asyncio.sleep(0.5)

            print("Starting BLE scan...")
            scanner = BleakScanner(self.callback)
            await scanner.start()

            while True:
                await asyncio.sleep(1)

    async def connect_to_main_node(self):
      try:
        await self.sio.connect(self.main_node_url)
        print(" Connected to main node.")
      except Exception as e:
        print(f" Failed to connect to main node: {e}")


if __name__ == "__main__":
    # Initialize the BLE scanner
    scanner = BleScanner()

    # Run the scanner asynchronously
    asyncio.run(scanner.run_scanner())

