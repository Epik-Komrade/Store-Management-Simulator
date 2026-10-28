"""First playable store-management conversion"""

import math
import os
import sys
import pygame

from database_setup import (
    DatabaseSetupError,
    MAX_SHELF_CAPACITY,
    add_catalogue_product,
    add_employee,
    add_shelf_item,
    delete_catalogue_product,
    delete_employee,
    delete_shelf_item,
    ensure_store_database,
    get_product_shelf_distribution,
    load_employees,
    load_finance_data,
    load_product_catalogue,
    load_shelf_categories,
    load_shelf_inventory,
    load_storage_inventory,
    order_storage_stock,
    sell_shelf_stock,
    set_store_balance,
    update_catalogue_product,
    update_employee,
    update_shelf_category,
    update_shelf_item,
)
from store_seed_data import CATEGORIES

SCREEN_WIDTH = 1000
MAP_HEIGHT = 600
SCREEN_HEIGHT = 680
HUD_HEIGHT = SCREEN_HEIGHT - MAP_HEIGHT
FPS = 60
TILE_SIZE = 40
PLAYER_SPEED = 210  # pixels per second
INTERACTION_DISTANCE = 52

from ui_theme import (
    SHELF_THEME,
    CATALOGUE_THEME,
    REGISTER_THEME,
    EMPLOYEE_THEME,
    STORAGE_THEME,
    WINDOW_COLOR,
    FLOOR_COLOR,
    WALL_COLOR,
    INFO_PANEL_COLOR,
    PLAYER_COLOR,
    ACCENT_COLOR,
    PANEL_BG,
    TEXT_PRIMARY as TEXT_COLOR,
    TEXT_MUTED,
    INPUT_BG,
    INPUT_BORDER_DEFAULT,
    PROFIT_GREEN,
    LOSS_RED,
    DELETE_RED,
    DELETE_RED_HOVER,
    SCROLL_TRACK_COLOR,
    OVERLAY_COLOR,
    get_fonts_dict,
    get_drop_shadow,
    brighten_color,
)
from ui_components import SmoothScroll

# Station Palette aliases for backwards-compatibility
SHELF_COLOR = SHELF_THEME.tile
SHELF_EDGE_COLOR = SHELF_THEME.edge
SHELF_BUTTON_COLOR = SHELF_THEME.button
SHELF_SELECTED_COLOR = SHELF_THEME.selected

CATALOGUE_COLOR = CATALOGUE_THEME.tile
CATALOGUE_EDGE_COLOR = CATALOGUE_THEME.edge
CATALOGUE_BUTTON_COLOR = CATALOGUE_THEME.button
CATALOGUE_SELECTED_COLOR = CATALOGUE_THEME.selected

REGISTER_COLOR = REGISTER_THEME.tile
REGISTER_EDGE_COLOR = REGISTER_THEME.edge
REGISTER_BUTTON_COLOR = REGISTER_THEME.button
REGISTER_SELECTED_COLOR = REGISTER_THEME.selected

EMPLOYEE_COLOR = EMPLOYEE_THEME.tile
EMPLOYEE_EDGE_COLOR = EMPLOYEE_THEME.edge
EMPLOYEE_BUTTON_COLOR = EMPLOYEE_THEME.button
EMPLOYEE_SELECTED_COLOR = EMPLOYEE_THEME.selected

STORAGE_COLOR = STORAGE_THEME.tile
STORAGE_EDGE_COLOR = STORAGE_THEME.edge
STORAGE_BUTTON_COLOR = STORAGE_THEME.button
STORAGE_SELECTED_COLOR = STORAGE_THEME.selected

ROLES = ["Cashier", "Stocker", "Store Assistant"]
SHELF_CATEGORIES = ["General", *CATEGORIES]

SHELF_CATEGORY_THEMES = {
    "General": {
        "fill": SHELF_COLOR,
        "edge": SHELF_EDGE_COLOR,
        "button": SHELF_BUTTON_COLOR,
        "selected": SHELF_SELECTED_COLOR,
    },
    "Frozen Goods": {
        "fill": (102, 186, 232),
        "edge": (42, 126, 176),
        "button": (64, 150, 200),
        "selected": (218, 240, 252),
    },
    "Bed & Bath": {
        "fill": (162, 128, 208),
        "edge": (108, 74, 156),
        "button": (132, 96, 180),
        "selected": (236, 226, 250),
    },
    "Appliances": {
        "fill": (118, 148, 176),
        "edge": (68, 96, 124),
        "button": (90, 120, 148),
        "selected": (226, 236, 244),
    },
    "Groceries & Pantry": {
        "fill": (96, 182, 108),
        "edge": (48, 130, 60),
        "button": (68, 154, 80),
        "selected": (222, 244, 226),
    },
    "Beverages & Snacks": {
        "fill": (235, 134, 66),
        "edge": (182, 84, 26),
        "button": (208, 108, 44),
        "selected": (252, 232, 216),
    },
    "Household & Cleaning": {
        "fill": (68, 186, 166),
        "edge": (28, 134, 116),
        "button": (46, 158, 140),
        "selected": (218, 246, 240),
    },
}


def get_shelf_theme(category):
    return SHELF_CATEGORY_THEMES.get(category or "General", SHELF_CATEGORY_THEMES["General"])


class GameState:
    PLAYING = 0
    SHELF_MENU = 1
    CATALOGUE_MENU = 2
    EDIT_ITEM = 3
    ADD_ITEM = 4
    PRODUCT_EDITOR = 5
    FINANCE_MENU = 6
    EMPLOYEE_MENU = 7
    EMPLOYEE_EDITOR = 8
    STORAGE_MENU = 9
    STORAGE_DISTRIBUTION = 10
    STORAGE_ORDER = 11


class Shelf:
    #solid store shelf with inventory loaded from MySQL

    def __init__(self, shelf_id, grid_x, grid_y, items, category="General"):
        self.shelf_id = shelf_id
        self.grid_x = grid_x
        self.grid_y = grid_y
        self.rect = pygame.Rect(grid_x * TILE_SIZE, grid_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
        self.items = list(items)
        self.category = category or "General"
        self.display_name = f"Shelf {shelf_id}"

    def get_visible_items(self, product_catalogue=None):
        if not self.category or self.category == "General" or not product_catalogue:
            return self.items
        cat_by_id = {p[0]: (p[5] if len(p) > 5 else "General") for p in product_catalogue}
        return [item for item in self.items if cat_by_id.get(item[0], "General") == self.category]

    def get_total_quantity(self, product_catalogue=None):
        return sum(item[2] for item in self.get_visible_items(product_catalogue))


def recompute_shelf_display_names(shelves):
    category_counts = {}
    for shelf in sorted(shelves, key=lambda s: s.shelf_id):
        cat = getattr(shelf, "category", "General") or "General"
        if cat == "General":
            shelf.display_name = f"Shelf {shelf.shelf_id}"
        else:
            category_counts[cat] = category_counts.get(cat, 0) + 1
            shelf.display_name = f"{cat} {category_counts[cat]}"


class ProductCatalogue:
    #solid store catalogue terminal, placed once in the map as C

    def __init__(self, grid_x, grid_y):
        self.rect = pygame.Rect(grid_x * TILE_SIZE, grid_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)


class CashRegister:
    #one finance terminal, placed once in the map as R

    def __init__(self, grid_x, grid_y):
        self.rect = pygame.Rect(grid_x * TILE_SIZE, grid_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)


class EmployeeTerminal:
    #one staff roster terminal, placed once in the map as E

    def __init__(self, grid_x, grid_y):
        self.rect = pygame.Rect(grid_x * TILE_SIZE, grid_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)


class StorageDepot:
    #backroom storage & restock depot, placed in map as B

    def __init__(self, grid_x, grid_y):
        self.grid_x = grid_x
        self.grid_y = grid_y
        self.rect = pygame.Rect(grid_x * TILE_SIZE, grid_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)

#___________________________________________PLAYER CLASS_______________________________________________________________

def load_sound(filename, volume=0.5):
    """Load a sound effect safely with volume control, returning None if missing."""
    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    if os.path.exists(filepath):
        try:
            sound = pygame.mixer.Sound(filepath)
            sound.set_volume(volume)
            return sound
        except Exception as error:
            print(f"Error loading sound {filename}: {error}")
    return None


class Player:
    #minimal manager/player character

    def __init__(self, position, step_sound=None):
        self.rect = pygame.Rect(position[0], position[1], 24, 24)
        self.position = pygame.Vector2(self.rect.topleft)
        self.angle = 0.0
        self.step_sound = step_sound
        self.step_timer = 0.28

    def update(self, dt, solid_rects):
        keys = pygame.key.get_pressed()
        direction = pygame.Vector2(
            int(keys[pygame.K_d]) - int(keys[pygame.K_a]),
            int(keys[pygame.K_s]) - int(keys[pygame.K_w]),
        )
        if direction.length_squared() > 0:
            direction = direction.normalize()

        old_position = pygame.Vector2(self.position)
        self._move(direction.x * PLAYER_SPEED * dt, 0, solid_rects)
        self._move(0, direction.y * PLAYER_SPEED * dt, solid_rects)

        actually_moved = (self.position - old_position).length_squared() > 0.01
        if actually_moved:
            self.step_timer += dt
            if self.step_timer >= 0.28:
                if self.step_sound:
                    self.step_sound.play()
                self.step_timer = 0.0
        else:
            self.step_timer = 0.28

        mouse_x, mouse_y = pygame.mouse.get_pos()
        center_x, center_y = self.rect.center
        self.angle = math.degrees(math.atan2(-(mouse_y - center_y), mouse_x - center_x))

    def _move(self, dx, dy, solid_rects):
        if dx:
            self.position.x += dx
            self.rect.x = round(self.position.x)
            for solid in solid_rects:
                if self.rect.colliderect(solid):
                    if dx > 0:
                        self.rect.right = solid.left
                    else:
                        self.rect.left = solid.right
                    self.position.x = self.rect.x

        if dy:
            self.position.y += dy
            self.rect.y = round(self.position.y)
            for solid in solid_rects:
                if self.rect.colliderect(solid):
                    if dy > 0:
                        self.rect.bottom = solid.top
                    else:
                        self.rect.top = solid.bottom
                    self.position.y = self.rect.y

    def draw(self, surface):
        pygame.draw.circle(surface, PLAYER_COLOR, self.rect.center, 10)
        end_x = self.rect.centerx + math.cos(math.radians(self.angle)) * 18
        end_y = self.rect.centery - math.sin(math.radians(self.angle)) * 18
        pygame.draw.line(surface, ACCENT_COLOR, self.rect.center, (end_x, end_y), 2)

#___________________________________________MAP FILE LOAD_______________________________________________________________

def load_store_map(filename, inventory_by_position):
    #map load
    with open(filename, "r", encoding="utf-8") as map_file:
        lines = [line.rstrip("\r\n") for line in map_file]

    if not lines:
        raise ValueError("The store map is empty.")

    widths = {len(line) for line in lines}
    if len(widths) != 1:
        raise ValueError("Every store-map row must have the same width.")

    expected_width = SCREEN_WIDTH // TILE_SIZE
    expected_height = MAP_HEIGHT // TILE_SIZE
    if len(lines) != expected_height or widths.pop() != expected_width:
        raise ValueError(f"Store map must be exactly {expected_width} columns by {expected_height} rows.")

    walls = []
    shelves = []
    catalogue = None
    cash_register = None
    employee_terminal = None
    storage_depot = None
    player_spawn = None
    for grid_y, line in enumerate(lines):
        for grid_x, tile in enumerate(line):
            tile_rect = pygame.Rect(grid_x * TILE_SIZE, grid_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            if tile == "#":
                walls.append(tile_rect)
            elif tile == "S":
                database_shelf = inventory_by_position.get((grid_x, grid_y))
                if database_shelf is None:
                    raise ValueError(
                        f"Shelf at row {grid_y + 1}, column {grid_x + 1} is missing from MySQL."
                    )
                shelf_id, item_set = database_shelf
                shelves.append(Shelf(shelf_id, grid_x, grid_y, item_set))
            elif tile == "C":
                if catalogue is not None:
                    raise ValueError("The store map can contain only one product catalogue (C).")
                catalogue = ProductCatalogue(grid_x, grid_y)
            elif tile == "R":
                if cash_register is not None:
                    raise ValueError("The store map can contain only one cash register (R).")
                cash_register = CashRegister(grid_x, grid_y)
            elif tile == "E":
                if employee_terminal is not None:
                    raise ValueError("The store map can contain only one employee terminal (E).")
                employee_terminal = EmployeeTerminal(grid_x, grid_y)
            elif tile == "B":
                if storage_depot is not None:
                    raise ValueError("The store map can contain only one storage depot (B).")
                storage_depot = StorageDepot(grid_x, grid_y)
            elif tile == "P":
                if player_spawn is not None:
                    raise ValueError("The store map can contain only one player spawn (P).")
                player_spawn = (tile_rect.x + 8, tile_rect.y + 8)
            elif tile != ".":
                raise ValueError(f"Unsupported map symbol {tile!r} at row {grid_y + 1}.")

    if player_spawn is None:
        raise ValueError("The store map needs one player spawn (P).")
    if catalogue is None:
        raise ValueError("The store map needs one product catalogue (C).")
    if cash_register is None:
        raise ValueError("The store map needs one cash register (R).")
    if employee_terminal is None:
        raise ValueError("The store map needs one employee terminal (E).")

    return walls, shelves, catalogue, cash_register, employee_terminal, storage_depot, player_spawn

#_________________________________________SHELF INTERACTION CHECKS_________________________________________________________________

def distance_to_rect(point, rect):
    #shortest distance from a point to a rectangle
    nearest_x = max(rect.left, min(point[0], rect.right))
    nearest_y = max(rect.top, min(point[1], rect.bottom))
    return math.hypot(point[0] - nearest_x, point[1] - nearest_y)


def get_targeted_object(player, shelves, catalogue, cash_register, employee_terminal, storage_depot=None):
    #store objects are usable only when close to the manager and mouse aimed
    mouse_position = pygame.mouse.get_pos()
    interactive_items = [*shelves, catalogue, cash_register, employee_terminal]
    if storage_depot:
        interactive_items.append(storage_depot)
    candidates = [
        item
        for item in interactive_items
        if item.rect.collidepoint(mouse_position)
        and distance_to_rect(player.rect.center, item.rect) <= INTERACTION_DISTANCE
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda item: distance_to_rect(player.rect.center, item.rect))

#________________________________________SHELF MENU__________________________________________________________________

def shelf_menu_layout(shelf, selected_item_id, first_item, product_catalogue=None):
    visible_items = shelf.get_visible_items(product_catalogue)
    row_height = 44
    visible_rows = min(8, max(1, len(visible_items)))
    panel_height = 195 + visible_rows * row_height
    panel_width = 820
    panel = pygame.Rect((SCREEN_WIDTH - panel_width) // 2, max(14, (MAP_HEIGHT - panel_height) // 2), panel_width, panel_height)
    header_y = panel.y + 68
    rows = []
    for row_index, item in enumerate(visible_items[first_item:first_item + visible_rows]):
        row_rect = pygame.Rect(panel.x + 20, header_y + 39 + row_index * row_height, 725, 38)
        delete_rect = pygame.Rect(panel.right - 60, row_rect.y + 2, 28, 32)
        rows.append((item, row_rect, delete_rect))

    cat_prev_button = pygame.Rect(panel.x + 395, panel.y + 19, 30, 32)
    cat_box_rect = pygame.Rect(panel.x + 430, panel.y + 19, 195, 32)
    cat_next_button = pygame.Rect(panel.x + 630, panel.y + 19, 30, 32)

    action_y = panel.bottom - 78
    add_button = pygame.Rect(panel.x + 24, action_y, 42, 36)
    edit_button = None
    sell_down_button = None
    sell_qty_box = None
    sell_up_button = None
    sell_button = None
    if selected_item_id is not None:
        edit_button = pygame.Rect(panel.x + 76, action_y, 84, 36)
        sell_down_button = pygame.Rect(panel.x + 184, action_y, 34, 36)
        sell_qty_box = pygame.Rect(panel.x + 223, action_y, 64, 36)
        sell_up_button = pygame.Rect(panel.x + 292, action_y, 34, 36)
        sell_button = pygame.Rect(panel.x + 334, action_y, 84, 36)

    scroll_track = None
    scroll_thumb = None
    if len(visible_items) > visible_rows:
        scroll_track = pygame.Rect(panel.right - 18, header_y + 42, 8, visible_rows * row_height - 8)
        scroll_thumb = make_scroll_thumb(scroll_track, len(visible_items), visible_rows, first_item)
    return (
        panel, header_y, rows, add_button, edit_button,
        cat_prev_button, cat_box_rect, cat_next_button,
        sell_down_button, sell_qty_box, sell_up_button, sell_button,
        visible_rows, scroll_track, scroll_thumb,
    )


def make_scroll_thumb(track, item_count, visible_rows, first_item):
    max_start = max(1, item_count - visible_rows)
    thumb_height = max(28, round(track.height * visible_rows / item_count))
    travel = track.height - thumb_height
    thumb_y = track.y + round(travel * first_item / max_start)
    return pygame.Rect(track.x, thumb_y, track.width, thumb_height)


def draw_button(surface, rect, label, color, font, hover_color=None, border_radius=7):
    mouse_pos = pygame.mouse.get_pos()
    is_hovered = rect.collidepoint(mouse_pos)
    effective_hover = hover_color or brighten_color(color, 25)
    btn_color = effective_hover if is_hovered else color

    # Subtle 1px lift on hover
    draw_rect = rect.move(0, -1) if is_hovered else rect

    if is_hovered:
        shadow_rect = rect.move(0, 2)
        pygame.draw.rect(surface, (0, 0, 0, 30), shadow_rect, border_radius=border_radius)

    pygame.draw.rect(surface, btn_color, draw_rect, border_radius=border_radius)
    label_surface = font.render(label, True, (255, 255, 255))
    surface.blit(label_surface, label_surface.get_rect(center=draw_rect.center))


def draw_shelf_menu(
    surface,
    fonts,
    shelf,
    selected_item_id,
    first_item,
    message,
    product_catalogue=None,
    sell_qty_text="1",
    sell_active_input=False,
    cursor_visible=True,
):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((*OVERLAY_COLOR, 130))
    surface.blit(overlay, (0, 0))

    visible_items = shelf.get_visible_items(product_catalogue)
    (
        panel, header_y, rows, add_button, edit_button,
        cat_prev_button, cat_box_rect, cat_next_button,
        sell_down_button, sell_qty_box, sell_up_button, sell_button,
        visible_rows, scroll_track, scroll_thumb,
    ) = shelf_menu_layout(shelf, selected_item_id, first_item, product_catalogue)

    theme = get_shelf_theme(shelf.category)
    edge_col = theme["edge"]
    btn_col = theme["button"]
    sel_col = theme["selected"]

    # Soft drop shadow
    shadow = get_drop_shadow(panel.width, panel.height, radius=10, blur=14, alpha=50, offset_y=5)
    surface.blit(shadow, (panel.x - 14, panel.y - 9))

    pygame.draw.rect(surface, PANEL_BG, panel, border_radius=10)
    pygame.draw.rect(surface, edge_col, panel, 3, border_radius=10)

    title = fonts["title"].render(shelf.display_name, True, TEXT_COLOR)
    surface.blit(title, (panel.x + 26, panel.y + 17))

    # Category Stepper
    draw_button(surface, cat_prev_button, "<", btn_col, fonts["body"])
    draw_input_box(surface, cat_box_rect, shelf.category, False, fonts["small"], edge_col)
    draw_button(surface, cat_next_button, ">", btn_col, fonts["body"])

    # Capacity Indicator
    total_qty = shelf.get_total_quantity(product_catalogue)
    cap_color = LOSS_RED if total_qty >= MAX_SHELF_CAPACITY else ((215, 130, 25) if total_qty >= 40 else PROFIT_GREEN)
    cap_surf = fonts["header"].render(f"Cap: {total_qty}/{MAX_SHELF_CAPACITY}", True, cap_color)
    surface.blit(cap_surf, (panel.right - cap_surf.get_width() - 24, panel.y + 25))

    columns = [("Item ID", 30), ("Item name", 125), ("Quantity", 495), ("Price", 615)]
    pygame.draw.line(surface, edge_col, (panel.x + 25, header_y + 28), (panel.right - 25, header_y + 28), 2)
    for heading, offset in columns:
        header = fonts["body"].render(heading, True, edge_col)
        surface.blit(header, (panel.x + offset, header_y))

    dividers = [115, 480, 600, 740]
    table_bottom = header_y + 36 + visible_rows * 44
    for div_x in dividers:
        pygame.draw.line(surface, (228, 220, 210), (panel.x + div_x, header_y + 4), (panel.x + div_x, table_bottom), 1)

    mouse_pos = pygame.mouse.get_pos()
    if not rows:
        empty_msg = (
            f"No {shelf.category} products on this shelf yet. Click '+' to stock items."
            if shelf.category != "General"
            else "This shelf is empty. Click '+' to stock items."
        )
        empty_surf = fonts["body"].render(empty_msg, True, TEXT_MUTED)
        surface.blit(empty_surf, (panel.x + 30, header_y + 46))
    else:
        for item, row_rect, delete_rect in rows:
            item_id, item_name, quantity, price = item
            if item_id == selected_item_id:
                pygame.draw.rect(surface, sel_col, row_rect, border_radius=6)
            elif row_rect.collidepoint(mouse_pos):
                pygame.draw.rect(surface, (248, 244, 238), row_rect, border_radius=6)

            values = (str(item_id), item_name, str(quantity), f"Rs. {price:.2f}")
            for value, (_, offset) in zip(values, columns):
                text = fonts["body"].render(value, True, TEXT_COLOR)
                surface.blit(text, (panel.x + offset, row_rect.y + 7))
            draw_button(surface, delete_rect, "X", DELETE_RED, fonts["body"], hover_color=DELETE_RED_HOVER)

    draw_button(surface, add_button, "+", btn_col, fonts["body"])
    if edit_button:
        draw_button(surface, edit_button, "Edit", edge_col, fonts["body"])
        pygame.draw.line(
            surface,
            (215, 210, 200),
            (panel.x + 172, edit_button.y + 4),
            (panel.x + 172, edit_button.bottom - 4),
            2,
        )
        draw_button(surface, sell_down_button, "-", btn_col, fonts["body"])
        draw_input_box(
            surface,
            sell_qty_box,
            sell_qty_text,
            sell_active_input,
            fonts["body"],
            edge_col,
            cursor_visible=cursor_visible,
        )
        draw_button(surface, sell_up_button, "+", btn_col, fonts["body"])
        draw_button(surface, sell_button, "Sell", PROFIT_GREEN, fonts["body"])

        sel_item = next((it for it in visible_items if it[0] == selected_item_id), None)
        if sel_item:
            try:
                s_qty = max(0, int(sell_qty_text or "0"))
            except ValueError:
                s_qty = 0
            profit_val = sel_item[3] * s_qty
            profit_surf = fonts["body"].render(f"Profit: +Rs. {profit_val:,.2f}", True, PROFIT_GREEN)
            surface.blit(profit_surf, (sell_button.right + 14, sell_button.y + 7))

    if message:
        msg_col = PROFIT_GREEN if message.startswith(("Sold ", "Updated ", "Added ", "Category ")) else LOSS_RED
        message_text = fonts["small"].render(message, True, msg_col)
        surface.blit(message_text, (panel.x + 24, panel.bottom - 34))
    else:
        hint = fonts["small"].render("Click a row to select or sell  |  < > to set shelf category  |  E or Esc to close", True, TEXT_MUTED)
        surface.blit(hint, (panel.x + 24, panel.bottom - 34))

    if len(visible_items) > visible_rows:
        page_text = fonts["small"].render(
            f"Items {first_item + 1}-{min(first_item + visible_rows, len(visible_items))} of {len(visible_items)}",
            True,
            TEXT_MUTED,
        )
        surface.blit(page_text, (panel.right - page_text.get_width() - 26, panel.bottom - 34))
        pygame.draw.rect(surface, SCROLL_TRACK_COLOR, scroll_track, border_radius=4)
        pygame.draw.rect(surface, edge_col, scroll_thumb, border_radius=4)


def item_editor_layout():
    panel = pygame.Rect(270, 110, 460, 380)
    product_button = pygame.Rect(panel.x + 160, panel.y + 82, 260, 36)
    quantity_y = panel.y + 142
    return (
        panel,
        product_button,
        pygame.Rect(panel.x + 165, quantity_y, 40, 36),
        pygame.Rect(panel.x + 335, quantity_y, 40, 36),
        pygame.Rect(panel.x + 220, quantity_y, 100, 36),
        pygame.Rect(panel.x + 165, quantity_y + 61, 40, 36),
        pygame.Rect(panel.x + 335, quantity_y + 61, 40, 36),
        pygame.Rect(panel.x + 220, quantity_y + 61, 100, 36),
        pygame.Rect(panel.x + 82, panel.bottom - 55, 120, 36),
        pygame.Rect(panel.x + 238, panel.bottom - 55, 120, 36),
    )


def draw_input_box(
    surface,
    rect,
    text,
    active,
    font,
    outline_color=ACCENT_COLOR,
    cursor_visible=True,
    placeholder="",
):
    pygame.draw.rect(surface, INPUT_BG, rect, border_radius=6)
    border_color = outline_color if active else INPUT_BORDER_DEFAULT
    border_w = 2 if active else 1
    pygame.draw.rect(surface, border_color, rect, border_w, border_radius=6)

    display_text = text if (text or active) else placeholder
    text_color = TEXT_COLOR if text else TEXT_MUTED
    value = font.render(display_text, True, text_color)
    val_rect = value.get_rect(center=rect.center)
    surface.blit(value, val_rect)

    if active and cursor_visible:
        cursor_x = val_rect.right + 2 if text else rect.centerx
        cursor_y1 = rect.centery - font.get_height() // 2 + 3
        cursor_y2 = rect.centery + font.get_height() // 2 - 3
        pygame.draw.line(surface, outline_color, (cursor_x, cursor_y1), (cursor_x, cursor_y2), 2)


def product_picker_layout(available_products, first_item):
    panel = pygame.Rect(185, 65, 630, 505)
    visible_rows = min(8, len(available_products))
    rows = [
        (item, pygame.Rect(panel.x + 24, panel.y + 92 + index * 43, 550, 38))
        for index, item in enumerate(available_products[first_item:first_item + visible_rows])
    ]
    track = pygame.Rect(panel.right - 27, panel.y + 92, 8, visible_rows * 43 - 5)
    thumb = make_scroll_thumb(track, len(available_products), visible_rows, first_item)
    cancel = pygame.Rect(panel.right - 140, panel.bottom - 48, 110, 34)
    return panel, rows, track, thumb, cancel, visible_rows


def draw_product_picker(surface, fonts, available_products, first_item):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((*OVERLAY_COLOR, 145))
    surface.blit(overlay, (0, 0))
    panel, rows, track, thumb, cancel, visible_rows = product_picker_layout(available_products, first_item)

    # Soft drop shadow
    shadow = get_drop_shadow(panel.width, panel.height, radius=10, blur=14, alpha=50, offset_y=5)
    surface.blit(shadow, (panel.x - 14, panel.y - 9))

    pygame.draw.rect(surface, PANEL_BG, panel, border_radius=10)
    pygame.draw.rect(surface, CATALOGUE_EDGE_COLOR, panel, 3, border_radius=10)
    title = fonts["title"].render("Choose Product", True, TEXT_COLOR)
    surface.blit(title, (panel.x + 28, panel.y + 22))
    surface.blit(fonts["small"].render("Item ID", True, CATALOGUE_EDGE_COLOR), (panel.x + 28, panel.y + 68))
    surface.blit(fonts["small"].render("Product name", True, CATALOGUE_EDGE_COLOR), (panel.x + 145, panel.y + 68))
    surface.blit(fonts["small"].render("Price", True, CATALOGUE_EDGE_COLOR), (panel.right - 115, panel.y + 68))

    mouse_pos = pygame.mouse.get_pos()
    for item, row in rows:
        item_id, item_name, price = item[0], item[1], item[2]
        row_bg = (226, 238, 246) if row.collidepoint(mouse_pos) else (239, 246, 250)
        pygame.draw.rect(surface, row_bg, row, border_radius=5)
        label = fonts["body"].render(f"{item_id:<5}  {item_name}", True, TEXT_COLOR)
        surface.blit(label, (row.x + 12, row.y + 7))
        price_label = fonts["body"].render(f"Rs. {price:.2f}", True, TEXT_COLOR)
        surface.blit(price_label, (row.right - 115, row.y + 7))
    pygame.draw.rect(surface, SCROLL_TRACK_COLOR, track, border_radius=4)
    pygame.draw.rect(surface, CATALOGUE_EDGE_COLOR, thumb, border_radius=4)
    draw_button(surface, cancel, "Cancel", (130, 142, 152), fonts["body"])


def draw_item_editor(
    surface,
    fonts,
    item,
    quantity_text,
    price_text,
    add_mode,
    active_input,
    cursor_visible=True,
    message="",
    shelf=None,
):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((*OVERLAY_COLOR, 130))
    surface.blit(overlay, (0, 0))
    (
        panel, product_button, quantity_down, quantity_up, quantity_box,
        price_down, price_up, price_box, save_button, cancel_button,
    ) = item_editor_layout()

    theme = get_shelf_theme(shelf.category if shelf else "General")
    edge_col = theme["edge"]
    btn_col = theme["button"]

    # Soft drop shadow
    shadow = get_drop_shadow(panel.width, panel.height, radius=10, blur=14, alpha=50, offset_y=5)
    surface.blit(shadow, (panel.x - 14, panel.y - 9))

    pygame.draw.rect(surface, PANEL_BG, panel, border_radius=10)
    pygame.draw.rect(surface, edge_col, panel, 3, border_radius=10)
    title = fonts["title"].render("Add Shelf Item" if add_mode else "Edit Shelf Item", True, TEXT_COLOR)
    surface.blit(title, (panel.x + 28, panel.y + 22))
    surface.blit(fonts["body"].render("Product", True, TEXT_COLOR), (panel.x + 35, panel.y + 89))
    product_text = "Choose a product" if item is None else f"{item[0]} - {item[1]}"
    draw_input_box(surface, product_button, product_text, False, fonts["small"], edge_col)
    arrow = fonts["small"].render("v", True, TEXT_COLOR)
    surface.blit(arrow, (product_button.right - 18, product_button.y + 10))
    surface.blit(fonts["body"].render("Quantity", True, TEXT_COLOR), (panel.x + 35, quantity_box.y + 7))
    surface.blit(fonts["body"].render("Price", True, TEXT_COLOR), (panel.x + 35, price_box.y + 7))
    draw_button(surface, quantity_down, "-", btn_col, fonts["body"])
    draw_button(surface, quantity_up, "+", btn_col, fonts["body"])
    draw_button(surface, price_down, "-", btn_col, fonts["body"])
    draw_button(surface, price_up, "+", btn_col, fonts["body"])
    draw_input_box(
        surface, quantity_box, quantity_text, active_input == "quantity",
        fonts["body"], edge_col, cursor_visible=cursor_visible
    )
    draw_input_box(
        surface, price_box, price_text, active_input == "price",
        fonts["body"], edge_col, cursor_visible=cursor_visible
    )
    if message:
        err_surf = fonts["small"].render(message, True, LOSS_RED)
        surface.blit(err_surf, (panel.x + 28, panel.bottom - 90))
    draw_button(surface, save_button, "Save", edge_col, fonts["body"])
    draw_button(surface, cancel_button, "Cancel", (130, 142, 152), fonts["body"])


def build_catalogue_elements(products, expanded_categories):
    grouped = {cat: [] for cat in CATEGORIES}
    for item in products:
        cat = item[5] if len(item) > 5 else "General"
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(item)
    for cat in grouped:
        grouped[cat].sort(key=lambda x: x[0])

    doc_elements = []
    current_y = 0
    for cat, items in grouped.items():
        is_expanded = cat in expanded_categories
        header_rect = pygame.Rect(0, current_y, 775, 42)
        doc_elements.append(("category_header", header_rect, (cat, is_expanded, len(items))))
        current_y += 48

        if is_expanded:
            table_hdr_rect = pygame.Rect(10, current_y, 765, 26)
            doc_elements.append(("table_header", table_hdr_rect, cat))
            current_y += 30

            for item in items:
                row_rect = pygame.Rect(10, current_y, 715, 36)
                del_rect = pygame.Rect(738, current_y + 3, 26, 30)
                doc_elements.append(("product_row", row_rect, (item, del_rect)))
                current_y += 40
            current_y += 6
    return doc_elements, current_y


def draw_chevron(surface, center_x, center_y, is_expanded, color):
    if is_expanded:
        pts = [(center_x - 5, center_y - 3), (center_x + 5, center_y - 3), (center_x, center_y + 4)]
    else:
        pts = [(center_x - 3, center_y - 5), (center_x - 3, center_y + 5), (center_x + 4, center_y)]
    pygame.draw.polygon(surface, color, pts)


def catalogue_menu_layout(products, selected_item_id, expanded_categories, scroll_y):
    panel = pygame.Rect((SCREEN_WIDTH - 840) // 2, 32, 840, 536)
    viewport = pygame.Rect(panel.x + 24, panel.y + 70, 780, 396)

    doc_elements, total_content_height = build_catalogue_elements(products, expanded_categories)
    max_scroll = max(0, total_content_height - viewport.height)
    clamped_scroll = max(0, min(scroll_y, max_scroll))

    add_button = pygame.Rect(panel.x + 28, panel.bottom - 58, 42, 36)
    edit_button = None
    if selected_item_id is not None:
        edit_button = pygame.Rect(panel.x + 82, panel.bottom - 58, 100, 36)

    scroll_track = None
    scroll_thumb = None
    if total_content_height > viewport.height:
        scroll_track = pygame.Rect(panel.right - 20, viewport.top, 8, viewport.height)
        scroll_thumb = make_scroll_thumb(scroll_track, total_content_height, viewport.height, clamped_scroll)

    return (
        panel, viewport, doc_elements, total_content_height, max_scroll, clamped_scroll,
        add_button, edit_button, scroll_track, scroll_thumb,
    )


def draw_catalogue_menu(surface, fonts, products, selected_item_id, expanded_categories, scroll_y, message):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((*OVERLAY_COLOR, 130))
    surface.blit(overlay, (0, 0))

    (
        panel, viewport, doc_elements, total_content_height, max_scroll, clamped_scroll,
        add_button, edit_button, scroll_track, scroll_thumb,
    ) = catalogue_menu_layout(products, selected_item_id, expanded_categories, scroll_y)

    # Soft drop shadow
    shadow = get_drop_shadow(panel.width, panel.height, radius=10, blur=14, alpha=50, offset_y=5)
    surface.blit(shadow, (panel.x - 14, panel.y - 9))

    pygame.draw.rect(surface, PANEL_BG, panel, border_radius=10)
    pygame.draw.rect(surface, CATALOGUE_EDGE_COLOR, panel, 3, border_radius=10)

    title = fonts["title"].render("Store Product Catalogue", True, TEXT_COLOR)
    surface.blit(title, (panel.x + 28, panel.y + 18))

    columns = [("Item ID", 20), ("Item name", 105), ("Price", 465), ("Starting Qty", 595)]
    dividers = [95, 455, 585, 715]

    mouse_pos = pygame.mouse.get_pos()
    surface.set_clip(viewport)

    for elem_type, rect, data in doc_elements:
        screen_rect = rect.move(viewport.x, viewport.y - clamped_scroll)
        if screen_rect.bottom < viewport.top or screen_rect.top > viewport.bottom:
            continue

        if elem_type == "category_header":
            cat, is_expanded, count = data
            is_hovered = screen_rect.collidepoint(mouse_pos)
            banner_bg = (230, 242, 252) if is_hovered else ((238, 246, 252) if is_expanded else (246, 249, 252))
            pygame.draw.rect(surface, banner_bg, screen_rect, border_radius=6)
            pygame.draw.rect(surface, (200, 220, 235), screen_rect, 1, border_radius=6)

            draw_chevron(surface, screen_rect.x + 20, screen_rect.centery, is_expanded, CATALOGUE_EDGE_COLOR)

            cat_font = fonts.get("header") or fonts["body"]
            cat_surf = cat_font.render(cat.upper(), True, TEXT_COLOR)
            surface.blit(cat_surf, (screen_rect.x + 36, screen_rect.y + 11))

            badge_surf = fonts["small"].render(f"({count} items)", True, TEXT_MUTED)
            surface.blit(badge_surf, (screen_rect.x + 46 + cat_surf.get_width(), screen_rect.y + 13))

        elif elem_type == "table_header":
            for heading, offset in columns:
                hdr = fonts["small"].render(heading, True, CATALOGUE_EDGE_COLOR)
                surface.blit(hdr, (screen_rect.x + offset, screen_rect.y + 6))
            pygame.draw.line(surface, CATALOGUE_EDGE_COLOR, (screen_rect.x + 10, screen_rect.bottom - 2), (screen_rect.right - 10, screen_rect.bottom - 2), 1)

        elif elem_type == "product_row":
            item, del_rect = data
            item_id = item[0]
            item_name = item[1]
            price = item[2]
            min_q = item[3]
            max_q = item[4]

            if item_id == selected_item_id:
                pygame.draw.rect(surface, CATALOGUE_SELECTED_COLOR, screen_rect, border_radius=5)
            elif screen_rect.collidepoint(mouse_pos):
                pygame.draw.rect(surface, (244, 248, 254), screen_rect, border_radius=5)
            else:
                pygame.draw.rect(surface, (252, 253, 255), screen_rect, border_radius=5)

            for div_x in dividers:
                pygame.draw.line(surface, (230, 235, 242), (screen_rect.x + div_x, screen_rect.y + 2), (screen_rect.x + div_x, screen_rect.bottom - 2), 1)

            values = (str(item_id), item_name, f"Rs. {price:.2f}", f"{min_q}-{max_q}")
            for val, (_, offset) in zip(values, columns):
                txt = fonts["body"].render(val, True, TEXT_COLOR)
                surface.blit(txt, (screen_rect.x + offset, screen_rect.y + 7))

            screen_del = del_rect.move(viewport.x, viewport.y - clamped_scroll)
            draw_button(surface, screen_del, "X", DELETE_RED, fonts["small"], hover_color=DELETE_RED_HOVER)

    surface.set_clip(None)

    if scroll_track:
        pygame.draw.rect(surface, SCROLL_TRACK_COLOR, scroll_track, border_radius=4)
        pygame.draw.rect(surface, CATALOGUE_EDGE_COLOR, scroll_thumb, border_radius=4)

    draw_button(surface, add_button, "+", CATALOGUE_BUTTON_COLOR, fonts["body"])
    if edit_button:
        draw_button(surface, edit_button, "Edit", CATALOGUE_EDGE_COLOR, fonts["body"])

    if message:
        hint = fonts["small"].render(message, True, LOSS_RED)
    else:
        hint = fonts["small"].render(
            f"{len(products)} products across {len(CATEGORIES)} categories  |  Click category to expand/collapse  |  Esc: close",
            True,
            TEXT_MUTED,
        )
    surface.blit(hint, (panel.x + 200, panel.bottom - 48))


def product_editor_layout():
    panel = pygame.Rect((SCREEN_WIDTH - 500) // 2, 40, 500, 520)
    field_x = panel.x + 165
    field_width = 285
    start_y = panel.y + 78

    boxes = {
        "item_id": pygame.Rect(field_x, start_y, field_width, 36),
        "item_name": pygame.Rect(field_x, start_y + 54, field_width, 36),
        "price": pygame.Rect(field_x, start_y + 162, field_width, 36),
        "minimum_quantity": pygame.Rect(field_x + 55, start_y + 216, 120, 36),
        "maximum_quantity": pygame.Rect(field_x + 55, start_y + 270, 120, 36),
    }

    # Category stepper
    cat_y = start_y + 108
    cat_prev = pygame.Rect(field_x, cat_y, 40, 36)
    cat_box = pygame.Rect(field_x + 46, cat_y, field_width - 92, 36)
    cat_next = pygame.Rect(field_x + field_width - 40, cat_y, 40, 36)

    min_down = pygame.Rect(field_x + 5, boxes["minimum_quantity"].y, 42, 36)
    min_up = pygame.Rect(field_x + 185, boxes["minimum_quantity"].y, 42, 36)
    max_down = pygame.Rect(field_x + 5, boxes["maximum_quantity"].y, 42, 36)
    max_up = pygame.Rect(field_x + 185, boxes["maximum_quantity"].y, 42, 36)

    save_button = pygame.Rect(panel.x + 85, panel.bottom - 54, 130, 36)
    cancel_button = pygame.Rect(panel.x + 285, panel.bottom - 54, 130, 36)
    return (
        panel, boxes, cat_prev, cat_box, cat_next,
        min_down, min_up, max_down, max_up,
        save_button, cancel_button,
    )


def draw_product_editor(surface, fonts, fields, active_input, add_mode, message, cursor_visible=True):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((*OVERLAY_COLOR, 135))
    surface.blit(overlay, (0, 0))
    (
        panel, boxes, cat_prev, cat_box, cat_next,
        minimum_down, minimum_up, maximum_down, maximum_up,
        save_button, cancel_button,
    ) = product_editor_layout()

    # Soft drop shadow
    shadow = get_drop_shadow(panel.width, panel.height, radius=10, blur=14, alpha=50, offset_y=5)
    surface.blit(shadow, (panel.x - 14, panel.y - 9))

    pygame.draw.rect(surface, PANEL_BG, panel, border_radius=10)
    pygame.draw.rect(surface, CATALOGUE_EDGE_COLOR, panel, 3, border_radius=10)
    title = fonts["title"].render("Add Product" if add_mode else "Edit Product", True, TEXT_COLOR)
    surface.blit(title, (panel.x + 28, panel.y + 20))

    labels = (
        ("Item ID", "item_id"),
        ("Product name", "item_name"),
        ("Retail price", "price"),
        ("Min quantity", "minimum_quantity"),
        ("Max quantity", "maximum_quantity"),
    )
    for label, key in labels:
        surface.blit(
            fonts["small"].render(label, True, TEXT_COLOR),
            (panel.x + 32, boxes[key].y + 9),
        )
        draw_input_box(
            surface, boxes[key], fields[key], active_input == key, fonts["body"],
            CATALOGUE_EDGE_COLOR, cursor_visible=cursor_visible
        )

    # Category stepper row
    surface.blit(fonts["small"].render("Category", True, TEXT_COLOR), (panel.x + 32, cat_box.y + 9))
    draw_button(surface, cat_prev, "<", CATALOGUE_BUTTON_COLOR, fonts["body"])
    pygame.draw.rect(surface, INPUT_BG, cat_box, border_radius=6)
    pygame.draw.rect(surface, CATALOGUE_EDGE_COLOR, cat_box, 2, border_radius=6)
    cat_text = fields.get("category", CATEGORIES[0])
    cat_lbl = fonts["small"].render(cat_text, True, TEXT_COLOR)
    surface.blit(cat_lbl, cat_lbl.get_rect(center=cat_box.center))
    draw_button(surface, cat_next, ">", CATALOGUE_BUTTON_COLOR, fonts["body"])

    for button, label in (
        (minimum_down, "-"), (minimum_up, "+"),
        (maximum_down, "-"), (maximum_up, "+"),
    ):
        draw_button(surface, button, label, CATALOGUE_BUTTON_COLOR, fonts["body"])
    draw_button(surface, save_button, "Save", CATALOGUE_EDGE_COLOR, fonts["body"])
    draw_button(surface, cancel_button, "Cancel", (130, 142, 152), fonts["body"])
    if message:
        warning = fonts["small"].render(message, True, LOSS_RED)
        surface.blit(warning, (panel.x + 30, panel.bottom - 85))


def finance_menu_layout(history, first_item):
    panel = pygame.Rect(130, 32, 740, 536)
    balance_box = pygame.Rect(panel.x + 148, panel.y + 106, 160, 36)
    update_button = pygame.Rect(panel.x + 318, panel.y + 106, 96, 36)
    header_y = panel.y + 154
    visible_rows = min(7, max(1, len(history)))
    rows = []
    for row_index, entry in enumerate(history[first_item:first_item + visible_rows]):
        row_rect = pygame.Rect(panel.x + 22, header_y + 36 + row_index * 39, 658, 35)
        rows.append((entry, row_rect))

    scroll_track = None
    scroll_thumb = None
    if len(history) > visible_rows:
        scroll_track = pygame.Rect(panel.right - 27, header_y + 38, 8, visible_rows * 39 - 5)
        scroll_thumb = make_scroll_thumb(scroll_track, len(history), visible_rows, first_item)
    return (
        panel, balance_box, update_button, header_y, rows,
        visible_rows, scroll_track, scroll_thumb,
    )


def draw_finance_menu(
    surface, fonts, current_balance, balance_text, history, first_item, active_input, message, cursor_visible=True
):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((*OVERLAY_COLOR, 130))
    surface.blit(overlay, (0, 0))

    (
        panel, balance_box, update_button, header_y, rows,
        visible_rows, scroll_track, scroll_thumb,
    ) = finance_menu_layout(history, first_item)

    # Soft drop shadow
    shadow = get_drop_shadow(panel.width, panel.height, radius=10, blur=14, alpha=50, offset_y=5)
    surface.blit(shadow, (panel.x - 14, panel.y - 9))

    pygame.draw.rect(surface, PANEL_BG, panel, border_radius=10)
    pygame.draw.rect(surface, REGISTER_EDGE_COLOR, panel, 3, border_radius=10)

    title = fonts["title"].render("Cash Register & Finance", True, TEXT_COLOR)
    surface.blit(title, (panel.x + 28, panel.y + 18))

    current_label = fonts["body"].render("Current Balance:", True, TEXT_COLOR)
    surface.blit(current_label, (panel.x + 28, panel.y + 66))

    value_surface = fonts["balance"].render(
        f"Rs. {current_balance:,.2f}", True, REGISTER_EDGE_COLOR
    )
    surface.blit(value_surface, value_surface.get_rect(center=(panel.centerx, panel.y + 77)))

    set_label = fonts["body"].render("Set Balance:", True, TEXT_COLOR)
    surface.blit(set_label, (panel.x + 28, panel.y + 111))

    draw_input_box(
        surface,
        balance_box,
        balance_text,
        active_input,
        fonts["body"],
        REGISTER_EDGE_COLOR,
        cursor_visible=cursor_visible,
    )
    draw_button(surface, update_button, "Update", REGISTER_BUTTON_COLOR, fonts["body"])

    if message:
        if message.startswith("Profit"):
            msg_color = PROFIT_GREEN
        elif "unchanged" in message:
            msg_color = TEXT_MUTED
        else:
            msg_color = LOSS_RED
        message_surface = fonts["small"].render(message, True, msg_color)
        surface.blit(message_surface, (panel.x + 430, panel.y + 114))

    columns = [("ID", 30), ("Change", 100), ("Amount", 250), ("New Balance", 460)]
    pygame.draw.line(
        surface,
        REGISTER_EDGE_COLOR,
        (panel.x + 25, header_y + 26),
        (panel.right - 25, header_y + 26),
        2,
    )
    for heading, offset in columns:
        header = fonts["body"].render(heading, True, REGISTER_EDGE_COLOR)
        surface.blit(header, (panel.x + offset, header_y))

    mouse_pos = pygame.mouse.get_pos()
    if not history:
        empty_text = fonts["body"].render("No finance transactions recorded yet.", True, TEXT_MUTED)
        surface.blit(empty_text, empty_text.get_rect(center=(panel.centerx, header_y + 80)))
    else:
        for entry, row_rect in rows:
            history_id, change_type, amount, new_balance, recorded_at = entry
            amount_sign = "+" if change_type == "Profit" else "-"
            values = (
                str(history_id),
                change_type,
                f"{amount_sign}Rs. {amount:,.2f}",
                f"Rs. {new_balance:,.2f}",
            )

            # Subtle row hover
            if row_rect.collidepoint(mouse_pos):
                pygame.draw.rect(surface, (244, 250, 246), row_rect, border_radius=6)

            for value, (heading, offset) in zip(values, columns):
                if heading in ("Amount", "Change"):
                    val_color = PROFIT_GREEN if change_type == "Profit" else LOSS_RED
                else:
                    val_color = TEXT_COLOR
                text = fonts["body"].render(value, True, val_color)
                surface.blit(text, (panel.x + offset, row_rect.y + 6))

    if scroll_track:
        pygame.draw.rect(surface, SCROLL_TRACK_COLOR, scroll_track, border_radius=4)
        pygame.draw.rect(surface, REGISTER_EDGE_COLOR, scroll_thumb, border_radius=4)

    if history:
        last_item = min(first_item + visible_rows, len(history))
        page_label = f"Entries {first_item + 1}-{last_item} of {len(history)}"
    else:
        page_label = "No finance entries yet"
    page_text = fonts["body"].render(page_label, True, TEXT_MUTED)
    surface.blit(page_text, (panel.x + 28, panel.bottom - 54))

    hint = fonts["small"].render(
        "Click balance to edit  |  Enter or Update: save  |  E or Esc: close",
        True,
        TEXT_MUTED,
    )
    surface.blit(hint, (panel.x + 28, panel.bottom - 22))


#________________________________________EMPLOYEE MENU__________________________________________________________________

def employee_menu_layout(employees, selected_emp_id, first_item):
    panel = pygame.Rect(115, 24, 770, 552)
    header_y = panel.y + 104
    visible_rows = min(7, max(1, len(employees)))
    rows = []
    for row_index, emp in enumerate(employees[first_item:first_item + visible_rows]):
        row_rect = pygame.Rect(panel.x + 22, header_y + 38 + row_index * 42, 642, 38)
        delete_rect = pygame.Rect(panel.right - 78, row_rect.y + 2, 28, 32)
        rows.append((emp, row_rect, delete_rect))

    add_button = pygame.Rect(panel.x + 28, panel.bottom - 62, 120, 36)
    edit_button = None
    if selected_emp_id is not None:
        edit_button = pygame.Rect(panel.x + 160, panel.bottom - 62, 100, 36)

    scroll_track = None
    scroll_thumb = None
    if len(employees) > visible_rows:
        scroll_track = pygame.Rect(panel.right - 27, header_y + 38, 8, visible_rows * 42 - 4)
        scroll_thumb = make_scroll_thumb(scroll_track, len(employees), visible_rows, first_item)
    return (
        panel, header_y, rows, add_button, edit_button,
        visible_rows, scroll_track, scroll_thumb,
    )


def draw_employee_menu(surface, fonts, employees, selected_emp_id, first_item, message):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((*OVERLAY_COLOR, 130))
    surface.blit(overlay, (0, 0))

    (
        panel, header_y, rows, add_button, edit_button,
        visible_rows, scroll_track, scroll_thumb,
    ) = employee_menu_layout(employees, selected_emp_id, first_item)

    # Soft drop shadow
    shadow = get_drop_shadow(panel.width, panel.height, radius=10, blur=14, alpha=50, offset_y=5)
    surface.blit(shadow, (panel.x - 14, panel.y - 9))

    pygame.draw.rect(surface, PANEL_BG, panel, border_radius=10)
    pygame.draw.rect(surface, EMPLOYEE_EDGE_COLOR, panel, 3, border_radius=10)

    title = fonts["title"].render("Store Employee Register", True, TEXT_COLOR)
    surface.blit(title, (panel.x + 28, panel.y + 22))

    total_payroll = sum(emp[3] for emp in employees)
    stats_text = f"Active Staff: {len(employees)}   |   Total Monthly Payroll: Rs. {total_payroll:,.2f}"
    stats_rendered = fonts["small"].render(stats_text, True, EMPLOYEE_EDGE_COLOR)
    surface.blit(stats_rendered, (panel.x + 30, panel.y + 68))

    columns = [("Emp ID", 30), ("Staff Name", 140), ("Store Role", 370), ("Monthly Salary", 520)]
    pygame.draw.line(
        surface,
        EMPLOYEE_EDGE_COLOR,
        (panel.x + 25, header_y + 28),
        (panel.right - 25, header_y + 28),
        2,
    )
    for heading, offset in columns:
        header = fonts["body"].render(heading, True, EMPLOYEE_EDGE_COLOR)
        surface.blit(header, (panel.x + offset, header_y))

    mouse_pos = pygame.mouse.get_pos()
    for emp, row_rect, delete_rect in rows:
        emp_id, name, role, salary, hire_date = emp
        if emp_id == selected_emp_id:
            pygame.draw.rect(surface, EMPLOYEE_SELECTED_COLOR, row_rect, border_radius=6)
        elif row_rect.collidepoint(mouse_pos):
            pygame.draw.rect(surface, (246, 244, 252), row_rect, border_radius=6)

        values = (
            str(emp_id),
            name,
            role,
            f"Rs. {salary:,.2f}",
        )
        for value, (_, offset) in zip(values, columns):
            text = fonts["body"].render(value, True, TEXT_COLOR)
            surface.blit(text, (panel.x + offset, row_rect.y + 7))

        draw_button(surface, delete_rect, "X", DELETE_RED, fonts["body"], hover_color=DELETE_RED_HOVER)

    draw_button(surface, add_button, "+ Hire Staff", EMPLOYEE_BUTTON_COLOR, fonts["body"])
    if edit_button:
        draw_button(surface, edit_button, "Edit", EMPLOYEE_BUTTON_COLOR, fonts["body"])

    if scroll_track and scroll_thumb:
        pygame.draw.rect(surface, SCROLL_TRACK_COLOR, scroll_track, border_radius=4)
        pygame.draw.rect(surface, EMPLOYEE_EDGE_COLOR, scroll_thumb, border_radius=4)

    if message:
        msg_rendered = fonts["small"].render(message, True, LOSS_RED)
        surface.blit(msg_rendered, (panel.x + 280, panel.bottom - 55))

    hint = fonts["small"].render(
        "Click a staff member to select • Click + Hire Staff to recruit • Press E or Esc to return",
        True,
        TEXT_MUTED,
    )
    surface.blit(hint, (panel.x + 28, panel.bottom - 22))


def employee_editor_layout():
    panel = pygame.Rect(250, 48, 500, 505)
    field_x = panel.x + 175
    field_width = 265
    start_y = panel.y + 84
    boxes = {
        "employee_id": pygame.Rect(field_x, start_y, field_width, 36),
        "name": pygame.Rect(field_x, start_y + 57, field_width, 36),
        "salary": pygame.Rect(field_x + 55, start_y + 171, 110, 36),
    }
    role_prev = pygame.Rect(field_x, start_y + 114, 40, 36)
    role_box = pygame.Rect(field_x + 45, start_y + 114, field_width - 90, 36)
    role_next = pygame.Rect(field_x + field_width - 40, start_y + 114, 40, 36)
    salary_down = pygame.Rect(field_x + 5, start_y + 171, 45, 36)
    salary_up = pygame.Rect(field_x + 170, start_y + 171, 45, 36)
    save_button = pygame.Rect(panel.x + 90, panel.bottom - 54, 120, 36)
    cancel_button = pygame.Rect(panel.x + 290, panel.bottom - 54, 120, 36)
    return (
        panel, boxes, role_prev, role_box, role_next,
        salary_down, salary_up, save_button, cancel_button,
    )


def draw_employee_editor(surface, fonts, fields, active_input, add_mode, message, cursor_visible=True):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((*OVERLAY_COLOR, 135))
    surface.blit(overlay, (0, 0))

    (
        panel, boxes, role_prev, role_box, role_next,
        salary_down, salary_up, save_button, cancel_button,
    ) = employee_editor_layout()

    shadow = get_drop_shadow(panel.width, panel.height, radius=10, blur=14, alpha=50, offset_y=5)
    surface.blit(shadow, (panel.x - 14, panel.y - 9))

    pygame.draw.rect(surface, PANEL_BG, panel, border_radius=10)
    pygame.draw.rect(surface, EMPLOYEE_EDGE_COLOR, panel, 3, border_radius=10)

    title = fonts["title"].render("Hire Staff Member" if add_mode else "Edit Staff Details", True, TEXT_COLOR)
    surface.blit(title, (panel.x + 28, panel.y + 20))

    surface.blit(fonts["small"].render("Employee ID", True, TEXT_COLOR), (panel.x + 36, boxes["employee_id"].y + 9))
    surface.blit(fonts["small"].render("Staff Name", True, TEXT_COLOR), (panel.x + 36, boxes["name"].y + 9))
    surface.blit(fonts["small"].render("Store Role", True, TEXT_COLOR), (panel.x + 36, role_box.y + 9))
    surface.blit(fonts["small"].render("Monthly Salary", True, TEXT_COLOR), (panel.x + 36, boxes["salary"].y + 9))

    draw_input_box(
        surface, boxes["employee_id"], fields["employee_id"], active_input == "employee_id",
        fonts["body"], EMPLOYEE_EDGE_COLOR, cursor_visible=cursor_visible
    )
    draw_input_box(
        surface, boxes["name"], fields["name"], active_input == "name",
        fonts["body"], EMPLOYEE_EDGE_COLOR, cursor_visible=cursor_visible
    )
    draw_input_box(
        surface, boxes["salary"], fields["salary"], active_input == "salary",
        fonts["body"], EMPLOYEE_EDGE_COLOR, cursor_visible=cursor_visible
    )

    draw_button(surface, role_prev, "<", EMPLOYEE_BUTTON_COLOR, fonts["body"])
    pygame.draw.rect(surface, INPUT_BG, role_box, border_radius=6)
    pygame.draw.rect(surface, EMPLOYEE_EDGE_COLOR, role_box, 2, border_radius=6)
    role_rendered = fonts["body"].render(fields.get("role", "Cashier"), True, TEXT_COLOR)
    surface.blit(role_rendered, role_rendered.get_rect(center=role_box.center))
    draw_button(surface, role_next, ">", EMPLOYEE_BUTTON_COLOR, fonts["body"])

    draw_button(surface, salary_down, "-1k", EMPLOYEE_BUTTON_COLOR, fonts["small"])
    draw_button(surface, salary_up, "+1k", EMPLOYEE_BUTTON_COLOR, fonts["small"])

    draw_button(surface, save_button, "Save", EMPLOYEE_BUTTON_COLOR, fonts["body"])
    draw_button(surface, cancel_button, "Cancel", (130, 140, 150), fonts["body"])

    if message:
        rendered_msg = fonts["small"].render(message, True, LOSS_RED)
        surface.blit(rendered_msg, (panel.x + 36, panel.bottom - 90))


#________________________________________STORAGE DEPOT UI__________________________________________________________________

def build_storage_elements(storage_items, expanded_categories):
    grouped = {}
    for cat in CATEGORIES:
        grouped[cat] = []
    for item in storage_items:
        cat = item[2] if len(item) > 2 and item[2] else "General"
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(item)

    for cat in grouped:
        grouped[cat].sort(key=lambda x: x[0])

    active_grouped = {cat: items for cat, items in grouped.items() if items}

    doc_elements = []
    current_y = 0
    for cat, items in active_grouped.items():
        is_expanded = cat in expanded_categories
        header_rect = pygame.Rect(0, current_y, 775, 42)
        doc_elements.append(("category_header", header_rect, (cat, is_expanded, len(items))))
        current_y += 48

        if is_expanded:
            table_hdr_rect = pygame.Rect(10, current_y, 765, 26)
            doc_elements.append(("table_header", table_hdr_rect, cat))
            current_y += 30

            for item in items:
                row_rect = pygame.Rect(10, current_y, 755, 36)
                doc_elements.append(("storage_row", row_rect, item))
                current_y += 40
            current_y += 6
    return doc_elements, current_y


def storage_menu_layout(storage_items, selected_item_id, expanded_categories, scroll_y):
    panel = pygame.Rect((SCREEN_WIDTH - 840) // 2, 32, 840, 536)
    viewport = pygame.Rect(panel.x + 24, panel.y + 70, 780, 396)

    doc_elements, total_content_height = build_storage_elements(storage_items, expanded_categories)
    max_scroll = max(0, total_content_height - viewport.height)
    clamped_scroll = max(0, min(scroll_y, max_scroll))

    locations_button = None
    order_button = None
    if selected_item_id is not None:
        locations_button = pygame.Rect(panel.x + 28, panel.bottom - 58, 200, 36)
        order_button = pygame.Rect(panel.x + 240, panel.bottom - 58, 200, 36)

    scroll_track = None
    scroll_thumb = None
    if total_content_height > viewport.height:
        scroll_track = pygame.Rect(panel.right - 20, viewport.top, 8, viewport.height)
        scroll_thumb = make_scroll_thumb(scroll_track, total_content_height, viewport.height, clamped_scroll)

    return (
        panel, viewport, doc_elements, total_content_height, max_scroll, clamped_scroll,
        locations_button, order_button, scroll_track, scroll_thumb,
    )


def draw_storage_menu(surface, fonts, storage_items, selected_item_id, expanded_categories, scroll_y, store_balance, message):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((*OVERLAY_COLOR, 130))
    surface.blit(overlay, (0, 0))

    (
        panel, viewport, doc_elements, total_content_height, max_scroll, clamped_scroll,
        locations_button, order_button, scroll_track, scroll_thumb,
    ) = storage_menu_layout(storage_items, selected_item_id, expanded_categories, scroll_y)

    shadow = get_drop_shadow(panel.width, panel.height, radius=10, blur=14, alpha=50, offset_y=5)
    surface.blit(shadow, (panel.x - 14, panel.y - 9))

    pygame.draw.rect(surface, PANEL_BG, panel, border_radius=10)
    pygame.draw.rect(surface, STORAGE_EDGE_COLOR, panel, 3, border_radius=10)

    title = fonts["title"].render("Backroom Storage Depot", True, TEXT_COLOR)
    surface.blit(title, (panel.x + 28, panel.y + 18))

    bal_text = fonts["small"].render(f"Store Balance: Rs. {store_balance:,.2f}", True, PROFIT_GREEN)
    surface.blit(bal_text, (panel.right - bal_text.get_width() - 28, panel.y + 24))

    columns = [("Item ID", 20), ("Product name", 95), ("Cost Price", 365), ("In Storage", 495), ("On Shelves", 630)]
    dividers = [85, 355, 485, 620]

    mouse_pos = pygame.mouse.get_pos()
    surface.set_clip(viewport)

    for elem_type, rect, data in doc_elements:
        screen_rect = rect.move(viewport.x, viewport.y - clamped_scroll)
        if screen_rect.bottom < viewport.top or screen_rect.top > viewport.bottom:
            continue

        if elem_type == "category_header":
            cat, is_expanded, count = data
            is_hovered = screen_rect.collidepoint(mouse_pos)
            banner_bg = (255, 246, 235) if is_hovered else ((255, 242, 226) if is_expanded else (252, 248, 242))
            pygame.draw.rect(surface, banner_bg, screen_rect, border_radius=6)
            pygame.draw.rect(surface, (230, 195, 155), screen_rect, 1, border_radius=6)

            draw_chevron(surface, screen_rect.x + 20, screen_rect.centery, is_expanded, STORAGE_EDGE_COLOR)

            cat_font = fonts.get("header") or fonts["body"]
            cat_surf = cat_font.render(cat.upper(), True, TEXT_COLOR)
            surface.blit(cat_surf, (screen_rect.x + 36, screen_rect.y + 11))

            badge_surf = fonts["small"].render(f"({count} items)", True, TEXT_MUTED)
            surface.blit(badge_surf, (screen_rect.x + 46 + cat_surf.get_width(), screen_rect.y + 13))

        elif elem_type == "table_header":
            for heading, offset in columns:
                hdr = fonts["small"].render(heading, True, STORAGE_EDGE_COLOR)
                surface.blit(hdr, (screen_rect.x + offset, screen_rect.y + 6))
            pygame.draw.line(surface, STORAGE_EDGE_COLOR, (screen_rect.x + 10, screen_rect.bottom - 2), (screen_rect.right - 10, screen_rect.bottom - 2), 1)

        elif elem_type == "storage_row":
            item = data
            item_id = item[0]
            item_name = item[1]
            ws_price = item[4]
            storage_qty = item[5]
            shelf_qty = item[6]

            if item_id == selected_item_id:
                pygame.draw.rect(surface, STORAGE_SELECTED_COLOR, screen_rect, border_radius=5)
            elif screen_rect.collidepoint(mouse_pos):
                pygame.draw.rect(surface, (255, 252, 247), screen_rect, border_radius=5)
            else:
                pygame.draw.rect(surface, (255, 255, 255), screen_rect, border_radius=5)

            for div_x in dividers:
                pygame.draw.line(surface, (240, 230, 220), (screen_rect.x + div_x, screen_rect.y + 2), (screen_rect.x + div_x, screen_rect.bottom - 2), 1)

            storage_display = f"{storage_qty} units" if storage_qty > 0 else "0 (Empty!)"
            storage_color = TEXT_COLOR if storage_qty > 0 else LOSS_RED
            values = (
                (str(item_id), TEXT_COLOR),
                (item_name, TEXT_COLOR),
                (f"Rs. {ws_price:.2f}", TEXT_COLOR),
                (storage_display, storage_color),
                (f"{shelf_qty} units", TEXT_COLOR),
            )
            for (val, col), (_, offset) in zip(values, columns):
                txt = fonts["body"].render(val, True, col)
                surface.blit(txt, (screen_rect.x + offset, screen_rect.y + 7))

    surface.set_clip(None)

    if scroll_track:
        pygame.draw.rect(surface, SCROLL_TRACK_COLOR, scroll_track, border_radius=4)
        pygame.draw.rect(surface, STORAGE_EDGE_COLOR, scroll_thumb, border_radius=4)

    if locations_button:
        draw_button(surface, locations_button, "View Shelf Locations", STORAGE_EDGE_COLOR, fonts["small"])
    if order_button:
        draw_button(surface, order_button, "Order Stock from Supplier", STORAGE_BUTTON_COLOR, fonts["small"])

    if message:
        hint = fonts["small"].render(message, True, PROFIT_GREEN if "Ordered" in message else LOSS_RED)
    else:
        hint = fonts["small"].render(
            "Click item to inspect  |  Click category to expand/collapse  |  Esc: close",
            True,
            TEXT_MUTED,
        )
    bottom_y = panel.bottom - 46 if (locations_button or order_button) else panel.bottom - 36
    hint_x = panel.x + 455 if (locations_button or order_button) else panel.x + 28
    surface.blit(hint, (hint_x, bottom_y))


def storage_distribution_layout():
    panel = pygame.Rect((SCREEN_WIDTH - 660) // 2, 70, 660, 460)
    close_button = pygame.Rect((SCREEN_WIDTH - 120) // 2, panel.bottom - 52, 120, 36)
    return panel, close_button


def draw_storage_distribution(surface, fonts, selected_item, distribution_list, shelves=None):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((*OVERLAY_COLOR, 145))
    surface.blit(overlay, (0, 0))

    panel, close_button = storage_distribution_layout()
    shadow = get_drop_shadow(panel.width, panel.height, radius=10, blur=14, alpha=50, offset_y=5)
    surface.blit(shadow, (panel.x - 14, panel.y - 9))

    pygame.draw.rect(surface, PANEL_BG, panel, border_radius=10)
    pygame.draw.rect(surface, STORAGE_EDGE_COLOR, panel, 3, border_radius=10)

    item_name = selected_item[1]
    item_id = selected_item[0]
    total_shelves = selected_item[6]

    title = fonts["title"].render("Shelf Locations", True, TEXT_COLOR)
    surface.blit(title, (panel.x + 28, panel.y + 20))

    subtitle = fonts["body"].render(f"{item_name} (#{item_id})", True, STORAGE_EDGE_COLOR)
    surface.blit(subtitle, (panel.x + 28, panel.y + 60))

    total_txt = fonts["small"].render(f"Total on store shelves: {total_shelves} units", True, TEXT_MUTED)
    surface.blit(total_txt, (panel.right - total_txt.get_width() - 28, panel.y + 64))

    pygame.draw.line(surface, STORAGE_EDGE_COLOR, (panel.x + 24, panel.y + 95), (panel.right - 24, panel.y + 95), 2)

    shelf_names = {s.shelf_id: s.display_name for s in shelves} if shelves else {}

    if not distribution_list:
        empty_msg = fonts["body"].render("This product is not currently placed on any shelf in the store.", True, TEXT_MUTED)
        surface.blit(empty_msg, (panel.x + 36, panel.y + 140))
        hint_msg = fonts["small"].render("To display this item on shelves, walk to a shelf and click '+' in its menu.", True, TEXT_MUTED)
        surface.blit(hint_msg, (panel.x + 36, panel.y + 175))
    else:
        columns = [("Shelf Name", 16), ("Department", 205), ("Map Location", 385), ("Shelf Stock", 510)]
        header_y = panel.y + 105
        for heading, offset in columns:
            hdr = fonts["small"].render(heading, True, STORAGE_EDGE_COLOR)
            surface.blit(hdr, (panel.x + 28 + offset, header_y))

        for idx, row in enumerate(distribution_list[:7]):
            shelf_id, map_x, map_y, shelf_cat, qty, price = row
            row_y = header_y + 32 + idx * 36
            row_rect = pygame.Rect(panel.x + 28, row_y, panel.width - 56, 32)
            bg = (255, 252, 247) if idx % 2 == 0 else (250, 245, 238)
            pygame.draw.rect(surface, bg, row_rect, border_radius=4)

            s_name = shelf_names.get(shelf_id, f"Shelf {shelf_id}")
            values = (
                s_name,
                shelf_cat,
                f"Row {map_y + 1}, Col {map_x + 1}",
                f"{qty} units",
            )
            for val, (_, offset) in zip(values, columns):
                txt = fonts["body"].render(val, True, TEXT_COLOR)
                surface.blit(txt, (panel.x + 28 + offset, row_y + 4))

    draw_button(surface, close_button, "Close", STORAGE_EDGE_COLOR, fonts["body"])


def storage_order_layout():
    panel = pygame.Rect((SCREEN_WIDTH - 500) // 2, 70, 500, 460)
    field_x = panel.x + 165
    qty_y = panel.y + 200

    order_down_10 = pygame.Rect(field_x, qty_y, 44, 36)
    order_down = pygame.Rect(field_x + 48, qty_y, 38, 36)
    order_box = pygame.Rect(field_x + 90, qty_y, 85, 36)
    order_up = pygame.Rect(field_x + 179, qty_y, 38, 36)
    order_up_10 = pygame.Rect(field_x + 221, qty_y, 44, 36)

    confirm_button = pygame.Rect(panel.x + 60, panel.bottom - 54, 180, 36)
    cancel_button = pygame.Rect(panel.x + 260, panel.bottom - 54, 170, 36)

    return (
        panel, order_down_10, order_down, order_box, order_up, order_up_10,
        confirm_button, cancel_button,
    )


def draw_storage_order(surface, fonts, selected_item, order_qty_text, store_balance, message, active_input=False, cursor_visible=True):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((*OVERLAY_COLOR, 145))
    surface.blit(overlay, (0, 0))

    (
        panel, order_down_10, order_down, order_box, order_up, order_up_10,
        confirm_button, cancel_button,
    ) = storage_order_layout()

    shadow = get_drop_shadow(panel.width, panel.height, radius=10, blur=14, alpha=50, offset_y=5)
    surface.blit(shadow, (panel.x - 14, panel.y - 9))

    pygame.draw.rect(surface, PANEL_BG, panel, border_radius=10)
    pygame.draw.rect(surface, STORAGE_EDGE_COLOR, panel, 3, border_radius=10)

    title = fonts["title"].render("Supplier Restock Order", True, TEXT_COLOR)
    surface.blit(title, (panel.x + 28, panel.y + 20))

    item_id = selected_item[0]
    item_name = selected_item[1]
    ws_price = selected_item[4]

    try:
        qty = int(order_qty_text or "0")
    except ValueError:
        qty = 0
    total_cost = round(ws_price * qty, 2)
    can_afford = store_balance >= total_cost and qty > 0
    rem_balance = store_balance - total_cost

    labels = [
        ("Product:", f"{item_name} (#{item_id})", TEXT_COLOR),
        ("Wholesale Cost:", f"Rs. {ws_price:.2f} per unit", TEXT_COLOR),
        ("Current Balance:", f"Rs. {store_balance:,.2f}", PROFIT_GREEN),
    ]
    for idx, (lbl, val, col) in enumerate(labels):
        lbl_surf = fonts["small"].render(lbl, True, TEXT_MUTED)
        val_surf = fonts["body"].render(val, True, col)
        y = panel.y + 75 + idx * 38
        surface.blit(lbl_surf, (panel.x + 32, y + 4))
        surface.blit(val_surf, (panel.x + 165, y))

    surface.blit(fonts["small"].render("Order Quantity:", True, TEXT_COLOR), (panel.x + 32, order_box.y + 8))
    draw_button(surface, order_down_10, "-10", STORAGE_BUTTON_COLOR, fonts["small"])
    draw_button(surface, order_down, "-", STORAGE_BUTTON_COLOR, fonts["body"])
    draw_input_box(surface, order_box, order_qty_text, active_input, fonts["body"], STORAGE_EDGE_COLOR, cursor_visible=cursor_visible)
    draw_button(surface, order_up, "+", STORAGE_BUTTON_COLOR, fonts["body"])
    draw_button(surface, order_up_10, "+10", STORAGE_BUTTON_COLOR, fonts["small"])

    cost_surf = fonts["body"].render(f"Total Cost: Rs. {total_cost:,.2f}", True, TEXT_COLOR if can_afford else LOSS_RED)
    surface.blit(cost_surf, (panel.x + 165, panel.y + 250))

    rem_surf = fonts["small"].render(f"Remaining Funds: Rs. {rem_balance:,.2f}", True, TEXT_MUTED if can_afford else LOSS_RED)
    surface.blit(rem_surf, (panel.x + 165, panel.y + 280))

    if not can_afford and qty > 0:
        err_msg = fonts["small"].render("Insufficient store balance for this order!", True, LOSS_RED)
        surface.blit(err_msg, (panel.x + 32, panel.bottom - 95))
    elif message:
        msg_surf = fonts["small"].render(message, True, LOSS_RED)
        surface.blit(msg_surf, (panel.x + 32, panel.bottom - 95))

    confirm_col = STORAGE_BUTTON_COLOR if can_afford else (180, 180, 180)
    draw_button(surface, confirm_button, "Confirm & Pay", confirm_col, fonts["body"])
    draw_button(surface, cancel_button, "Cancel", (130, 140, 150), fonts["body"])


#________________________________________WORLD DRAW__________________________________________________________________

def draw_world(surface, player, walls, shelves, catalogue, cash_register, employee_terminal, storage_depot, targeted_object, fonts):
    surface.fill(WINDOW_COLOR)
    game_area = pygame.Rect(0, 0, SCREEN_WIDTH, MAP_HEIGHT)
    pygame.draw.rect(surface, FLOOR_COLOR, game_area)

    for wall in walls:
        pygame.draw.rect(surface, WALL_COLOR, wall)

    for shelf in shelves:
        theme = get_shelf_theme(shelf.category)
        fill_col = theme["fill"]
        color = theme["edge"] if shelf is targeted_object else fill_col
        pygame.draw.rect(surface, fill_col, shelf.rect)
        pygame.draw.rect(surface, color, shelf.rect, 3)
        pygame.draw.line(
            surface,
            color,
            (shelf.rect.left + 6, shelf.rect.centery),
            (shelf.rect.right - 6, shelf.rect.centery),
            2,
        )

    catalogue_color = CATALOGUE_EDGE_COLOR if catalogue is targeted_object else CATALOGUE_COLOR
    pygame.draw.rect(surface, CATALOGUE_COLOR, catalogue.rect)
    pygame.draw.rect(surface, catalogue_color, catalogue.rect, 3)
    pygame.draw.rect(surface, catalogue_color, catalogue.rect.inflate(-16, -10), 2, border_radius=3)

    register_color = REGISTER_EDGE_COLOR if cash_register is targeted_object else REGISTER_COLOR
    pygame.draw.rect(surface, REGISTER_COLOR, cash_register.rect, border_radius=4)
    pygame.draw.rect(surface, register_color, cash_register.rect, 3, border_radius=4)
    pygame.draw.rect(surface, register_color, cash_register.rect.inflate(-12, -19), 2, border_radius=2)
    pygame.draw.line(
        surface,
        register_color,
        (cash_register.rect.left + 7, cash_register.rect.bottom - 9),
        (cash_register.rect.right - 7, cash_register.rect.bottom - 9),
        2,
    )

    emp_color = EMPLOYEE_EDGE_COLOR if employee_terminal is targeted_object else EMPLOYEE_COLOR
    pygame.draw.rect(surface, EMPLOYEE_COLOR, employee_terminal.rect, border_radius=4)
    pygame.draw.rect(surface, emp_color, employee_terminal.rect, 3, border_radius=4)
    badge_rect = pygame.Rect(employee_terminal.rect.centerx - 7, employee_terminal.rect.centery - 9, 14, 18)
    pygame.draw.rect(surface, (255, 255, 255), badge_rect, border_radius=2)
    pygame.draw.rect(surface, emp_color, badge_rect, 1, border_radius=2)
    pygame.draw.line(surface, emp_color, (badge_rect.x + 3, badge_rect.y + 5), (badge_rect.right - 4, badge_rect.y + 5), 2)
    pygame.draw.line(surface, (140, 140, 140), (badge_rect.x + 3, badge_rect.y + 9), (badge_rect.right - 4, badge_rect.y + 9), 1)
    pygame.draw.line(surface, (140, 140, 140), (badge_rect.x + 3, badge_rect.y + 13), (badge_rect.right - 4, badge_rect.y + 13), 1)

    if storage_depot:
        depot_edge = STORAGE_EDGE_COLOR if storage_depot is targeted_object else STORAGE_COLOR
        pygame.draw.rect(surface, STORAGE_COLOR, storage_depot.rect, border_radius=4)
        pygame.draw.rect(surface, depot_edge, storage_depot.rect, 3, border_radius=4)
        crate_inner = storage_depot.rect.inflate(-10, -10)
        pygame.draw.rect(surface, depot_edge, crate_inner, 2, border_radius=2)
        pygame.draw.line(surface, depot_edge, crate_inner.topleft, crate_inner.bottomright, 2)
        pygame.draw.line(surface, depot_edge, crate_inner.bottomleft, crate_inner.topright, 2)

    player.draw(surface)
    instructions = fonts["body"].render("Movement: WASD | Interaction: E", True, TEXT_COLOR)
    info_panel = pygame.Rect(0, MAP_HEIGHT, SCREEN_WIDTH, HUD_HEIGHT)
    pygame.draw.rect(surface, INFO_PANEL_COLOR, info_panel)
    pygame.draw.line(surface, ACCENT_COLOR, (0, MAP_HEIGHT), (SCREEN_WIDTH, MAP_HEIGHT), 2)
    surface.blit(instructions, (20, MAP_HEIGHT + 12))

    if targeted_object:
        if isinstance(targeted_object, Shelf):
            prompt_text = f"Press E to inspect {targeted_object.display_name}"
        elif isinstance(targeted_object, ProductCatalogue):
            prompt_text = "Press E to open product catalogue"
        elif isinstance(targeted_object, CashRegister):
            prompt_text = "Press E to open cash register"
        elif isinstance(targeted_object, EmployeeTerminal):
            prompt_text = "Press E to open employee terminal"
        elif isinstance(targeted_object, StorageDepot):
            prompt_text = "Press E to open storage depot"
        else:
            prompt_text = "Press E to interact"
        prompt = fonts["body"].render(prompt_text, True, ACCENT_COLOR)
        surface.blit(prompt, (20, MAP_HEIGHT + 43))


def find_shelf_item(shelf, item_id):
    for item in shelf.items:
        if item[0] == item_id:
            return item
    return None


def available_products_for_shelf(shelf, products, included_item_id=None):
    saved_ids = {item[0] for item in shelf.items}
    shelf_cat = getattr(shelf, "category", "General") or "General"
    result = []
    for item in products:
        if item[0] in saved_ids and item[0] != included_item_id:
            continue
        item_cat = item[5] if len(item) > 5 else "General"
        if shelf_cat != "General" and item_cat != shelf_cat:
            continue
        result.append(item)
    return result


def parse_editor_values(quantity_text, price_text):
    quantity = int(quantity_text)
    price = float(price_text)
    if quantity < 0 or price < 0:
        raise ValueError
    return quantity, price


def parse_catalogue_values(fields):
    item_id = int(fields["item_id"])
    item_name = fields["item_name"].strip()
    price = float(fields["price"])
    minimum_quantity = int(fields["minimum_quantity"])
    maximum_quantity = int(fields["maximum_quantity"])
    if (
        item_id <= 0
        or not item_name
        or len(item_name) > 100
        or price <= 0
        or minimum_quantity < 0
        or maximum_quantity < minimum_quantity
    ):
        raise ValueError
    return item_id, item_name, price, minimum_quantity, maximum_quantity


def catalogue_item_by_id(products, item_id):
    for item in products:
        if item[0] == item_id:
            return item
    return None

#__________________________________________MAIN CODE________________________________________________________________

def main():
    pygame.init()
    try:
        pygame.mixer.init()
    except Exception as error:
        print(f"Audio device initialization note: {error}")

    step_sound = load_sound("step.wav", volume=0.35)
    interact_sound = load_sound("fruit1.wav", volume=0.45)

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Store Management Simulator v0.9.0")
    clock = pygame.time.Clock()
    fonts = get_fonts_dict()

    map_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "store_level1.txt")
    try:
        ensure_store_database(map_path)
        inventory_by_position = load_shelf_inventory(map_path)
        shelf_categories = load_shelf_categories(map_path)
        product_catalogue = list(load_product_catalogue(map_path))
        finance_balance, finance_history = load_finance_data(map_path)
        employees = list(load_employees(map_path))
        walls, shelves, catalogue, cash_register, employee_terminal, storage_depot, player_spawn = load_store_map(
            map_path, inventory_by_position
        )
        for shelf in shelves:
            shelf.category = shelf_categories.get(shelf.shelf_id, "General")
        recompute_shelf_display_names(shelves)
    except (OSError, ValueError, DatabaseSetupError) as error:
        print(f"Unable to start store simulator: {error}")
        pygame.quit()
        return

    player = Player(player_spawn, step_sound=step_sound)
    solid_rects = (
        walls
        + [shelf.rect for shelf in shelves]
        + [catalogue.rect, cash_register.rect, employee_terminal.rect]
        + ([storage_depot.rect] if storage_depot else [])
    )
    state = GameState.PLAYING
    selected_shelf = None
    selected_item_id = None
    shelf_first_item = 0
    sell_qty_text = "1"
    sell_active_input = False
    editing_item_id = None
    editor_product = None
    quantity_text = ""
    price_text = ""
    active_input = None
    product_picker_open = False
    product_picker_first_item = 0
    menu_message = ""
    selected_catalogue_id = None
    catalogue_editing_item_id = None
    catalogue_add_mode = True
    expanded_categories = set()
    catalogue_scroll_y = 0
    catalogue_fields = {
        "item_id": "",
        "item_name": "",
        "category": CATEGORIES[0],
        "price": "",
        "minimum_quantity": "",
        "maximum_quantity": "",
    }
    catalogue_active_input = None
    catalogue_message = ""
    storage_items = []
    selected_storage_id = None
    storage_expanded_categories = set()
    storage_scroll_y = 0
    storage_message = ""
    order_quantity_text = "10"
    order_active_input = False
    order_message = ""
    distribution_list = ()
    finance_balance_text = f"{finance_balance:.2f}"
    finance_history_start = 0
    finance_active_input = False
    finance_message = ""
    selected_employee_id = None
    employee_editing_id = None
    employee_add_mode = True
    employee_fields = {
        "employee_id": "",
        "name": "",
        "role": "Cashier",
        "salary": "",
    }
    employee_active_input = None
    employee_message = ""
    employee_start = 0
    running = True

    cursor_timer = 0.0
    cursor_visible = True

    shelf_scroll = SmoothScroll(0, 8)
    finance_scroll = SmoothScroll(len(finance_history), 7)
    picker_scroll = SmoothScroll(0, 8)
    employee_scroll = SmoothScroll(len(employees), 7)

    def commit_finance_balance():
        nonlocal finance_balance, finance_history, finance_balance_text
        nonlocal finance_message, finance_history_start, finance_active_input
        try:
            entered_balance = float(finance_balance_text)
            if entered_balance < 0:
                raise ValueError
            finance_balance, saved_entry = set_store_balance(
                map_path, entered_balance
            )
            finance_balance_text = f"{finance_balance:.2f}"
            if saved_entry is None:
                finance_message = "Balance is unchanged."
            else:
                finance_balance, finance_history = load_finance_data(map_path)
                sign = "+" if saved_entry[1] == "Profit" else "-"
                finance_message = (
                    f"{saved_entry[1]}: {sign}Rs. {saved_entry[2]:,.2f}"
                )
            finance_scroll.set_counts(len(finance_history), 7)
            finance_history_start = 0
            finance_active_input = False
        except ValueError:
            finance_message = "Enter a valid balance of zero or more."
        except DatabaseSetupError as error:
            finance_message = str(error)

    while running:
        dt = clock.tick(FPS) / 1000
        targeted_object = get_targeted_object(
            player, shelves, catalogue, cash_register, employee_terminal, storage_depot
        )

        cursor_timer += dt
        cursor_visible = (int(cursor_timer * 2.2) % 2) == 0

        shelf_scroll.update(dt)
        finance_scroll.update(dt)
        picker_scroll.update(dt)
        employee_scroll.update(dt)

        shelf_first_item = shelf_scroll.get_first_visible_index()
        finance_history_start = finance_scroll.get_first_visible_index()
        product_picker_first_item = picker_scroll.get_first_visible_index()
        employee_start = employee_scroll.get_first_visible_index()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                cursor_timer = 0.0
                cursor_visible = True
                if state == GameState.FINANCE_MENU:
                    if event.key == pygame.K_ESCAPE or (event.key == pygame.K_e and not finance_active_input):
                        state = GameState.PLAYING
                        finance_active_input = False
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        commit_finance_balance()
                    elif event.key == pygame.K_DOWN:
                        finance_scroll.scroll_by(1)
                    elif event.key == pygame.K_UP:
                        finance_scroll.scroll_by(-1)
                    elif event.key == pygame.K_PAGEDOWN:
                        finance_scroll.scroll_by(7)
                    elif event.key == pygame.K_PAGEUP:
                        finance_scroll.scroll_by(-7)
                    elif finance_active_input:
                        if event.key == pygame.K_BACKSPACE:
                            finance_balance_text = finance_balance_text[:-1]
                        elif event.unicode.isdigit() or (
                            event.unicode == "." and "." not in finance_balance_text
                        ):
                            finance_balance_text += event.unicode
                elif state == GameState.PRODUCT_EDITOR:
                    if event.key == pygame.K_ESCAPE:
                        state = GameState.CATALOGUE_MENU
                        catalogue_active_input = None
                        catalogue_message = ""
                    elif catalogue_active_input:
                        current_value = catalogue_fields[catalogue_active_input]
                        if event.key == pygame.K_BACKSPACE:
                            catalogue_fields[catalogue_active_input] = current_value[:-1]
                        elif catalogue_active_input in {
                            "item_id", "minimum_quantity", "maximum_quantity",
                        }:
                            if event.unicode.isdigit():
                                catalogue_fields[catalogue_active_input] += event.unicode
                        elif catalogue_active_input == "price":
                            if event.unicode.isdigit() or (
                                event.unicode == "." and "." not in current_value
                            ):
                                catalogue_fields[catalogue_active_input] += event.unicode
                        elif event.unicode.isprintable() and len(current_value) < 100:
                            catalogue_fields[catalogue_active_input] += event.unicode
                elif state in (GameState.EDIT_ITEM, GameState.ADD_ITEM):
                    if product_picker_open:
                        if event.key == pygame.K_ESCAPE:
                            product_picker_open = False
                    elif event.key == pygame.K_ESCAPE:
                        state = GameState.SHELF_MENU
                        active_input = None
                    elif active_input == "quantity":
                        if event.key == pygame.K_BACKSPACE:
                            quantity_text = quantity_text[:-1]
                        elif event.unicode.isdigit():
                            quantity_text += event.unicode
                    elif active_input == "price":
                        if event.key == pygame.K_BACKSPACE:
                            price_text = price_text[:-1]
                        elif event.unicode.isdigit() or (event.unicode == "." and "." not in price_text):
                            price_text += event.unicode
                elif state == GameState.PLAYING and event.key == pygame.K_e and targeted_object:
                    if interact_sound:
                        interact_sound.play()
                    if isinstance(targeted_object, Shelf):
                        selected_shelf = targeted_object
                        selected_item_id = None
                        sell_qty_text = "1"
                        sell_active_input = False
                        shelf_scroll.set_counts(len(selected_shelf.get_visible_items(product_catalogue)), 8)
                        shelf_scroll.scroll_to(0)
                        shelf_first_item = 0
                        menu_message = ""
                        state = GameState.SHELF_MENU
                    elif isinstance(targeted_object, ProductCatalogue):
                        expanded_categories = set()
                        catalogue_scroll_y = 0
                        selected_catalogue_id = None
                        catalogue_message = ""
                        state = GameState.CATALOGUE_MENU
                    elif isinstance(targeted_object, StorageDepot):
                        storage_items = list(load_storage_inventory(map_path))
                        finance_balance, finance_history = load_finance_data(map_path)
                        selected_storage_id = None
                        storage_expanded_categories = set()
                        storage_scroll_y = 0
                        storage_message = ""
                        state = GameState.STORAGE_MENU
                    elif isinstance(targeted_object, EmployeeTerminal):
                        employees = list(load_employees(map_path))
                        employee_scroll.set_counts(len(employees), 7)
                        employee_scroll.scroll_to(0)
                        employee_start = 0
                        selected_employee_id = None
                        employee_message = ""
                        state = GameState.EMPLOYEE_MENU
                    else:
                        finance_balance_text = f"{finance_balance:.2f}"
                        finance_scroll.set_counts(len(finance_history), 7)
                        finance_scroll.scroll_to(0)
                        finance_history_start = 0
                        finance_active_input = False
                        finance_message = ""
                        state = GameState.FINANCE_MENU
                elif state == GameState.SHELF_MENU:
                    if event.key == pygame.K_ESCAPE or (event.key == pygame.K_e and not sell_active_input):
                        selected_shelf = None
                        selected_item_id = None
                        shelf_first_item = 0
                        sell_active_input = False
                        state = GameState.PLAYING
                    elif event.key == pygame.K_DOWN:
                        shelf_scroll.scroll_by(1)
                    elif event.key == pygame.K_UP:
                        shelf_scroll.scroll_by(-1)
                    elif event.key == pygame.K_PAGEDOWN:
                        shelf_scroll.scroll_by(8)
                    elif event.key == pygame.K_PAGEUP:
                        shelf_scroll.scroll_by(-8)
                    elif sell_active_input:
                        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            sell_active_input = False
                        elif event.key == pygame.K_BACKSPACE:
                            sell_qty_text = sell_qty_text[:-1]
                        elif event.unicode.isdigit() and len(sell_qty_text) < 4:
                            sell_qty_text += event.unicode
                elif state == GameState.CATALOGUE_MENU and event.key in (pygame.K_e, pygame.K_ESCAPE):
                    state = GameState.PLAYING
                elif state == GameState.CATALOGUE_MENU and event.key == pygame.K_DOWN:
                    _, total_h = build_catalogue_elements(product_catalogue, expanded_categories)
                    catalogue_scroll_y = min(max(0, total_h - 396), catalogue_scroll_y + 36)
                elif state == GameState.CATALOGUE_MENU and event.key == pygame.K_UP:
                    catalogue_scroll_y = max(0, catalogue_scroll_y - 36)
                elif state == GameState.CATALOGUE_MENU and event.key == pygame.K_PAGEDOWN:
                    _, total_h = build_catalogue_elements(product_catalogue, expanded_categories)
                    catalogue_scroll_y = min(max(0, total_h - 396), catalogue_scroll_y + 200)
                elif state == GameState.CATALOGUE_MENU and event.key == pygame.K_PAGEUP:
                    catalogue_scroll_y = max(0, catalogue_scroll_y - 200)
                elif state == GameState.EMPLOYEE_MENU and event.key in (pygame.K_e, pygame.K_ESCAPE):
                    state = GameState.PLAYING
                elif state == GameState.EMPLOYEE_MENU and event.key == pygame.K_DOWN:
                    employee_scroll.scroll_by(1)
                elif state == GameState.EMPLOYEE_MENU and event.key == pygame.K_UP:
                    employee_scroll.scroll_by(-1)
                elif state == GameState.EMPLOYEE_MENU and event.key == pygame.K_PAGEDOWN:
                    employee_scroll.scroll_by(7)
                elif state == GameState.EMPLOYEE_MENU and event.key == pygame.K_PAGEUP:
                    employee_scroll.scroll_by(-7)
                elif state == GameState.STORAGE_MENU and event.key in (pygame.K_e, pygame.K_ESCAPE):
                    state = GameState.PLAYING
                elif state == GameState.STORAGE_MENU and event.key == pygame.K_DOWN:
                    _, total_h = build_storage_elements(storage_items, storage_expanded_categories)
                    storage_scroll_y = min(max(0, total_h - 396), storage_scroll_y + 36)
                elif state == GameState.STORAGE_MENU and event.key == pygame.K_UP:
                    storage_scroll_y = max(0, storage_scroll_y - 36)
                elif state == GameState.STORAGE_MENU and event.key == pygame.K_PAGEDOWN:
                    _, total_h = build_storage_elements(storage_items, storage_expanded_categories)
                    storage_scroll_y = min(max(0, total_h - 396), storage_scroll_y + 200)
                elif state == GameState.STORAGE_MENU and event.key == pygame.K_PAGEUP:
                    storage_scroll_y = max(0, storage_scroll_y - 200)
                elif state == GameState.STORAGE_DISTRIBUTION and event.key in (pygame.K_e, pygame.K_ESCAPE):
                    state = GameState.STORAGE_MENU
                elif state == GameState.STORAGE_ORDER:
                    if event.key in (pygame.K_ESCAPE,):
                        state = GameState.STORAGE_MENU
                    elif order_active_input:
                        if event.key == pygame.K_BACKSPACE:
                            order_quantity_text = order_quantity_text[:-1]
                        elif event.unicode.isdigit() and len(order_quantity_text) < 6:
                            order_quantity_text += event.unicode
                elif state == GameState.EMPLOYEE_EDITOR:
                    if event.key == pygame.K_ESCAPE:
                        state = GameState.EMPLOYEE_MENU
                        employee_active_input = None
                        employee_message = ""
                    elif event.key == pygame.K_TAB:
                        fields_cycle = ["employee_id", "name", "salary"]
                        if employee_active_input in fields_cycle:
                            curr_idx = fields_cycle.index(employee_active_input)
                            employee_active_input = fields_cycle[(curr_idx + 1) % len(fields_cycle)]
                        else:
                            employee_active_input = fields_cycle[0]
                    elif employee_active_input:
                        curr_val = employee_fields.get(employee_active_input, "")
                        if event.key == pygame.K_BACKSPACE:
                            employee_fields[employee_active_input] = curr_val[:-1]
                        elif employee_active_input == "employee_id":
                            if event.unicode.isdigit():
                                employee_fields[employee_active_input] += event.unicode
                        elif employee_active_input == "salary":
                            if event.unicode.isdigit() or (event.unicode == "." and "." not in curr_val):
                                employee_fields[employee_active_input] += event.unicode
                        elif event.unicode.isprintable() and len(curr_val) < 50:
                            employee_fields[employee_active_input] += event.unicode
                elif state == GameState.PLAYING and event.key == pygame.K_ESCAPE:
                    running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if state == GameState.FINANCE_MENU:
                    (
                        panel, balance_box, update_button, header_y, rows,
                        visible_rows, scroll_track, scroll_thumb,
                    ) = finance_menu_layout(finance_history, finance_history_start)
                    if balance_box.collidepoint(event.pos):
                        finance_active_input = True
                    elif update_button.collidepoint(event.pos):
                        commit_finance_balance()
                    elif scroll_track and scroll_track.collidepoint(event.pos):
                        finance_scroll.handle_track_click(scroll_track, event.pos[1])
                    else:
                        finance_active_input = False
                elif state == GameState.PRODUCT_EDITOR:
                    (
                        panel, boxes, cat_prev, cat_box, cat_next,
                        minimum_down, minimum_up, maximum_down, maximum_up,
                        save_button, cancel_button,
                    ) = product_editor_layout()
                    for field_name, field_box in boxes.items():
                        if field_box.collidepoint(event.pos):
                            catalogue_active_input = field_name
                            break
                    else:
                        catalogue_active_input = None
                        if cat_prev.collidepoint(event.pos):
                            cur_cat = catalogue_fields.get("category", CATEGORIES[0])
                            idx = (CATEGORIES.index(cur_cat) - 1) % len(CATEGORIES) if cur_cat in CATEGORIES else 0
                            catalogue_fields["category"] = CATEGORIES[idx]
                        elif cat_next.collidepoint(event.pos):
                            cur_cat = catalogue_fields.get("category", CATEGORIES[0])
                            idx = (CATEGORIES.index(cur_cat) + 1) % len(CATEGORIES) if cur_cat in CATEGORIES else 0
                            catalogue_fields["category"] = CATEGORIES[idx]
                        elif minimum_down.collidepoint(event.pos):
                            try:
                                catalogue_fields["minimum_quantity"] = str(
                                    max(0, int(catalogue_fields["minimum_quantity"] or "0") - 1)
                                )
                            except ValueError:
                                catalogue_fields["minimum_quantity"] = "0"
                        elif minimum_up.collidepoint(event.pos):
                            try:
                                catalogue_fields["minimum_quantity"] = str(
                                    int(catalogue_fields["minimum_quantity"] or "0") + 1
                                )
                            except ValueError:
                                catalogue_fields["minimum_quantity"] = "1"
                        elif maximum_down.collidepoint(event.pos):
                            try:
                                catalogue_fields["maximum_quantity"] = str(
                                    max(0, int(catalogue_fields["maximum_quantity"] or "0") - 1)
                                )
                            except ValueError:
                                catalogue_fields["maximum_quantity"] = "0"
                        elif maximum_up.collidepoint(event.pos):
                            try:
                                catalogue_fields["maximum_quantity"] = str(
                                    int(catalogue_fields["maximum_quantity"] or "0") + 1
                                )
                            except ValueError:
                                catalogue_fields["maximum_quantity"] = "1"
                        elif cancel_button.collidepoint(event.pos):
                            state = GameState.CATALOGUE_MENU
                            catalogue_active_input = None
                            catalogue_message = ""
                        elif save_button.collidepoint(event.pos):
                            try:
                                product_values = parse_catalogue_values(catalogue_fields)
                                cat = catalogue_fields.get("category", CATEGORIES[0])
                                ws_price = round(product_values[2] * 0.6, 2)
                                if catalogue_add_mode:
                                    add_catalogue_product(map_path, *product_values, category=cat, wholesale_price=ws_price)
                                    product_catalogue.append((*product_values, cat, ws_price))
                                    expanded_categories.add(cat)
                                else:
                                    old_product = catalogue_item_by_id(
                                        product_catalogue, catalogue_editing_item_id
                                    )
                                    update_catalogue_product(
                                        map_path,
                                        catalogue_editing_item_id,
                                        *product_values,
                                        category=cat,
                                        wholesale_price=ws_price,
                                    )
                                    product_catalogue[product_catalogue.index(old_product)] = (*product_values, cat, ws_price)
                                    for sh in shelves:
                                        for s_idx, s_it in enumerate(sh.items):
                                            if s_it[0] == product_values[0]:
                                                sh.items[s_idx] = (s_it[0], product_values[1], s_it[2], s_it[3])
                                product_catalogue.sort(key=lambda item: (item[5] if len(item) > 5 else "General", item[0]))
                                selected_catalogue_id = product_values[0]
                                catalogue_active_input = None
                                catalogue_message = ""
                                state = GameState.CATALOGUE_MENU
                            except ValueError:
                                catalogue_message = (
                                    "Enter a valid ID, name, price, and quantity range."
                                )
                            except DatabaseSetupError as error:
                                catalogue_message = str(error)
                elif state == GameState.CATALOGUE_MENU:
                    (
                        panel, viewport, doc_elements, total_content_height, max_scroll, clamped_scroll,
                        add_button, edit_button, scroll_track, scroll_thumb,
                    ) = catalogue_menu_layout(
                        product_catalogue, selected_catalogue_id, expanded_categories, catalogue_scroll_y
                    )
                    if add_button.collidepoint(event.pos):
                        catalogue_add_mode = True
                        catalogue_editing_item_id = None
                        default_cat = next(iter(expanded_categories)) if expanded_categories else CATEGORIES[0]
                        catalogue_fields = {
                            "item_id": "",
                            "item_name": "",
                            "category": default_cat,
                            "price": "",
                            "minimum_quantity": "",
                            "maximum_quantity": "",
                        }
                        catalogue_active_input = None
                        catalogue_message = ""
                        state = GameState.PRODUCT_EDITOR
                    elif edit_button and edit_button.collidepoint(event.pos):
                        selected_product = catalogue_item_by_id(
                            product_catalogue, selected_catalogue_id
                        )
                        if selected_product:
                            (
                                item_id, item_name, price,
                                minimum_quantity, maximum_quantity,
                            ) = selected_product[:5]
                            cat = selected_product[5] if len(selected_product) > 5 else CATEGORIES[0]
                            catalogue_add_mode = False
                            catalogue_editing_item_id = item_id
                            catalogue_fields = {
                                "item_id": str(item_id),
                                "item_name": item_name,
                                "category": cat,
                                "price": f"{price:.2f}",
                                "minimum_quantity": str(minimum_quantity),
                                "maximum_quantity": str(maximum_quantity),
                            }
                            catalogue_active_input = None
                            catalogue_message = ""
                            state = GameState.PRODUCT_EDITOR
                    elif scroll_track and scroll_track.collidepoint(event.pos):
                        rel_y = event.pos[1] - scroll_track.y
                        ratio = max(0.0, min(1.0, rel_y / scroll_track.height))
                        catalogue_scroll_y = int(ratio * max_scroll)
                    elif viewport.collidepoint(event.pos):
                        for elem_type, rect, data in doc_elements:
                            screen_rect = rect.move(viewport.x, viewport.y - clamped_scroll)
                            if screen_rect.bottom < viewport.top or screen_rect.top > viewport.bottom:
                                continue
                            if elem_type == "category_header":
                                if screen_rect.collidepoint(event.pos):
                                    cat = data[0]
                                    if cat in expanded_categories:
                                        expanded_categories.remove(cat)
                                    else:
                                        expanded_categories.add(cat)
                                    _, new_total = build_catalogue_elements(product_catalogue, expanded_categories)
                                    catalogue_scroll_y = max(0, min(catalogue_scroll_y, max(0, new_total - viewport.height)))
                                    break
                            elif elem_type == "product_row":
                                item, del_rect = data
                                screen_del = del_rect.move(viewport.x, viewport.y - clamped_scroll)
                                if screen_del.collidepoint(event.pos):
                                    try:
                                        delete_catalogue_product(map_path, item[0])
                                        product_catalogue.remove(item)
                                        if selected_catalogue_id == item[0]:
                                            selected_catalogue_id = None
                                        catalogue_message = ""
                                    except DatabaseSetupError as error:
                                        catalogue_message = str(error)
                                    break
                                elif screen_rect.collidepoint(event.pos):
                                    selected_catalogue_id = item[0]
                                    catalogue_message = ""
                                    break
                elif state == GameState.SHELF_MENU:
                    (
                        panel, header_y, rows, add_button, edit_button,
                        cat_prev_button, cat_box_rect, cat_next_button,
                        sell_down_button, sell_qty_box, sell_up_button, sell_button,
                        visible_rows, scroll_track, scroll_thumb,
                    ) = shelf_menu_layout(
                        selected_shelf, selected_item_id, shelf_first_item, product_catalogue
                    )
                    if sell_qty_box and sell_qty_box.collidepoint(event.pos):
                        sell_active_input = True
                    else:
                        sell_active_input = False

                    if cat_prev_button.collidepoint(event.pos) or cat_next_button.collidepoint(event.pos):
                        step = -1 if cat_prev_button.collidepoint(event.pos) else 1
                        cur_cat = selected_shelf.category if selected_shelf.category in SHELF_CATEGORIES else "General"
                        new_cat = SHELF_CATEGORIES[(SHELF_CATEGORIES.index(cur_cat) + step) % len(SHELF_CATEGORIES)]
                        try:
                            update_shelf_category(map_path, selected_shelf.shelf_id, new_cat)
                            selected_shelf.category = new_cat
                            recompute_shelf_display_names(shelves)
                            selected_item_id = None
                            sell_qty_text = "1"
                            shelf_scroll.set_counts(len(selected_shelf.get_visible_items(product_catalogue)), 8)
                            shelf_scroll.scroll_to(0)
                            shelf_first_item = 0
                            menu_message = f"Category set to {new_cat} ({selected_shelf.display_name})"
                        except DatabaseSetupError as error:
                            menu_message = str(error)
                    elif add_button.collidepoint(event.pos):
                        if selected_shelf.get_total_quantity(product_catalogue) >= MAX_SHELF_CAPACITY:
                            menu_message = f"Shelf capacity full ({MAX_SHELF_CAPACITY}/{MAX_SHELF_CAPACITY} units)!"
                        elif not available_products_for_shelf(selected_shelf, product_catalogue):
                            menu_message = "All products for this category are already on this shelf."
                        else:
                            editor_product = None
                            quantity_text = ""
                            price_text = ""
                            active_input = None
                            product_picker_open = False
                            product_picker_first_item = 0
                            menu_message = ""
                            state = GameState.ADD_ITEM
                    elif edit_button and edit_button.collidepoint(event.pos):
                        selected_item = find_shelf_item(selected_shelf, selected_item_id)
                        if selected_item:
                            editing_item_id = selected_item[0]
                            editor_product = selected_item
                            quantity_text = str(selected_item[2])
                            price_text = f"{selected_item[3]:.2f}"
                            active_input = None
                            menu_message = ""
                            state = GameState.EDIT_ITEM
                    elif sell_down_button and sell_down_button.collidepoint(event.pos):
                        try:
                            cur_s = int(sell_qty_text or "1")
                        except ValueError:
                            cur_s = 1
                        sell_qty_text = str(max(1, cur_s - 1))
                    elif sell_up_button and sell_up_button.collidepoint(event.pos):
                        selected_item = find_shelf_item(selected_shelf, selected_item_id)
                        max_s = selected_item[2] if selected_item else 1
                        try:
                            cur_s = int(sell_qty_text or "1")
                        except ValueError:
                            cur_s = 1
                        sell_qty_text = str(min(max_s, cur_s + 1))
                    elif sell_button and sell_button.collidepoint(event.pos):
                        selected_item = find_shelf_item(selected_shelf, selected_item_id)
                        if selected_item:
                            try:
                                s_qty = int(sell_qty_text or "0")
                                if s_qty <= 0:
                                    menu_message = "Enter a valid quantity to sell (at least 1)."
                                else:
                                    new_bal, revenue, new_qty = sell_shelf_stock(
                                        map_path, selected_shelf.shelf_id, selected_item_id, s_qty
                                    )
                                    finance_balance, finance_history = load_finance_data(map_path)
                                    finance_scroll.set_counts(len(finance_history), 7)
                                    if interact_sound:
                                        interact_sound.play()
                                    idx = selected_shelf.items.index(selected_item)
                                    if new_qty <= 0:
                                        selected_shelf.items.pop(idx)
                                        selected_item_id = None
                                        sell_qty_text = "1"
                                    else:
                                        selected_shelf.items[idx] = (
                                            selected_item[0], selected_item[1], new_qty, selected_item[3]
                                        )
                                        sell_qty_text = str(min(s_qty, new_qty))
                                    shelf_scroll.set_counts(len(selected_shelf.get_visible_items(product_catalogue)), 8)
                                    shelf_first_item = shelf_scroll.get_first_visible_index()
                                    menu_message = f"Sold {s_qty}x {selected_item[1]} — Profit: +Rs. {revenue:,.2f}!"
                            except ValueError:
                                menu_message = "Enter a valid quantity to sell."
                            except DatabaseSetupError as error:
                                menu_message = str(error)
                    elif scroll_track and scroll_track.collidepoint(event.pos):
                        shelf_scroll.handle_track_click(scroll_track, event.pos[1])
                    else:
                        for item, row_rect, delete_rect in rows:
                            if delete_rect.collidepoint(event.pos):
                                try:
                                    delete_shelf_item(map_path, selected_shelf.shelf_id, item[0])
                                    selected_shelf.items.remove(item)
                                    if selected_item_id == item[0]:
                                        selected_item_id = None
                                        sell_qty_text = "1"
                                    shelf_scroll.set_counts(len(selected_shelf.get_visible_items(product_catalogue)), 8)
                                    shelf_first_item = shelf_scroll.get_first_visible_index()
                                    menu_message = f"Removed {item[1]} and returned {item[2]} units to Storage Depot."
                                except DatabaseSetupError as error:
                                    menu_message = str(error)
                                break
                            if row_rect.collidepoint(event.pos):
                                selected_item_id = item[0]
                                sell_qty_text = "1"
                                menu_message = ""
                                break
                elif state in (GameState.EDIT_ITEM, GameState.ADD_ITEM):
                    included_item_id = editing_item_id if state == GameState.EDIT_ITEM else None
                    available_products = available_products_for_shelf(
                        selected_shelf, product_catalogue, included_item_id
                    )
                    if product_picker_open:
                        picker_panel, picker_rows, picker_track, picker_thumb, picker_cancel, picker_visible = product_picker_layout(
                            available_products, product_picker_first_item
                        )
                        if picker_cancel.collidepoint(event.pos):
                            product_picker_open = False
                        elif picker_track.collidepoint(event.pos):
                            picker_scroll.handle_track_click(picker_track, event.pos[1])
                        else:
                            for product, row_rect in picker_rows:
                                if row_rect.collidepoint(event.pos):
                                    editor_product = product
                                    price_text = f"{product[2]:.2f}"
                                    if state == GameState.ADD_ITEM:
                                        space_left = max(1, MAX_SHELF_CAPACITY - selected_shelf.get_total_quantity(product_catalogue))
                                        quantity_text = str(min(product[3], space_left))
                                    product_picker_open = False
                                    active_input = None
                                    menu_message = ""
                                    break
                    else:
                        add_mode = state == GameState.ADD_ITEM
                        (
                            panel, product_button, quantity_down, quantity_up, quantity_box,
                            price_down, price_up, price_box, save_button, cancel_button,
                        ) = item_editor_layout()
                        if product_button.collidepoint(event.pos):
                            product_picker_open = True
                            picker_scroll.set_counts(len(available_products), 8)
                            picker_scroll.scroll_to(0)
                            product_picker_first_item = 0
                        elif quantity_box.collidepoint(event.pos):
                            active_input = "quantity"
                        elif price_box.collidepoint(event.pos):
                            active_input = "price"
                        elif quantity_down.collidepoint(event.pos):
                            try:
                                quantity_text = str(max(1, int(quantity_text or "1") - 1))
                            except ValueError:
                                quantity_text = "1"
                        elif quantity_up.collidepoint(event.pos):
                            try:
                                quantity_text = str(int(quantity_text or "0") + 1)
                            except ValueError:
                                quantity_text = "1"
                        elif price_down.collidepoint(event.pos):
                            try:
                                price_text = f"{max(0.0, float(price_text or '0') - 1):.2f}"
                            except ValueError:
                                price_text = "0.00"
                        elif price_up.collidepoint(event.pos):
                            try:
                                price_text = f"{float(price_text or '0') + 1:.2f}"
                            except ValueError:
                                price_text = "1.00"
                        elif cancel_button.collidepoint(event.pos):
                            state = GameState.SHELF_MENU
                            active_input = None
                            menu_message = ""
                        elif save_button.collidepoint(event.pos):
                            try:
                                quantity, price = parse_editor_values(quantity_text, price_text)
                                if add_mode:
                                    if editor_product is None:
                                        raise ValueError
                                    item_id, item_name = editor_product[0], editor_product[1]
                                    add_shelf_item(
                                        map_path, selected_shelf.shelf_id,
                                        item_id, item_name, quantity, price,
                                    )
                                    selected_shelf.items.append((item_id, item_name, quantity, price))
                                    selected_shelf.items.sort(key=lambda item: item[0])
                                    shelf_scroll.set_counts(len(selected_shelf.get_visible_items(product_catalogue)), 8)
                                    selected_item_id = item_id
                                    sell_qty_text = "1"
                                else:
                                    update_shelf_item(
                                        map_path, selected_shelf.shelf_id,
                                        editing_item_id, editor_product[0], editor_product[1], quantity, price,
                                    )
                                    old_item = find_shelf_item(selected_shelf, editing_item_id)
                                    selected_shelf.items[selected_shelf.items.index(old_item)] = (
                                        editor_product[0], editor_product[1], quantity, price
                                    )
                                    selected_shelf.items.sort(key=lambda item: item[0])
                                    shelf_scroll.set_counts(len(selected_shelf.get_visible_items(product_catalogue)), 8)
                                    selected_item_id = editor_product[0]
                                    sell_qty_text = "1"
                                menu_message = ""
                                active_input = None
                                state = GameState.SHELF_MENU
                            except ValueError:
                                menu_message = "Choose a product and enter a valid quantity and price."
                            except DatabaseSetupError as error:
                                menu_message = str(error)
                elif state == GameState.EMPLOYEE_MENU:
                    (
                        panel, header_y, rows, add_button, edit_button,
                        visible_rows, scroll_track, scroll_thumb,
                    ) = employee_menu_layout(employees, selected_employee_id, employee_start)
                    if add_button.collidepoint(event.pos):
                        employee_add_mode = True
                        employee_editing_id = None
                        next_id = max([e[0] for e in employees], default=100) + 1
                        employee_fields = {
                            "employee_id": str(next_id),
                            "name": "",
                            "role": "Cashier",
                            "salary": "18000.00",
                        }
                        employee_active_input = "name"
                        employee_message = ""
                        state = GameState.EMPLOYEE_EDITOR
                    elif edit_button and edit_button.collidepoint(event.pos):
                        selected_emp = next((e for e in employees if e[0] == selected_employee_id), None)
                        if selected_emp:
                            employee_add_mode = False
                            employee_editing_id = selected_emp[0]
                            employee_fields = {
                                "employee_id": str(selected_emp[0]),
                                "name": selected_emp[1],
                                "role": selected_emp[2],
                                "salary": f"{selected_emp[3]:.2f}",
                            }
                            employee_active_input = "name"
                            employee_message = ""
                            state = GameState.EMPLOYEE_EDITOR
                    elif scroll_track and scroll_track.collidepoint(event.pos):
                        employee_scroll.handle_track_click(scroll_track, event.pos[1])
                    else:
                        for emp, row_rect, delete_rect in rows:
                            if delete_rect.collidepoint(event.pos):
                                try:
                                    delete_employee(map_path, emp[0])
                                    employees.remove(emp)
                                    if selected_employee_id == emp[0]:
                                        selected_employee_id = None
                                    employee_scroll.set_counts(len(employees), 7)
                                    employee_start = employee_scroll.get_first_visible_index()
                                    employee_message = ""
                                except DatabaseSetupError as error:
                                    employee_message = str(error)
                                break
                            if row_rect.collidepoint(event.pos):
                                selected_employee_id = emp[0]
                                employee_message = ""
                                break
                elif state == GameState.EMPLOYEE_EDITOR:
                    (
                        panel, boxes, role_prev, role_box, role_next,
                        salary_down, salary_up, save_button, cancel_button,
                    ) = employee_editor_layout()
                    for field_name, field_box in boxes.items():
                        if field_box.collidepoint(event.pos):
                            employee_active_input = field_name
                            break
                    else:
                        if role_prev.collidepoint(event.pos):
                            curr_idx = ROLES.index(employee_fields["role"]) if employee_fields["role"] in ROLES else 0
                            employee_fields["role"] = ROLES[(curr_idx - 1) % len(ROLES)]
                        elif role_next.collidepoint(event.pos):
                            curr_idx = ROLES.index(employee_fields["role"]) if employee_fields["role"] in ROLES else 0
                            employee_fields["role"] = ROLES[(curr_idx + 1) % len(ROLES)]
                        elif salary_down.collidepoint(event.pos):
                            try:
                                val = max(0.0, float(employee_fields["salary"] or "0") - 1000)
                                employee_fields["salary"] = f"{val:.2f}"
                            except ValueError:
                                employee_fields["salary"] = "0.00"
                        elif salary_up.collidepoint(event.pos):
                            try:
                                val = float(employee_fields["salary"] or "0") + 1000
                                employee_fields["salary"] = f"{val:.2f}"
                            except ValueError:
                                employee_fields["salary"] = "1000.00"
                        elif cancel_button.collidepoint(event.pos):
                            state = GameState.EMPLOYEE_MENU
                            employee_active_input = None
                            employee_message = ""
                        elif save_button.collidepoint(event.pos):
                            try:
                                emp_id = int(employee_fields["employee_id"])
                                emp_name = employee_fields["name"].strip()
                                emp_role = employee_fields["role"].strip()
                                emp_salary = float(employee_fields["salary"])
                                if not emp_name:
                                    raise ValueError("Staff name cannot be empty.")
                                if emp_salary < 0:
                                    raise ValueError("Salary cannot be negative.")
                                if employee_add_mode:
                                    add_employee(map_path, emp_id, emp_name, emp_role, emp_salary)
                                else:
                                    update_employee(map_path, employee_editing_id, emp_id, emp_name, emp_role, emp_salary)
                                employees = list(load_employees(map_path))
                                selected_employee_id = emp_id
                                employee_scroll.set_counts(len(employees), 7)
                                employee_active_input = None
                                employee_message = ""
                                state = GameState.EMPLOYEE_MENU
                            except ValueError as ve:
                                employee_message = str(ve) if str(ve) else "Enter a valid ID, name, and salary."
                            except DatabaseSetupError as error:
                                employee_message = str(error)
                elif state == GameState.STORAGE_MENU:
                    (
                        panel, viewport, doc_elements, total_content_height, max_scroll, clamped_scroll,
                        locations_button, order_button, scroll_track, scroll_thumb,
                    ) = storage_menu_layout(
                        storage_items, selected_storage_id, storage_expanded_categories, storage_scroll_y
                    )
                    if locations_button and locations_button.collidepoint(event.pos):
                        distribution_list = get_product_shelf_distribution(map_path, selected_storage_id)
                        state = GameState.STORAGE_DISTRIBUTION
                    elif order_button and order_button.collidepoint(event.pos):
                        order_quantity_text = "10"
                        order_message = ""
                        order_active_input = False
                        state = GameState.STORAGE_ORDER
                    elif scroll_track and scroll_track.collidepoint(event.pos):
                        rel_y = event.pos[1] - scroll_track.y
                        ratio = max(0.0, min(1.0, rel_y / scroll_track.height))
                        storage_scroll_y = int(ratio * max_scroll)
                    elif viewport.collidepoint(event.pos):
                        for elem_type, rect, data in doc_elements:
                            screen_rect = rect.move(viewport.x, viewport.y - clamped_scroll)
                            if screen_rect.bottom < viewport.top or screen_rect.top > viewport.bottom:
                                continue
                            if elem_type == "category_header":
                                if screen_rect.collidepoint(event.pos):
                                    cat = data[0]
                                    if cat in storage_expanded_categories:
                                        storage_expanded_categories.remove(cat)
                                    else:
                                        storage_expanded_categories.add(cat)
                                    _, new_total = build_storage_elements(storage_items, storage_expanded_categories)
                                    storage_scroll_y = max(0, min(storage_scroll_y, max(0, new_total - viewport.height)))
                                    break
                            elif elem_type == "storage_row":
                                if screen_rect.collidepoint(event.pos):
                                    selected_storage_id = data[0]
                                    storage_message = ""
                                    break
                elif state == GameState.STORAGE_DISTRIBUTION:
                    panel, close_button = storage_distribution_layout()
                    if close_button.collidepoint(event.pos):
                        state = GameState.STORAGE_MENU
                elif state == GameState.STORAGE_ORDER:
                    (
                        panel, order_down_10, order_down, order_box, order_up, order_up_10,
                        confirm_button, cancel_button,
                    ) = storage_order_layout()
                    selected_item = next((i for i in storage_items if i[0] == selected_storage_id), None)
                    if order_box.collidepoint(event.pos):
                        order_active_input = True
                    else:
                        order_active_input = False
                        try:
                            cur_q = int(order_quantity_text or "0")
                        except ValueError:
                            cur_q = 0
                        if order_down_10.collidepoint(event.pos):
                            order_quantity_text = str(max(1, cur_q - 10))
                        elif order_down.collidepoint(event.pos):
                            order_quantity_text = str(max(1, cur_q - 1))
                        elif order_up.collidepoint(event.pos):
                            order_quantity_text = str(cur_q + 1)
                        elif order_up_10.collidepoint(event.pos):
                            order_quantity_text = str(cur_q + 10)
                        elif cancel_button.collidepoint(event.pos):
                            state = GameState.STORAGE_MENU
                        elif confirm_button.collidepoint(event.pos) and selected_item:
                            try:
                                qty = int(order_quantity_text or "0")
                                if qty <= 0:
                                    order_message = "Order quantity must be at least 1."
                                else:
                                    new_bal, cost = order_storage_stock(map_path, selected_storage_id, qty)
                                    finance_balance, finance_history = load_finance_data(map_path)
                                    storage_items = list(load_storage_inventory(map_path))
                                    storage_message = f"Ordered {qty} units of {selected_item[1]} for Rs. {cost:,.2f}!"
                                    state = GameState.STORAGE_MENU
                            except DatabaseSetupError as dse:
                                order_message = str(dse)
            elif event.type == pygame.MOUSEWHEEL and state == GameState.CATALOGUE_MENU:
                _, total_h = build_catalogue_elements(product_catalogue, expanded_categories)
                max_scroll = max(0, total_h - 396)
                catalogue_scroll_y = max(0, min(catalogue_scroll_y - event.y * 36, max_scroll))
            elif event.type == pygame.MOUSEWHEEL and state == GameState.STORAGE_MENU:
                _, total_h = build_storage_elements(storage_items, storage_expanded_categories)
                max_scroll = max(0, total_h - 396)
                storage_scroll_y = max(0, min(storage_scroll_y - event.y * 36, max_scroll))
            elif event.type == pygame.MOUSEWHEEL and state == GameState.FINANCE_MENU:
                finance_scroll.scroll_by(-event.y)
            elif event.type == pygame.MOUSEWHEEL and state == GameState.SHELF_MENU:
                shelf_scroll.scroll_by(-event.y)
            elif event.type == pygame.MOUSEWHEEL and state == GameState.EMPLOYEE_MENU:
                employee_scroll.scroll_by(-event.y)
            elif (
                event.type == pygame.MOUSEWHEEL
                and state in (GameState.EDIT_ITEM, GameState.ADD_ITEM)
                and product_picker_open
            ):
                picker_scroll.scroll_by(-event.y)

        if state == GameState.PLAYING:
            player.update(dt, solid_rects)
            targeted_object = get_targeted_object(
                player, shelves, catalogue, cash_register, employee_terminal, storage_depot
            )

        draw_world(
            screen,
            player,
            walls,
            shelves,
            catalogue,
            cash_register,
            employee_terminal,
            storage_depot,
            targeted_object,
            fonts,
        )
        if state == GameState.SHELF_MENU:
            draw_shelf_menu(
                screen,
                fonts,
                selected_shelf,
                selected_item_id,
                shelf_first_item,
                menu_message,
                product_catalogue=product_catalogue,
                sell_qty_text=sell_qty_text,
                sell_active_input=sell_active_input,
                cursor_visible=cursor_visible,
            )
        elif state in (GameState.EDIT_ITEM, GameState.ADD_ITEM):
            draw_item_editor(
                screen,
                fonts,
                editor_product,
                quantity_text,
                price_text,
                state == GameState.ADD_ITEM,
                active_input,
                cursor_visible=cursor_visible,
                message=menu_message,
                shelf=selected_shelf,
            )
            if product_picker_open:
                draw_product_picker(
                    screen,
                    fonts,
                    available_products_for_shelf(
                        selected_shelf,
                        product_catalogue,
                        editing_item_id if state == GameState.EDIT_ITEM else None,
                    ),
                    product_picker_first_item,
                )
        elif state == GameState.CATALOGUE_MENU:
            draw_catalogue_menu(
                screen,
                fonts,
                product_catalogue,
                selected_catalogue_id,
                expanded_categories,
                catalogue_scroll_y,
                catalogue_message,
            )
        elif state == GameState.PRODUCT_EDITOR:
            draw_product_editor(
                screen,
                fonts,
                catalogue_fields,
                catalogue_active_input,
                catalogue_add_mode,
                catalogue_message,
                cursor_visible=cursor_visible,
            )
        elif state == GameState.FINANCE_MENU:
            draw_finance_menu(
                screen,
                fonts,
                finance_balance,
                finance_balance_text,
                finance_history,
                finance_history_start,
                finance_active_input,
                finance_message,
                cursor_visible=cursor_visible,
            )
        elif state == GameState.EMPLOYEE_MENU:
            draw_employee_menu(
                screen,
                fonts,
                employees,
                selected_employee_id,
                employee_start,
                employee_message,
            )
        elif state == GameState.EMPLOYEE_EDITOR:
            draw_employee_editor(
                screen,
                fonts,
                employee_fields,
                employee_active_input,
                employee_add_mode,
                employee_message,
                cursor_visible=cursor_visible,
            )
        elif state == GameState.STORAGE_MENU:
            draw_storage_menu(
                screen,
                fonts,
                storage_items,
                selected_storage_id,
                storage_expanded_categories,
                storage_scroll_y,
                finance_balance,
                storage_message,
            )
        elif state == GameState.STORAGE_DISTRIBUTION:
            selected_item = next((i for i in storage_items if i[0] == selected_storage_id), None)
            if selected_item:
                draw_storage_distribution(screen, fonts, selected_item, distribution_list, shelves=shelves)
        elif state == GameState.STORAGE_ORDER:
            selected_item = next((i for i in storage_items if i[0] == selected_storage_id), None)
            if selected_item:
                draw_storage_order(
                    screen,
                    fonts,
                    selected_item,
                    order_quantity_text,
                    finance_balance,
                    order_message,
                    order_active_input,
                    cursor_visible=cursor_visible,
                )
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
