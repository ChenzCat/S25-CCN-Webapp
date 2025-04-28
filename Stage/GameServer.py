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
penaltyBalls = []

ANGULAR_DAMPING = 0.98
LAUNCHER_Y = SCREEN_H - 50

# Precompute cloud center
CENTER_X = SCREEN_W // 2
CENTER_Y = SCREEN_H // 3



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

    # Draw Bubble with texture if available
    def draw(self, surf):
        tex = bubble_textures.get(self.color)
        if tex:
            surf.blit(tex, (int(self.x - BUBBLE_RADIUS), int(self.y - BUBBLE_RADIUS)))
        else:
            pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), BUBBLE_RADIUS)

# --- Shatter Class ---
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

def spawnShatter():
    #SHATTER_SOUND.play()
    for i in range(6):
        ang = math.radians(60 * i + 30)
        x = CENTER_X + math.cos(ang) * CORE_RADIUS
        y = CENTER_Y + math.sin(ang) * CORE_RADIUS
        dir_ang = random.uniform(ang - 0.5, ang + 0.5)
        speed = random.uniform(200, 300)
        vx, vy = math.cos(dir_ang) * speed, math.sin(dir_ang) * speed
        shatterParticles.append(ShatterParticle((x, y), (vx, vy), BLUE_COLOR, 1.0))

def updateShatterParticles(dt):
    for p in shatterParticles[:]:
        p.update(dt)
        if p.life <= 0:
            shatterParticles.remove(p)

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
    rot = pygame.transform.rotate(tmp, math.degrees(-angle) + 30) # +30 to align with the surrounding balls

    # Center the rotated hexagon
    rect = rot.get_rect(center=(CENTER_X, CENTER_Y))

    # Draw the rotated hexagon
    surf.blit(rot, rect)

def handleCoreHit(b):
    if math.hypot(b.x - CENTER_X, b.y - CENTER_Y) < CORE_RADIUS:
        spawnShatter()
        return True
    return False


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

        if q == 0 and r == 0:
            continue

        if max(abs(q), abs(r), abs(s)) <= initialRings:
            slot["occupied"] = True
            cloud.append({
                "slot": slot,
                "color": random.choice(COLORS)
            })
    return cloud

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

def shouldResetLauncher(b):
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
    if to_fall:
        FALL_SOUND.play()
    for e in to_fall:
        fx, fy = worldPos(e, angle, cx, cy)
        nb = Bubble(fx, fy, e["color"])
        nb.falling = True
        fall_list.append(nb)

# --- Module Functions ---
def init_pygame():
    pygame.init()
    pygame.font.init()
    pygame.mixer.init()
    
    #
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
    
    
# load textures
    for color, path in BUBBLE_TEXTURE_PATHS.items():
        try:
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.scale(img, (BUBBLE_DIAM, BUBBLE_DIAM))
            bubble_textures[color] = img
            
            # scale to half size for preview
            # preview = half-diameter
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
    nextB = Bubble(CENTER_X, LAUNCHER_Y, random.choice(COLORS))
    firing = False
    running = True
    initialCount = random.randint(3,7)
    activeColors = [e["color"] for e in cloud] or COLORS
    ammoQueue    = [random.choice(activeColors) for _ in range(initialCount)]

    # nextB should be the first color in the queue
    nextB = Bubble(CENTER_X, LAUNCHER_Y, ammoQueue[0])



    return slots, cloud, falling, angle, angVel, score, nextB, firing, running, ammoQueue  

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

def handleKeyboard(nextB, firing, dt):
    keys = pygame.key.get_pressed()
    if keys[pygame.K_a]:
        nextB.x = max(BUBBLE_RADIUS, nextB.x - 5)
    if keys[pygame.K_d]:
        nextB.x = min(SCREEN_W - BUBBLE_RADIUS, nextB.x + 5)
    if not firing:
        nextB.y = LAUNCHER_Y
    return nextB


def updateProjectile(
    nextB, firing, slots, cloud, falling,
    angle, angVel, score, ammoQueue                
):
    
    nextB.update()
    handleWallAndCeilingBounce(nextB)

    if shouldResetLauncher(nextB):
        firing = False

        xtB = Bubble(CENTER_X, LAUNCHER_Y, nextB.color)
        nextB.x, nextB.y      = CENTER_X, LAUNCHER_Y
        nextB.vx, nextB.vy    = 0, 0
        nextB.bounce_count    = 0
        return firing, nextB, slots, cloud, falling, angVel, score, ammoQueue

    # When a Bubble hits the core: End The Game, Shatter Effect, and Score Calculation
    if handleCoreHit(nextB):
        global gameOver, endTime, outcome, baseScore, stars
        spawnShatter()                      # Trigger: Shard Effects
        SHATTER_SOUND.play()                # Play:    Shatter Sound.mp3
        outcome   = 'win'                   # Set:     Outcome to Win  
        gameOver     = True                 # Set:     Game Over to True    
        endTime   = pygame.time.get_ticks() 
        baseScore    = score

        # compute stars (same logic you had at end)
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


    cloud, impulse = attach_to_cloud(
        nextB, cloud, slots, angle, CENTER_X, CENTER_Y
    )
    if impulse:
        angVel += impulse
                # the new bubble is last in cloud
        HIT_SOUND.play()
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

        # only consume one ammo if NOTHING was removed
        if not toFall and not extraFall:
            ammoQueue.pop(0)

        # if we ran out of ammo, refill
        if not ammoQueue:
            newCount     = random.randint(3,7)
            activeColors = [e["color"] for e in cloud] or COLORS
            ammoQueue    = [random.choice(activeColors) for _ in range(newCount)]
            spawnPenaltyBalls(cloud, slots)

        firing = False
        nextB = Bubble(CENTER_X, LAUNCHER_Y, ammoQueue[0])
    return firing, nextB, slots, cloud, falling, angVel, score, ammoQueue

def updateFalling(falling, dt):
    for b in falling[:]:
        b.vy += 400 * dt
        b.x += b.vx * dt
        b.y += b.vy * dt
        if b.y - BUBBLE_RADIUS > SCREEN_H:
            falling.remove(b)
    return falling

def spawnPenaltyBalls(cloud, slots, speed=LAUNCH_SPEED):
    """
    Pick 3–9 balls from the current cloud colors,
    launch them from the circle perimeter inward.
    """
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
        penaltyBalls.append(b)

def updatePenaltyBalls(slots, cloud, angle):
    """
    Move penaltyBalls toward center, and attach them to the cloud
    on first collision (no cluster removal).
    """
    for b in penaltyBalls[:]:
        b.update()
        # check collision against every existing bubble in cloud
        for entry in cloud:
            sx, sy = worldPos(entry, angle, CENTER_X, CENTER_Y)
            if math.hypot(b.x - sx, b.y - sy) < BUBBLE_DIAM:
                # attach without clearing clusters
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
            # not collided yet
            continue
        # if we did collide, remove from penaltyBalls
        penaltyBalls.remove(b)

def update_rotation(angle, angVel):
    angle += angVel
    angVel *= ANGULAR_DAMPING
    return angle, angVel

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


def drawScore(screen, score):
    txt = scoreFont.render(f"Score: {score}", True, (255,255,255))
    screen.blit(txt, (10, SCREEN_H - txt.get_height() - 10))

def debugPrintFinalScore(baseScore, stars, finalScore):
    print(f"Game Over! You earned {stars} star{'s' if stars != 1 else ''}.")
    print(f"Base Score: {baseScore}  Final Score: {finalScore} ({max(1, stars)}×)")


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

    # 4) draw any shatter fragments
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

    for b in penaltyBalls:
        b.draw(screen)

    # live score HUD
    drawScore(screen, score)
    if net_mouse_pos:
        mx, my = net_mouse_pos
        dot = pygame.Surface((10,10), pygame.SRCALPHA)
        pygame.draw.circle(dot, (128,128,128,128), (5,5), 5)
        screen.blit(dot, (mx-5, my-5))
        
    pygame.display.flip()



# --- Game Over Logic ---
def show_end_sequence(screen, baseScore, stars):
    # Darken background behind
    pygame.font.init()
    font = pygame.font.SysFont(None, 64)
    small = pygame.font.SysFont(None, 48)

    # dark overlay
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((0,0,0,200))
    screen.blit(overlay, (0,0))

    # initial score text
    txt = font.render(f"Score: {baseScore}", True, (255,255,255))
    rect = txt.get_rect(center=(SCREEN_W//2, SCREEN_H//2 - 100))
    screen.blit(txt, rect)
    pygame.display.flip()
    pygame.time.delay(800)

    final = 0
    # reveal stars one at a time
    w,h      = star_full_texture.get_size()
    spacing  = w + 20
    total_w  = spacing*2 + w
    start_x  = (SCREEN_W - total_w)//2
    y        = SCREEN_H//2

    for i in range(stars):
        # draw stars row
        for j in range(3):
            tex = star_full_texture if j <= i else star_empty_texture
            x = start_x + j*spacing
            screen.blit(tex, (x, y))
        # update and draw multiplied score
        final = baseScore * (i+1)
        txt2 = small.render(f"× {i+1} apple {final}", True, (255,255,255))
        r2   = txt2.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 100))
        screen.blit(txt2, r2)

        pygame.display.flip()
        pygame.time.delay(800)

        
    # hold for a moment before quitting
    pygame.time.delay(1200)

def revealOutcome(screen, outcome, baseScore, stars, finalScore):
    # 1) Fade to black
    fade = pygame.Surface((SCREEN_W, SCREEN_H))
    for alpha in range(0, 256, 8):
        fade.set_alpha(alpha)
        fade.fill((0, 0, 0))
        screen.blit(fade, (0, 0))
        pygame.display.flip()
        pygame.time.delay(30)

    # 2) Draw the outcome text & stars
    pygame.font.init()
    titleF = pygame.font.SysFont(None, 80)
    smallF = pygame.font.SysFont(None, 48)

    title = "You Win" if outcome == "win" else "You Lose"
    txtT = titleF.render(title, True, (255, 255, 255))
    rT = txtT.get_rect(center=(SCREEN_W//2, SCREEN_H//2 - 150))
    screen.blit(txtT, rT)

    # stars row
    w, h = star_full_texture.get_size()
    spacing = w + 20
    total_w = spacing * 2 + w
    start_x = (SCREEN_W - total_w)//2
    y_star = SCREEN_H//2 - 50
    for i in range(3):
        tex = star_full_texture if i < stars else star_empty_texture
        screen.blit(tex, (start_x + i*spacing, y_star))

    # final score
    txtF = smallF.render(f"Final Score: {finalScore}", True, (255, 255, 255))
    rF = txtF.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 100))
    screen.blit(txtF, rF)

    # 3) **Flip** to show it
    pygame.display.flip()

    # 4) Hold for ten seconds (or until input)
    start = pygame.time.get_ticks()
    while pygame.time.get_ticks() - start < 10000:
        for ev in pygame.event.get():
            if ev.type in (pygame.QUIT, pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                return
        pygame.time.delay(50)
# ----------------------------------------------------------------------------------------------------------

def processRemoteInput(nextB, firing):
    global net_mouse_pos

    while not net_input.empty():
        cmd = net_input.get().strip()
        if cmd == 'A':
            nextB.x = max(BUBBLE_RADIUS, nextB.x - 5)

        elif cmd == 'D':
            nextB.x = min(SCREEN_W - BUBBLE_RADIUS, nextB.x + 5)

        elif cmd.startswith('MOUSEMOVE:'):
            # just update cursor
            try:
                _, coords = cmd.split(':',1)
                mx, my    = map(int, coords.split(',',1))
                net_mouse_pos = (mx, my)
            except:
                continue

        elif cmd.startswith('MOUSECLICK:'):
            # update cursor + fire a shot
            try:
                _, coords = cmd.split(':',1)
                mx, my    = map(int, coords.split(',',1))
                net_mouse_pos = (mx, my)
            except:
                continue

            if not firing:
                dx, dy = mx - nextB.x, my - nextB.y
                mag    = math.hypot(dx, dy) or 1
                nextB.vx = dx / mag * LAUNCH_SPEED
                nextB.vy = dy / mag * LAUNCH_SPEED
                firing   = True

    return nextB, firing

def drawRemoteCursor(screen):
    if net_mouse_pos:
        mx, my = net_mouse_pos
        dot = pygame.Surface((10,10), pygame.SRCALPHA)
        pygame.draw.circle(dot, (128,128,128,128), (5,5), 5)
        screen.blit(dot, (mx-5, my-5))


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
            # —  Display: Game Over Sequence  — 
        if gameOver:
            # 1) ensure endTime is set exactly once
            if endTime is None:
                endTime = pygame.time.get_ticks()

            # 2) draw the static game-over frame
            screen.fill((30, 30, 30))
            if outcome == 'win':
                drawCore(screen, angle)
                for p in shatterParticles:
                    p.draw(screen)
            else:
                for e in cloud:
                    x, y = worldPos(e, angle, CENTER_X, CENTER_Y)
                    tex = bubble_textures.get(e["color"])
                    if tex:
                        screen.blit(tex, (int(x - BUBBLE_RADIUS), int(y - BUBBLE_RADIUS)))
                    else:
                        pygame.draw.circle(screen, e["color"], (int(x), int(y)), BUBBLE_RADIUS)
                drawCore(screen, angle)

            drawRemoteCursor(screen)
            pygame.display.flip()

            # 3) after 2s, show the final outcome once
            if pygame.time.get_ticks() - endTime > 2000:
                finalScore = baseScore * max(1, stars)
                revealOutcome(screen, outcome, baseScore, stars, finalScore)
                running = False

            # 4) don’t run any other logic until we quit
            continue

    
                




















        # c) input
        running, firing, nextB, ammoQueue = processInput(nextB, firing, cloud, ammoQueue)
        nextB = handleKeyboard(nextB, firing, dt)

        # Update: Previvew Colors
        if not firing:
            activeColors = [e["color"] for e in cloud]
            if activeColors and nextB.color not in activeColors:
                nextB.color = random.choice(activeColors)

        # e) firing & attachment logic
        if firing:
            firing, nextB, slots, cloud, falling, angVel, score, ammoQueue = \
                updateProjectile(nextB, firing, slots, cloud, falling, angle, angVel, score, ammoQueue)

        # f) physics updates
        falling = updateFalling(falling, dt)
        angle, angVel = update_rotation(angle, angVel)

        # g) boundary‐hit: Trigger Game Over
        # Check if any bubble is outside the screen bounds
        
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

        # h) penalty balls
        updatePenaltyBalls(slots, cloud, angle)

        # i) final draw (cloud, core, bubbles, launcher, score HUD…)
        draw(screen, cloud, falling, nextB, angle, ammoQueue, score)
    pygame.quit()


if __name__ == "__main__":
    main()
