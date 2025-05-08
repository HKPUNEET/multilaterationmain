from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import json
import os

app = Flask(__name__)
socketio = SocketIO(app)

triangulator_location = [12.2476667, 76.7153]


@app.route("/")
def index():
   return render_template("index.html", triangulator=triangulator_location)

@socketio.on("connect")
def handle_connect():
  print("Client connected")

@socketio.on("request_device_data")
def send_device_data():
  if os.path.exists("ble_devices.json"):
     with open("ble_devices.json") as f:
        devices = json.load(f)
     emit("device_data", {"devices": devices, "triangulator": triangulator_location})

if __name__ == "__main__":
  socketio.run(app, debug=True)

