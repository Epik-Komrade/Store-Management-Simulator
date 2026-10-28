"""Store Simulator launcher with first-run MySQL initialization and DB configuration modal."""

import os
import subprocess
import sys

import pygame

import db_config
from database_setup import DatabaseSetupError, ensure_store_database, reload_db_config
from ui_theme import (
    INPUT_BG,
    INPUT_BORDER_DEFAULT,
    LOSS_RED,
    OVERLAY_COLOR,
    PROFIT_GREEN,
    TEXT_MUTED,
    get_drop_shadow,
)

#_____________________________SETTINGS_____________________________
SCREEN_WIDTH = 900
SCREEN_HEIGHT = 540
BACKGROUND = (235, 243, 248)
PANEL = (255, 255, 255)
TEXT = (42, 57, 70)
ACCENT = (55, 126, 174)
DISABLED = (163, 177, 188)

CHARSET_OPTIONS = ("utf8mb4", "utf8", "latin1")
CHARSET_LABELS = {
    "utf8mb4": "utf8mb4 (MySQL 5.5+ / 8.x / 9.x)",
    "utf8": "utf8 (MySQL 5.0+ Compatible)",
    "latin1": "latin1 (Legacy Fallback)",
}


def prepare_database(map_path):
    try:
        reload_db_config()
        return True, ensure_store_database(map_path)
    except DatabaseSetupError as error:
        return False, str(error)


def save_db_config_file(config_path, host, port, user, password, charset):
    """Write updated MySQL connection settings to db_config.py."""
    import json
    content = (
        '"""Local MySQL connection settings."""\n\n'
        f"DB_HOST = {json.dumps(host)}\n"
        f"DB_PORT = {int(port)}\n"
        f"DB_USER = {json.dumps(user)}\n"
        f"DB_PASSWORD = {json.dumps(password)}\n"
        f"DB_CHARSET = {json.dumps(charset)}\n"
    )
    with open(config_path, "w", encoding="utf-8") as cfg_file:
        cfg_file.write(content)


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


def settings_modal_layout():
    modal = pygame.Rect((SCREEN_WIDTH - 520) // 2, 38, 520, 464)
    field_x = modal.x + 150
    field_w = 335
    start_y = modal.y + 76
    step_y = 52

    boxes = {
        "host": pygame.Rect(field_x, start_y, field_w, 36),
        "port": pygame.Rect(field_x, start_y + step_y, 140, 36),
        "user": pygame.Rect(field_x, start_y + step_y * 2, field_w, 36),
        "password": pygame.Rect(field_x, start_y + step_y * 3, field_w - 76, 36),
    }
    show_pw_btn = pygame.Rect(boxes["password"].right + 8, boxes["password"].y, 68, 36)

    charset_y = start_y + step_y * 4
    charset_prev = pygame.Rect(field_x, charset_y, 36, 36)
    charset_box = pygame.Rect(field_x + 42, charset_y, field_w - 84, 36)
    charset_next = pygame.Rect(field_x + field_w - 36, charset_y, 36, 36)

    save_btn = pygame.Rect(modal.x + 75, modal.bottom - 56, 185, 38)
    cancel_btn = pygame.Rect(modal.x + 280, modal.bottom - 56, 165, 38)
    return (
        modal,
        boxes,
        show_pw_btn,
        charset_prev,
        charset_box,
        charset_next,
        save_btn,
        cancel_btn,
    )


def draw_input_field(surface, rect, text, is_active, font, cursor_visible=True, mask=False):
    pygame.draw.rect(surface, INPUT_BG, rect, border_radius=6)
    border_col = ACCENT if is_active else INPUT_BORDER_DEFAULT
    pygame.draw.rect(surface, border_col, rect, 2 if is_active else 1, border_radius=6)

    shown_text = ("*" * len(text)) if mask else text
    txt_surf = font.render(shown_text, True, TEXT)
    txt_rect = txt_surf.get_rect(midleft=(rect.x + 12, rect.centery))
    surface.set_clip(rect.inflate(-8, -4))
    surface.blit(txt_surf, txt_rect)
    if is_active and cursor_visible:
        cx = min(rect.right - 8, txt_rect.right + 2)
        cy1 = rect.centery - font.get_height() // 2 + 2
        cy2 = rect.centery + font.get_height() // 2 - 2
        pygame.draw.line(surface, ACCENT, (cx, cy1), (cx, cy2), 2)
    surface.set_clip(None)


def draw_settings_modal(
    surface,
    fonts,
    fields,
    active_field,
    show_password,
    error_msg,
    cursor_visible,
    mouse_pos,
):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((*OVERLAY_COLOR, 135))
    surface.blit(overlay, (0, 0))

    (
        modal,
        boxes,
        show_pw_btn,
        charset_prev,
        charset_box,
        charset_next,
        save_btn,
        cancel_btn,
    ) = settings_modal_layout()

    shadow = get_drop_shadow(modal.width, modal.height, radius=12, blur=14, alpha=50, offset_y=5)
    surface.blit(shadow, (modal.x - 14, modal.y - 9))

    pygame.draw.rect(surface, PANEL, modal, border_radius=12)
    pygame.draw.rect(surface, ACCENT, modal, 3, border_radius=12)

    title_surf = fonts["modal_title"].render("MySQL Database Settings", True, TEXT)
    surface.blit(title_surf, (modal.x + 28, modal.y + 20))
    pygame.draw.line(surface, (222, 232, 240), (modal.x + 28, modal.y + 58), (modal.right - 28, modal.y + 58), 1)

    field_labels = (
        ("MySQL Host:", "host"),
        ("MySQL Port:", "port"),
        ("Username:", "user"),
        ("Password:", "password"),
    )
    for label_text, key in field_labels:
        box = boxes[key]
        lbl = fonts["label"].render(label_text, True, TEXT)
        surface.blit(lbl, (modal.x + 28, box.y + 8))
        draw_input_field(
            surface,
            box,
            fields[key],
            active_field == key,
            fonts["body"],
            cursor_visible=cursor_visible,
            mask=(key == "password" and not show_password),
        )

    # Port helper note
    port_hint = fonts["small"].render("(Default: 3306 or 3307)", True, TEXT_MUTED)
    surface.blit(port_hint, (boxes["port"].right + 12, boxes["port"].y + 9))

    # Show/Hide password button
    pw_hover = show_pw_btn.collidepoint(mouse_pos)
    pw_bg = (224, 236, 246) if pw_hover else (238, 244, 249)
    pygame.draw.rect(surface, pw_bg, show_pw_btn, border_radius=6)
    pygame.draw.rect(surface, ACCENT if pw_hover else INPUT_BORDER_DEFAULT, show_pw_btn, 1, border_radius=6)
    pw_lbl = fonts["small_bold"].render("Hide" if show_password else "Show", True, ACCENT)
    surface.blit(pw_lbl, pw_lbl.get_rect(center=show_pw_btn.center))

    # Encoding / Charset stepper
    enc_lbl = fonts["label"].render("DB Encoding:", True, TEXT)
    surface.blit(enc_lbl, (modal.x + 28, charset_box.y + 8))

    for btn, sym in ((charset_prev, "<"), (charset_next, ">")):
        b_hov = btn.collidepoint(mouse_pos)
        pygame.draw.rect(surface, (72, 145, 192) if b_hov else ACCENT, btn, border_radius=6)
        s_surf = fonts["small_bold"].render(sym, True, (255, 255, 255))
        surface.blit(s_surf, s_surf.get_rect(center=btn.center))

    pygame.draw.rect(surface, INPUT_BG, charset_box, border_radius=6)
    pygame.draw.rect(surface, ACCENT, charset_box, 2, border_radius=6)
    cs_val = fields.get("charset", "utf8mb4")
    cs_display = CHARSET_LABELS.get(cs_val, cs_val)
    cs_surf = fonts["small_bold"].render(cs_display, True, TEXT)
    surface.blit(cs_surf, cs_surf.get_rect(center=charset_box.center))

    # Fallback explanation note
    fb_note = fonts["small"].render(
        "Note: Auto-falls back to utf8 if server lacks utf8mb4 (e.g. MySQL 5.0 Error 1115).",
        True,
        TEXT_MUTED,
    )
    surface.blit(fb_note, (modal.x + 28, charset_box.bottom + 12))

    if error_msg:
        err_surf = fonts["small_bold"].render(error_msg, True, LOSS_RED)
        surface.blit(err_surf, (modal.x + 28, modal.bottom - 84))

    # Save & Cancel buttons
    save_hov = save_btn.collidepoint(mouse_pos)
    pygame.draw.rect(surface, (58, 138, 95) if save_hov else PROFIT_GREEN, save_btn, border_radius=8)
    save_txt = fonts["small_bold"].render("Save & Reconnect", True, (255, 255, 255))
    surface.blit(save_txt, save_txt.get_rect(center=save_btn.center))

    cancel_hov = cancel_btn.collidepoint(mouse_pos)
    pygame.draw.rect(surface, (148, 160, 170) if cancel_hov else (130, 142, 152), cancel_btn, border_radius=8)
    cancel_txt = fonts["small_bold"].render("Cancel (Esc)", True, (255, 255, 255))
    surface.blit(cancel_txt, cancel_txt.get_rect(center=cancel_btn.center))


#_____________________________SCREEN DRAW_____________________________
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    map_path = os.path.join(script_dir, "store_level1.txt")
    game_path = os.path.join(script_dir, "store_sim.py")
    editor_path = os.path.join(script_dir, "mapeditor.py")
    config_path = os.path.join(script_dir, "db_config.py")

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Store Simulator")
    clock = pygame.time.Clock()
    title_font = pygame.font.SysFont("Arial", 50, bold=True)
    body_font = pygame.font.SysFont("Arial", 20)
    button_font = pygame.font.SysFont("Arial", 24, bold=True)
    small_btn_font = pygame.font.SysFont("Arial", 18, bold=True)

    modal_fonts = {
        "modal_title": pygame.font.SysFont("Arial", 24, bold=True),
        "label": pygame.font.SysFont("Arial", 17, bold=True),
        "body": pygame.font.SysFont("Arial", 19),
        "small": pygame.font.SysFont("Arial", 14),
        "small_bold": pygame.font.SysFont("Arial", 16, bold=True),
    }

    ready, status = prepare_database(map_path)
    panel = pygame.Rect(110, 60, 680, 410)
    settings_button = pygame.Rect(panel.right - 142, panel.y + 16, 124, 34)
    editor_button = pygame.Rect(300, 290, 300, 44)
    sim_button = pygame.Rect(265, 350, 370, 62)

    settings_open = False
    settings_fields = {
        "host": str(getattr(db_config, "DB_HOST", "localhost")),
        "port": str(getattr(db_config, "DB_PORT", 3307)),
        "user": str(getattr(db_config, "DB_USER", "root")),
        "password": str(getattr(db_config, "DB_PASSWORD", "")),
        "charset": str(getattr(db_config, "DB_CHARSET", "utf8mb4")),
    }
    active_field = "port"
    show_password = False
    settings_error = ""
    cursor_timer = 0.0
    cursor_visible = True
    running = True

    def open_settings_modal():
        nonlocal settings_open, settings_fields, active_field, settings_error
        reload_db_config()
        settings_fields = {
            "host": str(getattr(db_config, "DB_HOST", "localhost")),
            "port": str(getattr(db_config, "DB_PORT", 3307)),
            "user": str(getattr(db_config, "DB_USER", "root")),
            "password": str(getattr(db_config, "DB_PASSWORD", "")),
            "charset": str(getattr(db_config, "DB_CHARSET", "utf8mb4")),
        }
        if settings_fields["charset"] not in CHARSET_OPTIONS:
            settings_fields["charset"] = "utf8mb4"
        active_field = "port"
        settings_error = ""
        settings_open = True

    def commit_settings():
        nonlocal settings_open, settings_error, ready, status
        host = settings_fields["host"].strip()
        port_str = settings_fields["port"].strip()
        user = settings_fields["user"].strip()
        password = settings_fields["password"]
        charset = settings_fields["charset"]

        if not host:
            settings_error = "MySQL Host cannot be empty."
            return
        if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
            settings_error = "Port must be a number between 1 and 65535."
            return
        if not user:
            settings_error = "Username cannot be empty."
            return

        try:
            save_db_config_file(config_path, host, int(port_str), user, password, charset)
            ready, status = prepare_database(map_path)
            settings_open = False
            settings_error = ""
        except OSError as err:
            settings_error = f"Could not write db_config.py: {err}"

    while running:
        dt = clock.tick(60) / 1000.0
        cursor_timer += dt
        cursor_visible = (int(cursor_timer * 2.2) % 2) == 0
        mouse_position = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif settings_open:
                if event.type == pygame.KEYDOWN:
                    cursor_timer = 0.0
                    cursor_visible = True
                    if event.key == pygame.K_ESCAPE:
                        settings_open = False
                        settings_error = ""
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        commit_settings()
                    elif event.key == pygame.K_TAB:
                        order = ("host", "port", "user", "password")
                        idx = (order.index(active_field) + 1) % len(order) if active_field in order else 0
                        active_field = order[idx]
                    elif active_field:
                        cur_val = settings_fields[active_field]
                        if event.key == pygame.K_BACKSPACE:
                            settings_fields[active_field] = cur_val[:-1]
                        elif active_field == "port":
                            if event.unicode.isdigit() and len(cur_val) < 5:
                                settings_fields["port"] += event.unicode
                        elif event.unicode.isprintable() and len(cur_val) < 64:
                            settings_fields[active_field] += event.unicode

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    (
                        modal,
                        boxes,
                        show_pw_btn,
                        charset_prev,
                        charset_box,
                        charset_next,
                        save_btn,
                        cancel_btn,
                    ) = settings_modal_layout()
                    for k, box in boxes.items():
                        if box.collidepoint(event.pos):
                            active_field = k
                            cursor_timer = 0.0
                            cursor_visible = True
                            break
                    else:
                        if show_pw_btn.collidepoint(event.pos):
                            show_password = not show_password
                        elif charset_prev.collidepoint(event.pos):
                            cur_cs = settings_fields["charset"]
                            idx = (CHARSET_OPTIONS.index(cur_cs) - 1) % len(CHARSET_OPTIONS)
                            settings_fields["charset"] = CHARSET_OPTIONS[idx]
                        elif charset_next.collidepoint(event.pos):
                            cur_cs = settings_fields["charset"]
                            idx = (CHARSET_OPTIONS.index(cur_cs) + 1) % len(CHARSET_OPTIONS)
                            settings_fields["charset"] = CHARSET_OPTIONS[idx]
                        elif save_btn.collidepoint(event.pos):
                            commit_settings()
                        elif cancel_btn.collidepoint(event.pos):
                            settings_open = False
                            settings_error = ""
                        else:
                            active_field = None

            else:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        ready, status = prepare_database(map_path)
                    elif event.key == pygame.K_s:
                        open_settings_modal()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if settings_button.collidepoint(event.pos):
                        open_settings_modal()
                    elif editor_button.collidepoint(event.pos):
                        subprocess.Popen([sys.executable, editor_path], cwd=script_dir)
                    elif sim_button.collidepoint(event.pos):
                        ready, status = prepare_database(map_path)
                        if ready:
                            subprocess.Popen([sys.executable, game_path], cwd=script_dir)
                            running = False

        screen.fill(BACKGROUND)
        pygame.draw.rect(screen, PANEL, panel, border_radius=16)
        pygame.draw.rect(screen, ACCENT, panel, 3, border_radius=16)

        # Top-Right DB Settings Button
        settings_hover = not settings_open and settings_button.collidepoint(mouse_position)
        settings_bg = (224, 236, 246) if settings_hover else (240, 246, 250)
        pygame.draw.rect(screen, settings_bg, settings_button, border_radius=7)
        pygame.draw.rect(screen, ACCENT, settings_button, 1, border_radius=7)
        settings_lbl = modal_fonts["small_bold"].render("DB Settings", True, ACCENT)
        screen.blit(settings_lbl, settings_lbl.get_rect(center=settings_button.center))

        title = title_font.render("Store Simulator", True, TEXT)
        screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 125)))

        status_color = PROFIT_GREEN if ready else LOSS_RED
        draw_wrapped_text(
            screen,
            status,
            body_font,
            status_color,
            pygame.Rect(165, 175, 570, 95),
        )

        # Map Editor Button (smaller button above Start Store Simulator)
        editor_hover = not settings_open and editor_button.collidepoint(mouse_position)
        editor_bg = (226, 238, 248) if editor_hover else (240, 246, 250)
        editor_border = (40, 105, 150) if editor_hover else ACCENT
        pygame.draw.rect(screen, editor_bg, editor_button, border_radius=8)
        pygame.draw.rect(screen, editor_border, editor_button, 2, border_radius=8)
        editor_text = small_btn_font.render("Launch Map Editor", True, ACCENT)
        screen.blit(editor_text, editor_text.get_rect(center=editor_button.center))

        # Main Simulator Button
        if ready:
            button_color = (72, 145, 192) if (not settings_open and sim_button.collidepoint(mouse_position)) else ACCENT
            label = "Start Store Simulator"
        else:
            button_color = DISABLED
            label = "Database setup required"

        pygame.draw.rect(screen, button_color, sim_button, border_radius=10)
        button_text = button_font.render(label, True, (255, 255, 255))
        screen.blit(button_text, button_text.get_rect(center=sim_button.center))

        # Active connection info badge at bottom of card
        conn_info = modal_fonts["small"].render(
            f"MySQL: {db_config.DB_USER}@{db_config.DB_HOST}:{db_config.DB_PORT}  |  Encoding: {getattr(db_config, 'DB_CHARSET', 'utf8mb4')}",
            True,
            TEXT_MUTED,
        )
        screen.blit(conn_info, conn_info.get_rect(center=(SCREEN_WIDTH // 2, panel.bottom - 22)))

        if not ready:
            retry = body_font.render("Click 'DB Settings' to configure port/password, or press R to retry.", True, TEXT)
            screen.blit(retry, retry.get_rect(center=(SCREEN_WIDTH // 2, 495)))

        if settings_open:
            draw_settings_modal(
                screen,
                modal_fonts,
                settings_fields,
                active_field,
                show_password,
                settings_error,
                cursor_visible,
                mouse_position,
            )

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
