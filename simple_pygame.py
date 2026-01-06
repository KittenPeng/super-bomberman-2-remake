import pygame
import sys

pygame.init()

WIDTH, HEIGHT = 640, 480
window = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Pygame Test Window")

BLUE = (50, 100, 200)
clock = pygame.time.Clock()
running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    window.fill(BLUE)
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()
