"""Store Simulator launcher with first-run MySQL initialization."""

import os
import subprocess
import sys

import pygame

from database_setup import DatabaseSetupError, ensure_store_database


SCREEN_WIDTH = 900
SCREEN_HEIGHT = 540
BACKGROUND = (235, 243, 248)
PANEL = (255, 255, 255)
TEXT = (42, 57, 70)
ACCENT = (55, 126, 174)
DISABLED = (163, 177, 188)


def prepare_database(map_path):
    try:
        return True, ensure_store_database(map_path)
    except DatabaseSetupError as error:
        return False, str(error)


def draw_wrapped_text(surface, text, font, color, rect, line_spacing=7):
    words = text.split()
    lines = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if font.size(candidate)[0] <= rect.width:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)

    total_height = len(lines) * font.get_linesize() + max(0, len(lines) - 1) * line_spacing
    y = rect.y + (rect.height - total_height) // 2
    for line in lines:
        rendered = font.render(line, True, color)
        surface.blit(rendered, rendered.get_rect(centerx=rect.centerx, y=y))
        y += font.get_linesize() + line_spacing


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    map_path = os.path.join(script_dir, "store_level1.txt")
    game_path = os.path.join(script_dir, "store_sim.py")

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Store Simulator")
    clock = pygame.time.Clock()
    title_font = pygame.font.SysFont("Arial", 52, bold=True)
    body_font = pygame.font.SysFont("Arial", 22)
    button_font = pygame.font.SysFont("Arial", 26, bold=True)

    ready, status = prepare_database(map_path)
    button = pygame.Rect(275, 380, 350, 70)
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_r and not ready:
                ready, status = prepare_database(map_path)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if ready and button.collidepoint(event.pos):
                    subprocess.Popen([sys.executable, game_path], cwd=script_dir)
                    running = False

        mouse_position = pygame.mouse.get_pos()
        screen.fill(BACKGROUND)
        panel = pygame.Rect(110, 75, 680, 390)
        pygame.draw.rect(screen, PANEL, panel, border_radius=16)
        pygame.draw.rect(screen, ACCENT, panel, 3, border_radius=16)

        title = title_font.render("Store Simulator", True, TEXT)
        screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 145)))

        status_color = (47, 116, 79) if ready else (178, 65, 65)
        draw_wrapped_text(
            screen,
            status,
            body_font,
            status_color,
            pygame.Rect(165, 205, 570, 100),
        )

        if ready:
            button_color = ACCENT if button.collidepoint(mouse_position) else (72, 145, 192)
            label = "Start Store Simulator"
        else:
            button_color = DISABLED
            label = "Database setup required"

        pygame.draw.rect(screen, button_color, button, border_radius=10)
        button_text = button_font.render(label, True, (255, 255, 255))
        screen.blit(button_text, button_text.get_rect(center=button.center))

        if not ready:
            retry = body_font.render("Fix db_config.py, then press R to retry.", True, TEXT)
            screen.blit(retry, retry.get_rect(center=(SCREEN_WIDTH // 2, 485)))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
