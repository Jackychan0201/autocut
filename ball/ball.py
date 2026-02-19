import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Arc, Circle

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

MAX_SPEED = 7.0
MIN_SPEED = 3.0
DAMPING = 0.001
MIN_RESTITUTION = 1.1

# Vivid color palette
VIVID_COLORS = [
    "lime", "cyan", "magenta", "yellow", "orange", 
    "red", "deepskyblue", "springgreen", "fuchsia", "gold"
]

# ======================
# SIMULATION TARGETS
# ======================
TARGET_SIM_LENGTH = 50  # Desired duration in seconds
# With RESTITUTION 1.6, the ball clears rings much faster. Increasing ring density.
NUM_RINGS = max(10, int(TARGET_SIM_LENGTH * 0.7))
# Larger radius as requested
BALL_RADIUS = np.clip(0.15 - (TARGET_SIM_LENGTH * 0.001), 0.04, 0.06)

# Vivid color palette
VIVID_COLORS = [
    "lime", "cyan", "magenta", "yellow", "orange", 
    "red", "deepskyblue", "springgreen", "fuchsia", "gold"
]

INNER_RADIUS = 0.4
RADIUS_STEP = 1.6 / max(NUM_RINGS, 1) # Adjust step to fit max radius (~2.0)
GAP_SIZE = np.pi / 5  # Made gaps smaller (pi/5 -> pi/7)
BASE_ROT_SPEED = 2.2  # Faster rotation to make it harder (0.8 -> 1.5)

BALL_COLOR = np.random.choice(VIVID_COLORS)
RING_COLOR = np.random.choice(VIVID_COLORS)
while RING_COLOR == BALL_COLOR:
    RING_COLOR = np.random.choice(VIVID_COLORS)

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
ball_vel = np.array([1.5, 0.0])

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
base_gap_angle = np.pi / 2

for i in range(NUM_RINGS):
    r = INNER_RADIUS + i * RADIUS_STEP
    bias = np.random.uniform(-0.15,0.15)
    gap_angle = base_gap_angle + bias
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
# UPDATE FUNCTION
# ======================
def update(frame):
    global ball_pos, ball_vel, ROT_DIR, elapsed_time, SIM_LENGTH, simulation_running, cur_restitution

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
            print(f"🎯 Target was: {TARGET_SIM_LENGTH} seconds")
            simulation_running = False
            # We don't stop the animation source immediately to allow the last frame to render
            # but we flag it to stop processing physics.
            ani.event_source.stop()

    # Update visuals
    for ring in rings:
        if not ring["alive"]:
            continue
        ring["arc"].theta1 = np.degrees(ring["gap_angle"] + GAP_SIZE / 2)
        ring["arc"].theta2 = np.degrees(
            ring["gap_angle"] - GAP_SIZE / 2 + 2 * np.pi
        )

    # Update stopwatch
    mins = int(elapsed_time // 60)
    secs = int(elapsed_time % 60)
    cent = int((elapsed_time * 100) % 100)
    timer_text.set_text(f"{mins:02d}:{secs:02d}:{cent:02d}")

    ball.center = ball_pos
    return [ball, timer_text] + [r["arc"] for r in rings]

# ======================
# RUN ANIMATION
# ======================
ani = FuncAnimation(fig, update, interval=1000 / FPS, blit=True)
plt.show()
