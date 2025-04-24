import pygame
import random
import math

# --- Constants ---
SCREEN_W, SCREEN_H = 600, 750
BUBBLE_RADIUS = 18
BUBBLE_DIAM = BUBBLE_RADIUS * 2
VERTICAL_STEP = int(BUBBLE_RADIUS * math.sqrt(3))
R_STEP = BUBBLE_DIAM

LAUNCH_SPEED = 12
CLOUD_RADIUS = 400
CORE_RADIUS = 26

ANGULAR_DAMPING = 0.98
LAUNCHER_Y = SCREEN_H - 50

COLORS = [
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255),
]
GOLDEN_COLOR = (212, 175, 55)

# Precompute cloud center
CENTER_X = SCREEN_W // 2
CENTER_Y = SCREEN_H // 3


# --- Bubble Class ---
class Bubble:
    def __init__(self, x, y, color):
        self.x, self.y = x, y
        self.color = color
        self.vx = self.vy = 0
        self.bounce_count = 0

    def update(self):
        self.x += self.vx
        self.y += self.vy

    def draw(self, surf):
        pygame.draw.circle(
            surf,
            self.color,
            (int(self.x), int(self.y)),
            BUBBLE_RADIUS
        )


# --- Utility Functions ---
def worldPos(entry, angle, cx, cy):
    sin_a, cos_a = math.sin(angle), math.cos(angle)
    rx, ry = entry["slot"]["rx"], entry["slot"]["ry"]
    x = cx + rx * cos_a - ry * sin_a
    y = cy + rx * sin_a + ry * cos_a
    return x, y


def createSlots(gridRadius):
    """
    Builds a hexagon of slots using axial coordinates (q,r).
    gridRadius = how many rings out from center you want.
    """
    slots = []
    for q in range(-gridRadius, gridRadius + 1):
        for r in range(-gridRadius, gridRadius + 1):
            s = -q - r
            if abs(s) > gridRadius:
                continue
            # convert axial (q,r) to pixel offsets
            rx = q * BUBBLE_DIAM + r * BUBBLE_RADIUS
            ry = r * VERTICAL_STEP
            slots.append({
                "q": q,
                "r": r,
                "rx": rx,
                "ry": ry,
                "occupied": False
            })
    return slots


def seedInitialCloud(slots, initialRings=3):
    """
    Occupy every slot whose axial distance ≤ initialRings.
    """
    cloud = []
    for slot in slots:
        q, r = slot["q"], slot["r"]
        s      = -q - r
        if max(abs(q), abs(r), abs(s)) <= initialRings:
            slot["occupied"] = True
            cloud.append({
                "slot": slot,
                "color": random.choice(COLORS)
            })
    return cloud


def findNearestFreeSlot(slots, rx_new, ry_new):
 # how far out from center we are
    dist     = math.hypot(rx_new, ry_new)
    ring     = int(round(dist / R_STEP))
    max_local = R_STEP * 2      # you can tweak this (2× slot spacing)

def findNearestFreeSlot(slots, rxNew, ryNew):
    """
    Look only on ring, ring-1, ring+1 (in pixel‐based ring units),
    and pick the nearest free slot.
    """
    import math

    dist     = math.hypot(rxNew, ryNew)
    ringIdx  = int(round(dist / R_STEP))
    maxLocal = R_STEP * 2

    def ringSlots(r):
        return [
            s for s in slots
            if (not s["occupied"])
            and abs(math.hypot(s["rx"], s["ry"]) - r * R_STEP) < (R_STEP / 2)
        ]

    # try your ring, then one in / one out
    for r in (ringIdx, ringIdx - 1, ringIdx + 1):
        candidates = ringSlots(r)
        if not candidates:
            continue

        # prefer truly local ones first
        local = [
            s for s in candidates
            if (s["rx"] - rxNew)**2 + (s["ry"] - ryNew)**2 < maxLocal**2
        ]
        use = local if local else candidates

        # pick Cartesian‐closest
        return min(
            use,
            key=lambda s: (s["rx"] - rxNew)**2 + (s["ry"] - ryNew)**2
        )

    # no slot nearby
    return None


def findConnectedCluster(cloud, startIdx, worldPosFn):
    """
    DFS from the newly placed bubble at startIdx,
    collecting only same-color neighbors.
    """
    N       = len(cloud)
    target  = cloud[startIdx]["color"]
    visited = {startIdx}
    stack   = [startIdx]
    # cache world positions
    W = [worldPosFn(e) for e in cloud]

    while stack:
        u = stack.pop()
        ux, uy = W[u]
        for v in range(N):
            if v in visited or cloud[v]["color"] != target:
                continue
            vx, vy = W[v]
            # adjacent if centers < ~1.14*diameter
            if math.hypot(ux - vx, uy - vy) < BUBBLE_DIAM * 1.14:
                visited.add(v)
                stack.append(v)

    return visited

def removeClusterFromIndex(cloud, startIdx, worldPosFn, score):
    """
    Only remove the component containing startIdx (if size≥3).
    Returns (newCloud, removedEntries, newScore).
    """
    connected = findConnectedCluster(cloud, startIdx, worldPosFn)
    if len(connected) < 3:
        return cloud, [], score

    # clear those slots
    removed = [cloud[i] for i in connected]
    for entry in removed:
        entry["slot"]["occupied"] = False

    # rebuild survivors and update score
    newCloud = [e for i,e in enumerate(cloud) if i not in connected]
    score   += len(removed)
    return newCloud, removed, score

def removeFloatingClusters(cloud, worldPosFn, score):
    """
    After cluster removal, drop any bubbles that cannot
    trace a path back to the core.
    """
    import math
    N = len(cloud)
    W = [worldPosFn(e) for e in cloud]

    # 1) build adjacency lists
    neigh = [set() for _ in range(N)]
    for i in range(N):
        xi, yi = W[i]
        for j in range(i+1, N):
            xj, yj = W[j]
            if math.hypot(xi - xj, yi - yj) < BUBBLE_DIAM * 1.14:
                neigh[i].add(j)
                neigh[j].add(i)

    # 2) find all bubbles touching the core
    seeds = []
    for i,(x,y) in enumerate(W):
        if math.hypot(x - CENTER_X, y - CENTER_Y) < BUBBLE_DIAM * 1.1:
            seeds.append(i)

    # 3) flood-fill from those seeds
    reachable = set(seeds)
    stack     = seeds[:]
    while stack:
        u = stack.pop()
        for v in neigh[u]:
            if v not in reachable:
                reachable.add(v)
                stack.append(v)

    # 4) anything not in `reachable` is floating
    floating = [cloud[i] for i in range(N) if i not in reachable]
    for e in floating:
        e["slot"]["occupied"] = False
    survivors = [e for i,e in enumerate(cloud) if i in reachable]
    score += len(floating)
    return survivors, floating, score






# --- Physics Helpers ---
def handle_wall_and_ceiling_bounce(b):
    # walls
    if b.x < BUBBLE_RADIUS or b.x > SCREEN_W - BUBBLE_RADIUS:
        b.vx *= -1
        b.x = max(BUBBLE_RADIUS, min(b.x, SCREEN_W - BUBBLE_RADIUS))
        b.bounce_count += 1
    # ceiling
    if b.y < BUBBLE_RADIUS:
        b.vy *= -1
        b.y = BUBBLE_RADIUS


def should_reset_launcher(b):
    return b.bounce_count > 3 or b.y > SCREEN_H


def check_core_collision(b, cx, cy):
    return math.hypot(b.x - cx, b.y - cy) < CORE_RADIUS


def attach_to_cloud(b, cloud, slots, angle, cx, cy):
    rel_x = b.x - cx
    rel_y = b.y - cy
    sin_a, cos_a = math.sin(-angle), math.cos(-angle)
    rx_new = rel_x * cos_a - rel_y * sin_a
    ry_new = rel_x * sin_a + rel_y * cos_a

    for entry in cloud:
        sx, sy = worldPos(entry, angle, cx, cy)
        if math.hypot(b.x - sx, b.y - sy) < BUBBLE_DIAM:
            slot = findNearestFreeSlot(slots, rx_new, ry_new)
            if slot:
                slot["occupied"] = True
                cloud.append({"slot": slot, "color": b.color})
                impulse = (rel_x * b.vy - rel_y * b.vx) * 0.00008
                return cloud, impulse
    return cloud, 0.0

def spawnFalling(fall_list, to_fall, angle, cx, cy):
    for e in to_fall:
        fx, fy = worldPos(e, angle, cx, cy)
        nb = Bubble(fx, fy, e["color"])
        nb.falling = True
        fall_list.append(nb)


# --- Module Functions ---
def init_pygame():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Bubbles")
    clock = pygame.time.Clock()
    return screen, clock


def initGame():
    gridRadius = CLOUD_RADIUS // R_STEP
    slots      = createSlots(gridRadius)
    cloud = seedInitialCloud(slots, initialRings=3)
    falling = []
    angle = 0.0
    angVel = 5.0
    score = 0
    next_b = Bubble(CENTER_X, LAUNCHER_Y, random.choice(COLORS))
    firing = False
    running = True
    return slots, cloud, falling, angle, angVel, score, next_b, firing, running


def process_input(next_b, firing, cloud):
    running = True
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False
        elif (ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE) \
             or (ev.type == pygame.MOUSEBUTTONDOWN):
            if not firing:
                next_b.y = LAUNCHER_Y
                active = {e["color"] for e in cloud}
                if next_b.color not in active and active:
                    next_b.color = random.choice(list(active))
                mx, my = pygame.mouse.get_pos()
                dx, dy = mx - next_b.x, my - next_b.y
                mag = math.hypot(dx, dy)
                if mag:
                    next_b.vx = dx / mag * LAUNCH_SPEED
                    next_b.vy = dy / mag * LAUNCH_SPEED
                    firing = True
    return running, firing, next_b


def handle_keyboard(next_b, firing, dt):
    keys = pygame.key.get_pressed()
    if keys[pygame.K_a]:
        next_b.x = max(BUBBLE_RADIUS, next_b.x - 5)
    if keys[pygame.K_d]:
        next_b.x = min(SCREEN_W - BUBBLE_RADIUS, next_b.x + 5)
    if not firing:
        next_b.y = LAUNCHER_Y
    return next_b


def updateProjectile(
    next_b, firing, slots, cloud, falling,
    angle, angVel, score
):
    next_b.update()
    handle_wall_and_ceiling_bounce(next_b)

    if should_reset_launcher(next_b):
        firing = False
        next_b = Bubble(CENTER_X, LAUNCHER_Y, next_b.color)
        return firing, next_b, slots, cloud, falling, angVel, score

    if check_core_collision(next_b, CENTER_X, CENTER_Y):
        print(f"Game Over! Hit the core. Final Score: {score}")
        pygame.time.wait(2000)
        return False, next_b, slots, cloud, falling, angVel, score

    cloud, impulse = attach_to_cloud(
        next_b, cloud, slots, angle, CENTER_X, CENTER_Y
    )
    if impulse:
        angVel += impulse
                # the new bubble is last in cloud
        startIdx = len(cloud) - 1
        worldFn  = lambda e: worldPos(e, angle, CENTER_X, CENTER_Y)
        cloud, toFall, score = removeClusterFromIndex(
            cloud, startIdx, worldFn, score
        )

        spawnFalling(falling, toFall, angle, CENTER_X, CENTER_Y)

        cloud, extraFall, score = removeFloatingClusters(
            cloud,
            lambda e: worldPos(e, angle, CENTER_X, CENTER_Y), 
            score
        )
    
        spawnFalling(falling, extraFall, angle, CENTER_X, CENTER_Y)


        firing = False
        next_b = Bubble(CENTER_X, LAUNCHER_Y, random.choice(COLORS))



    return firing, next_b, slots, cloud, falling, angVel, score


def update_falling(falling, dt):
    for b in falling[:]:
        b.vy += 400 * dt
        b.x += b.vx * dt
        b.y += b.vy * dt
        if b.y - BUBBLE_RADIUS > SCREEN_H:
            falling.remove(b)
    return falling


def update_rotation(angle, angVel):
    angle += angVel
    angVel *= ANGULAR_DAMPING
    return angle, angVel


def draw(
    screen, cloud, falling, next_b, angle
):
    screen.fill((30, 30, 30))

    for b in falling:
        b.draw(screen)

    for e in cloud:
        x, y = worldPos(e, angle, CENTER_X, CENTER_Y)
        pygame.draw.circle(
            screen,
            e["color"],
            (int(x), int(y)),
            BUBBLE_RADIUS
        )

    pygame.draw.circle(
        screen,
        GOLDEN_COLOR,
        (CENTER_X, CENTER_Y),
        BUBBLE_RADIUS * 2
    )
    # launcher tube
    pygame.draw.line(
        screen,
        (200, 200, 200),
        (next_b.x - 20, LAUNCHER_Y + 20),
        (next_b.x + 20, LAUNCHER_Y + 20),
        4
    )
    next_b.draw(screen)
    pygame.display.flip()


# --- Main ---
def main():
    screen, clock = init_pygame()
    (
        slots, cloud, falling,
        angle, angVel, score,
        next_b, firing, running
    ) = initGame()

    while running:
        dt = clock.tick(60) / 1000.0

        running, firing, next_b = process_input(next_b, firing, cloud)
        next_b = handle_keyboard(next_b, firing, dt)

        if firing:
            (
                firing, next_b, slots,
                cloud, falling, angVel, score
            ) = updateProjectile(
                next_b, firing, slots,
                cloud, falling, angle,
                angVel, score
            )

        falling = update_falling(falling, dt)
        angle, angVel = update_rotation(angle, angVel)
        draw(screen, cloud, falling, next_b, angle)

    pygame.quit()


if __name__ == "__main__":
    main()
