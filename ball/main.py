import pygame
import math
import random
import numpy as np
from collections import deque
pygame.init()

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
PURPLE = (128, 0, 128)
ORANGE = (255, 165, 0)
PINK = (255, 192, 203)
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
LIME = (50, 205, 50)
TEAL = (0, 128, 128)
VIOLET = (238, 130, 238)
GOLD = (255, 215, 0)
CORAL = (255, 127, 80)
TURQUOISE = (64, 224, 208)

ball_colors = [RED, GREEN, BLUE, YELLOW, PURPLE, ORANGE, PINK, CYAN, MAGENTA, LIME, TEAL, VIOLET, GOLD, CORAL, TURQUOISE]

screen_width = 600
screen_height = 740
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Bouncing Ball")
circle_radius = 250
circle_center = np.array((screen_width // 2, screen_height // 2), float)
ball_color = RED
trail_length = 10
trail_fade = 20
GRAVITY = np.array([0,0.1])
def distance(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

class Ball:
    def __init__(self, pos, vel, radius, color=RED):
        self.pos = pos
        self.vel = vel
        self.radius = radius
        self.color = color
        self.trail = deque()
    def next_frame(self):
            self.pos += self.vel
            self.vel += GRAVITY
            self.trail.appendleft(self.pos.copy())
            if len(self.trail) > trail_length:
                self.trail.pop()
    def draw_trail(self):
        for i, pos in enumerate(self.trail):
            trail_color_faded = tuple((max(comp - i * trail_fade, 0) for comp in self.color))
            pygame.draw.circle(screen, trail_color_faded, pos.astype(int), self.radius - i, width=0)
class Circle:
    def __init__(self, center, radius=250):
        self.radius = radius
        self.center = center
    def check_collision(self, ball):
        # with edge
        dist = distance(ball.pos, self.center)
        if dist > (self.radius - ball.radius):

            # self.radius -= 3
            normal = (ball.pos - self.center) / dist
            dot_product = np.dot(ball.vel, normal)
            ball.vel -= 2 * dot_product * normal

            dist_to_correct = dist + ball.radius - self.radius
            ball.pos -= dist_to_correct * normal


def collision_handler(ball):
    for other_ball in balls:
        if ball is not other_ball:
            dist = distance(ball.pos, other_ball.pos)
            if dist < (ball.radius + other_ball.radius):
                dv = ball.vel - other_ball.vel
                normal = (ball.pos - other_ball.pos) / dist
                dot_product = np.dot(dv, normal)
                ball.vel -= dot_product * normal
                other_ball.vel += dot_product * normal

                proportion = ball.radius / (ball.radius + other_ball.radius)
                ball.pos += normal * proportion
                other_ball.pos -= normal * (1 - proportion)

running = True
clock = pygame.time.Clock()

circle = Circle(circle_center, circle_radius)
balls = []
color = 1
while running:
    screen.fill(BLACK)
    pygame.draw.circle(screen, WHITE, circle.center, circle.radius, 1)
    for ball in balls:
        ball.next_frame()
        circle.check_collision(ball)
        collision_handler(ball)
        ball.draw_trail()
    for ball in balls:
        pygame.draw.circle(screen, ball.color, ball.pos.astype(int), ball.radius, width=0)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            balls.append(Ball(pygame.mouse.get_pos(), np.array([0,0], float), random.randint(10, 25), ball_colors[color % len(ball_colors)]))
            color += 1
        keys = pygame.key.get_pressed()
        if keys[pygame.K_c]:
                balls.clear()
    pygame.display.flip()
    clock.tick(60)

pygame.quit()