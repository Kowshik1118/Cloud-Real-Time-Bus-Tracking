from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from database import get_connection, create_database
from werkzeug.security import check_password_hash, generate_password_hash
import threading
import time

app = Flask(__name__)
app.secret_key = "bus-tracking-demo-secret-key-change-this"
create_database()
status_timers={}

def login_required():
    return "user_id" in session

def simulate_bus_movement():
    import random



    while True:
        try:
            connection = get_connection()

            buses = connection.execute("""
                SELECT id, latitude, longitude, speed, direction, status
                FROM buses
            """).fetchall()

            current_time = time.time()

            for bus in buses:

                bus_id = bus["id"]

                # Create timer for each bus
                if bus_id not in status_timers:

                    # Start with Active
                    status_timers[bus_id] = {
                        "next_change": current_time + random.randint(50, 100)
                    }

                timer = status_timers[bus_id]

                # Check whether status should change
                if current_time >= timer["next_change"]:

                    if bus["status"] == "Active":

                        # ACTIVE -> INACTIVE
                        new_status = "Inactive"

                        # Inactive for 5-10 seconds
                        timer["next_change"] = (
                            current_time + random.randint(50, 70)
                        )

                    else:

                        # INACTIVE -> ACTIVE
                        new_status = "Active"

                        # Active for 8-15 seconds
                        timer["next_change"] = (
                            current_time + random.randint(500, 700)
                        )

                    connection.execute("""
                        UPDATE buses
                        SET status=?
                        WHERE id=?
                    """, (
                        new_status,
                        bus_id
                    ))

                    bus_status = new_status

                else:

                    bus_status = bus["status"]


                # Move ONLY active buses
                if bus_status == "Active":

                    step = 0.00045 * (
                        max(bus["speed"], 10) / 30
                    )

                    direction = bus["direction"] or 1

                    new_lat = (
                        bus["latitude"]
                        + step * direction
                    )

                    new_lng = (
                        bus["longitude"]
                        + step * 0.65 * direction
                    )


                    # Keep buses inside Bengaluru area
                    if (
                        new_lat > 13.08
                        or new_lat < 12.88
                        or new_lng > 77.82
                        or new_lng < 77.45
                    ):

                        direction = -direction

                        new_lat = (
                            bus["latitude"]
                            + step * direction
                        )

                        new_lng = (
                            bus["longitude"]
                            + step * 0.65 * direction
                        )


                    connection.execute("""
                        UPDATE buses
                        SET latitude=?,
                            longitude=?,
                            direction=?
                        WHERE id=?
                    """, (
                        new_lat,
                        new_lng,
                        direction,
                        bus_id
                    ))


            connection.commit()
            connection.close()

        except Exception as error:

            print(
                "Simulation error:",
                error
            )

        # Check every 2 seconds
        time.sleep(2)

threading.Thread(target=simulate_bus_movement, daemon=True).start()

@app.route("/")
def home():
    if not login_required():
        return redirect(url_for("login"))
    return render_template("index.html", user_name=session.get("user_name"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        connection = get_connection()
        user = connection.execute("""
            SELECT * FROM users
            WHERE email = ? OR mobile = ?
        """, (identifier, identifier)).fetchone()
        connection.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("home"))

        return render_template("login.html", error="Invalid mobile/email or password.")

    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        mobile = request.form.get("mobile", "").strip()
        password = request.form.get("password", "")

        if not name or not password or (not email and not mobile):
            return render_template("signup.html", error="Please fill all required fields.")

        connection = get_connection()
        try:
            connection.execute("""
                INSERT INTO users (name, email, mobile, password)
                VALUES (?, ?, ?, ?)
            """, (name, email or None, mobile or None, generate_password_hash(password)))
            connection.commit()
        except Exception:
            connection.close()
            return render_template("signup.html", error="Email or mobile already registered.")
        connection.close()

        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/admin")
def admin():
    if not login_required():
        return redirect(url_for("login"))
    return render_template("admin.html")

@app.route("/api/buses", methods=["GET"])
def get_buses():

    if not login_required():
        return jsonify({"error": "Login required"}), 401

    connection = get_connection()

    buses = connection.execute(
        "SELECT * FROM buses ORDER BY id"
    ).fetchall()

    connection.close()

    current_time = time.time()

    result = []

    for bus in buses:

        bus_data = dict(bus)

        if bus["id"] in status_timers:

            remaining = max(
                0,
                int(
                    status_timers[bus["id"]]["next_change"]
                    - current_time
                )
            )

            bus_data["remaining_seconds"] = remaining

        else:

            bus_data["remaining_seconds"] = 0

        result.append(bus_data)

    return jsonify(result)

@app.route("/api/buses/<int:bus_id>/location", methods=["PUT"])
def update_location(bus_id):
    if not login_required():
        return jsonify({"error": "Login required"}), 401

    data = request.get_json() or {}
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    speed = data.get("speed", 30)
    status = data.get("status", "Active")

    if latitude is None or longitude is None:
        return jsonify({"error": "Latitude and longitude are required"}), 400

    connection = get_connection()
    cursor = connection.execute("""
        UPDATE buses SET latitude=?, longitude=?, speed=?, status=? WHERE id=?
    """, (latitude, longitude, speed, status, bus_id))
    connection.commit()
    connection.close()

    if cursor.rowcount == 0:
        return jsonify({"error": "Bus not found"}), 404
    return jsonify({"message": "Bus location updated successfully"})

@app.route("/api/buses", methods=["POST"])
def add_bus():
    if not login_required():
        return jsonify({"error": "Login required"}), 401

    data = request.get_json() or {}
    if not data.get("bus_number") or not data.get("route"):
        return jsonify({"error": "Bus number and route are required"}), 400

    connection = get_connection()
    cursor = connection.execute("""
        INSERT INTO buses
        (bus_number, route, latitude, longitude, speed, status, direction)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data["bus_number"], data["route"],
        data.get("latitude", 12.9716),
        data.get("longitude", 77.5946),
        data.get("speed", 30), "Active", 1
    ))
    connection.commit()
    bus_id = cursor.lastrowid
    connection.close()
    return jsonify({"message": "Bus added successfully", "bus_id": bus_id})

@app.route("/api/buses/<int:bus_id>", methods=["DELETE"])
def delete_bus(bus_id):
    if not login_required():
        return jsonify({"error": "Login required"}), 401

    connection = get_connection()
    cursor = connection.execute("DELETE FROM buses WHERE id=?", (bus_id,))
    connection.commit()
    connection.close()

    if cursor.rowcount == 0:
        return jsonify({"error": "Bus not found"}), 404
    return jsonify({"message": "Bus deleted successfully"})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)
