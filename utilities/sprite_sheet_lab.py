"""Windowed sprite sheet metadata helper.

This utility is intentionally separate from the game runtime. It scans the
project assets and sprite metadata, lets a user preview horizontal animation
strips, adjust the shared content crop, and copy/save a JSON snippet compatible
with data/sprites.json.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
from pygame._sdl2 import Renderer, Texture, Window


ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
DATA_DIR = ROOT_DIR / "data"
SPRITES_JSON = DATA_DIR / "sprites.json"
TERRAIN_JSON = DATA_DIR / "terrain.json"
OUTPUT_DIR = ROOT_DIR / "utilities" / "sprite_metadata_exports"

WINDOW_SIZE = (1030, 760)
SHEET_WINDOW_SIZE = (1160, 720)
SHEET_HEADER_H = 74
SIDEBAR_W = 330
INSPECTOR_W = 350
PADDING = 16
MIN_ZOOM_PERCENT = 50
MAX_ZOOM_PERCENT = 600
ZOOM_STEP_PERCENT = 25
BG = (22, 24, 28)
PANEL = (34, 38, 44)
PANEL_ALT = (42, 48, 56)
TEXT = (232, 236, 241)
MUTED = (152, 162, 175)
ACCENT = (94, 197, 255)
WARN = (255, 189, 94)
GOOD = (126, 222, 151)
GRID = (255, 255, 255, 80)
RED = (255, 92, 92)


@dataclass(frozen=True)
class AnimationRef:
    rig: str
    anim: str
    file: str
    frame: tuple[int, int]
    frames: int
    fps: float
    loop: bool
    content: tuple[int, int, int, int] | None
    scale: tuple[int, int] | None
    anchor: tuple[int, int] | None
    face: str


@dataclass(frozen=True)
class Draft:
    rig: str
    anim: str
    file: str
    frame: tuple[int, int]
    frames: int
    fps: float
    loop: bool
    content: tuple[int, int, int, int]
    scale: tuple[int, int] | None
    anchor: tuple[int, int] | None
    face: str


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_animation_refs() -> list[AnimationRef]:
    refs: list[AnimationRef] = []
    sprite_meta = load_json(SPRITES_JSON)
    terrain_meta = load_json(TERRAIN_JSON).get("rigs", {})
    all_meta = {**sprite_meta, **terrain_meta}
    for rig, rig_meta in sorted(all_meta.items()):
        frame = tuple(int(v) for v in rig_meta.get("frame", (64, 64)))
        content = rig_meta.get("content")
        content_tuple = tuple(int(v) for v in content) if content else None
        scale = rig_meta.get("scale")
        scale_tuple = tuple(int(v) for v in scale) if scale else None
        anchor = rig_meta.get("anchor")
        anchor_tuple = tuple(int(v) for v in anchor) if anchor else None
        face = str(rig_meta.get("face", "right"))
        for anim, spec in sorted(rig_meta.get("anims", {}).items()):
            refs.append(AnimationRef(
                rig=rig,
                anim=anim,
                file=str(spec["file"]),
                frame=frame,
                frames=int(spec.get("frames", 1)),
                fps=float(spec.get("fps", 8.0)),
                loop=bool(spec.get("loop", True)),
                content=content_tuple,
                scale=scale_tuple,
                anchor=anchor_tuple,
                face=face,
            ))
    return refs


def find_pngs() -> list[str]:
    if not ASSETS_DIR.exists():
        return []
    return sorted(path.relative_to(ASSETS_DIR).as_posix() for path in ASSETS_DIR.rglob("*.png"))


def infer_frame_count(sheet: pygame.Surface, frame: tuple[int, int]) -> int:
    fw, fh = frame
    if fw <= 0 or fh <= 0:
        return 1
    return max(1, sheet.get_width() // fw)


def clamp_rect(rect: pygame.Rect, bounds: pygame.Rect) -> pygame.Rect:
    rect = rect.copy()
    rect.w = max(1, min(rect.w, bounds.w))
    rect.h = max(1, min(rect.h, bounds.h))
    rect.x = max(0, min(rect.x, bounds.w - rect.w))
    rect.y = max(0, min(rect.y, bounds.h - rect.h))
    return rect


def slice_frames(sheet: pygame.Surface, frame: tuple[int, int], count: int) -> list[pygame.Surface]:
    fw, fh = frame
    out: list[pygame.Surface] = []
    for index in range(max(1, count)):
        rect = pygame.Rect(index * fw, 0, fw, fh)
        if not sheet.get_rect().contains(rect):
            break
        out.append(sheet.subsurface(rect).copy())
    return out


def detect_shared_content(frames: list[pygame.Surface], alpha_threshold: int = 1) -> tuple[int, int, int, int]:
    if not frames:
        return (0, 0, 1, 1)
    rects: list[pygame.Rect] = []
    for frame in frames:
        mask = pygame.mask.from_surface(frame, alpha_threshold)
        rects.extend(mask.get_bounding_rects())
    if not rects:
        return (0, 0, frames[0].get_width(), frames[0].get_height())
    union = rects[0].copy()
    for rect in rects[1:]:
        union.union_ip(rect)
    return (union.x, union.y, union.w, union.h)


def build_metadata(draft: Draft) -> dict:
    rig_meta: dict[str, object] = {
        "frame": list(draft.frame),
        "content": list(draft.content),
        "face": draft.face,
        "anims": {
            draft.anim: {
                "file": draft.file,
                "frames": draft.frames,
                "fps": int(draft.fps) if draft.fps.is_integer() else draft.fps,
                "loop": draft.loop,
            }
        },
    }
    if draft.scale:
        rig_meta["scale"] = list(draft.scale)
    if draft.anchor:
        rig_meta["anchor"] = list(draft.anchor)
    return {draft.rig: rig_meta}


def metadata_text(draft: Draft) -> str:
    return json.dumps(build_metadata(draft), indent=2)


def save_metadata(draft: Draft) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{draft.rig}_{draft.anim}".replace("/", "_").replace(" ", "_")
    path = OUTPUT_DIR / f"{stem}.sprite.json"
    path.write_text(metadata_text(draft) + "\n", encoding="utf-8")
    return path


def try_copy_to_clipboard(text: str) -> bool:
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return True
    except Exception:
        return False


class Button:
    def __init__(self, rect: pygame.Rect, label: str, action: str) -> None:
        self.rect = rect
        self.label = label
        self.action = action


class SpriteSheetLab:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Sprite Sheet Lab")
        self.screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
        self.sheet_window = Window("Sprite Sheet View", size=SHEET_WINDOW_SIZE, resizable=True)
        self.sheet_renderer = Renderer(self.sheet_window)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 16) or pygame.font.Font(None, 16)
        self.small = pygame.font.SysFont("consolas", 13) or pygame.font.Font(None, 13)
        self.large = pygame.font.SysFont("consolas", 21) or pygame.font.Font(None, 21)
        self.refs = load_animation_refs()
        self.pngs = find_pngs()
        self.buttons: list[Button] = []
        self.mode = "metadata" if self.refs else "pngs"
        self.selected = 0
        self.sheet: pygame.Surface | None = None
        self.frames: list[pygame.Surface] = []
        self.draft: Draft | None = None
        self.current_frame = 0
        self.playing = True
        self.zoom_percent = 100
        self.show_scaled = False
        self.sheet_scroll_x = 0
        self.sheet_scroll_y = 0
        self.status = "Loaded metadata entries." if self.refs else "No metadata found; showing PNG files."
        self.dragging = False
        self.drag_origin = (0, 0)
        self.drag_rect_origin = pygame.Rect(0, 0, 1, 1)
        self.last_anim_tick = 0.0
        self.load_selected()

    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == getattr(pygame, "WINDOWCLOSE", -1):
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                elif event.type == pygame.KEYDOWN:
                    self.handle_key(event)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if self.is_sheet_event(event):
                        self.handle_sheet_mouse_down(event)
                    else:
                        self.handle_mouse_down(event)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self.dragging = False
                elif event.type == pygame.MOUSEMOTION:
                    if self.is_sheet_event(event):
                        self.handle_sheet_mouse_motion(event)
                elif event.type == pygame.MOUSEWHEEL:
                    self.handle_wheel(event)
            self.advance_animation(dt)
            self.draw()
        pygame.quit()

    def load_selected(self) -> None:
        items = self.current_items()
        if not items:
            self.sheet = None
            self.frames = []
            self.draft = None
            return
        self.selected = max(0, min(self.selected, len(items) - 1))
        try:
            if self.mode == "metadata":
                ref = self.refs[self.selected]
                self.sheet = pygame.image.load(str(ASSETS_DIR / ref.file)).convert_alpha()
                content = ref.content or detect_shared_content(slice_frames(self.sheet, ref.frame, ref.frames))
                self.draft = Draft(
                    rig=ref.rig,
                    anim=ref.anim,
                    file=ref.file,
                    frame=ref.frame,
                    frames=ref.frames,
                    fps=ref.fps,
                    loop=ref.loop,
                    content=content,
                    scale=ref.scale,
                    anchor=ref.anchor,
                    face=ref.face,
                )
            else:
                rel_path = self.pngs[self.selected]
                self.sheet = pygame.image.load(str(ASSETS_DIR / rel_path)).convert_alpha()
                frame = (self.sheet.get_height(), self.sheet.get_height())
                count = infer_frame_count(self.sheet, frame)
                content = detect_shared_content(slice_frames(self.sheet, frame, count))
                self.draft = Draft(
                    rig=Path(rel_path).parent.name or Path(rel_path).stem,
                    anim=Path(rel_path).stem,
                    file=rel_path,
                    frame=frame,
                    frames=count,
                    fps=8.0,
                    loop=True,
                    content=content,
                    scale=None,
                    anchor=None,
                    face="right",
                )
            self.rebuild_frames()
            self.current_frame = 0
            self.clamp_sheet_scroll()
            self.status = f"Loaded {self.draft.file}"
        except (FileNotFoundError, pygame.error, ValueError) as exc:
            self.sheet = None
            self.frames = []
            self.draft = None
            self.status = f"Unable to load selection: {exc}"

    def rebuild_frames(self) -> None:
        if self.sheet is None or self.draft is None:
            self.frames = []
            return
        raw = slice_frames(self.sheet, self.draft.frame, self.draft.frames)
        crop = pygame.Rect(*self.draft.content)
        frame_bounds = pygame.Rect(0, 0, *self.draft.frame)
        crop = clamp_rect(crop, frame_bounds)
        self.draft = replace(self.draft, content=(crop.x, crop.y, crop.w, crop.h), frames=max(1, len(raw)))
        self.frames = [frame.subsurface(crop).copy() for frame in raw]

    def current_items(self) -> list[AnimationRef] | list[str]:
        return self.refs if self.mode == "metadata" else self.pngs

    def select_delta(self, delta: int) -> None:
        items = self.current_items()
        if not items:
            return
        self.selected = (self.selected + delta) % len(items)
        self.load_selected()

    def is_sheet_event(self, event: pygame.event.Event) -> bool:
        return getattr(event, "window", None) == self.sheet_window.id

    def sheet_scale(self) -> float:
        return self.zoom_percent / 100.0

    def scaled_sheet_size(self) -> tuple[int, int]:
        if self.sheet is None:
            return (1, 1)
        scale = self.sheet_scale()
        return (max(1, round(self.sheet.get_width() * scale)),
                max(1, round(self.sheet.get_height() * scale)))

    def clamp_sheet_scroll(self) -> None:
        win_w, win_h = self.sheet_window.size
        sheet_w, sheet_h = self.scaled_sheet_size()
        view_w = max(1, win_w - PADDING * 2)
        view_h = max(1, win_h - SHEET_HEADER_H - PADDING * 2)
        self.sheet_scroll_x = max(0, min(self.sheet_scroll_x, max(0, sheet_w - view_w)))
        self.sheet_scroll_y = max(0, min(self.sheet_scroll_y, max(0, sheet_h - view_h)))

    def handle_key(self, event: pygame.event.Event) -> None:
        mods = pygame.key.get_mods()
        resize = bool(mods & pygame.KMOD_SHIFT)
        fast = 8 if mods & pygame.KMOD_CTRL else 1
        if event.key == pygame.K_ESCAPE:
            pygame.event.post(pygame.event.Event(pygame.QUIT))
        elif event.key == pygame.K_s and not resize:
            self.select_delta(1)
        elif event.key == pygame.K_w and not resize:
            self.select_delta(-1)
        elif event.key == pygame.K_TAB:
            self.toggle_mode()
        elif event.key == pygame.K_SPACE:
            self.playing = not self.playing
        elif event.key == pygame.K_a and not resize:
            self.current_frame = max(0, self.current_frame - 1)
        elif event.key == pygame.K_d and not resize:
            self.current_frame = min(max(0, len(self.frames) - 1), self.current_frame + 1)
        elif event.key == pygame.K_LEFT and not resize:
            self.nudge_crop(-fast, 0, 0, 0)
        elif event.key == pygame.K_RIGHT and not resize:
            self.nudge_crop(fast, 0, 0, 0)
        elif event.key == pygame.K_UP and not resize:
            self.nudge_crop(0, -fast, 0, 0)
        elif event.key == pygame.K_DOWN and not resize:
            self.nudge_crop(0, fast, 0, 0)
        elif event.key == pygame.K_LEFT and resize:
            self.nudge_crop(0, 0, -fast, 0)
        elif event.key == pygame.K_RIGHT and resize:
            self.nudge_crop(0, 0, fast, 0)
        elif event.key == pygame.K_UP and resize:
            self.nudge_crop(0, 0, 0, -fast)
        elif event.key == pygame.K_DOWN and resize:
            self.nudge_crop(0, 0, 0, fast)
        elif event.key == pygame.K_PAGEUP:
            self.sheet_scroll_y = max(0, self.sheet_scroll_y - 120)
        elif event.key == pygame.K_PAGEDOWN:
            self.sheet_scroll_y += 120
            self.clamp_sheet_scroll()
        elif event.key == pygame.K_q:
            self.sheet_scroll_x = max(0, self.sheet_scroll_x - 120)
        elif event.key == pygame.K_e:
            self.sheet_scroll_x += 120
            self.clamp_sheet_scroll()
        elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self.zoom_percent = min(MAX_ZOOM_PERCENT, self.zoom_percent + ZOOM_STEP_PERCENT)
            self.clamp_sheet_scroll()
        elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.zoom_percent = max(MIN_ZOOM_PERCENT, self.zoom_percent - ZOOM_STEP_PERCENT)
            self.clamp_sheet_scroll()
        elif event.key == pygame.K_f:
            self.show_scaled = not self.show_scaled
        elif event.key == pygame.K_r:
            self.auto_crop()
        elif event.key == pygame.K_c:
            self.copy_json()
        elif event.key == pygame.K_o:
            self.save_json()

    def handle_mouse_down(self, event: pygame.event.Event) -> None:
        if event.button == 1:
            for button in self.buttons:
                if button.rect.collidepoint(event.pos):
                    self.run_action(button.action)
                    return

    def handle_sheet_mouse_down(self, event: pygame.event.Event) -> None:
        if event.button == 1:
            crop_rect = self.crop_screen_rect()
            if crop_rect and crop_rect.collidepoint(event.pos):
                self.dragging = True
                self.drag_origin = event.pos
                self.drag_rect_origin = pygame.Rect(*self.draft.content) if self.draft else pygame.Rect(0, 0, 1, 1)
        elif event.button == 4:
            self.sheet_scroll_y = max(0, self.sheet_scroll_y - 32)
        elif event.button == 5:
            self.sheet_scroll_y += 32
            self.clamp_sheet_scroll()

    def handle_sheet_mouse_motion(self, event: pygame.event.Event) -> None:
        if not self.dragging or self.draft is None:
            return
        scale = self.sheet_scale()
        dx = round((event.pos[0] - self.drag_origin[0]) / scale)
        dy = round((event.pos[1] - self.drag_origin[1]) / scale)
        origin = self.drag_rect_origin
        self.set_crop(origin.x + dx, origin.y + dy, origin.w, origin.h)

    def handle_wheel(self, event: pygame.event.Event) -> None:
        if self.is_sheet_event(event):
            mods = pygame.key.get_mods()
            if event.x:
                self.sheet_scroll_x = max(0, self.sheet_scroll_x - event.x * 40)
            if mods & pygame.KMOD_SHIFT:
                self.sheet_scroll_x = max(0, self.sheet_scroll_x - event.y * 40)
            else:
                self.sheet_scroll_y = max(0, self.sheet_scroll_y - event.y * 40)
            self.clamp_sheet_scroll()
            return
        mouse_x = pygame.mouse.get_pos()[0]
        if mouse_x < SIDEBAR_W:
            self.select_delta(-event.y)

    def run_action(self, action: str) -> None:
        if action == "mode":
            self.toggle_mode()
        elif action == "auto":
            self.auto_crop()
        elif action == "copy":
            self.copy_json()
        elif action == "save":
            self.save_json()
        elif action == "scale":
            self.show_scaled = not self.show_scaled
        elif action == "play":
            self.playing = not self.playing

    def toggle_mode(self) -> None:
        self.mode = "pngs" if self.mode == "metadata" else "metadata"
        self.selected = 0
        self.load_selected()

    def nudge_crop(self, dx: int, dy: int, dw: int, dh: int) -> None:
        if self.draft is None:
            return
        x, y, w, h = self.draft.content
        self.set_crop(x + dx, y + dy, w + dw, h + dh)

    def set_crop(self, x: int, y: int, w: int, h: int) -> None:
        if self.draft is None:
            return
        rect = clamp_rect(pygame.Rect(x, y, w, h), pygame.Rect(0, 0, *self.draft.frame))
        self.draft = replace(self.draft, content=(rect.x, rect.y, rect.w, rect.h))
        self.rebuild_frames()

    def auto_crop(self) -> None:
        if self.sheet is None or self.draft is None:
            return
        frames = slice_frames(self.sheet, self.draft.frame, self.draft.frames)
        self.draft = replace(self.draft, content=detect_shared_content(frames))
        self.rebuild_frames()
        self.status = "Auto-detected shared content crop."

    def copy_json(self) -> None:
        if self.draft is None:
            return
        copied = try_copy_to_clipboard(metadata_text(self.draft))
        self.status = "Copied JSON snippet to clipboard." if copied else "Clipboard unavailable; use Save JSON."

    def save_json(self) -> None:
        if self.draft is None:
            return
        path = save_metadata(self.draft)
        self.status = f"Saved {path.relative_to(ROOT_DIR).as_posix()}"

    def advance_animation(self, dt: float) -> None:
        if not self.playing or not self.frames or self.draft is None:
            return
        self.last_anim_tick += dt
        frame_time = 1.0 / max(1.0, self.draft.fps)
        if self.last_anim_tick >= frame_time:
            steps = int(self.last_anim_tick / frame_time)
            self.last_anim_tick %= frame_time
            self.current_frame = (self.current_frame + steps) % len(self.frames)

    def draw(self) -> None:
        self.screen.fill(BG)
        self.buttons = []
        self.draw_sidebar()
        self.draw_workspace()
        self.draw_inspector()
        pygame.display.flip()
        self.draw_sheet_window()

    def draw_sidebar(self) -> None:
        area = pygame.Rect(0, 0, SIDEBAR_W, self.screen.get_height())
        pygame.draw.rect(self.screen, PANEL, area)
        self.text("Sprite Sheet Lab", (PADDING, 14), self.large, TEXT)
        self.text("Tab switches metadata / PNG browser", (PADDING, 42), self.small, MUTED)
        self.add_button(pygame.Rect(PADDING, 70, 138, 32), "Metadata" if self.mode == "pngs" else "PNG Browser", "mode")
        items = self.current_items()
        y = 118
        row_h = 34
        visible = max(1, (self.screen.get_height() - y - 20) // row_h)
        start = max(0, min(self.selected - visible // 2, max(0, len(items) - visible)))
        for offset, item in enumerate(items[start:start + visible]):
            index = start + offset
            rect = pygame.Rect(PADDING, y + offset * row_h, SIDEBAR_W - PADDING * 2, row_h - 4)
            pygame.draw.rect(self.screen, PANEL_ALT if index == self.selected else PANEL, rect, border_radius=4)
            if index == self.selected:
                pygame.draw.rect(self.screen, ACCENT, rect, 2, border_radius=4)
            if isinstance(item, AnimationRef):
                label = f"{item.rig}/{item.anim}"
                sub = item.file
            else:
                label = Path(item).name
                sub = str(Path(item).parent)
            self.text(label, (rect.x + 8, rect.y + 3), self.small, TEXT)
            self.text(sub, (rect.x + 8, rect.y + 18), self.small, MUTED)

    def draw_workspace(self) -> None:
        left = SIDEBAR_W
        right = self.screen.get_width() - INSPECTOR_W
        area = pygame.Rect(left, 0, max(120, right - left), self.screen.get_height())
        if self.sheet is None or self.draft is None:
            self.text(self.status, (area.x + PADDING, area.y + PADDING), self.large, WARN)
            return
        title = f"{self.draft.file}   frame {self.current_frame + 1}/{max(1, len(self.frames))}"
        self.text(title, (area.x + PADDING, 14), self.large, TEXT)
        self.text("Use the Sprite Sheet View window for sheet scrolling and crop dragging.",
                  (area.x + PADDING, 42), self.small, MUTED)

        self.draw_preview(pygame.Rect(area.x + PADDING, 86, area.w - PADDING * 2, 260))

    def draw_sheet_window(self) -> None:
        win_w, win_h = self.sheet_window.size
        canvas = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
        canvas.fill(BG)
        pygame.draw.rect(canvas, PANEL, pygame.Rect(0, 0, win_w, SHEET_HEADER_H))
        self.text_on(canvas, "Sprite Sheet View", (PADDING, 12), self.large, TEXT)
        if self.sheet is None or self.draft is None:
            self.text_on(canvas, self.status, (PADDING, 42), self.small, WARN)
            self.present_sheet_canvas(canvas)
            return

        self.clamp_sheet_scroll()
        zoom = f"{self.zoom_percent}%"
        scroll = f"scroll x:{self.sheet_scroll_x} y:{self.sheet_scroll_y}"
        self.text_on(canvas, f"{self.draft.file}   zoom {zoom}   {scroll}", (PADDING, 42), self.small, MUTED)
        self.text_on(canvas, "Wheel scrolls vertically. Shift+wheel or Q/E scrolls horizontally. +/- zooms 50%-600%.",
                     (win_w // 2, 42), self.small, MUTED)

        viewport = pygame.Rect(PADDING, SHEET_HEADER_H, max(1, win_w - PADDING * 2),
                               max(1, win_h - SHEET_HEADER_H - PADDING))
        pygame.draw.rect(canvas, (18, 20, 24), viewport)
        origin = (viewport.x - self.sheet_scroll_x, viewport.y - self.sheet_scroll_y)
        scaled_sheet = pygame.transform.scale(self.sheet, self.scaled_sheet_size())
        old_clip = canvas.get_clip()
        canvas.set_clip(viewport)
        canvas.blit(scaled_sheet, origin)
        self.draw_frame_grid(canvas, origin)
        self.draw_crop_overlay(canvas, origin)
        canvas.set_clip(old_clip)
        pygame.draw.rect(canvas, ACCENT, viewport, 1)
        self.present_sheet_canvas(canvas)

    def present_sheet_canvas(self, canvas: pygame.Surface) -> None:
        texture = Texture.from_surface(self.sheet_renderer, canvas)
        self.sheet_renderer.clear()
        self.sheet_renderer.blit(texture)
        self.sheet_renderer.present()

    def draw_frame_grid(self, target: pygame.Surface, origin: tuple[int, int]) -> None:
        if self.draft is None or self.sheet is None:
            return
        fw, fh = self.draft.frame
        scale = self.sheet_scale()
        for index in range(self.draft.frames):
            rect = pygame.Rect(origin[0] + round(index * fw * scale), origin[1],
                               max(1, round(fw * scale)), max(1, round(fh * scale)))
            color = ACCENT if index == self.current_frame else GRID
            pygame.draw.rect(target, color, rect, 1)

    def draw_crop_overlay(self, target: pygame.Surface, origin: tuple[int, int]) -> None:
        rect = self.crop_screen_rect(origin)
        if rect is None:
            return
        pygame.draw.rect(target, RED, rect, 2)

    def crop_screen_rect(self, origin: tuple[int, int] | None = None) -> pygame.Rect | None:
        if self.draft is None:
            return None
        if origin is None:
            origin = (PADDING - self.sheet_scroll_x, SHEET_HEADER_H - self.sheet_scroll_y)
        scale = self.sheet_scale()
        x, y, w, h = self.draft.content
        return pygame.Rect(
            origin[0] + round((self.current_frame * self.draft.frame[0] + x) * scale),
            origin[1] + round(y * scale),
            max(1, round(w * scale)),
            max(1, round(h * scale)),
        )

    def draw_preview(self, area: pygame.Rect) -> None:
        pygame.draw.rect(self.screen, PANEL, area, border_radius=6)
        self.text("Preview", (area.x + 12, area.y + 10), self.large, TEXT)
        if not self.frames or self.draft is None:
            return
        frame = self.frames[self.current_frame]
        label = "cropped"
        if self.show_scaled and self.draft.scale:
            frame = pygame.transform.scale(frame, self.draft.scale)
            label = "scaled"
        max_w = area.w - 40
        max_h = area.h - 56
        factor = min(max_w / frame.get_width(), max_h / frame.get_height(), 5)
        factor = max(1, int(factor))
        shown = pygame.transform.scale(frame, (frame.get_width() * factor, frame.get_height() * factor))
        pos = (area.centerx - shown.get_width() // 2, area.y + 46)
        self.screen.blit(shown, pos)
        self.text(label, (area.x + 12, area.bottom - 24), self.small, MUTED)

    def draw_inspector(self) -> None:
        x = self.screen.get_width() - INSPECTOR_W
        area = pygame.Rect(x, 0, INSPECTOR_W, self.screen.get_height())
        pygame.draw.rect(self.screen, PANEL, area)
        self.text("Metadata", (x + PADDING, 14), self.large, TEXT)
        y = 52
        if self.draft is None:
            self.text(self.status, (x + PADDING, y), self.small, WARN)
            return
        lines = [
            f"rig: {self.draft.rig}",
            f"anim: {self.draft.anim}",
            f"frame: {list(self.draft.frame)}",
            f"frames: {self.draft.frames}",
            f"fps: {self.draft.fps:g}",
            f"loop: {str(self.draft.loop).lower()}",
            f"content: {list(self.draft.content)}",
            f"scale: {list(self.draft.scale) if self.draft.scale else None}",
            f"anchor: {list(self.draft.anchor) if self.draft.anchor else None}",
            f"face: {self.draft.face}",
        ]
        for line in lines:
            self.text(line, (x + PADDING, y), self.small, TEXT)
            y += 22

        y += 10
        self.add_button(pygame.Rect(x + PADDING, y, 130, 32), "Play/Pause", "play")
        self.add_button(pygame.Rect(x + PADDING + 142, y, 130, 32), "Scaled", "scale")
        y += 44
        self.add_button(pygame.Rect(x + PADDING, y, 130, 32), "Auto Crop", "auto")
        self.add_button(pygame.Rect(x + PADDING + 142, y, 130, 32), "Copy JSON", "copy")
        y += 44
        self.add_button(pygame.Rect(x + PADDING, y, 272, 32), "Save JSON Snippet", "save")
        y += 52

        self.text("Shortcuts", (x + PADDING, y), self.large, TEXT)
        y += 30
        for line in [
            "Mouse wheel: browse/scroll",
            "W/S: previous/next asset",
            "A/D: previous/next frame",
            "+/-: zoom sheet",
            "F: toggle scale preview",
            "C: copy JSON",
            "O: save JSON",
            "Esc: quit",
        ]:
            self.text(line, (x + PADDING, y), self.small, MUTED)
            y += 20
        self.text(self.status, (x + PADDING, self.screen.get_height() - 42), self.small,
                  GOOD if self.status.startswith(("Saved", "Copied", "Loaded")) else WARN)

    def add_button(self, rect: pygame.Rect, label: str, action: str) -> None:
        self.buttons.append(Button(rect, label, action))
        mouse_over = rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(self.screen, PANEL_ALT if mouse_over else BG, rect, border_radius=5)
        pygame.draw.rect(self.screen, ACCENT, rect, 1, border_radius=5)
        text = self.small.render(label, True, TEXT)
        self.screen.blit(text, text.get_rect(center=rect.center))

    def text(self, value: str, pos: tuple[int, int], font: pygame.font.Font, color: tuple[int, int, int]) -> None:
        surface = font.render(value, True, color)
        self.screen.blit(surface, pos)

    def text_on(self, target: pygame.Surface, value: str, pos: tuple[int, int],
                font: pygame.font.Font, color: tuple[int, int, int]) -> None:
        surface = font.render(value, True, color)
        target.blit(surface, pos)


def main() -> int:
    SpriteSheetLab().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())