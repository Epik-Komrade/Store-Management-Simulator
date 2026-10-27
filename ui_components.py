"""Lightweight, animated UI components for Pygame using delta-time easing."""

import math
import pygame

from ui_theme import (
    DELETE_RED,
    DELETE_RED_HOVER,
    INPUT_BG,
    INPUT_BORDER_DEFAULT,
    OVERLAY_COLOR,
    PANEL_BG,
    SCROLL_TRACK_COLOR,
    TEXT_MUTED,
    TEXT_PRIMARY,
    brighten_color,
    get_drop_shadow,
    get_font,
    lerp_color,
)


# -------------------------------------------------------------------------
# Math & Easing Helpers
# -------------------------------------------------------------------------
def clamp(val, low, high):
    """Clamp a value within [low, high]."""
    return max(low, min(high, val))


def lerp(current, target, rate, dt):
    """Frame-rate independent exponential interpolation."""
    if dt <= 0:
        return current
    blend = 1.0 - math.exp(-rate * dt)
    return current + (target - current) * blend


def ease_out_cubic(t):
    """Cubic ease-out curve for smooth deceleration."""
    t = clamp(t, 0.0, 1.0)
    return 1.0 - (1.0 - t) ** 3


# -------------------------------------------------------------------------
# Animated Button
# -------------------------------------------------------------------------
class AnimatedButton:
    """Button with smooth hover illumination, subtle lift, and press feedback."""

    def __init__(
        self,
        rect,
        label,
        base_color,
        hover_color=None,
        text_color=(255, 255, 255),
        font_name="body",
        border_radius=7,
    ):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.base_color = base_color
        self.hover_color = hover_color or brighten_color(base_color, 25)
        self.text_color = text_color
        self.font_name = font_name
        self.border_radius = border_radius

        self.hover_t = 0.0
        self.press_t = 0.0

    def update(self, dt, mouse_pos):
        """Update hover and press animation states."""
        is_hovered = self.rect.collidepoint(mouse_pos)
        target_hover = 1.0 if is_hovered else 0.0
        self.hover_t = lerp(self.hover_t, target_hover, 16.0, dt)
        if self.press_t > 0:
            self.press_t = max(0.0, self.press_t - dt * 6.0)

    def draw(self, surface, fonts=None):
        """Render the button with animated color transition and subtle depth."""
        color = lerp_color(self.base_color, self.hover_color, self.hover_t)

        # Subtle 1px lift on hover, slight depression on press
        offset_y = 1 if self.press_t > 0 else (-1 if self.hover_t > 0.5 else 0)
        draw_rect = self.rect.move(0, offset_y)

        # Soft button shadow when lifted
        if self.hover_t > 0.2 and offset_y < 0:
            shadow_rect = self.rect.move(0, 2)
            pygame.draw.rect(
                surface,
                (0, 0, 0, int(25 * self.hover_t)),
                shadow_rect,
                border_radius=self.border_radius,
            )

        pygame.draw.rect(surface, color, draw_rect, border_radius=self.border_radius)

        font = fonts[self.font_name] if fonts and self.font_name in fonts else get_font(self.font_name)
        text_surface = font.render(self.label, True, self.text_color)
        surface.blit(text_surface, text_surface.get_rect(center=draw_rect.center))

    def handle_event(self, event):
        """Return True if clicked with the primary mouse button."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.press_t = 1.0
                return True
        return False


# -------------------------------------------------------------------------
# Animated Text Input Box
# -------------------------------------------------------------------------
class AnimatedTextInput:
    """Text input field with smooth border focus illumination and blinking cursor."""

    def __init__(
        self,
        rect,
        initial_text="",
        theme_color=(55, 126, 174),
        font_name="body",
        border_radius=6,
        placeholder="",
    ):
        self.rect = pygame.Rect(rect)
        self.text = str(initial_text)
        self.theme_color = theme_color
        self.font_name = font_name
        self.border_radius = border_radius
        self.placeholder = placeholder

        self.active = False
        self.focus_t = 0.0
        self.cursor_timer = 0.0
        self.cursor_visible = True

    def set_text(self, text):
        self.text = str(text)

    def update(self, dt):
        """Update focus glow and cursor blink timing."""
        target_focus = 1.0 if self.active else 0.0
        self.focus_t = lerp(self.focus_t, target_focus, 18.0, dt)

        if self.active:
            self.cursor_timer += dt
            self.cursor_visible = (int(self.cursor_timer * 2.2) % 2) == 0
        else:
            self.cursor_visible = False
            self.cursor_timer = 0.0

    def draw(self, surface, fonts=None):
        """Render the input field with border glow and blinking cursor."""
        font = fonts[self.font_name] if fonts and self.font_name in fonts else get_font(self.font_name)

        # Background
        pygame.draw.rect(surface, INPUT_BG, self.rect, border_radius=self.border_radius)

        # Smooth border color interpolation
        border_color = lerp_color(INPUT_BORDER_DEFAULT, self.theme_color, self.focus_t)
        border_thickness = 2 if self.focus_t > 0.3 else 1
        pygame.draw.rect(
            surface, border_color, self.rect, border_thickness, border_radius=self.border_radius
        )

        # Text or placeholder
        display_text = self.text if (self.text or self.active) else self.placeholder
        color = TEXT_PRIMARY if self.text else TEXT_MUTED
        text_surface = font.render(display_text, True, color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)

        # Blinking vertical cursor line
        if self.active and self.cursor_visible:
            cursor_x = text_rect.right + 2 if self.text else self.rect.centerx
            cursor_y1 = self.rect.centery - font.get_height() // 2 + 2
            cursor_y2 = self.rect.centery + font.get_height() // 2 - 2
            pygame.draw.line(surface, self.theme_color, (cursor_x, cursor_y1), (cursor_x, cursor_y2), 2)

    def handle_event(self, event, numeric_only=False, decimal_only=False):
        """Process clicks and typing. Returns True if value changed."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            clicked_inside = self.rect.collidepoint(event.pos)
            if clicked_inside != self.active:
                self.active = clicked_inside
                self.cursor_timer = 0.0
                self.cursor_visible = True
            return False

        if not self.active or event.type != pygame.KEYDOWN:
            return False

        self.cursor_timer = 0.0
        self.cursor_visible = True

        if event.key == pygame.K_BACKSPACE:
            if self.text:
                self.text = self.text[:-1]
                return True
        elif decimal_only:
            if event.unicode.isdigit() or (event.unicode == "." and "." not in self.text):
                self.text += event.unicode
                return True
        elif numeric_only:
            if event.unicode.isdigit():
                self.text += event.unicode
                return True
        elif event.unicode.isprintable() and len(self.text) < 100:
            self.text += event.unicode
            return True

        return False


# -------------------------------------------------------------------------
# Smooth Scrollbar & Table Viewport
# -------------------------------------------------------------------------
class SmoothScroll:
    """Decoupled smooth scrolling controller with inertia easing."""

    def __init__(self, item_count, visible_rows, row_height=40, speed=16.0):
        self.item_count = item_count
        self.visible_rows = visible_rows
        self.row_height = row_height
        self.speed = speed

        self.target_offset = 0.0
        self.current_offset = 0.0
        self.is_dragging = False
        self.drag_start_y = 0
        self.drag_start_target = 0.0

    def set_counts(self, item_count, visible_rows):
        self.item_count = item_count
        self.visible_rows = visible_rows
        max_start = max(0, self.item_count - self.visible_rows)
        self.target_offset = clamp(self.target_offset, 0.0, float(max_start))

    def scroll_by(self, delta):
        max_start = max(0, self.item_count - self.visible_rows)
        self.target_offset = clamp(self.target_offset + delta, 0.0, float(max_start))

    def scroll_to(self, index):
        max_start = max(0, self.item_count - self.visible_rows)
        self.target_offset = clamp(float(index), 0.0, float(max_start))

    def update(self, dt):
        """Smoothly ease current scroll offset towards target offset."""
        self.current_offset = lerp(self.current_offset, self.target_offset, self.speed, dt)
        if abs(self.current_offset - self.target_offset) < 0.005:
            self.current_offset = self.target_offset

    def get_first_visible_index(self):
        return int(round(self.current_offset))

    def get_thumb_rect(self, track_rect):
        """Compute the smoothly positioned scroll thumb rectangle."""
        if self.item_count <= self.visible_rows:
            return None

        max_start = max(1, self.item_count - self.visible_rows)
        thumb_height = max(28, round(track_rect.height * self.visible_rows / self.item_count))
        travel = track_rect.height - thumb_height
        thumb_y = track_rect.y + round(travel * (self.current_offset / max_start))
        return pygame.Rect(track_rect.x, thumb_y, track_rect.width, thumb_height)

    def handle_track_click(self, track_rect, mouse_y):
        """Map a mouse click on the scroll track to target index."""
        if self.item_count <= self.visible_rows:
            return
        max_start = max(1, self.item_count - self.visible_rows)
        thumb_height = max(28, round(track_rect.height * self.visible_rows / self.item_count))
        travel = max(1, track_rect.height - thumb_height)
        thumb_top = clamp(mouse_y - thumb_height // 2, track_rect.y, track_rect.bottom - thumb_height)
        self.target_offset = round((thumb_top - track_rect.y) * max_start / travel)


# -------------------------------------------------------------------------
# Animated Modal Dialog (Fade-In, Scale-In & Drop Shadow)
# -------------------------------------------------------------------------
class AnimatedModal:
    """Modal container with smooth fade/scale entrance and pre-baked drop shadow."""

    def __init__(self, target_rect, theme_edge_color, border_radius=10):
        self.target_rect = pygame.Rect(target_rect)
        self.theme_edge_color = theme_edge_color
        self.border_radius = border_radius

        self.progress = 0.0  # 0.0 (closed) to 1.0 (fully open)
        self.is_open = False
        self.shadow_surface = get_drop_shadow(
            self.target_rect.width, self.target_rect.height, radius=self.border_radius
        )

    def open(self):
        self.is_open = True

    def close(self):
        self.is_open = False

    def update(self, dt):
        target = 1.0 if self.is_open else 0.0
        self.progress = lerp(self.progress, target, 16.0, dt)
        if abs(self.progress - target) < 0.005:
            self.progress = target

    def draw_backdrop_and_panel(self, surface):
        """Draw darkened animated backdrop, drop shadow, and container card."""
        if self.progress <= 0.01:
            return None

        # Dark overlay with smooth alpha fade
        alpha = int(125 * ease_out_cubic(self.progress))
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((*OVERLAY_COLOR, alpha))
        surface.blit(overlay, (0, 0))

        # Entrance motion: starts 8px higher and scales subtly into place
        eased_t = ease_out_cubic(self.progress)
        offset_y = round((1.0 - eased_t) * -10)
        draw_rect = self.target_rect.move(0, offset_y)

        # Pre-baked drop shadow
        if self.progress > 0.4:
            shadow_pos = (draw_rect.x - 14, draw_rect.y - 10)
            surface.blit(self.shadow_surface, shadow_pos)

        # Modal panel
        pygame.draw.rect(surface, PANEL_BG, draw_rect, border_radius=self.border_radius)
        pygame.draw.rect(
            surface, self.theme_edge_color, draw_rect, 3, border_radius=self.border_radius
        )

        return draw_rect
