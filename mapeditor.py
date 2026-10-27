"""Store Map Editor - Visual level designer for Store Management Simulator.

Enforces 25x15 grid standards, procedural station previews, singleton validation
(Player, Catalogue, Cash Register, Employee Terminal), and live database conformity.
Strictly targets store_level1.txt without creating any secondary level files.
"""

import os
import sys
import pygame

from ui_theme import (
    ACCENT_COLOR,
    CATALOGUE_THEME,
    DELETE_RED,
    EMPLOYEE_THEME,
    FLOOR_COLOR,
    INPUT_BG,
    INPUT_BORDER_DEFAULT,
    LOSS_RED,
    PANEL_BG,
    PLAYER_COLOR,
    PROFIT_GREEN,
    REGISTER_THEME,
    SCROLL_TRACK_COLOR,
    SHELF_THEME,
    TEXT_MUTED,
    TEXT_PRIMARY,
    WALL_COLOR,
    WINDOW_COLOR,
    brighten_color,
    get_drop_shadow,
)

#_____________________________SETTINGS_____________________________
TILE_SIZE = 40
GRID_COLS = 25
GRID_ROWS = 15
GAME_WIDTH = GRID_COLS * TILE_SIZE   # 1000px
GAME_HEIGHT = GRID_ROWS * TILE_SIZE  # 600px
SIDEBAR_WIDTH = 280
SCREEN_WIDTH = GAME_WIDTH + SIDEBAR_WIDTH  # 1280px
SCREEN_HEIGHT = GAME_HEIGHT                # 600px
FPS = 60

MAP_FILENAME = "store_level1.txt"

# Valid map tiles conforming to database_setup.py MAP_TILES
MAP_TILES = ("#", ".", "S", "C", "R", "E", "P")

TOOL_METADATA = {
    "#": {
        "name": "Wall",
        "hotkey": "W",
        "description": "Solid store boundary or partition",
        "color": WALL_COLOR,
        "is_singleton": False,
    },
    ".": {
        "name": "Walkable Floor",
        "hotkey": "X",
        "description": "Walkable customer/manager tile",
        "color": FLOOR_COLOR,
        "is_singleton": False,
    },
    "S": {
        "name": "Shelf",
        "hotkey": "S",
        "description": "Inventory display fixture",
        "color": SHELF_THEME.tile,
        "is_singleton": False,
    },
    "C": {
        "name": "Catalogue",
        "hotkey": "C",
        "description": "Master products database terminal",
        "color": CATALOGUE_THEME.tile,
        "is_singleton": True,
    },
    "R": {
        "name": "Cash Register",
        "hotkey": "R",
        "description": "Finance & transactions counter",
        "color": REGISTER_THEME.tile,
        "is_singleton": True,
    },
    "E": {
        "name": "Staff Desk",
        "hotkey": "E",
        "description": "Employee roster terminal",
        "color": EMPLOYEE_THEME.tile,
        "is_singleton": True,
    },
    "P": {
        "name": "Manager Spawn",
        "hotkey": "P",
        "description": "Initial player start point",
        "color": PLAYER_COLOR,
        "is_singleton": True,
    },
}

#_____________________________SOUND HELPER_____________________________

def load_sound(filename, volume=0.4):
    """Safely load a sound effect, returning None if audio hardware is absent."""
    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    if os.path.exists(filepath):
        try:
            sound = pygame.mixer.Sound(filepath)
            sound.set_volume(volume)
            return sound
        except Exception:
            pass
    return None

#_____________________________MAP LOAD & SAVE_____________________________

def default_template():
    """Create a valid default store layout conforming to database_setup rules."""
    grid = [["." for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
    # Border walls
    for x in range(GRID_COLS):
        grid[0][x] = "#"
        grid[GRID_ROWS - 1][x] = "#"
    for y in range(GRID_ROWS):
        grid[y][0] = "#"
        grid[y][GRID_COLS - 1] = "#"

    # Singletons
    grid[1][1] = "P"
    grid[1][12] = "C"
    grid[1][13] = "R"
    grid[1][14] = "E"

    # Sample Shelves
    for y in (2, 5, 8, 11):
        for x in range(2, 7):
            grid[y][x] = "S"
        for x in range(18, 23):
            grid[y][x] = "S"

    return grid


def load_store_map():
    """Load store_level1.txt into a 25x15 2D character array."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(script_dir, MAP_FILENAME)
    if not os.path.exists(filename):
        return default_template()

    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = [line.rstrip("\r\n") for line in f]
    except OSError:
        return default_template()

    grid = []
    for line in lines[:GRID_ROWS]:
        row = list(line)
        while len(row) < GRID_COLS:
            row.append(".")
        grid.append(row[:GRID_COLS])

    while len(grid) < GRID_ROWS:
        grid.append(["." for _ in range(GRID_COLS)])

    return grid


def save_store_map(grid):
    """Save the 25x15 grid strictly to store_level1.txt."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(script_dir, MAP_FILENAME)
    with open(filename, "w", encoding="utf-8") as f:
        for row in grid:
            f.write("".join(row) + "\n")


def validate_store_map(grid):
    """Verify conformity with store simulator and database_setup requirements."""
    counts = {"#": 0, ".": 0, "S": 0, "C": 0, "R": 0, "E": 0, "P": 0}
    for row in grid:
        for char in row:
            if char in counts:
                counts[char] += 1

    errors = []
    if counts["P"] != 1:
        errors.append("Must have exactly 1 Player Spawn (P)")
    if counts["C"] != 1:
        errors.append("Must have exactly 1 Catalogue Terminal (C)")
    if counts["R"] != 1:
        errors.append("Must have exactly 1 Cash Register (R)")
    if counts["E"] != 1:
        errors.append("Must have exactly 1 Employee Terminal (E)")
    if counts["S"] < 1:
        errors.append("Store requires at least 1 Shelf (S)")

    return {
        "counts": counts,
        "is_valid": len(errors) == 0,
        "errors": errors,
    }

#_____________________________TILE RENDERING_____________________________

def draw_tile_at(surface, tile_char, rect, is_hovered=False):
    """Draw a tile using identical procedural rendering as store_sim.py."""
    # Always draw clean store floor underneath
    pygame.draw.rect(surface, FLOOR_COLOR, rect)
    # Subtle tile grid line
    pygame.draw.rect(surface, (230, 235, 241), rect, 1)

    if tile_char == "#":
        # Solid wall
        pygame.draw.rect(surface, WALL_COLOR, rect)
        pygame.draw.rect(surface, (140, 168, 190), rect, 1)
    elif tile_char == "S":
        # Shelf fixture
        edge_col = SHELF_THEME.edge
        pygame.draw.rect(surface, SHELF_THEME.tile, rect)
        pygame.draw.rect(surface, edge_col, rect, 3)
        pygame.draw.line(
            surface,
            edge_col,
            (rect.left + 5, rect.centery),
            (rect.right - 5, rect.centery),
            2,
        )
    elif tile_char == "C":
        # Catalogue terminal
        edge_col = CATALOGUE_THEME.edge
        pygame.draw.rect(surface, CATALOGUE_THEME.tile, rect)
        pygame.draw.rect(surface, edge_col, rect, 3)
        pygame.draw.rect(surface, edge_col, rect.inflate(-16, -10), 2, border_radius=3)
    elif tile_char == "R":
        # Cash register
        edge_col = REGISTER_THEME.edge
        pygame.draw.rect(surface, REGISTER_THEME.tile, rect, border_radius=4)
        pygame.draw.rect(surface, edge_col, rect, 3, border_radius=4)
        pygame.draw.rect(surface, edge_col, rect.inflate(-12, -19), 2, border_radius=2)
        pygame.draw.line(
            surface,
            edge_col,
            (rect.left + 7, rect.bottom - 9),
            (rect.right - 7, rect.bottom - 9),
            2,
        )
    elif tile_char == "E":
        # Employee terminal with ID badge
        edge_col = EMPLOYEE_THEME.edge
        pygame.draw.rect(surface, EMPLOYEE_THEME.tile, rect, border_radius=4)
        pygame.draw.rect(surface, edge_col, rect, 3, border_radius=4)
        badge_rect = pygame.Rect(rect.centerx - 7, rect.centery - 9, 14, 18)
        pygame.draw.rect(surface, (255, 255, 255), badge_rect, border_radius=2)
        pygame.draw.rect(surface, edge_col, badge_rect, 1, border_radius=2)
        pygame.draw.line(surface, edge_col, (badge_rect.x + 3, badge_rect.y + 5), (badge_rect.right - 4, badge_rect.y + 5), 2)
        pygame.draw.line(surface, (140, 140, 140), (badge_rect.x + 3, badge_rect.y + 9), (badge_rect.right - 4, badge_rect.y + 9), 1)
        pygame.draw.line(surface, (140, 140, 140), (badge_rect.x + 3, badge_rect.y + 13), (badge_rect.right - 4, badge_rect.y + 13), 1)
    elif tile_char == "P":
        # Manager spawn avatar
        pygame.draw.circle(surface, PLAYER_COLOR, rect.center, 12)
        pygame.draw.circle(surface, ACCENT_COLOR, rect.center, 12, 2)
        pygame.draw.circle(surface, ACCENT_COLOR, (rect.centerx + 7, rect.centery), 3)

    if is_hovered:
        pygame.draw.rect(surface, ACCENT_COLOR, rect, 2)


def draw_mini_preview(surface, tile_char, rect):
    """Draw a scaled thumbnail preview of a tile for sidebar tool buttons."""
    pygame.draw.rect(surface, FLOOR_COLOR, rect, border_radius=3)
    if tile_char == "#":
        pygame.draw.rect(surface, WALL_COLOR, rect, border_radius=3)
    elif tile_char == "S":
        pygame.draw.rect(surface, SHELF_THEME.tile, rect, border_radius=3)
        pygame.draw.rect(surface, SHELF_THEME.edge, rect, 2, border_radius=3)
        pygame.draw.line(surface, SHELF_THEME.edge, (rect.left + 3, rect.centery), (rect.right - 3, rect.centery), 2)
    elif tile_char == "C":
        pygame.draw.rect(surface, CATALOGUE_THEME.tile, rect, border_radius=3)
        pygame.draw.rect(surface, CATALOGUE_THEME.edge, rect, 2, border_radius=3)
        pygame.draw.rect(surface, CATALOGUE_THEME.edge, rect.inflate(-10, -8), 1, border_radius=2)
    elif tile_char == "R":
        pygame.draw.rect(surface, REGISTER_THEME.tile, rect, border_radius=3)
        pygame.draw.rect(surface, REGISTER_THEME.edge, rect, 2, border_radius=3)
        pygame.draw.line(surface, REGISTER_THEME.edge, (rect.left + 4, rect.bottom - 6), (rect.right - 4, rect.bottom - 6), 2)
    elif tile_char == "E":
        pygame.draw.rect(surface, EMPLOYEE_THEME.tile, rect, border_radius=3)
        pygame.draw.rect(surface, EMPLOYEE_THEME.edge, rect, 2, border_radius=3)
        badge = pygame.Rect(rect.centerx - 4, rect.centery - 5, 8, 10)
        pygame.draw.rect(surface, (255, 255, 255), badge, border_radius=1)
    elif tile_char == "P":
        pygame.draw.circle(surface, PLAYER_COLOR, rect.center, 8)
        pygame.draw.circle(surface, ACCENT_COLOR, rect.center, 8, 2)
    else:
        # Floor thumbnail
        pygame.draw.rect(surface, (220, 226, 232), rect, 1, border_radius=3)

#_____________________________MAIN EDITOR_____________________________

def main():
    pygame.init()
    try:
        pygame.mixer.init()
    except Exception:
        pass

    interact_sound = load_sound("fruit1.wav", volume=0.4)
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Store Simulator - Map Editor v1.0")
    clock = pygame.time.Clock()

    fonts = {
        "title": pygame.font.SysFont("Arial", 18, bold=True),
        "body": pygame.font.SysFont("Arial", 14),
        "body_bold": pygame.font.SysFont("Arial", 14, bold=True),
        "section": pygame.font.SysFont("Arial", 12, bold=True),
        "badge": pygame.font.SysFont("Arial", 12, bold=True),
        "small": pygame.font.SysFont("Arial", 11),
    }

    grid = load_store_map()
    current_tool = "#"

    message = f"Loaded {MAP_FILENAME}"
    message_color = PROFIT_GREEN
    msg_timer = 3.0

    # UI Geometry in Sidebar
    sb_x = GAME_WIDTH + 14
    sb_w = SIDEBAR_WIDTH - 28

    tool_rects = {}
    tool_y = 86
    for char in MAP_TILES:
        tool_rects[char] = pygame.Rect(sb_x, tool_y, sb_w, 32)
        tool_y += 36

    save_btn_rect = pygame.Rect(sb_x, 484, sb_w, 36)
    reset_btn_rect = pygame.Rect(sb_x, 526, sb_w, 26)

    running = True
    mouse_is_down = False
    active_mouse_btn = None

    def trigger_save():
        nonlocal message, message_color, msg_timer
        val = validate_store_map(grid)
        save_store_map(grid)
        if interact_sound:
            interact_sound.play()
        if val["is_valid"]:
            message = f"Saved {MAP_FILENAME} (Valid Map)"
            message_color = PROFIT_GREEN
        else:
            message = f"Saved with warnings: {val['errors'][0]}"
            message_color = LOSS_RED
        msg_timer = 4.0

    def apply_tool(grid_x, grid_y, tool):
        if not (0 <= grid_x < GRID_COLS and 0 <= grid_y < GRID_ROWS):
            return

        meta = TOOL_METADATA.get(tool)
        if not meta:
            return

        # Singleton enforcement: only 1 instance allowed
        if meta["is_singleton"]:
            for r in range(GRID_ROWS):
                for c in range(GRID_COLS):
                    if grid[r][c] == tool:
                        grid[r][c] = "."

        grid[grid_y][grid_x] = tool

    while running:
        dt = clock.tick(FPS) / 1000.0
        if msg_timer > 0:
            msg_timer -= dt

        mouse_pos = pygame.mouse.get_pos()
        mx, my = mouse_pos
        is_ctrl = pygame.key.get_mods() & pygame.KMOD_CTRL

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                save_store_map(grid)
                running = False

            elif event.type == pygame.KEYDOWN:
                # Ctrl+S to save
                if event.key == pygame.K_s and is_ctrl:
                    trigger_save()

                # Tool selection hotkeys
                elif event.key == pygame.K_w:
                    current_tool = "#"
                elif event.key == pygame.K_x:
                    current_tool = "."
                elif event.key == pygame.K_s and not is_ctrl:
                    current_tool = "S"
                elif event.key == pygame.K_c:
                    current_tool = "C"
                elif event.key == pygame.K_r:
                    current_tool = "R"
                elif event.key == pygame.K_e:
                    current_tool = "E"
                elif event.key == pygame.K_p:
                    current_tool = "P"

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button in (1, 3):
                    mouse_is_down = True
                    active_mouse_btn = event.button

                    # Check grid click
                    if mx < GAME_WIDTH and my < GAME_HEIGHT:
                        gx = mx // TILE_SIZE
                        gy = my // TILE_SIZE
                        if event.button == 1:
                            apply_tool(gx, gy, current_tool)
                        elif event.button == 3:
                            grid[gy][gx] = "."

                    # Check tool button clicks
                    for char, r in tool_rects.items():
                        if r.collidepoint(mouse_pos) and event.button == 1:
                            current_tool = char

                    # Check Save button
                    if save_btn_rect.collidepoint(mouse_pos) and event.button == 1:
                        trigger_save()

                    # Check Reset template button
                    if reset_btn_rect.collidepoint(mouse_pos) and event.button == 1:
                        grid = default_template()
                        message = "Reset map to standard template"
                        message_color = TEXT_MUTED
                        msg_timer = 2.5

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button in (1, 3):
                    mouse_is_down = False
                    active_mouse_btn = None

        # Continuous drag painting (only for multi-tiles like Wall, Floor, Shelf or Erase)
        if mouse_is_down and mx < GAME_WIDTH and my < GAME_HEIGHT:
            gx = mx // TILE_SIZE
            gy = my // TILE_SIZE
            if 0 <= gx < GRID_COLS and 0 <= gy < GRID_ROWS:
                if active_mouse_btn == 1:
                    # Multi-tiles can drag paint; singletons only paint on single click
                    if not TOOL_METADATA[current_tool]["is_singleton"]:
                        apply_tool(gx, gy, current_tool)
                elif active_mouse_btn == 3:
                    grid[gy][gx] = "."

        # --- RENDERING ---
        screen.fill(WINDOW_COLOR)

        # 1. Render Map Tiles
        hovered_gx = mx // TILE_SIZE if mx < GAME_WIDTH else -1
        hovered_gy = my // TILE_SIZE if my < GAME_HEIGHT else -1

        for y in range(GRID_ROWS):
            for x in range(GRID_COLS):
                tile_rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                is_hov = (x == hovered_gx and y == hovered_gy)
                draw_tile_at(screen, grid[y][x], tile_rect, is_hovered=is_hov)

        # Map border divider
        pygame.draw.line(screen, (200, 212, 224), (GAME_WIDTH, 0), (GAME_WIDTH, SCREEN_HEIGHT), 2)

        # 2. Render Sidebar
        sidebar_rect = pygame.Rect(GAME_WIDTH, 0, SIDEBAR_WIDTH, SCREEN_HEIGHT)
        pygame.draw.rect(screen, PANEL_BG, sidebar_rect)
        pygame.draw.line(screen, (215, 226, 236), (GAME_WIDTH, 0), (GAME_WIDTH, SCREEN_HEIGHT), 1)

        # Header Title
        title_surf = fonts["title"].render("STORE MAP EDITOR", True, TEXT_PRIMARY)
        screen.blit(title_surf, (sb_x, 16))

        sub_surf = fonts["small"].render(f"Target: {MAP_FILENAME} (25x15 Grid)", True, TEXT_MUTED)
        screen.blit(sub_surf, (sb_x, 40))

        # Subtle divider
        pygame.draw.line(screen, (230, 236, 242), (sb_x, 58), (sb_x + sb_w, 58), 1)

        # Section: Tile Palette
        pal_label = fonts["section"].render("PALETTE TOOLS", True, TEXT_MUTED)
        screen.blit(pal_label, (sb_x, 68))

        for char, r in tool_rects.items():
            meta = TOOL_METADATA[char]
            is_selected = (char == current_tool)
            is_hover = r.collidepoint(mouse_pos)

            # Card background
            if is_selected:
                card_bg = (235, 243, 250)
                card_border = ACCENT_COLOR
                border_width = 2
            elif is_hover:
                card_bg = (245, 248, 252)
                card_border = (180, 200, 218)
                border_width = 1
            else:
                card_bg = (255, 255, 255)
                card_border = (225, 232, 238)
                border_width = 1

            pygame.draw.rect(screen, card_bg, r, border_radius=4)
            pygame.draw.rect(screen, card_border, r, border_width, border_radius=4)

            # Mini Tile Preview Icon
            icon_r = pygame.Rect(r.x + 6, r.y + 5, 22, 22)
            draw_mini_preview(screen, char, icon_r)

            # Tool Name
            name_col = ACCENT_COLOR if is_selected else TEXT_PRIMARY
            name_surf = fonts["body_bold" if is_selected else "body"].render(meta["name"], True, name_col)
            screen.blit(name_surf, (r.x + 36, r.y + 6))

            # Hotkey Badge
            badge_surf = fonts["badge"].render(f"[{meta['hotkey']}]", True, TEXT_MUTED if not is_selected else ACCENT_COLOR)
            screen.blit(badge_surf, (r.right - badge_surf.get_width() - 8, r.y + 7))

        # Section: Validation Checklist
        val_summary = validate_store_map(grid)
        val_y = 346
        val_label = fonts["section"].render("MAP VALIDATION", True, TEXT_MUTED)
        screen.blit(val_label, (sb_x, val_y))

        val_card = pygame.Rect(sb_x, val_y + 16, sb_w, 108)
        val_bg = (248, 252, 249) if val_summary["is_valid"] else (255, 248, 248)
        val_border = PROFIT_GREEN if val_summary["is_valid"] else (230, 180, 180)
        pygame.draw.rect(screen, val_bg, val_card, border_radius=6)
        pygame.draw.rect(screen, val_border, val_card, 1, border_radius=6)

        c = val_summary["counts"]
        checklist = [
            ("P Manager Spawn:", c["P"] == 1, f"{c['P']}/1"),
            ("C Catalogue:", c["C"] == 1, f"{c['C']}/1"),
            ("R Cash Register:", c["R"] == 1, f"{c['R']}/1"),
            ("E Staff Desk:", c["E"] == 1, f"{c['E']}/1"),
            ("S Shelves:", c["S"] >= 1, f"{c['S']} placed"),
        ]

        item_y = val_card.y + 6
        for name, ok, count_str in checklist:
            mark = "OK" if ok else "NO"
            mark_col = PROFIT_GREEN if ok else LOSS_RED
            mark_surf = fonts["badge"].render(mark, True, mark_col)
            screen.blit(mark_surf, (val_card.x + 10, item_y))

            lbl_surf = fonts["small"].render(name, True, TEXT_PRIMARY)
            screen.blit(lbl_surf, (val_card.x + 36, item_y))

            cnt_surf = fonts["small"].render(count_str, True, TEXT_MUTED if ok else LOSS_RED)
            screen.blit(cnt_surf, (val_card.right - cnt_surf.get_width() - 10, item_y))
            item_y += 19

        # Save Button
        save_hover = save_btn_rect.collidepoint(mouse_pos)
        save_bg = PROFIT_GREEN if not save_hover else brighten_color(PROFIT_GREEN, 15)
        # Drop shadow
        save_shadow = save_btn_rect.copy()
        save_shadow.y += 2
        pygame.draw.rect(screen, (210, 220, 228), save_shadow, border_radius=6)
        pygame.draw.rect(screen, save_bg, save_btn_rect, border_radius=6)
        save_txt = fonts["body_bold"].render("SAVE MAP  (Ctrl+S)", True, (255, 255, 255))
        screen.blit(save_txt, save_txt.get_rect(center=save_btn_rect.center))

        # Reset to Template Button
        reset_hover = reset_btn_rect.collidepoint(mouse_pos)
        reset_bg = (240, 243, 246) if not reset_hover else (230, 235, 240)
        pygame.draw.rect(screen, reset_bg, reset_btn_rect, border_radius=4)
        pygame.draw.rect(screen, (200, 212, 220), reset_btn_rect, 1, border_radius=4)
        reset_txt = fonts["small"].render("Reset to Standard Template", True, TEXT_MUTED)
        screen.blit(reset_txt, reset_txt.get_rect(center=reset_btn_rect.center))

        # Status / Message Toast
        if msg_timer > 0:
            status_surf = fonts["small"].render(message, True, message_color)
            screen.blit(status_surf, (sb_x, 564))
        else:
            helper_surf = fonts["small"].render("L-Click: Place | R-Click: Erase", True, TEXT_MUTED)
            screen.blit(helper_surf, (sb_x, 564))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
