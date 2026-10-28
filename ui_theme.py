"""UI Theme definitions, color palettes, fonts, and cached visual effects."""

import pygame

# -------------------------------------------------------------------------
# Global World & Window Colors
# -------------------------------------------------------------------------
WINDOW_COLOR = (231, 239, 245)
FLOOR_COLOR = (250, 247, 238)
WALL_COLOR = (174, 197, 214)
INFO_PANEL_COLOR = (213, 228, 239)
PLAYER_COLOR = (190, 190, 190)
ACCENT_COLOR = (55, 126, 174)

# -------------------------------------------------------------------------
# Neutral UI Palette
# -------------------------------------------------------------------------
PANEL_BG = (255, 255, 255)
TEXT_PRIMARY = (42, 57, 70)
TEXT_MUTED = (92, 106, 118)
TEXT_LIGHT = (255, 255, 255)
INPUT_BG = (250, 252, 253)
INPUT_BORDER_DEFAULT = (185, 198, 208)
SCROLL_TRACK_COLOR = (220, 232, 241)
OVERLAY_COLOR = (30, 42, 54)

# Status & Feedback Colors
PROFIT_GREEN = (47, 116, 79)
PROFIT_BG = (232, 245, 236)
LOSS_RED = (178, 65, 65)
LOSS_BG = (253, 238, 238)
DELETE_RED = (184, 79, 79)
DELETE_RED_HOVER = (212, 94, 94)

# -------------------------------------------------------------------------
# Station-Specific Palettes
# -------------------------------------------------------------------------
class StationTheme:
    """Theme bundle for a specific interactable station."""
    def __init__(
        self,
        name,
        tile_color,
        edge_color,
        button_color,
        button_hover,
        selected_bg,
        subtle_accent,
    ):
        self.name = name
        self.tile = tile_color
        self.edge = edge_color
        self.button = button_color
        self.button_hover = button_hover
        self.selected = selected_bg
        self.subtle = subtle_accent


# Shelf Theme: Warm Mahogany & Golden Amber Wood
SHELF_THEME = StationTheme(
    name="Shelf",
    tile_color=(207, 157, 96),
    edge_color=(132, 91, 48),
    button_color=(148, 103, 56),
    button_hover=(175, 122, 68),
    selected_bg=(248, 238, 224),
    subtle_accent=(238, 222, 200),
)

# Product Catalogue Theme: Deep Slate & Steel Navy
CATALOGUE_THEME = StationTheme(
    name="Catalogue",
    tile_color=(123, 170, 194),
    edge_color=(53, 104, 133),
    button_color=(60, 115, 146),
    button_hover=(78, 142, 178),
    selected_bg=(218, 235, 246),
    subtle_accent=(195, 220, 238),
)

# Cash Register Theme: Forest Emerald & Mint
REGISTER_THEME = StationTheme(
    name="Register",
    tile_color=(112, 177, 151),
    edge_color=(44, 111, 86),
    button_color=(44, 111, 86),
    button_hover=(58, 140, 109),
    selected_bg=(222, 242, 232),
    subtle_accent=(198, 232, 214),
)

# Employee Terminal Theme: Royal Violet & Amethyst
EMPLOYEE_THEME = StationTheme(
    name="Employee",
    tile_color=(158, 142, 198),
    edge_color=(92, 68, 145),
    button_color=(99, 74, 158),
    button_hover=(122, 93, 191),
    selected_bg=(238, 233, 248),
    subtle_accent=(224, 214, 242),
)

# Storage Depot Theme: Warm Industrial Crate Amber & Bronze
STORAGE_THEME = StationTheme(
    name="Storage",
    tile_color=(205, 128, 42),
    edge_color=(156, 92, 22),
    button_color=(185, 112, 32),
    button_hover=(210, 134, 48),
    selected_bg=(255, 238, 215),
    subtle_accent=(245, 222, 192),
)

# -------------------------------------------------------------------------
# Typography & Font Cache
# -------------------------------------------------------------------------
_FONT_CACHE = {}


def get_font(name="body"):
    """Return a cached Pygame SysFont to avoid expensive per-frame re-creations."""
    if not pygame.font.get_init():
        pygame.font.init()

    if name not in _FONT_CACHE:
        if name == "title":
            _FONT_CACHE[name] = pygame.font.SysFont("Arial", 32, bold=True)
        elif name == "balance":
            _FONT_CACHE[name] = pygame.font.SysFont("Arial", 26, bold=True)
        elif name == "subtitle":
            _FONT_CACHE[name] = pygame.font.SysFont("Arial", 24, bold=True)
        elif name == "body_bold":
            _FONT_CACHE[name] = pygame.font.SysFont("Arial", 22, bold=True)
        elif name == "body":
            _FONT_CACHE[name] = pygame.font.SysFont("Arial", 22)
        elif name == "header":
            _FONT_CACHE[name] = pygame.font.SysFont("Arial", 18, bold=True)
        elif name == "small":
            _FONT_CACHE[name] = pygame.font.SysFont("Arial", 16)
        elif name == "small_bold":
            _FONT_CACHE[name] = pygame.font.SysFont("Arial", 16, bold=True)
        else:
            _FONT_CACHE[name] = pygame.font.SysFont("Arial", 22)

    return _FONT_CACHE[name]


def get_fonts_dict():
    """Return all standard fonts as a dictionary for backwards-compatibility."""
    return {
        "title": get_font("title"),
        "balance": get_font("balance"),
        "header": get_font("header"),
        "body": get_font("body"),
        "small": get_font("small"),
    }


# -------------------------------------------------------------------------
# Cached Drop Shadow Generator
# -------------------------------------------------------------------------
_SHADOW_CACHE = {}


def get_drop_shadow(width, height, radius=10, blur=14, alpha=45, offset_y=4):
    """Generate or retrieve a pre-rendered soft alpha shadow surface."""
    key = (width, height, radius, blur, alpha, offset_y)
    if key in _SHADOW_CACHE:
        return _SHADOW_CACHE[key]

    shadow_w = width + blur * 2
    shadow_h = height + blur * 2 + offset_y
    shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)

    # Render multi-layered alpha falloff for a soft, modern diffusion
    steps = max(3, blur // 2)
    for i in range(steps, 0, -1):
        step_alpha = int(alpha * (1.0 - (i / steps) ** 1.5) / steps * 2.2)
        step_alpha = max(1, min(255, step_alpha))
        expand = i * (blur / steps)
        rect = pygame.Rect(
            blur - expand,
            blur + offset_y - expand,
            width + expand * 2,
            height + expand * 2,
        )
        pygame.draw.rect(
            shadow_surf,
            (20, 30, 40, step_alpha),
            rect,
            border_radius=int(radius + expand),
        )

    _SHADOW_CACHE[key] = shadow_surf
    return shadow_surf


# -------------------------------------------------------------------------
# Color Utilities
# -------------------------------------------------------------------------
def lerp_color(c1, c2, t):
    """Linearly interpolate between two RGB/RGBA color tuples."""
    t = max(0.0, min(1.0, t))
    return tuple(round(c1[i] + (c2[i] - c1[i]) * t) for i in range(len(c1)))


def brighten_color(color, amount=30):
    """Brighten an RGB color tuple by a set amount, clamped to 255."""
    return tuple(min(255, max(0, c + amount)) for c in color)
