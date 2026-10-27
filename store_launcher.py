"""Store Simulator launcher with first-run MySQL initialization."""

import os
import subprocess
import sys

import pygame

from database_setup import DatabaseSetupError, ensure_store_database

#_____________________________SETTINGS_____________________________
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

#_____________________________SCREEN DRAW_____________________________
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    map_path = os.path.join(script_dir, "store_level1.txt")
    game_path = os.path.join(script_dir, "store_sim.py")
    editor_path = os.path.join(script_dir, "mapeditor.py")

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Store Simulator")
    clock = pygame.time.Clock()
    title_font = pygame.font.SysFont("Arial", 50, bold=True)
    body_font = pygame.font.SysFont("Arial", 20)
    button_font = pygame.font.SysFont("Arial", 24, bold=True)
    small_btn_font = pygame.font.SysFont("Arial", 18, bold=True)

    ready, status = prepare_database(map_path)
    editor_button = pygame.Rect(300, 290, 300, 44)
    sim_button = pygame.Rect(265, 350, 370, 62)
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                ready, status = prepare_database(map_path)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if editor_button.collidepoint(event.pos):
                    subprocess.Popen([sys.executable, editor_path], cwd=script_dir)
                elif ready and sim_button.collidepoint(event.pos):
                    subprocess.Popen([sys.executable, game_path], cwd=script_dir)
                    running = False

        mouse_position = pygame.mouse.get_pos()
        screen.fill(BACKGROUND)
        panel = pygame.Rect(110, 60, 680, 410)
        pygame.draw.rect(screen, PANEL, panel, border_radius=16)
        pygame.draw.rect(screen, ACCENT, panel, 3, border_radius=16)

        title = title_font.render("Store Simulator", True, TEXT)
        screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 125)))

        status_color = (47, 116, 79) if ready else (178, 65, 65)
        draw_wrapped_text(
            screen,
            status,
            body_font,
            status_color,
            pygame.Rect(165, 175, 570, 95),
        )

        # Map Editor Button (smaller button above Start Store Simulator)
        editor_hover = editor_button.collidepoint(mouse_position)
        editor_bg = (226, 238, 248) if editor_hover else (240, 246, 250)
        editor_border = (40, 105, 150) if editor_hover else ACCENT
        pygame.draw.rect(screen, editor_bg, editor_button, border_radius=8)
        pygame.draw.rect(screen, editor_border, editor_button, 2, border_radius=8)
        editor_text = small_btn_font.render("Launch Map Editor", True, ACCENT)
        screen.blit(editor_text, editor_text.get_rect(center=editor_button.center))

        # Main Simulator Button
        if ready:
            button_color = (72, 145, 192) if sim_button.collidepoint(mouse_position) else ACCENT
            label = "Start Store Simulator"
        else:
            button_color = DISABLED
            label = "Database setup required"

        pygame.draw.rect(screen, button_color, sim_button, border_radius=10)
        button_text = button_font.render(label, True, (255, 255, 255))
        screen.blit(button_text, button_text.get_rect(center=sim_button.center))

        if not ready:
            retry = body_font.render("Fix db_config.py or map, then press R to retry.", True, TEXT)
            screen.blit(retry, retry.get_rect(center=(SCREEN_WIDTH // 2, 490)))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
