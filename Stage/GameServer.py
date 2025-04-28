import pygame
import random
import math
import socket
import threading
import queue
import time

# Network
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
ENABLE_NETWORK_INPUT = True
net_input = queue.Queue()
client_connected = False
net_mouse_pos = None

def server_thread(host='', port=5000):
    global client_connected

    # figure out a reasonable outward‐facing IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    host_ip = s.getsockname()[0]
    s.close()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(1)

    print(f"Server listening on {host_ip}:{port}, waiting for client…")

    conn, addr = srv.accept()
    print(f"Client connected from {addr[0]}:{addr[1]}")
    client_connected = True

    conn.setblocking(False)
    while True:
        try:
            data = conn.recv(128).decode()
            if not data:
                break
            net_input.put(data)
        except BlockingIOError:
            pass
        time.sleep(0.01)

    conn.close()
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Global Values
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
SCREEN_W, SCREEN_H = 600, 750
BUBBLE_RADIUS = 18
BUBBLE_DIAM = BUBBLE_RADIUS * 2
VERTICAL_STEP = int(BUBBLE_RADIUS * math.sqrt(3))
R_STEP = BUBBLE_DIAM

#--- Game Constants ---
LAUNCH_SPEED = 12
CLOUD_RADIUS = 400
CORE_RADIUS = 20
penaltybubbles = []

ANGULAR_DAMPING = 0.98
LAUNCHER_Y = SCREEN_H - 50

# Precompute cloud center
CENTER_X = SCREEN_W // 2
CENTER_Y = SCREEN_H // 3
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Game Ending States
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
gameOver = False

# Alloted time for score sequence
endTime     = None        

# 'win' or 'lose'
outcome     = None   

# Score Outcome     
baseScore = 0
stars = 0
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Assets and Constants
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Bubble Textures
BUBBLE_TEXTURE_PATHS = {
    (255,   0,   0): 'assets/textures/bubbleRed.png',
    (  0, 255,   0): 'assets/textures/bubbleGreen.png',
    (  0,   0, 255): 'assets/textures/bubbleBlue.png',
    (255, 255,   0): 'assets/textures/bubbleYellow.png',
    (255,   0, 255): 'assets/textures/bubblePurple.png',
    (255, 165,   0): 'assets/textures/bubbleOrange.png',
}

# Bubble Texture Implementation
bubble_textures  = {}   # full-size
preview_textures = {}   # half-size for ammo queue


# Star Textures
STAR_EMPTY_PATH = 'assets/textures/star_empty.png'
STAR_FULL_PATH  = 'assets/textures/star_full.png'

# Star Texture Implementation
star_empty_texture = None
star_full_texture  = None

# Constant Colors
COLORS = [
    (255,   0,   0),   # red
    (  0, 255,   0),   # green
    (  0,   0, 255),   # blue
    (255, 255,   0),   # yellow
    (255,   0, 255),   # purple
    (255, 165,   0),   # orange
]

# Core Color
BLUE_COLOR = (40, 175, 230)

# --------------------------------------------------------------------------------

# Sound Engine
SHATTER_SOUND = None #pygame.mixer.Sound('assets/sounds/shatter.wav')

# Thud Sound
THUD_SOUND = None #pygame.mixer.Sound('assets/sounds/thud.wav')

# Fall Sound
FALL_SOUND = None #pygame.mixer.Sound('assets/sounds/fall.mp3')

# Fall Sound
HIT_SOUND = None #pygame.mixer.Sound('assets/sounds/hit.wav')
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Bubble Class
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
class Bubble:
    def __init__(self, x, y, color):
        self.x, self.y = x, y
        self.color = color
        self.vx = self.vy = 0
        self.bounce_count = 0

    def update(self):
        self.x += self.vx
        self.y += self.vy

    # Draw Bubble with texture if available
    def draw(self, surf):
        tex = bubble_textures.get(self.color)
        if tex:
            surf.blit(tex, (int(self.x - BUBBLE_RADIUS), int(self.y - BUBBLE_RADIUS)))
        else:
            pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), BUBBLE_RADIUS)
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Shatter Class
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
class ShatterParticle:
    def __init__(self, pos, vel, color, lifetime=1.0):
        self.x, self.y = pos
        self.vx, self.vy = vel
        self.color = color
        self.life = lifetime

    def update(self, dt):
        self.life -= dt
        self.x += self.vx * dt
        self.y += self.vy * dt

    def draw(self, surf):
        if self.life > 0:
            r = int(CORE_RADIUS * (self.life))  # shrink over time
            pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), max(1,r))
shatterParticles = []
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Core Render Functions
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def spawnShatter():
    for i in range(6):
        ang = math.radians(60 * i + 30)
        x = CENTER_X + math.cos(ang) * CORE_RADIUS
        y = CENTER_Y + math.sin(ang) * CORE_RADIUS
        dir_ang = random.uniform(ang - 0.5, ang + 0.5)
        speed = random.uniform(200, 300)
        vx, vy = math.cos(dir_ang) * speed, math.sin(dir_ang) * speed
        shatterParticles.append(ShatterParticle((x, y), (vx, vy), BLUE_COLOR, 1.0))
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Shatter Adjustment Function
def updateShatterParticles(dt):
    for p in shatterParticles[:]:
        p.update(dt)
        if p.life <= 0:
            shatterParticles.remove(p)
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Create Core Function
def drawCore(surf, angle):
    hexR = CORE_RADIUS
    
    diam = hexR * 2

    tmp = pygame.Surface((diam, diam), pygame.SRCALPHA)
    col = (*BLUE_COLOR, 128)
    pts = [(hexR + math.cos(math.radians(60*i)) * hexR,
            hexR + math.sin(math.radians(60*i)) * hexR)
           for i in range(6)]
    pygame.draw.polygon(tmp, col, pts)

      # Rotate the hexagon
    rot = pygame.transform.rotate(tmp, math.degrees(-angle) + 30) # +30 to align with the surrounding bubbles

    # Center the rotated hexagon
    rect = rot.get_rect(center=(CENTER_X, CENTER_Y))

    # Draw the rotated hexagon
    surf.blit(rot, rect)
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Collision Logic Function
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def handleCoreHit(b):
    if math.hypot(b.x - CENTER_X, b.y - CENTER_Y) < CORE_RADIUS:
        return True
    return False
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Slot Position Function
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def worldPos(entry, angle, cx, cy):
    sin_a, cos_a = math.sin(angle), math.cos(angle)
    rx, ry = entry["slot"]["rx"], entry["slot"]["ry"]
    x = cx + rx * cos_a - ry * sin_a
    y = cy + rx * sin_a + ry * cos_a
    return x, y


# Empty Slot Generation Function
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def createSlots(gridRadius):
    slots = []
    for q in range(-gridRadius, gridRadius + 1):
        for r in range(-gridRadius, gridRadius + 1):
            s = -q - r
            if abs(s) > gridRadius:
                continue
            # Convert Axis to Cartesian coordinates (Very Fun)
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


# Seed Bubble Cloud Core Slots
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def seedInitialCloud(slots, initialRings=3):
    cloud = []
    for slot in slots:
        q, r = slot["q"], slot["r"]
        s      = -q - r

        if q == 0 and r == 0:
            continue

        if max(abs(q), abs(r), abs(s)) <= initialRings:
            slot["occupied"] = True
            cloud.append({
                "slot": slot,
                "color": random.choice(COLORS)
            })
    return cloud


# Identify Nearest Free Slot Function
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def findNearestFreeSlot(slots, rxNew, ryNew):
    dist     = math.hypot(rxNew, ryNew)
    ringIdx  = int(round(dist / R_STEP))
    maxLocal = R_STEP * 2

    def ringSlots(r):
        return [
            s for s in slots
            if (not s["occupied"])
            and abs(math.hypot(s["rx"], s["ry"]) - r * R_STEP) < (R_STEP / 2)
        ]

    # Ring slots are ordered by distance from center
    for r in (ringIdx, ringIdx - 1, ringIdx + 1):
        candidates = ringSlots(r)
        if not candidates:
            continue

        # Perfer a slot in the same ring (Causes bugs but works)
        local = [
            s for s in candidates
            if (s["rx"] - rxNew)**2 + (s["ry"] - ryNew)**2 < maxLocal**2
        ]
        use = local if local else candidates

        # Attempt secondary ring if no slots found
        return min(
            use,
            key=lambda s: (s["rx"] - rxNew)**2 + (s["ry"] - ryNew)**2
        )

    # No slots found, already occupied or out of bounds. The game should be over very soon...
    return None


# Idenify and Remove Clusters Function
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def findConnectedCluster(cloud, startIdx, worldPosFn):
    #Neighborhood search
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
            # Adjusted distance check to avoid floating point errors
            if math.hypot(ux - vx, uy - vy) < BUBBLE_DIAM * 1.14:
                visited.add(v)
                stack.append(v)
    return visited


# Remove Cluster Index Function
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def removeClusterFromIndex(cloud, startIdx, worldPosFn, score):
    connected = findConnectedCluster(cloud, startIdx, worldPosFn)
    if len(connected) < 3:
        return cloud, [], score

    # clear those slots
    removed = [cloud[i] for i in connected]
    for entry in removed:
        entry["slot"]["occupied"] = False

    # rebuild the cloud without the removed entries. Adjust the slots and score
    newCloud = [e for i,e in enumerate(cloud) if i not in connected]
    score   += len(removed)
    return newCloud, removed, score

def removeFloatingClusters(cloud, worldPosFn, score):
    N = len(cloud)
    W = [worldPosFn(e) for e in cloud]

    # Build adjacency lists
    neigh = [set() for _ in range(N)]
    for i in range(N):
        xi, yi = W[i]
        for j in range(i+1, N):
            xj, yj = W[j]
            if math.hypot(xi - xj, yi - yj) < BUBBLE_DIAM * 1.14:
                neigh[i].add(j)
                neigh[j].add(i)

    # Find all bubbles touching the core
    seeds = []
    for i, (x, y) in enumerate(W):
        if math.hypot(x - CENTER_X, y - CENTER_Y) < BUBBLE_DIAM * 1.1:
            seeds.append(i)

    # Flood-fill from those seeds
    reachable = set(seeds)
    stack     = seeds[:]
    while stack:
        u = stack.pop()
        for v in neigh[u]:
            if v not in reachable:
                reachable.add(v)
                stack.append(v)

    # Anything not reachable is floating and removed
    floating = [cloud[i] for i in range(N) if i not in reachable]
    for e in floating:
        e["slot"]["occupied"] = False

    # HUGE potential BUG here: Occupied slots can be overwritten and cause unwanted collisions
    # (we should only overwrite slots that are not occupied by survivors) look through every slot referenced by BOTH survivors and floating entries)
    for slot in (e["slot"] for e in cloud + floating):
        if slot["q"] == 0 and slot["r"] == 0:
            slot["occupied"] = True
            break

    # Rebuild and update score
    survivors = [e for i, e in enumerate(cloud) if i in reachable]
    score    += len(floating)
    return survivors, floating, score
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Physics Functions
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def handleWallAndCeilingBounce(b):
    # walls
    if b.x < BUBBLE_RADIUS or b.x > SCREEN_W - BUBBLE_RADIUS:
        b.vx *= -1
        b.x = max(BUBBLE_RADIUS, min(b.x, SCREEN_W - BUBBLE_RADIUS))
        b.bounce_count += 1
    # ceiling
    if b.y < BUBBLE_RADIUS:
        b.vy *= -1
        b.y = BUBBLE_RADIUS
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Check if the launcher should be reset
def shouldResetLauncher(b):
    return b.bounce_count > 3 or b.y > SCREEN_H


# Attach to cloud function
def attachToCloud(b, cloud, slots, angle, cx, cy):
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
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Spawn falling bubbles
def spawnFalling(fall_list, to_fall, angle, cx, cy):
    if to_fall:
        FALL_SOUND.play()
    for e in to_fall:
        fx, fy = worldPos(e, angle, cx, cy)
        nb = Bubble(fx, fy, e["color"])
        nb.falling = True
        fall_list.append(nb)
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Initialize Pygame assets and textures
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def init_pygame():
    pygame.init()
    pygame.font.init()
    pygame.mixer.init()
    
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Bubbles")
    global star_empty_texture, star_full_texture, scoreFont  

    global SHATTER_SOUND, THUD_SOUND, FALL_SOUND, HIT_SOUND
    SHATTER_SOUND = pygame.mixer.Sound('assets/sounds/shatter.wav')
    THUD_SOUND    = pygame.mixer.Sound('assets/sounds/thud.wav')
    FALL_SOUND    = pygame.mixer.Sound('assets/sounds/fall.mp3')
    HIT_SOUND     = pygame.mixer.Sound('assets/sounds/hit.wav')

    # Sound: volume
    SHATTER_SOUND.set_volume(0.5)
    THUD_SOUND.set_volume(0.5)
    FALL_SOUND.set_volume(0.5)
    HIT_SOUND.set_volume(0.4)
    
    # Score Font Setup
    scoreFont = pygame.font.SysFont("Arial", 24)
    
    # Load textures
    for color, path in BUBBLE_TEXTURE_PATHS.items():
        try:
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.scale(img, (BUBBLE_DIAM, BUBBLE_DIAM))
            bubble_textures[color] = img
            
            # Scale to half size for preview
            # Preview = half-diameter
            pv = pygame.transform.scale(img, (BUBBLE_RADIUS, BUBBLE_RADIUS))
            preview_textures[color] = pv

        except pygame.error as e:
            print(f"Failed to load {path}: {e}")

    global star_empty_texture, star_full_texture
    try:
        star_empty_texture = pygame.image.load(STAR_EMPTY_PATH).convert_alpha()
        star_full_texture  = pygame.image.load(STAR_FULL_PATH ).convert_alpha()
        star_empty_texture = pygame.transform.scale(star_empty_texture, (64,64))
        star_full_texture  = pygame.transform.scale(star_full_texture,  (64,64))
    except pygame.error as e:
        print(f"Failed to load star textures: {e}")

    clock = pygame.time.Clock()
    return screen, clock

# Game Initialization
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def initGame():
    global initialBallCount

    gridRadius = CLOUD_RADIUS // R_STEP
    slots      = createSlots(gridRadius)
    for slot in slots:
        if slot["q"] == 0 and slot["r"] == 0:
            slot["occupied"] = True
            break
    cloud = seedInitialCloud(slots, initialRings=3)
    initialBallCount = len(cloud)
    falling = []
    angle = 0.0
    angVel = 5.0
    score = 0
    firing = False
    running = True
    initialCount = random.randint(3,7)
    activeColors = [e["color"] for e in cloud] or COLORS
    ammoQueue    = [random.choice(activeColors) for _ in range(initialCount)]

    # nextB should be the first color in the queue
    nextB = Bubble(CENTER_X, LAUNCHER_Y, ammoQueue[0])
    return slots, cloud, falling, angle, angVel, score, nextB, firing, running, ammoQueue  

# Input Processing Function
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def processInput(nextB, firing, cloud, ammoQueue):
    running = True
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False
        elif (ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE) \
             or (ev.type == pygame.MOUSEBUTTONDOWN):
            if not firing:
                nextB.y = LAUNCHER_Y
                active = [e["color"] for e in cloud]
                if active and nextB.color not in active:
                    nextB.color = random.choice(active)
                mx, my = pygame.mouse.get_pos()
                dx, dy = mx - nextB.x, my - nextB.y
                mag = math.hypot(dx, dy)
                if mag:
                    nextB.vx = dx / mag * LAUNCH_SPEED
                    nextB.vy = dy / mag * LAUNCH_SPEED
                    firing = True
    # ammoQueue is unchanged here
    return running, firing, nextB, ammoQueue
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Keyboard Input Function
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def handleKeyboard(nextB, firing, dt):
    keys = pygame.key.get_pressed()
    if keys[pygame.K_a]:
        nextB.x = max(BUBBLE_RADIUS, nextB.x - 5)
    if keys[pygame.K_d]:
        nextB.x = min(SCREEN_W - BUBBLE_RADIUS, nextB.x + 5)
    if not firing:
        nextB.y = LAUNCHER_Y
    return nextB
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Projectile Update Function
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def updateProjectile(
    nextB, firing, slots, cloud, falling,
    angle, angVel, score, ammoQueue                
):
    nextB.update()
    handleWallAndCeilingBounce(nextB)

    # reset launcher if too many bounces or out of bounds
    if shouldResetLauncher(nextB):
        firing = False
        nextB.x, nextB.y   = CENTER_X, LAUNCHER_Y
        nextB.vx, nextB.vy = 0, 0
        nextB.bounce_count = 0
        return firing, nextB, slots, cloud, falling, angVel, score, ammoQueue

    # core‐hit check → end game
    if handleCoreHit(nextB):
        global gameOver, endTime, outcome, baseScore, stars
        spawnShatter()
        SHATTER_SOUND.play()
        outcome   = 'win'
        gameOver  = True
        endTime   = pygame.time.get_ticks()
        baseScore = score

        remaining = len(cloud)
        frac      = remaining / initialBallCount
        if remaining == 0:
            stars = 3
        elif frac < 0.25:
            stars = 2
        elif frac < 0.50:
            stars = 1
        else:
            stars = 0

        return firing, nextB, slots, cloud, falling, angVel, score, ammoQueue

    # try to attach to the cloud
    before = len(cloud)
    cloud, impulse = attachToCloud(
        nextB, cloud, slots, angle, CENTER_X, CENTER_Y
    )
    attached = len(cloud) > before

    if attached:
        # even if impulse == 0.0, we know we hit
        angVel += impulse
        HIT_SOUND.play()

        # remove clusters
        startIdx = len(cloud) - 1
        worldFn  = lambda e: worldPos(e, angle, CENTER_X, CENTER_Y)
        cloud, toFall, score = removeClusterFromIndex(
            cloud, startIdx, worldFn, score
        )
        spawnFalling(falling, toFall, angle, CENTER_X, CENTER_Y)

        cloud, extraFall, score = removeFloatingClusters(
            cloud, worldFn, score
        )
        spawnFalling(falling, extraFall, angle, CENTER_X, CENTER_Y)

        # only consume ammo if nothing was removed
        if not toFall and not extraFall:
            ammoQueue.pop(0)

        # refill ammo & spawn penalty bubbles if needed
        if not ammoQueue:
            newCount     = random.randint(3, 7)
            activeColors = [e["color"] for e in cloud] or COLORS
            ammoQueue    = [random.choice(activeColors) for _ in range(newCount)]
            spawnPenaltybubbles(cloud, slots)

        # prepare next shot
        firing = False
        nextB = Bubble(CENTER_X, LAUNCHER_Y, ammoQueue[0])
    return firing, nextB, slots, cloud, falling, angVel, score, ammoQueue
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Falling Bubbles Function
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def updateFalling(falling, dt):
    for b in falling[:]:
        b.vy += 400 * dt
        b.x += b.vx * dt
        b.y += b.vy * dt
        if b.y - BUBBLE_RADIUS > SCREEN_H:
            falling.remove(b)
    return falling


# Gameplay Loop Function
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def spawnPenaltybubbles(cloud, slots, speed=LAUNCH_SPEED):
    #Pick 3–9 bubbles from the current cloud colors
    count = random.randint(3, 9)
    active = [e["color"] for e in cloud] or COLORS
    for _ in range(count):
        color = random.choice(active)
        theta = random.uniform(0, 2*math.pi)
        x0 = CENTER_X + math.cos(theta) * CLOUD_RADIUS
        y0 = CENTER_Y + math.sin(theta) * CLOUD_RADIUS
        dx, dy = CENTER_X - x0, CENTER_Y - y0
        mag = math.hypot(dx, dy) or 1
        b = Bubble(x0, y0, color)
        b.vx = dx/mag * speed
        b.vy = dy/mag * speed
        penaltybubbles.append(b)

# Position Penalty Bubbles
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def updatePenaltybubbles(slots, cloud, angle):
    # Move bubbles toward center, and attach them to the cloud
    for b in penaltybubbles[:]:
        b.update()
        # Check collision against every existing bubble in cloud
        for entry in cloud:
            sx, sy = worldPos(entry, angle, CENTER_X, CENTER_Y)
            if math.hypot(b.x - sx, b.y - sy) < BUBBLE_DIAM:
                # Attach without clearing clusters
                rel_x, rel_y = b.x - CENTER_X, b.y - CENTER_Y
                sin_a, cos_a = math.sin(-angle), math.cos(-angle)
                rx_new = rel_x*cos_a - rel_y*sin_a
                ry_new = rel_x*sin_a + rel_y*cos_a
                slot = findNearestFreeSlot(slots, rx_new, ry_new)
                if slot:
                    slot["occupied"] = True
                    cloud.append({"slot": slot, "color": b.color})
                    HIT_SOUND.play()
                break
        else:
            # Not collided yet
            continue
        # And if we did collide, remove from penaltybubbles
        penaltybubbles.remove(b)

# Main Gameplay Mechanic Functions
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def update_rotation(angle, angVel):
    angle += angVel
    angVel *= ANGULAR_DAMPING
    return angle, angVel
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Draw Stars Function
def show_stars(screen, star_count):
    # Draw 3 star slots in the center
    if not (star_empty_texture and star_full_texture):
        return

    # Load and scale star textures
    w,h = star_full_texture.get_size()
    spacing = w + 10
    total_w = spacing*2 + w
    start_x = (SCREEN_W - total_w)//2
    y = (SCREEN_H - h)//2

    # Darken background behind
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((0,0,0,180))
    screen.blit(overlay, (0,0))
    pygame.display.flip()
    pygame.time.delay(300)

    # reveal one star at a time
    for i in range(3):
        tx = start_x + i*spacing
        # choose full vs empty
        tex = star_full_texture if i < star_count else star_empty_texture
        screen.blit(tex, (tx, y))
        pygame.display.flip()
        pygame.time.delay(300)
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Draw Score Function
def drawScore(screen, score):
    txt = scoreFont.render(f"Score: {score}", True, (255,255,255))
    screen.blit(txt, (10, SCREEN_H - txt.get_height() - 10))
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Main Creation Function
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def draw(screen, cloud, falling, nextB, angle, ammoQueue, score):
    screen.fill((30, 30, 30))

    for b in falling:
        b.draw(screen)

    for e in cloud:
        x, y = worldPos(e, angle, CENTER_X, CENTER_Y)
        tex = bubble_textures.get(e["color"])
        if tex:
            screen.blit( 
                tex,  (int(x - BUBBLE_RADIUS), int(y - BUBBLE_RADIUS))
            )
        else:
            # Fallback to drawing a circle if texture is not available
            pygame.draw.circle( screen, e["color"], (int(x), int(y)), BUBBLE_RADIUS)

    drawCore(screen, angle)

    # Shatter particles
    for p in shatterParticles:
        p.draw(screen)

    # Launcher Spot
    pygame.draw.line(
        screen,
        (200, 200, 200),
        (nextB.x - 20, LAUNCHER_Y + 20),
        (nextB.x + 20, LAUNCHER_Y + 20),
        4
    )
    
    nextB.draw(screen)
    previewR = BUBBLE_RADIUS // 2
    spacing  = previewR * 2 + 4
    for i, col in enumerate(ammoQueue[1:]):
        px = nextB.x + (i+1) * spacing
        py = LAUNCHER_Y
        tex = preview_textures.get(col)
        if tex:
            screen.blit(
            tex,
            (int(px - previewR), int(py - previewR))
        )
        else:
            pygame.draw.circle(screen, col, (int(px), int(py)), previewR)

    for b in penaltybubbles:
        b.draw(screen)

    # live score HUD
    drawScore(screen, score)
    drawRemoteCursor(screen)

    pygame.display.flip()
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Game Over Sequences
def revealOutcome(screen, outcome, baseScore, stars, finalScore):
    # Fade to black
    fade = pygame.Surface((SCREEN_W, SCREEN_H))
    for alpha in range(0, 256, 8):
        fade.set_alpha(alpha)
        fade.fill((0, 0, 0))
        screen.blit(fade, (0, 0))
        pygame.display.flip()
        pygame.time.delay(30)

    # Draw the outcome text & stars
    pygame.font.init()
    titleF = pygame.font.SysFont(None, 80)
    smallF = pygame.font.SysFont(None, 48)

    title = "You Win" if outcome == "win" else "You Lose"
    txtT = titleF.render(title, True, (255, 255, 255))
    rT = txtT.get_rect(center=(SCREEN_W//2, SCREEN_H//2 - 150))
    screen.blit(txtT, rT)

    # Star Row
    w, h = star_full_texture.get_size()
    spacing = w + 20
    total_w = spacing * 2 + w
    start_x = (SCREEN_W - total_w)//2
    y_star = SCREEN_H//2 - 50
    for i in range(3):
        tex = star_full_texture if i < stars else star_empty_texture
        screen.blit(tex, (start_x + i*spacing, y_star))

    # Final score
    txtF = smallF.render(f"Final Score: {finalScore}", True, (255, 255, 255))
    rF = txtF.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 100))
    screen.blit(txtF, rF)

    # Show Scene
    pygame.display.flip()

    # Delay (Ten Seconds)
    start = pygame.time.get_ticks()
    while pygame.time.get_ticks() - start < 10000:
        for ev in pygame.event.get():
            if ev.type in (pygame.QUIT, pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                return
        pygame.time.delay(50)
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Network Input Processing
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def processRemoteInput(nextB, firing):
    global net_mouse_pos
    if not net_input.empty():
        cmd = net_input.get().strip()
        if cmd == 'A':
            nextB.x = max(BUBBLE_RADIUS, nextB.x - 5)

        elif cmd == 'D':
            nextB.x = min(SCREEN_W - BUBBLE_RADIUS, nextB.x + 5)

        elif cmd.startswith('MOUSEMOVE:'):
            # Update cursor
            try:
                _, coords     = cmd.split(':', 1)
                mx, my        = map(int, coords.split(',', 1))
                net_mouse_pos = (mx, my)
            except ValueError:
                pass
        
        elif cmd.startswith('MOUSECLICK:'):
            # Update Firing
            try:
                _, coords     = cmd.split(':', 1)
                mx, my        = map(int, coords.split(',', 1))
                net_mouse_pos = (mx, my)
           
            except ValueError:
                pass
            else:
                if not firing:
                    dx, dy       = mx - nextB.x, my - nextB.y
                    mag          = math.hypot(dx, dy) or 1
                    nextB.vx     = dx / mag * LAUNCH_SPEED
                    nextB.vy     = dy / mag * LAUNCH_SPEED
                    firing       = True
    return nextB, firing
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Draw Remote Cursor Function
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def drawRemoteCursor(screen):
    if net_mouse_pos:
        mx, my = net_mouse_pos
        dot = pygame.Surface((10,10), pygame.SRCALPHA)
        pygame.draw.circle(dot, (128,128,128,128), (5,5), 5)
        screen.blit(dot, (mx-5, my-5))
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Main Initialization
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def main():
    global gameOver, baseScore, stars, endTime, outcome
    screen, clock = init_pygame()

    # Initialize: Client Connection
    if ENABLE_NETWORK_INPUT:
        threading.Thread(target=server_thread, daemon=True).start()
        while not client_connected:
            print("Waiting for network client…")            # Ctrl+C: Exit Search
            time.sleep(5.0)
    
    # Initialize: Game State
    slots, cloud, falling, angle, angVel, score, nextB, firing, running, ammoQueue = initGame()

    # Initalize: Game Loop
    while running:
        dt = clock.tick(60) / 1000.0

        # Enable: Remote Cursor
        if ENABLE_NETWORK_INPUT:
            nextB, firing = processRemoteInput(nextB, firing)

        # Display: Special Effects
        updateShatterParticles(dt)
        if gameOver:
            # ensure endTime is set exactly once
            if endTime is None:
                endTime = pygame.time.get_ticks()

        # Draw the final still frame
            draw(screen, cloud, falling, nextB, angle, ammoQueue, score)
            drawRemoteCursor(screen)
            pygame.display.flip()

        # After two seconds: reveal the outcome and exit
            if pygame.time.get_ticks() - endTime > 2000:
                finalScore = baseScore * max(1, stars)
                revealOutcome(screen, outcome, baseScore, stars, finalScore)
                running = False
            continue

        # Inputs
        running, firing, nextB, ammoQueue = processInput(nextB, firing, cloud, ammoQueue)
        nextB = handleKeyboard(nextB, firing, dt)

        # Update: Previvew Colors
        if not firing:
            activeColors = [e["color"] for e in cloud]
            if activeColors and nextB.color not in activeColors:
                nextB.color = random.choice(activeColors)

        # Firing and Projectile Updates
        if firing:
            firing, nextB, slots, cloud, falling, angVel, score, ammoQueue = \
                updateProjectile(nextB, firing, slots, cloud, falling, angle, angVel, score, ammoQueue)

        # Physics Updates
        falling = updateFalling(falling, dt)
        angle, angVel = update_rotation(angle, angVel)

        # Boundary Check: Cloud
        for e in cloud:
            x, y = worldPos(e, angle, CENTER_X, CENTER_Y)
            if (x - BUBBLE_RADIUS <= 0 or x + BUBBLE_RADIUS >= SCREEN_W
             or y - BUBBLE_RADIUS <= 0 or y + BUBBLE_RADIUS >= SCREEN_H):
                # Trigger Game Over
                gameOver = True
                outcome   = 'lose'
                endTime   = pygame.time.get_ticks()
                baseScore = score
                THUD_SOUND.play()
            
                # Compute stars
                remaining   = len(cloud)
                frac        = remaining / initialBallCount
                if remaining == 0:         stars = 3
                elif frac < 0.25:          stars = 2
                elif frac < 0.50:          stars = 1
                else:                      stars = 0
                break

        if gameOver:
            continue

        # Send Penalty Bubbles
        updatePenaltybubbles(slots, cloud, angle)

        # Finish Drawing
        draw(screen, cloud, falling, nextB, angle, ammoQueue, score)
    pygame.quit()

if __name__ == "__main__":
    main()
