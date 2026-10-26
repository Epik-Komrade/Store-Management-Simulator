"""First playable store-management conversion"""

import math
import os
import sys
import pygame

from database_setup import (
    DatabaseSetupError,
    add_catalogue_product,
    add_shelf_item,
    delete_catalogue_product,
    delete_shelf_item,
    ensure_store_database,
    load_finance_data,
    load_product_catalogue,
    load_shelf_inventory,
    set_store_balance,
    update_catalogue_product,
    update_shelf_item,
)

SCREEN_WIDTH = 1000
MAP_HEIGHT = 600
SCREEN_HEIGHT = 680
HUD_HEIGHT = SCREEN_HEIGHT - MAP_HEIGHT
FPS = 60
TILE_SIZE = 40
PLAYER_SPEED = 210  # pixels per second
INTERACTION_DISTANCE = 52

WINDOW_COLOR = (231, 239, 245)
FLOOR_COLOR = (250, 247, 238)
WALL_COLOR = (174, 197, 214)

# Shelf Palette (Warm Wood / Amber)
SHELF_COLOR = (207, 157, 96)
SHELF_EDGE_COLOR = (132, 91, 48)
SHELF_BUTTON_COLOR = (148, 103, 56)
SHELF_SELECTED_COLOR = (248, 238, 224)

# Product Catalogue Palette (Slate Navy / Steel Blue)
CATALOGUE_COLOR = (123, 170, 194)
CATALOGUE_EDGE_COLOR = (53, 104, 133)
CATALOGUE_BUTTON_COLOR = (60, 115, 146)
CATALOGUE_SELECTED_COLOR = (218, 235, 246)

# Cash Register Palette (Forest Emerald / Mint)
REGISTER_COLOR = (112, 177, 151)
REGISTER_EDGE_COLOR = (44, 111, 86)
REGISTER_BUTTON_COLOR = (44, 111, 86)
REGISTER_SELECTED_COLOR = (222, 242, 232)

INFO_PANEL_COLOR = (213, 228, 239)
PLAYER_COLOR = (190, 190, 190)
TEXT_COLOR = (42, 57, 70)
ACCENT_COLOR = (55, 126, 174)


class GameState:
    PLAYING = 0
    SHELF_MENU = 1
    CATALOGUE_MENU = 2
    EDIT_ITEM = 3
    ADD_ITEM = 4
    PRODUCT_EDITOR = 5
    FINANCE_MENU = 6


class Shelf:
    #solid store shelf with inventory loaded from MySQL

    def __init__(self, shelf_id, grid_x, grid_y, items):
        self.shelf_id = shelf_id
        self.rect = pygame.Rect(grid_x * TILE_SIZE, grid_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
        self.items = list(items)


class ProductCatalogue:
    #solid store catalogue terminal, placed once in the map as C

    def __init__(self, grid_x, grid_y):
        self.rect = pygame.Rect(grid_x * TILE_SIZE, grid_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)


class CashRegister:
    #one finance terminal, placed once in the map as R

    def __init__(self, grid_x, grid_y):
        self.rect = pygame.Rect(grid_x * TILE_SIZE, grid_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)

#___________________________________________PLAYER CLASS_______________________________________________________________

class Player:
    #minimal manager/player character

    def __init__(self, position):
        self.rect = pygame.Rect(position[0], position[1], 24, 24)
        self.position = pygame.Vector2(self.rect.topleft)
        self.angle = 0.0

    def update(self, dt, solid_rects):
        keys = pygame.key.get_pressed()
        direction = pygame.Vector2(
            int(keys[pygame.K_d]) - int(keys[pygame.K_a]),
            int(keys[pygame.K_s]) - int(keys[pygame.K_w]),
        )
        if direction.length_squared() > 0:
            direction = direction.normalize()

        self._move(direction.x * PLAYER_SPEED * dt, 0, solid_rects)
        self._move(0, direction.y * PLAYER_SPEED * dt, solid_rects)

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

    return walls, shelves, catalogue, cash_register, player_spawn

#_________________________________________SHELF INTERACTION CHECKS_________________________________________________________________

def distance_to_rect(point, rect):
    #shortest distance from a point to a rectangle
    nearest_x = max(rect.left, min(point[0], rect.right))
    nearest_y = max(rect.top, min(point[1], rect.bottom))
    return math.hypot(point[0] - nearest_x, point[1] - nearest_y)


def get_targeted_object(player, shelves, catalogue, cash_register):
    #store objects are usable only when close to the manager and mouse aimed
    mouse_position = pygame.mouse.get_pos()
    candidates = [
        item
        for item in [*shelves, catalogue, cash_register]
        if item.rect.collidepoint(mouse_position)
        and distance_to_rect(player.rect.center, item.rect) <= INTERACTION_DISTANCE
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda item: distance_to_rect(player.rect.center, item.rect))

#________________________________________SHELF MENU__________________________________________________________________

def shelf_menu_layout(shelf, selected_item_id, first_item):
    row_height = 44
    visible_rows = min(8, max(1, len(shelf.items)))
    panel_height = 190 + visible_rows * row_height
    panel = pygame.Rect(180, max(14, (MAP_HEIGHT - panel_height) // 2), 640, panel_height)
    header_y = panel.y + 68
    rows = []
    for row_index, item in enumerate(shelf.items[first_item:first_item + visible_rows]):
        row_rect = pygame.Rect(panel.x + 22, header_y + 39 + row_index * row_height, 542, 38)
        delete_rect = pygame.Rect(panel.right - 52, row_rect.y + 2, 28, 32)
        rows.append((item, row_rect, delete_rect))

    add_button = pygame.Rect(panel.x + 24, panel.bottom - 78, 42, 36)
    edit_button = None
    if selected_item_id is not None:
        edit_button = pygame.Rect(panel.x + 78, panel.bottom - 78, 100, 36)

    scroll_track = None
    scroll_thumb = None
    if len(shelf.items) > visible_rows:
        scroll_track = pygame.Rect(panel.right - 16, header_y + 42, 8, visible_rows * row_height - 8)
        scroll_thumb = make_scroll_thumb(scroll_track, len(shelf.items), visible_rows, first_item)
    return panel, header_y, rows, add_button, edit_button, visible_rows, scroll_track, scroll_thumb


def make_scroll_thumb(track, item_count, visible_rows, first_item):
    max_start = max(1, item_count - visible_rows)
    thumb_height = max(28, round(track.height * visible_rows / item_count))
    travel = track.height - thumb_height
    thumb_y = track.y + round(travel * first_item / max_start)
    return pygame.Rect(track.x, thumb_y, track.width, thumb_height)


def scroll_start_from_mouse(track, item_count, visible_rows, mouse_y):
    max_start = max(0, item_count - visible_rows)
    if max_start == 0:
        return 0
    thumb_height = max(28, round(track.height * visible_rows / item_count))
    travel = max(1, track.height - thumb_height)
    thumb_top = max(track.y, min(mouse_y - thumb_height // 2, track.bottom - thumb_height))
    return round((thumb_top - track.y) * max_start / travel)


def draw_button(surface, rect, label, color, font):
    pygame.draw.rect(surface, color, rect, border_radius=7)
    label_surface = font.render(label, True, (255, 255, 255))
    surface.blit(label_surface, label_surface.get_rect(center=rect.center))


def draw_shelf_menu(surface, fonts, shelf, selected_item_id, first_item, message):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((35, 50, 65, 115))
    surface.blit(overlay, (0, 0))

    panel, header_y, rows, add_button, edit_button, visible_rows, scroll_track, scroll_thumb = shelf_menu_layout(
        shelf, selected_item_id, first_item
    )
    pygame.draw.rect(surface, (255, 255, 255), panel, border_radius=10)
    pygame.draw.rect(surface, SHELF_EDGE_COLOR, panel, 3, border_radius=10)

    title = fonts["title"].render(f"Shelf {shelf.shelf_id} Inventory", True, TEXT_COLOR)
    surface.blit(title, (panel.x + 28, panel.y + 18))

    columns = [("Item ID", 30), ("Item name", 150), ("Quantity", 330), ("Price", 460)]
    pygame.draw.line(surface, SHELF_EDGE_COLOR, (panel.x + 25, header_y + 28), (panel.right - 25, header_y + 28), 2)
    for heading, offset in columns:
        header = fonts["body"].render(heading, True, SHELF_EDGE_COLOR)
        surface.blit(header, (panel.x + offset, header_y))

    for item, row_rect, delete_rect in rows:
        item_id, item_name, quantity, price = item
        if item_id == selected_item_id:
            pygame.draw.rect(surface, SHELF_SELECTED_COLOR, row_rect, border_radius=5)
        values = (str(item_id), item_name, str(quantity), f"Rs. {price:.2f}")
        for value, (_, offset) in zip(values, columns):
            text = fonts["body"].render(value, True, TEXT_COLOR)
            surface.blit(text, (panel.x + offset, row_rect.y + 7))
        draw_button(surface, delete_rect, "X", (184, 79, 79), fonts["body"])

    draw_button(surface, add_button, "+", SHELF_BUTTON_COLOR, fonts["body"])
    if edit_button:
        draw_button(surface, edit_button, "Edit", SHELF_EDGE_COLOR, fonts["body"])

    if message:
        message_text = fonts["small"].render(message, True, (178, 65, 65))
        surface.blit(message_text, (panel.x + 24, panel.bottom - 34))
    else:
        hint = fonts["small"].render("Click a row to select  |  Mouse wheel to browse  |  E or Esc to close", True, (92, 106, 118))
        surface.blit(hint, (panel.x + 24, panel.bottom - 34))

    if len(shelf.items) > visible_rows:
        page_text = fonts["small"].render(
            f"Items {first_item + 1}-{min(first_item + visible_rows, len(shelf.items))} of {len(shelf.items)}",
            True,
            (92, 106, 118),
        )
        surface.blit(page_text, (panel.x + 200, panel.bottom - 67))
        pygame.draw.rect(surface, INFO_PANEL_COLOR, scroll_track, border_radius=4)
        pygame.draw.rect(surface, SHELF_EDGE_COLOR, scroll_thumb, border_radius=4)


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


def draw_input_box(surface, rect, text, active, font, outline_color=ACCENT_COLOR):
    outline = outline_color if active else (154, 172, 184)
    pygame.draw.rect(surface, (250, 252, 253), rect, border_radius=5)
    pygame.draw.rect(surface, outline, rect, 2, border_radius=5)
    value = font.render(text, True, TEXT_COLOR)
    surface.blit(value, value.get_rect(center=rect.center))


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
    overlay.fill((35, 50, 65, 140))
    surface.blit(overlay, (0, 0))
    panel, rows, track, thumb, cancel, visible_rows = product_picker_layout(available_products, first_item)
    pygame.draw.rect(surface, (255, 255, 255), panel, border_radius=10)
    pygame.draw.rect(surface, CATALOGUE_EDGE_COLOR, panel, 3, border_radius=10)
    title = fonts["title"].render("Choose Product", True, TEXT_COLOR)
    surface.blit(title, (panel.x + 28, panel.y + 22))
    surface.blit(fonts["small"].render("Item ID", True, CATALOGUE_EDGE_COLOR), (panel.x + 28, panel.y + 68))
    surface.blit(fonts["small"].render("Product name", True, CATALOGUE_EDGE_COLOR), (panel.x + 145, panel.y + 68))
    surface.blit(fonts["small"].render("Price", True, CATALOGUE_EDGE_COLOR), (panel.right - 115, panel.y + 68))
    for item, row in rows:
        item_id, item_name, price, minimum_quantity, maximum_quantity = item
        pygame.draw.rect(surface, (239, 246, 250), row, border_radius=5)
        label = fonts["body"].render(f"{item_id:<5}  {item_name}", True, TEXT_COLOR)
        surface.blit(label, (row.x + 12, row.y + 7))
        price_label = fonts["body"].render(f"Rs. {price}", True, TEXT_COLOR)
        surface.blit(price_label, (row.right - 115, row.y + 7))
    pygame.draw.rect(surface, INFO_PANEL_COLOR, track, border_radius=4)
    pygame.draw.rect(surface, CATALOGUE_EDGE_COLOR, thumb, border_radius=4)
    draw_button(surface, cancel, "Cancel", (130, 142, 152), fonts["body"])


def draw_item_editor(surface, fonts, item, quantity_text, price_text, add_mode, active_input):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((35, 50, 65, 115))
    surface.blit(overlay, (0, 0))
    (
        panel, product_button, quantity_down, quantity_up, quantity_box,
        price_down, price_up, price_box, save_button, cancel_button,
    ) = item_editor_layout()
    pygame.draw.rect(surface, (255, 255, 255), panel, border_radius=10)
    pygame.draw.rect(surface, SHELF_EDGE_COLOR, panel, 3, border_radius=10)
    title = fonts["title"].render("Add Shelf Item" if add_mode else "Edit Shelf Item", True, TEXT_COLOR)
    surface.blit(title, (panel.x + 28, panel.y + 22))
    surface.blit(fonts["body"].render("Product", True, TEXT_COLOR), (panel.x + 35, panel.y + 89))
    product_text = "Choose a product" if item is None else f"{item[0]} - {item[1]}"
    draw_input_box(surface, product_button, product_text, False, fonts["small"], SHELF_EDGE_COLOR)
    arrow = fonts["small"].render("v", True, TEXT_COLOR)
    surface.blit(arrow, (product_button.right - 18, product_button.y + 10))
    surface.blit(fonts["body"].render("Quantity", True, TEXT_COLOR), (panel.x + 35, quantity_box.y + 7))
    surface.blit(fonts["body"].render("Price", True, TEXT_COLOR), (panel.x + 35, price_box.y + 7))
    draw_button(surface, quantity_down, "-", SHELF_BUTTON_COLOR, fonts["body"])
    draw_button(surface, quantity_up, "+", SHELF_BUTTON_COLOR, fonts["body"])
    draw_button(surface, price_down, "-", SHELF_BUTTON_COLOR, fonts["body"])
    draw_button(surface, price_up, "+", SHELF_BUTTON_COLOR, fonts["body"])
    draw_input_box(surface, quantity_box, quantity_text, active_input == "quantity", fonts["body"], SHELF_EDGE_COLOR)
    draw_input_box(surface, price_box, price_text, active_input == "price", fonts["body"], SHELF_EDGE_COLOR)
    draw_button(surface, save_button, "Save", SHELF_EDGE_COLOR, fonts["body"])
    draw_button(surface, cancel_button, "Cancel", (130, 142, 152), fonts["body"])


def catalogue_menu_layout(products, selected_item_id, first_item):
    panel = pygame.Rect(115, 32, 770, 536)
    header_y = panel.y + 78
    visible_rows = min(7, max(1, len(products)))
    rows = []
    for row_index, item in enumerate(products[first_item:first_item + visible_rows]):
        row_rect = pygame.Rect(panel.x + 22, header_y + 39 + row_index * 43, 642, 38)
        delete_rect = pygame.Rect(panel.right - 78, row_rect.y + 2, 28, 32)
        rows.append((item, row_rect, delete_rect))

    add_button = pygame.Rect(panel.x + 28, panel.bottom - 62, 42, 36)
    edit_button = None
    if selected_item_id is not None:
        edit_button = pygame.Rect(panel.x + 82, panel.bottom - 62, 100, 36)

    scroll_track = None
    scroll_thumb = None
    if len(products) > visible_rows:
        scroll_track = pygame.Rect(panel.right - 27, header_y + 42, 8, visible_rows * 43 - 5)
        scroll_thumb = make_scroll_thumb(scroll_track, len(products), visible_rows, first_item)
    return (
        panel, header_y, rows, add_button, edit_button,
        visible_rows, scroll_track, scroll_thumb,
    )


def draw_catalogue_menu(surface, fonts, products, selected_item_id, first_item, message):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((35, 50, 65, 115))
    surface.blit(overlay, (0, 0))

    (
        panel, header_y, rows, add_button, edit_button,
        visible_rows, scroll_track, scroll_thumb,
    ) = catalogue_menu_layout(products, selected_item_id, first_item)
    pygame.draw.rect(surface, (255, 255, 255), panel, border_radius=10)
    pygame.draw.rect(surface, CATALOGUE_EDGE_COLOR, panel, 3, border_radius=10)

    title = fonts["title"].render("Store Product Catalogue", True, TEXT_COLOR)
    surface.blit(title, (panel.x + 28, panel.y + 22))

    columns = [("Item ID", 30), ("Item name", 155), ("Price", 425), ("Starting quantity", 540)]
    pygame.draw.line(
        surface,
        CATALOGUE_EDGE_COLOR,
        (panel.x + 25, header_y + 28),
        (panel.right - 25, header_y + 28),
        2,
    )
    for heading, offset in columns:
        header = fonts["body"].render(heading, True, CATALOGUE_EDGE_COLOR)
        surface.blit(header, (panel.x + offset, header_y))

    for item, row_rect, delete_rect in rows:
        item_id, item_name, price, minimum_quantity, maximum_quantity = item
        if item_id == selected_item_id:
            pygame.draw.rect(surface, CATALOGUE_SELECTED_COLOR, row_rect, border_radius=5)
        values = (
            str(item_id),
            item_name,
            f"Rs. {price:.2f}",
            f"{minimum_quantity}-{maximum_quantity}",
        )
        for value, (_, offset) in zip(values, columns):
            text = fonts["body"].render(value, True, TEXT_COLOR)
            surface.blit(text, (panel.x + offset, row_rect.y + 7))
        draw_button(surface, delete_rect, "X", (184, 79, 79), fonts["body"])

    draw_button(surface, add_button, "+", CATALOGUE_BUTTON_COLOR, fonts["body"])
    if edit_button:
        draw_button(surface, edit_button, "Edit", CATALOGUE_EDGE_COLOR, fonts["body"])

    if scroll_track:
        pygame.draw.rect(surface, INFO_PANEL_COLOR, scroll_track, border_radius=4)
        pygame.draw.rect(surface, CATALOGUE_EDGE_COLOR, scroll_thumb, border_radius=4)

    if products:
        last_item = min(first_item + visible_rows, len(products))
        page_label = f"Products {first_item + 1}-{last_item} of {len(products)}"
    else:
        page_label = "No catalogue products yet"
    page_text = fonts["body"].render(page_label, True, (92, 106, 118))
    surface.blit(page_text, (panel.x + 205, panel.bottom - 56))
    if message:
        hint = fonts["small"].render(message, True, (178, 65, 65))
    else:
        hint = fonts["small"].render(
            "Click a row to select  |  Mouse wheel: browse  |  E or Esc: close",
            True,
            (92, 106, 118),
        )
    surface.blit(hint, (panel.x + 28, panel.bottom - 22))


def product_editor_layout():
    panel = pygame.Rect(250, 38, 500, 525)
    field_x = panel.x + 175
    field_width = 265
    start_y = panel.y + 84
    fields = {
        "item_id": pygame.Rect(field_x, start_y, field_width, 36),
        "item_name": pygame.Rect(field_x, start_y + 57, field_width, 36),
        "price": pygame.Rect(field_x, start_y + 114, field_width, 36),
        "minimum_quantity": pygame.Rect(field_x + 55, start_y + 171, 110, 36),
        "maximum_quantity": pygame.Rect(field_x + 55, start_y + 228, 110, 36),
    }
    return (
        panel,
        fields,
        pygame.Rect(field_x + 5, fields["minimum_quantity"].y, 40, 36),
        pygame.Rect(field_x + 175, fields["minimum_quantity"].y, 40, 36),
        pygame.Rect(field_x + 5, fields["maximum_quantity"].y, 40, 36),
        pygame.Rect(field_x + 175, fields["maximum_quantity"].y, 40, 36),
        pygame.Rect(panel.x + 90, panel.bottom - 52, 120, 36),
        pygame.Rect(panel.x + 290, panel.bottom - 52, 120, 36),
    )


def draw_product_editor(surface, fonts, fields, active_input, add_mode, message):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((35, 50, 65, 135))
    surface.blit(overlay, (0, 0))
    (
        panel, boxes, minimum_down, minimum_up, maximum_down, maximum_up,
        save_button, cancel_button,
    ) = product_editor_layout()
    pygame.draw.rect(surface, (255, 255, 255), panel, border_radius=10)
    pygame.draw.rect(surface, CATALOGUE_EDGE_COLOR, panel, 3, border_radius=10)
    title = fonts["title"].render("Add Product" if add_mode else "Edit Product", True, TEXT_COLOR)
    surface.blit(title, (panel.x + 28, panel.y + 20))

    labels = (
        ("Item ID", "item_id"),
        ("Product name", "item_name"),
        ("Price", "price"),
        ("Minimum quantity", "minimum_quantity"),
        ("Maximum quantity", "maximum_quantity"),
    )
    for label, key in labels:
        surface.blit(
            fonts["small"].render(label, True, TEXT_COLOR),
            (panel.x + 36, boxes[key].y + 9),
        )
        draw_input_box(
            surface, boxes[key], fields[key], active_input == key, fonts["body"], CATALOGUE_EDGE_COLOR
        )

    for button, label in (
        (minimum_down, "-"), (minimum_up, "+"),
        (maximum_down, "-"), (maximum_up, "+"),
    ):
        draw_button(surface, button, label, CATALOGUE_BUTTON_COLOR, fonts["body"])
    draw_button(surface, save_button, "Save", CATALOGUE_EDGE_COLOR, fonts["body"])
    draw_button(surface, cancel_button, "Cancel", (130, 142, 152), fonts["body"])
    if message:
        warning = fonts["small"].render(message, True, (178, 65, 65))
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
    surface, fonts, current_balance, balance_text, history, first_item, active_input, message
):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((35, 50, 65, 115))
    surface.blit(overlay, (0, 0))

    (
        panel, balance_box, update_button, header_y, rows,
        visible_rows, scroll_track, scroll_thumb,
    ) = finance_menu_layout(history, first_item)

    pygame.draw.rect(surface, (255, 255, 255), panel, border_radius=10)
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
        surface, balance_box, balance_text, active_input, fonts["body"], REGISTER_EDGE_COLOR
    )
    draw_button(surface, update_button, "Update", REGISTER_BUTTON_COLOR, fonts["body"])

    if message:
        if message.startswith("Profit"):
            msg_color = (47, 116, 79)
        elif "unchanged" in message:
            msg_color = (92, 106, 118)
        else:
            msg_color = (178, 65, 65)
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

    if not history:
        empty_text = fonts["body"].render("No finance transactions recorded yet.", True, (92, 106, 118))
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
            for value, (heading, offset) in zip(values, columns):
                if heading in ("Amount", "Change"):
                    val_color = (47, 116, 79) if change_type == "Profit" else (178, 65, 65)
                else:
                    val_color = TEXT_COLOR
                text = fonts["body"].render(value, True, val_color)
                surface.blit(text, (panel.x + offset, row_rect.y + 6))

    if scroll_track:
        pygame.draw.rect(surface, INFO_PANEL_COLOR, scroll_track, border_radius=4)
        pygame.draw.rect(surface, REGISTER_EDGE_COLOR, scroll_thumb, border_radius=4)

    if history:
        last_item = min(first_item + visible_rows, len(history))
        page_label = f"Entries {first_item + 1}-{last_item} of {len(history)}"
    else:
        page_label = "No finance entries yet"
    page_text = fonts["body"].render(page_label, True, (92, 106, 118))
    surface.blit(page_text, (panel.x + 28, panel.bottom - 54))

    hint = fonts["small"].render(
        "Click balance to edit  |  Enter or Update: save  |  E or Esc: close",
        True,
        (92, 106, 118),
    )
    surface.blit(hint, (panel.x + 28, panel.bottom - 22))

#________________________________________WORLD DRAW__________________________________________________________________

def draw_world(surface, player, walls, shelves, catalogue, cash_register, targeted_object, fonts):
    surface.fill(WINDOW_COLOR)
    game_area = pygame.Rect(0, 0, SCREEN_WIDTH, MAP_HEIGHT)
    pygame.draw.rect(surface, FLOOR_COLOR, game_area)

    for wall in walls:
        pygame.draw.rect(surface, WALL_COLOR, wall)

    for shelf in shelves:
        color = SHELF_EDGE_COLOR if shelf is targeted_object else SHELF_COLOR
        pygame.draw.rect(surface, SHELF_COLOR, shelf.rect)
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

    player.draw(surface)
    instructions = fonts["body"].render("Movement: WASD | Interaction: E", True, TEXT_COLOR)
    info_panel = pygame.Rect(0, MAP_HEIGHT, SCREEN_WIDTH, HUD_HEIGHT)
    pygame.draw.rect(surface, INFO_PANEL_COLOR, info_panel)
    pygame.draw.line(surface, ACCENT_COLOR, (0, MAP_HEIGHT), (SCREEN_WIDTH, MAP_HEIGHT), 2)
    surface.blit(instructions, (20, MAP_HEIGHT + 12))

    if targeted_object:
        if isinstance(targeted_object, Shelf):
            prompt_text = "Press E to inspect shelf"
        elif isinstance(targeted_object, ProductCatalogue):
            prompt_text = "Press E to open product catalogue"
        else:
            prompt_text = "Press E to open cash register"
        prompt = fonts["body"].render(prompt_text, True, ACCENT_COLOR)
        surface.blit(prompt, (20, MAP_HEIGHT + 43))


def find_shelf_item(shelf, item_id):
    for item in shelf.items:
        if item[0] == item_id:
            return item
    return None


def available_products_for_shelf(shelf, products, included_item_id=None):
    saved_ids = {item[0] for item in shelf.items}
    return [
        item for item in products
        if item[0] not in saved_ids or item[0] == included_item_id
    ]


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
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Store Management Simulator - Shelf Prototype")
    clock = pygame.time.Clock()
    fonts = {
        "body": pygame.font.SysFont("Arial", 22),
        "balance": pygame.font.SysFont("Arial", 26, bold=True),
        "small": pygame.font.SysFont("Arial", 16),
        "title": pygame.font.SysFont("Arial", 32, bold=True),
    }

    map_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "store_level1.txt")
    try:
        ensure_store_database(map_path)
        inventory_by_position = load_shelf_inventory(map_path)
        product_catalogue = list(load_product_catalogue(map_path))
        finance_balance, finance_history = load_finance_data(map_path)
        walls, shelves, catalogue, cash_register, player_spawn = load_store_map(
            map_path, inventory_by_position
        )
    except (OSError, ValueError, DatabaseSetupError) as error:
        print(f"Unable to start store simulator: {error}")
        pygame.quit()
        return

    player = Player(player_spawn)
    solid_rects = walls + [shelf.rect for shelf in shelves] + [catalogue.rect, cash_register.rect]
    state = GameState.PLAYING
    selected_shelf = None
    selected_item_id = None
    shelf_first_item = 0
    editing_item_id = None
    editor_product = None
    quantity_text = ""
    price_text = ""
    active_input = None
    product_picker_open = False
    product_picker_first_item = 0
    menu_message = ""
    catalogue_start = 0
    selected_catalogue_id = None
    catalogue_editing_item_id = None
    catalogue_add_mode = True
    catalogue_fields = {
        "item_id": "",
        "item_name": "",
        "price": "",
        "minimum_quantity": "",
        "maximum_quantity": "",
    }
    catalogue_active_input = None
    catalogue_message = ""
    finance_balance_text = f"{finance_balance:.2f}"
    finance_history_start = 0
    finance_active_input = False
    finance_message = ""
    running = True

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
            finance_history_start = 0
            finance_active_input = False
        except ValueError:
            finance_message = "Enter a valid balance of zero or more."
        except DatabaseSetupError as error:
            finance_message = str(error)

    while running:
        dt = clock.tick(FPS) / 1000
        targeted_object = get_targeted_object(player, shelves, catalogue, cash_register)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if state == GameState.FINANCE_MENU:
                    if event.key in (pygame.K_e, pygame.K_ESCAPE):
                        state = GameState.PLAYING
                        finance_active_input = False
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        commit_finance_balance()
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
                    if isinstance(targeted_object, Shelf):
                        selected_shelf = targeted_object
                        selected_item_id = None
                        shelf_first_item = 0
                        menu_message = ""
                        state = GameState.SHELF_MENU
                    elif isinstance(targeted_object, ProductCatalogue):
                        catalogue_start = 0
                        selected_catalogue_id = None
                        catalogue_message = ""
                        state = GameState.CATALOGUE_MENU
                    else:
                        finance_balance_text = f"{finance_balance:.2f}"
                        finance_history_start = 0
                        finance_active_input = False
                        finance_message = ""
                        state = GameState.FINANCE_MENU
                elif state == GameState.SHELF_MENU and event.key in (pygame.K_e, pygame.K_ESCAPE):
                    selected_shelf = None
                    selected_item_id = None
                    shelf_first_item = 0
                    state = GameState.PLAYING
                elif state == GameState.CATALOGUE_MENU and event.key in (pygame.K_e, pygame.K_ESCAPE):
                    state = GameState.PLAYING
                elif state == GameState.CATALOGUE_MENU and event.key == pygame.K_DOWN:
                    catalogue_start = min(catalogue_start + 1, max(0, len(product_catalogue) - 7))
                elif state == GameState.CATALOGUE_MENU and event.key == pygame.K_UP:
                    catalogue_start = max(catalogue_start - 1, 0)
                elif state == GameState.CATALOGUE_MENU and event.key == pygame.K_PAGEDOWN:
                    catalogue_start = min(catalogue_start + 7, max(0, len(product_catalogue) - 7))
                elif state == GameState.CATALOGUE_MENU and event.key == pygame.K_PAGEUP:
                    catalogue_start = max(catalogue_start - 7, 0)
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
                        finance_history_start = scroll_start_from_mouse(
                            scroll_track, len(finance_history), visible_rows, event.pos[1]
                        )
                    else:
                        finance_active_input = False
                elif state == GameState.PRODUCT_EDITOR:
                    (
                        panel, boxes, minimum_down, minimum_up, maximum_down, maximum_up,
                        save_button, cancel_button,
                    ) = product_editor_layout()
                    for field_name, field_box in boxes.items():
                        if field_box.collidepoint(event.pos):
                            catalogue_active_input = field_name
                            break
                    else:
                        if minimum_down.collidepoint(event.pos):
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
                                if catalogue_add_mode:
                                    add_catalogue_product(map_path, *product_values)
                                    product_catalogue.append(product_values)
                                else:
                                    update_catalogue_product(
                                        map_path,
                                        catalogue_editing_item_id,
                                        *product_values,
                                    )
                                    old_product = catalogue_item_by_id(
                                        product_catalogue, catalogue_editing_item_id
                                    )
                                    product_catalogue[product_catalogue.index(old_product)] = product_values
                                product_catalogue.sort(key=lambda item: item[0])
                                selected_catalogue_id = product_values[0]
                                catalogue_start = min(
                                    catalogue_start, max(0, len(product_catalogue) - 7)
                                )
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
                        panel, header_y, rows, add_button, edit_button,
                        visible_rows, scroll_track, scroll_thumb,
                    ) = catalogue_menu_layout(
                        product_catalogue, selected_catalogue_id, catalogue_start
                    )
                    if add_button.collidepoint(event.pos):
                        catalogue_add_mode = True
                        catalogue_editing_item_id = None
                        catalogue_fields = {
                            "item_id": "",
                            "item_name": "",
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
                            ) = selected_product
                            catalogue_add_mode = False
                            catalogue_editing_item_id = item_id
                            catalogue_fields = {
                                "item_id": str(item_id),
                                "item_name": item_name,
                                "price": f"{price:.2f}",
                                "minimum_quantity": str(minimum_quantity),
                                "maximum_quantity": str(maximum_quantity),
                            }
                            catalogue_active_input = None
                            catalogue_message = ""
                            state = GameState.PRODUCT_EDITOR
                    elif scroll_track and scroll_track.collidepoint(event.pos):
                        catalogue_start = scroll_start_from_mouse(
                            scroll_track, len(product_catalogue), visible_rows, event.pos[1]
                        )
                    else:
                        for product, row_rect, delete_rect in rows:
                            if delete_rect.collidepoint(event.pos):
                                try:
                                    delete_catalogue_product(map_path, product[0])
                                    product_catalogue.remove(product)
                                    if selected_catalogue_id == product[0]:
                                        selected_catalogue_id = None
                                    catalogue_start = min(
                                        catalogue_start, max(0, len(product_catalogue) - 7)
                                    )
                                    catalogue_message = ""
                                except DatabaseSetupError as error:
                                    catalogue_message = str(error)
                                break
                            if row_rect.collidepoint(event.pos):
                                selected_catalogue_id = product[0]
                                catalogue_message = ""
                                break
                elif state == GameState.SHELF_MENU:
                    (
                        panel, header_y, rows, add_button, edit_button,
                        visible_rows, scroll_track, scroll_thumb,
                    ) = shelf_menu_layout(
                        selected_shelf, selected_item_id, shelf_first_item
                    )
                    if add_button.collidepoint(event.pos):
                        if not available_products_for_shelf(selected_shelf, product_catalogue):
                            menu_message = "All catalogue products are already on this shelf."
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
                            state = GameState.EDIT_ITEM
                    elif scroll_track and scroll_track.collidepoint(event.pos):
                        shelf_first_item = scroll_start_from_mouse(
                            scroll_track, len(selected_shelf.items), visible_rows, event.pos[1]
                        )
                    else:
                        for item, row_rect, delete_rect in rows:
                            if delete_rect.collidepoint(event.pos):
                                try:
                                    delete_shelf_item(map_path, selected_shelf.shelf_id, item[0])
                                    selected_shelf.items.remove(item)
                                    if selected_item_id == item[0]:
                                        selected_item_id = None
                                    menu_message = ""
                                except DatabaseSetupError as error:
                                    menu_message = str(error)
                                break
                            if row_rect.collidepoint(event.pos):
                                selected_item_id = item[0]
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
                            product_picker_first_item = scroll_start_from_mouse(
                                picker_track, len(available_products), picker_visible, event.pos[1]
                            )
                        else:
                            for product, row_rect in picker_rows:
                                if row_rect.collidepoint(event.pos):
                                    editor_product = product
                                    price_text = f"{product[2]:.2f}"
                                    if state == GameState.ADD_ITEM:
                                        quantity_text = str(product[3])
                                    product_picker_open = False
                                    active_input = None
                                    break
                    else:
                        add_mode = state == GameState.ADD_ITEM
                        (
                            panel, product_button, quantity_down, quantity_up, quantity_box,
                            price_down, price_up, price_box, save_button, cancel_button,
                        ) = item_editor_layout()
                        if product_button.collidepoint(event.pos):
                            product_picker_open = True
                            product_picker_first_item = 0
                        elif quantity_box.collidepoint(event.pos):
                            active_input = "quantity"
                        elif price_box.collidepoint(event.pos):
                            active_input = "price"
                        elif quantity_down.collidepoint(event.pos):
                            try:
                                quantity_text = str(max(0, int(quantity_text or "0") - 1))
                            except ValueError:
                                quantity_text = "0"
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
                                    selected_item_id = item_id
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
                                    selected_item_id = editor_product[0]
                                menu_message = ""
                                active_input = None
                                state = GameState.SHELF_MENU
                            except ValueError:
                                menu_message = "Choose a product and enter a valid quantity and price."
                            except DatabaseSetupError as error:
                                menu_message = str(error)
            elif event.type == pygame.MOUSEWHEEL and state == GameState.CATALOGUE_MENU:
                catalogue_start = max(
                    0, min(catalogue_start - event.y, max(0, len(product_catalogue) - 7))
                )
            elif event.type == pygame.MOUSEWHEEL and state == GameState.FINANCE_MENU:
                finance_history_start = max(
                    0, min(finance_history_start - event.y, max(0, len(finance_history) - 7))
                )
            elif event.type == pygame.MOUSEWHEEL and state == GameState.SHELF_MENU:
                shelf_first_item = max(
                    0,
                    min(shelf_first_item - event.y, max(0, len(selected_shelf.items) - 8)),
                )
            elif event.type == pygame.MOUSEWHEEL and state in (GameState.EDIT_ITEM, GameState.ADD_ITEM) and product_picker_open:
                included_item_id = editing_item_id if state == GameState.EDIT_ITEM else None
                available_products = available_products_for_shelf(
                    selected_shelf, product_catalogue, included_item_id
                )
                product_picker_first_item = max(
                    0,
                    min(product_picker_first_item - event.y, max(0, len(available_products) - 8)),
                )

        if state == GameState.PLAYING:
            player.update(dt, solid_rects)
            targeted_object = get_targeted_object(player, shelves, catalogue, cash_register)

        draw_world(
            screen, player, walls, shelves, catalogue, cash_register, targeted_object, fonts
        )
        if state == GameState.SHELF_MENU:
            draw_shelf_menu(
                screen, fonts, selected_shelf, selected_item_id, shelf_first_item, menu_message
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
                catalogue_start,
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
            )
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
