import argparse
import socket
import pygame

# Constants
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
SCREEN_W, SCREEN_H = 600, 750 # Similar to the server window size
CORE_REF_RADIUS = 20
CORE_REF_POS    = (SCREEN_W//2, SCREEN_H//3)

# Terminal Feedback
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Remote input client for Bubbles game")
    parser.add_argument("-H", "--host", default="10.22.18.153", help="Server IP address")
    parser.add_argument("-P", "--port", type=int, default=5000, help="Server port")
    return parser.parse_args()

# Pygame Clientside Server
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def client_program(host, port):
    pygame.init()
    pygame.key.set_repeat(100, 100)     
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Bubbles Input Client")

    # — connect to server —
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
        print(f"✔ Connected to {host}:{port}")
    except Exception as e:
        print(f"✖ Could not connect to {host}:{port}: {e}")
        pygame.quit()
        return

    running = True
    while running:
        
        for ev in pygame.event.get():
            # Quit (window close or Q key)
            if ev.type == pygame.QUIT:
                running = False

            # Keys A, D, Q
            elif ev.type == pygame.KEYDOWN:
                try:
                    if ev.key == pygame.K_a:
                        sock.sendall(b"A")
                    elif ev.key == pygame.K_d:
                        sock.sendall(b"D")
                    elif ev.key == pygame.K_q:
                        running = False
                except Exception:
                    running = False

            # Mouse click: send the click position
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                mx, my = ev.pos
                sock.sendall(f"MOUSECLICK:{mx},{my}".encode())

            elif ev.type == pygame.MOUSEMOTION:
                mx, my = ev.pos
                try:
                    sock.sendall(f"MOUSEMOVE:{mx},{my}".encode())
                except Exception:
                    running = False

        # Background
        screen.fill((50, 50, 50))
        
        pygame.draw.circle( screen,(128, 128, 128), CORE_REF_POS, CORE_REF_RADIUS, 2)   
        pygame.display.flip()

        pygame.time.wait(10)

    sock.close()
    pygame.quit()

if __name__ == "__main__":
    args = parse_args()
    client_program(args.host, args.port)
