import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Arc, Circle
import logging

# ======================
# CONFIGURATION
# ======================
FPS = 60
DT = 1 / FPS

GRAVITY = -3.0
BASE_RESTITUTION = 1.8
cur_restitution = BASE_RESTITUTION
TANGENTIAL_KICK = 0.6
SUBSTEPS = 3

MAX_SPEED_BASE = 5.6
MIN_SPEED_BASE = 2.4
MAX_SPEED = MAX_SPEED_BASE
MIN_SPEED = MIN_SPEED_BASE
DAMPING = 0.001
MIN_RESTITUTION = 1.1


# ======================
# SIMULATION SETTINGS
# ======================
NUM_RINGS = 30
BALL_RADIUS = 0.05

# Vivid color palette
VIVID_COLORS = [
    "lime", "cyan", "magenta", "yellow", "orange", 
    "red", "deepskyblue", "springgreen", "fuchsia", "gold"
]

INNER_RADIUS = 0.4
RADIUS_STEP = 1.6 / max(NUM_RINGS, 1) # Adjust step to fit max radius (~2.0)
GAP_SIZE = np.pi / 5  # Made gaps smaller (pi/5 -> pi/7)
BASE_ROT_SPEED = 3.2  # Increased speed for higher difficulty

def get_contrast_colors():
    """Pick two highly contrasting colors from the vivid palette."""
    c1 = np.random.choice(VIVID_COLORS)
    # Filter out colors that might be too similar (simplified for now by just picking a different one)
    c2 = np.random.choice([c for c in VIVID_COLORS if c != c1])
    return c1, c2

BALL_COLOR, RING_COLOR = get_contrast_colors()

# Timing state
elapsed_time = 0.0
SIM_LENGTH = 0.0
simulation_running = True

# ======================
# FIGURE SETUP
# ======================
fig, ax = plt.subplots(figsize=(6, 6), facecolor="black")
ax.set_facecolor("black")
ax.set_xlim(-2, 2)
ax.set_ylim(-2.5, 2)
ax.set_aspect("equal")
ax.axis("off")

# ======================
# BALL
# ======================
ball_pos = np.array([0.0, 0.0])
ball_vel = np.array([1.2, 0.0])

ball = Circle(ball_pos, BALL_RADIUS, color=BALL_COLOR)
ax.add_patch(ball)

# ======================
# STOPWATCH
# ======================
timer_text = ax.text(
    0, -2.35, "00:00:00", 
    color="white", 
    fontsize=24, 
    ha="center", 
    fontfamily="monospace",
    fontweight="bold",
    bbox=dict(facecolor='black', edgecolor='black', alpha=1.0)
)

# ======================
# RINGS
# ======================
rings = []
shared_gap_angle = np.random.uniform(0, 2 * np.pi)

for i in range(NUM_RINGS):
    r = INNER_RADIUS + i * RADIUS_STEP
    gap_angle = shared_gap_angle
    speed = BASE_ROT_SPEED / (1 + i * 0.15)

    arc = Arc(
        (0, 0),
        2 * r,
        2 * r,
        linewidth=2,
        color=RING_COLOR,
    )
    ax.add_patch(arc)

    rings.append({
        "radius": r,
        "gap_angle": gap_angle,
        "speed": speed,
        "arc": arc,
        "alive": True,
    })

# ======================
# GLOBAL ROTATION DIRECTION
# ======================
ROT_DIR = 1   # flips after each ring pass

# ======================
# HELPERS
# ======================
def wrap(a):
    return np.mod(a, 2 * np.pi)

def in_gap(theta, gap):
    d = wrap(theta - gap)
    return d < GAP_SIZE / 2 or d > 2 * np.pi - GAP_SIZE / 2

# ======================
# PARTICLES (Optimized using Scatter)
# ======================
# We use a single scatter collection for all particles to maximize FPS
particle_scatter = ax.scatter([], [], s=5, alpha=0.9, edgecolors="none")
particles_data = []

def spawn_particles(x, y, color):
    """Add new particle data to the system."""
    num_particles = 25
    for _ in range(num_particles):
        angle = np.random.uniform(0, 2 * np.pi)
        speed = np.random.uniform(1.0, 4.5)
        p_vel = np.array([np.cos(angle) * speed, np.sin(angle) * speed])
        
        particles_data.append({
            "pos": np.array([x, y]),
            "vel": p_vel,
            "life": 0.4 + np.random.uniform(0, 0.4),
            "color": color
        })

# ======================
# UPDATE FUNCTION
# ======================
def update(frame):
    global ball_pos, ball_vel, ROT_DIR, elapsed_time, SIM_LENGTH, simulation_running, cur_restitution, particles_data

    if not simulation_running:
        return [ball] + [r["arc"] for r in rings]

    for _ in range(SUBSTEPS):
        prev_pos = ball_pos.copy()
        
        elapsed_time += DT / SUBSTEPS

        # Gravity
        ball_vel[1] += GRAVITY * DT / SUBSTEPS
        ball_pos += ball_vel * DT / SUBSTEPS

        r_prev = np.linalg.norm(prev_pos)
        r_now = np.linalg.norm(ball_pos)
        theta_ball = np.arctan2(ball_pos[1], ball_pos[0])

        for ring in rings:
            if not ring["alive"]:
                continue

            # Rotate using global direction
            ring["gap_angle"] = wrap(
                ring["gap_angle"] + ROT_DIR * ring["speed"] * DT / SUBSTEPS
            )

            r = ring["radius"]
            crossed = (r_prev - r) * (r_now - r) <= 0

            if crossed:
                if in_gap(theta_ball, ring["gap_angle"]):
                    ring["alive"] = False
                    ring["arc"].set_visible(False)
                    # ✨ SPAWN PARTICLES
                    spawn_particles(ball_pos[0], ball_pos[1], RING_COLOR)

                    # � NERF: Decrease speed and bounce power
                    ball_vel *= 0.6
                    cur_restitution = max(MIN_RESTITUTION, cur_restitution * 0.6)

                    # �🔄 REVERSE ALL RINGS
                    ROT_DIR *= -1

                else:
                    normal = ball_pos / (r_now + 1e-8)
                    tangent = np.array([-normal[1], normal[0]])

                    vn = np.dot(ball_vel, normal)

                    # Bounce
                    ball_vel -= (1 + cur_restitution) * vn * normal
                    ball_vel += TANGENTIAL_KICK * tangent
                    
                    # 📈 REGAIN: Increase bounce power per impact
                    cur_restitution = min(BASE_RESTITUTION, cur_restitution + 0.2)

                    # Re-project
                    direction = np.sign(r_prev - r)
                    ball_pos = normal * (r + direction * BALL_RADIUS)

        # -------- Speed control --------
        speed = np.linalg.norm(ball_vel)
        if speed > 1e-6:
            ball_vel *= (1 - DAMPING * speed)

        if speed > MAX_SPEED:
            ball_vel *= MAX_SPEED / speed
        elif speed < MIN_SPEED and speed > 1e-6:
            ball_vel *= MIN_SPEED / speed

    # Check if all rings are gone
    if all(not r["alive"] for r in rings):
        if simulation_running:
            SIM_LENGTH = elapsed_time
            print(f"✅ Simulation Complete!")
            print(f"⏱️  Actual SIM_LENGTH: {SIM_LENGTH:.2f} seconds")
            
            if SIM_LENGTH < 20.0:
                logger.info("⏩ Too fast (<20s). Auto-Restarting...")
                reset_simulation()
                return [ball, timer_text, particle_scatter] + [r["arc"] for r in rings]

            simulation_running = False
            ani.event_source.stop()

    # Update visuals only for ALIVE rings
    living_rings = [r for r in rings if r["alive"]]
    for ring in living_rings:
        ring["arc"].theta1 = np.degrees(ring["gap_angle"] + GAP_SIZE / 2)
        ring["arc"].theta2 = np.degrees(ring["gap_angle"] - GAP_SIZE / 2 + 2 * np.pi)

    # Update stopwatch
    mins = int(elapsed_time // 60)
    secs = int(elapsed_time % 60)
    cent = int((elapsed_time * 100) % 100)
    timer_text.set_text(f"{mins:02d}:{secs:02d}:{cent:02d}")

    # ⏱️ AUTO-RESTART: If exceeds 30 seconds
    if elapsed_time > 30.0:
        logger.info("⏰ Time Limit Reached (30s). Auto-Restarting...")
        reset_simulation()
        return [ball, timer_text, particle_scatter] + [r["arc"] for r in rings]

    # 🎇 Update Particles (Highly Optimized)
    alive_p = []
    points = []
    colors = []
    
    for p in particles_data:
        p["life"] -= DT
        if p["life"] > 0:
            p["vel"][1] += GRAVITY * DT
            p["pos"] += p["vel"] * DT
            alive_p.append(p)
            points.append(p["pos"])
            # Alpha logic: mapping color name to RGBA
            rgb = plt.cm.colors.to_rgba(p["color"])
            colors.append((rgb[0], rgb[1], rgb[2], p["life"]))
    
    particles_data[:] = alive_p
    
    if points:
        particle_scatter.set_offsets(points)
        particle_scatter.set_color(colors)
        particle_scatter.set_visible(True)
    else:
        particle_scatter.set_visible(False)

    ball.center = ball_pos
    return [ball, timer_text, particle_scatter] + [r["arc"] for r in rings]

# ======================
# INTERACTIVITY & RESET
# ======================
def reset_simulation():
    global ball_pos, ball_vel, cur_restitution, elapsed_time, simulation_running, ROT_DIR, rings, particles_data, RING_COLOR, MAX_SPEED, MIN_SPEED
    
    # 🧹 Clear Particles
    particles_data.clear()
    particle_scatter.set_offsets(np.empty((0, 2)))
    
    # 🏎️ SCALE PHYSICS
    ball_pos = np.array([0.0, 0.0])
    ball_vel = np.array([1.2, 0.0]) 
    MAX_SPEED = MAX_SPEED_BASE
    MIN_SPEED = MIN_SPEED_BASE
    cur_restitution = 1.8           
    
    elapsed_time = 0.0
    ROT_DIR = 1
    
    # 🎲 SHARED RANDOM GAP POSITION
    shared_gap_angle = np.random.uniform(0, 2 * np.pi)
    
    # Reset rings
    for i, ring in enumerate(rings):
        ring["alive"] = True
        ring["arc"].set_visible(True)
        # Apply current speed multiplier to rings
        ring["speed"] = (BASE_ROT_SPEED) / (1 + i * 0.15)
        # All rings start aligned at the shared center
        ring["gap_angle"] = shared_gap_angle
    
    # Reset UI
    timer_text.set_text("00:00:00")
    
    # Reset Colors
    new_ball_color, new_ring_color = get_contrast_colors()
    RING_COLOR = new_ring_color # Update global for particles
    ball.set_color(new_ball_color)
    for ring in rings:
        ring["arc"].set_color(new_ring_color)
    
    # 🛠️ macOS Stability: Only start if not already running
    if not simulation_running:
        simulation_running = True
        try:
            if ani.event_source:
                ani.event_source.start()
        except Exception:
            pass
    else:
        simulation_running = True

def on_key(event):
    if event.key == "enter":
        reset_simulation()

fig.canvas.mpl_connect("key_press_event", on_key)

# Configure logging for the script
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("BallSim")

# ======================
# RUN ANIMATION
# ======================
ani = FuncAnimation(fig, update, interval=1000 / FPS, blit=True, cache_frame_data=False)
plt.show()
