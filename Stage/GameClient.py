import pygame, socket

def client_program(host='192.168.1.84', port=5000):
    pygame.init()
    screen = pygame.display.set_mode((1,1), pygame.HIDDEN)
    sock = socket.socket()
    sock.connect((host, port))

    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

            # keys
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_a:
                    sock.send(b'A')
                elif ev.key == pygame.K_d:
                    sock.send(b'D')
                elif ev.key == pygame.K_q:
                    running = False

            # mouse click or move
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                mx, my = ev.pos
                msg = f"MOUSE:{mx},{my}".encode()
                sock.send(msg)

        pygame.time.wait(10)

    sock.close()
    pygame.quit()

if __name__=="__main__":
    client_program()
