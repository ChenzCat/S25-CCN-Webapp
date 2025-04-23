import pygame
import random
import math

# --- Constants ---
SCREEN_W, SCREEN_H = 600, 750
BUBBLE_RADIUS = 18
BUBBLE_DIAM = BUBBLE_RADIUS + 19
R_STEP = BUBBLE_RADIUS + 16

LAUNCH_SPEED = 12
CLOUD_RADIUS = 400
CORE_RADIUS = 50

ANGULAR_VELOCITY = 0.97

LAUNCHER_Y = SCREEN_H - 50

COLORS = [
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255),
]
GOLDEN_COLOR = (212, 175, 55)

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
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), BUBBLE_RADIUS)

# --- Utility Functions ---
def world_pos(entry, angle, center_x, center_y):
    sin_a, cos_a = math.sin(angle), math.cos(angle)
    rx, ry = entry["slot"]["rx"], entry["slot"]["ry"]
    x = center_x + rx * cos_a - ry * sin_a
    y = center_y + rx * sin_a + ry * cos_a
    return x, y

def create_slots():
    slots = []
    for r in range(R_STEP, CLOUD_RADIUS + 1, R_STEP):
        count = max(6, int(2 * math.pi * r / BUBBLE_DIAM))
        for i in range(count):
            theta = 2 * math.pi * i / count
            rx, ry = math.cos(theta) * r, math.sin(theta) * r
            slots.append({"rx": rx, "ry": ry, "occupied": False})
    return slots

def seed_initial_cloud(slots):
    cloud = []
    for slot in slots:
        if abs(math.hypot(slot["rx"], slot["ry"]) - R_STEP) < 5:
            slot["occupied"] = True
            cloud.append({"slot": slot, "color": random.choice(COLORS)})
    return cloud

def find_nearest_free_slot(slots, rx_new, ry_new):
    return min(
        (slot for slot in slots if not slot["occupied"]),
        key=lambda s: (s["rx"] - rx_new) ** 2 + (s["ry"] - ry_new) ** 2,
        default=None
    )

def remove_clusters(cloud, world_pos_fn, score):
    N = len(cloud)
    if N < 3:
        return cloud, score

    W = [world_pos_fn(e) for e in cloud]
    C = [e["color"] for e in cloud]
    neighbors = [set() for _ in range(N)]

    for i in range(N):
        xi, yi = W[i]
        for j in range(i + 1, N):
            if math.hypot(xi - W[j][0], yi - W[j][1]) < BUBBLE_DIAM * 1.14:
                neighbors[i].add(j)
                neighbors[j].add(i)

    visited, to_remove = set(), set()
    for i in range(N):
        if i in visited:
            continue
        stack, comp = [i], []
        visited.add(i)
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in neighbors[u]:
                if v not in visited and C[v] == C[u]:
                    visited.add(v)
                    stack.append(v)
        if len(comp) >= 3:
            to_remove.update(comp)

    if not to_remove:
        return cloud, score

    for idx in to_remove:
        cloud[idx]["slot"]["occupied"] = False
    cloud = [e for idx, e in enumerate(cloud) if idx not in to_remove]
    score += len(to_remove)

    # Drop isolated
    W = [world_pos_fn(e) for e in cloud]
    survivors = []
    for i, (xi, yi) in enumerate(W):
        close = any(
            i != j and math.hypot(xi - xj, yi - yj) < BUBBLE_DIAM * 1.05
            for j, (xj, yj) in enumerate(W)
        )
        if close:
            survivors.append(cloud[i])
        else:
            cloud[i]["slot"]["occupied"] = False
            score += 1
    return survivors, score

# --- Main Game ---
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Bubbles")
    clock = pygame.time.Clock()

    center_x, center_y = SCREEN_W // 2, SCREEN_H // 3
    slots = create_slots()
    cloud = seed_initial_cloud(slots)

    angle, angular_velocity, score = 0.0, 5.0, 0
    next_bubble = Bubble(center_x, LAUNCHER_Y, random.choice(COLORS))
    firing = False

    running = True
    while running:
        clock.tick(60)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif (ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE) or (ev.type == pygame.MOUSEBUTTONDOWN):
                if not firing:
                    mx, my = pygame.mouse.get_pos()
                    dx, dy = mx - next_bubble.x, my - next_bubble.y
                    mag = math.hypot(dx, dy)
                    if mag:
                        next_bubble.vx = dx / mag * LAUNCH_SPEED
                        next_bubble.vy = dy / mag * LAUNCH_SPEED
                        firing = True

        keys = pygame.key.get_pressed()
        if keys[pygame.K_a]:
            next_bubble.x = max(BUBBLE_RADIUS, next_bubble.x - 5)
        if keys[pygame.K_d]:
            next_bubble.x = min(SCREEN_W - BUBBLE_RADIUS, next_bubble.x + 5)
        if not firing:
            next_bubble.y = LAUNCHER_Y

        # Update bubble movement
        if firing:
            next_bubble.update()
            if next_bubble.x < BUBBLE_RADIUS or next_bubble.x > SCREEN_W - BUBBLE_RADIUS:
                next_bubble.vx *= -1
                next_bubble.x = max(BUBBLE_RADIUS, min(next_bubble.x, SCREEN_W - BUBBLE_RADIUS))
                next_bubble.bounce_count += 1
            if next_bubble.y < BUBBLE_RADIUS:
                next_bubble.vy *= -1
                next_bubble.y = BUBBLE_RADIUS

            if next_bubble.bounce_count > 3 or next_bubble.y > SCREEN_H:
                firing = False
                next_bubble = Bubble(center_x, LAUNCHER_Y, next_bubble.color)
                continue

            dist_core = math.hypot(next_bubble.x - center_x, next_bubble.y - center_y)
            if dist_core < CORE_RADIUS:
                print(f"Game Over! Hit the core. Final Score: {score}")
                pygame.time.wait(2000)
                break

            rel_x = next_bubble.x - center_x
            rel_y = next_bubble.y - center_y
            sin_a, cos_a = math.sin(-angle), math.cos(-angle)
            rx_new = rel_x * cos_a - rel_y * sin_a
            ry_new = rel_x * sin_a + rel_y * cos_a

            for s in cloud:
                sx, sy = world_pos(s, angle, center_x, center_y)
                if math.hypot(next_bubble.x - sx, next_bubble.y - sy) < BUBBLE_DIAM:
                    best = find_nearest_free_slot(slots, rx_new, ry_new)
                    if best:
                        best["occupied"] = True
                        cloud.append({"slot": best, "color": next_bubble.color})
                        impulse = (rel_x * next_bubble.vy - rel_y * next_bubble.vx) * 0.00008
                        angular_velocity += impulse
                        cloud, score = remove_clusters(cloud, lambda e: world_pos(e, angle, center_x, center_y), score)
                    firing = False
                    next_bubble = Bubble(center_x, LAUNCHER_Y, random.choice(COLORS))
                    break

        angle += angular_velocity
        angular_velocity *= ANGULAR_VELOCITY

        # Check bounds overflow
        for e in cloud:
            wx, wy = world_pos(e, angle, center_x, center_y)
            if not (0 < wx < SCREEN_W and 0 < wy < SCREEN_H):
                print(f"Game Over! Score: {score}")
                running = False
                break

        # --- Drawing ---
        screen.fill((30, 30, 30))
        for e in cloud:
            x, y = world_pos(e, angle, center_x, center_y)
            pygame.draw.circle(screen, e["color"], (int(x), int(y)), BUBBLE_RADIUS)
        pygame.draw.circle(screen, GOLDEN_COLOR, (center_x, center_y), BUBBLE_RADIUS * 2)
        pygame.draw.line(screen, (200, 200, 200), (next_bubble.x - 20, LAUNCHER_Y + 20), (next_bubble.x + 20, LAUNCHER_Y + 20), 4)
        next_bubble.draw(screen)
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()

