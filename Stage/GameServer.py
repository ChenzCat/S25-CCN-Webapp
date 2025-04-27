import pygame
import random
import math

# --- Constants ---
SCREEN_W, SCREEN_H = 600, 750
BUBBLE_RADIUS = 18
BUBBLE_DIAM = BUBBLE_RADIUS * 2
VERTICAL_STEP = int(BUBBLE_RADIUS * math.sqrt(3))
R_STEP = BUBBLE_DIAM

# --- Texture Constants ---
BUBBLE_TEXTURE_PATHS = {
    (255,   0,   0): 'assets/textures/bubbleRed.png',
    (  0, 255,   0): 'assets/textures/bubbleGreen.png',
    (  0,   0, 255): 'assets/textures/bubbleBlue.png',
    (255, 255,   0): 'assets/textures/bubbleYellow.png',
    (255,   0, 255): 'assets/textures/bubblePurple.png',
    (255, 165,   0): 'assets/textures/bubbleOrange.png',
}

STAR_EMPTY_PATH = 'assets/textures/star_empty.png'
STAR_FULL_PATH  = 'assets/textures/star_full.png'
star_empty_texture = None
star_full_texture  = None

COLORS = [
    (255,   0,   0),   # red
    (  0, 255,   0),   # green
    (  0,   0, 255),   # blue
    (255, 255,   0),   # yellow
    (255,   0, 255),   # purple
    (255, 165,   0),   # orange
]

bubble_textures  = {}   # full-size
preview_textures = {}   # half-size for ammo queue

#--- Game Constants ---
LAUNCH_SPEED = 12
CLOUD_RADIUS = 400
CORE_RADIUS = 20
penaltyBalls = []

ANGULAR_DAMPING = 0.98
LAUNCHER_Y = SCREEN_H - 50

BLUE_COLOR = (40, 175, 230)

# Precompute cloud center
CENTER_X = SCREEN_W // 2
CENTER_Y = SCREEN_H // 3

# Sound Engine
pygame.mixer.init()
#SHATTER_SOUND = pygame.mixer.Sound('assets/sounds/shatter.wav')

# Game Ending States
gameOver = False
coreHitTime = None
baseScore = 0
stars = 0

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
    global star_empty_texture, star_full_texture


# load & scale each color’s PNG
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

initialBallCount = 0

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

    if handleCoreHit(nextB):
        global gameOver, coreHitTime, baseScore, stars
        spawnShatter()                      # trigger shards
        gameOver     = True
        coreHitTime = pygame.time.get_ticks()
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

def draw(screen, cloud, falling, nextB, angle, ammoQueue):
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

    # Core

    #pygame.draw.circle(
        #screen,
        #BLUE_COLOR,
        #(CENTER_X, CENTER_Y),
        #BUBBLE_RADIUS * 2
    #)

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
        txt2 = small.render(f"× {i+1} → {final}", True, (255,255,255))
        r2   = txt2.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 100))
        screen.blit(txt2, r2)

        pygame.display.flip()
        pygame.time.delay(800)

        
    # hold for a moment before quitting
    pygame.time.delay(1200)
# ----------------------------------------------------------------------------------------------------------



# --- Main ---
def main():
    global gameOver, coreHitTime, baseScore, stars
    screen, clock = init_pygame()

    # 1) Initialize everything once — note: 'slots' not 'lots'
    slots, cloud, falling, angle, angVel, score, nextB, firing, running, ammoQueue = initGame()

    # 2) Main loop
    while running:
        dt = clock.tick(60) / 1000.0
        updateShatterParticles(dt)
                
        
        # — if we've hit the core, freeze the play state and show end screen after delay —
        if gameOver:
            # draw just the core + shards
            screen.fill((30,30,30))
            drawCore(screen, angle)
            for p in shatterParticles:
                p.draw(screen)
            pygame.display.flip()

            # after 2s, fire off your end-sequence
            if pygame.time.get_ticks() - coreHitTime > 2000:
                show_end_sequence(screen, baseScore, stars)
                running = False
            continue



        # — input —
        running, firing, nextB, ammoQueue = processInput(nextB, firing, cloud, ammoQueue)

        # — move the preview bubble left/right —
        nextB = handleKeyboard(nextB, firing, dt)

        # — ensure preview color stays valid —
        if not firing:
            activeColors = [e["color"] for e in cloud]
            if activeColors and nextB.color not in activeColors:
                nextB.color = random.choice(activeColors)

        # — firing logic —
        if firing:
            firing, nextB, slots, cloud, falling, angVel, score, ammoQueue = updateProjectile(
                nextB, firing, slots,
                cloud, falling, angle,
                angVel, score, ammoQueue
            )

        # — update falling bubbles & rotation —
        falling = updateFalling(falling, dt)
        angle, angVel = update_rotation(angle, angVel)
        for e in cloud:
            x, y = worldPos(e, angle, CENTER_X, CENTER_Y)
            if (x - BUBBLE_RADIUS <= 0
                or x + BUBBLE_RADIUS >= SCREEN_W
                or y - BUBBLE_RADIUS <= 0
                or y + BUBBLE_RADIUS >= SCREEN_H):
                gameOver     = True
                coreHitTime  = pygame.time.get_ticks()
                baseScore    = score
                # compute stars same as core-hit
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
                break

    # if we just hit the boundary, skip straight to your game-over handler
        if gameOver:
            continue
        


        updatePenaltyBalls(slots, cloud, angle)
        # — draw everything each frame —
        draw(screen, cloud, falling, nextB, angle, ammoQueue)

    remaining = len(cloud)
    frac = remaining / initialBallCount

    # Calculate stars based on remaining bubbles
    if remaining == 0:
        stars = 3
    elif frac < 0.25:
        stars = 2
    elif frac < 0.50:
        stars = 1
    else:
        stars = 0

    final_score = score * stars

    # pop up the stars
    show_stars(screen, stars)
    pygame.time.delay(1000)  # give them a moment

    print(f"Game Over! You earned {stars} star{'s' if stars != 1 else ''}.")
    print(f"Score: {score} → {final_score} ({stars}×)")

    pygame.quit()


if __name__ == "__main__":
    main()
