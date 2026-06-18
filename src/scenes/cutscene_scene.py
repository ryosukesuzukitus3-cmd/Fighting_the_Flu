"""データ駆動の全画面カットシーン。

`src/story/lines.py` の `Page`（話者＋複数行）リストを、タイプライター＋
話者ネームプレート＋SE/FX 付きで順次再生する。終了後は on_complete を呼ぶ。

プロローグ・ステージ幕間・ブラックホール・エピローグ・エンドロール等で共用。
"""
from __future__ import annotations
import math
import random
from typing import Callable
import pygame

from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.scenes.dialogue_panel import DARK_STYLE, LIGHT_STYLE, draw_story_panel
from src.story.lines import Page

_TYPEWRITER_SPEED = 30.0   # 1秒あたりの文字数
_TYPE_SE_INTERVAL = 0.045
_TYPE_SE_VOLUME = 0.16


class CutsceneScene(Scene):
    def __init__(self, game, pages: list[Page], on_complete: Callable[[], None],
                 *, theme: str = "dark", bgm_alias: str | None = None,
                 stop_bgm: bool = False, title: str | None = None,
                 decor: "Callable[[pygame.Surface, float], None] | None" = None,
                 fade_out_on_finish: bool = True) -> None:
        super().__init__(game)
        self._pages       = list(pages)
        self._on_complete = on_complete
        self._theme       = theme
        self._bgm_alias   = bgm_alias
        self._stop_bgm    = stop_bgm
        self._title       = title
        self._decor       = decor   # 呼び出し元が渡す追加描画フック(surf, progress 0.0-1.0)
        # 同テーマの会話シーンへ地続きに繋ぐ場合は黒フェードを挟まず即遷移する
        self._fade_out_on_finish = fade_out_on_finish

    # ── ライフサイクル ────────────────────────────────────────────
    def on_enter(self) -> None:
        self._font_name  = self.game.resources.pixelfont(20)
        self._font_body  = self.game.resources.pixelfont(26)
        self._font_hint  = self.game.resources.pixelfont(18)
        self._font_title = self.game.resources.pixelfont(40)
        self._page       = 0
        self._chars      = 0.0
        self._blink      = 0.0
        self._type_se_cooldown = 0.0
        self._shake_t    = 0.0
        self._flash_t    = 0.0
        # FX 駆動
        self._fx_time    = 0.0      # 渦回転・脈動用アキュムレータ
        self._glitch_t   = 0.0      # 文字化け残り時間
        self._redglow    = False    # 赤後光（red_noise）有効ページか
        self._fade_in_t  = 0.45     # 入場の黒フェード残り
        self._fade_out_active = False
        self._fade_out_t = 0.0
        self._finished   = False    # on_complete 多重呼び防止
        self._story_active  = None   # 直近に話した登場人物（立ち絵ハイライト用）
        self._story_partner = None   # その前に話した登場人物（会話相手）
        if self._stop_bgm:
            self.game.sound.stop_bgm()
        elif self._bgm_alias:
            self.game.sound.play_bgm_alias(self._bgm_alias)
        self._enter_page()

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    # ── ページ進行 ────────────────────────────────────────────────
    def _cur(self) -> Page:
        return self._pages[self._page]

    def _enter_page(self) -> None:
        self._chars = 0.0
        self._type_se_cooldown = 0.0
        if not self._pages:
            return
        pg = self._cur()
        # 立ち絵ハイライト用に直近2人の登場人物を記録（味方左/敵右の割り当ては描画時）
        from src.story.speakers import is_character
        if is_character(pg.speaker) and pg.speaker != self._story_active:
            self._story_partner = self._story_active
            self._story_active = pg.speaker
        if pg.se:
            self.game.sound.play_se_alias(pg.se)
        if "shake" in pg.fx or "blackhole" in pg.fx:
            self._shake_t = 0.4
        if any(f in pg.fx for f in ("fade_white", "white_particle", "light")):
            self._flash_t = 0.35
        if "glitch" in pg.fx:
            self._glitch_t = 0.6
        self._redglow = ("red_noise" in pg.fx)

    def _total_chars(self) -> int:
        return sum(len(ln) for ln in self._cur().lines)

    def _is_complete(self) -> bool:
        return int(self._chars) >= self._total_chars()

    def _tick_type_sound(self, dt: float, previous_chars: int) -> None:
        self._type_se_cooldown = max(0.0, self._type_se_cooldown - dt)
        current_chars = min(int(self._chars), self._total_chars())
        if current_chars > previous_chars and self._type_se_cooldown <= 0.0:
            self.game.sound.play_se_alias("SE_TYPE", volume=_TYPE_SE_VOLUME)
            self._type_se_cooldown = _TYPE_SE_INTERVAL

    def _begin_finish(self) -> None:
        """黒フェードアウトを開始する（完了時に on_complete）。
        fade_out_on_finish=False の場合はフェードを挟まず即 on_complete。"""
        if self._fade_out_active or self._finished:
            return
        if not self._fade_out_on_finish:
            self._finished = True
            self._on_complete()
            return
        self._fade_out_active = True
        self._fade_out_t = 0.0

    def update(self, dt: float) -> None:
        self._blink   += dt
        self._fx_time += dt
        if self._shake_t  > 0: self._shake_t  -= dt
        if self._flash_t  > 0: self._flash_t  -= dt
        if self._glitch_t > 0: self._glitch_t -= dt
        if self._fade_in_t > 0: self._fade_in_t -= dt
        previous_chars = min(int(self._chars), self._total_chars())
        if not self._is_complete():
            self._chars = min(self._chars + _TYPEWRITER_SPEED * dt, float(self._total_chars()))
        self._tick_type_sound(dt, previous_chars)

        # 黒フェードアウト中は入力を受けず、完了で on_complete
        if self._fade_out_active:
            self._fade_out_t += dt
            if self._fade_out_t >= 0.4 and not self._finished:
                self._finished = True
                self._on_complete()
            return

        if not self._pages:
            self._begin_finish()
            return

        inp = self.game.input
        # ENTER/SPACE は長押しで連続送り（オートリピート）
        advance = (inp.is_held_with_repeat(pygame.K_RETURN, 0.25, 0.12)
                   or inp.is_held_with_repeat(pygame.K_SPACE, 0.25, 0.12))
        if advance:
            if not self._is_complete():
                self._chars = float(self._total_chars() + 1)
            elif self._page < len(self._pages) - 1:
                self._page += 1
                self._enter_page()
            else:
                self._begin_finish()
        if inp.is_just_pressed(pygame.K_x):
            self._begin_finish()

    # ── 背景テーマ ────────────────────────────────────────────────
    def _draw_bg(self, screen: pygame.Surface) -> None:
        theme = self._theme
        if theme == "window":
            self._draw_window_bg(screen)
        elif theme == "blackhole":
            self._draw_blackhole_bg(screen)
        elif theme == "chessboard":
            self._draw_chessboard_bg(screen)
        else:  # "dark"
            screen.fill((8, 8, 20))

    def _draw_blackhole_bg(self, screen: pygame.Surface) -> None:
        """承認欲求ブラックホール: 中心へ収束する回転アーク＋吸い込み粒子。"""
        screen.fill((6, 4, 14))
        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        t = self._fx_time
        # 暗紫グラデの同心円（外周ほど暗い）
        for i in range(7, 0, -1):
            r = 60 + i * 46
            a = max(0, 60 - i * 7)
            ring = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(ring, (60, 24, 80, a), (r, r), r)
            screen.blit(ring, (cx - r, cy - r))
        # 回転スパイラルアーク
        for arm in range(5):
            pts = []
            for k in range(26):
                ang = t * 1.4 + arm * (6.2832 / 5) + k * 0.32
                rad = 18 + k * 13
                px = cx + math.cos(ang) * rad
                py = cy + math.sin(ang) * rad
                pts.append((px, py))
            if len(pts) >= 2:
                pygame.draw.lines(screen, (130, 70, 160), False, pts, 2)
        # 吸い込まれる白い粒子（決定的擬似ランダム）
        for n in range(40):
            seed = (n * 137) % 360
            ang = t * (0.8 + (n % 5) * 0.2) + math.radians(seed)
            phase = (t * (0.4 + (n % 7) * 0.05) + n * 0.13) % 1.0
            rad = (1.0 - phase) * 340 + 6
            px = int(cx + math.cos(ang) * rad)
            py = int(cy + math.sin(ang) * rad)
            a = int(220 * phase)
            sz = 2 if phase < 0.6 else 1
            s = pygame.Surface((sz * 2, sz * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (220, 210, 255, a), (sz, sz), sz)
            screen.blit(s, (px, py))
        # 中心の黒い穴
        pygame.draw.circle(screen, (2, 1, 6), (cx, cy), 30)
        pygame.draw.circle(screen, (40, 18, 60), (cx, cy), 30, 2)

    def _draw_window_bg(self, screen: pygame.Surface) -> None:
        """エピローグ用: 日差しの差し込む窓とカーテン。"""
        screen.fill((252, 245, 220))
        ray = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for i in range(5):
            ox = 160 + i * 90
            pygame.draw.polygon(ray, (255, 255, 190, 22), [
                (ox, 0), (ox + 50, 0), (ox + 220, SCREEN_HEIGHT), (ox + 170, SCREEN_HEIGHT)])
        screen.blit(ray, (0, 0))
        wfx = SCREEN_WIDTH // 2 - 150
        wfy, wfw, wfh = 25, 300, 260
        pygame.draw.rect(screen, (205, 225, 255), (wfx + 6, wfy + 6, wfw - 12, wfh - 12))
        pygame.draw.rect(screen, (85, 55, 25), (wfx, wfy, wfw, wfh), 7)
        pygame.draw.line(screen, (85, 55, 25), (wfx, wfy + wfh // 2), (wfx + wfw, wfy + wfh // 2), 5)
        pygame.draw.line(screen, (85, 55, 25), (wfx + wfw // 2, wfy), (wfx + wfw // 2, wfy + wfh), 5)
        for side in range(2):
            cx0 = 0 if side == 0 else SCREEN_WIDTH - 135
            pygame.draw.rect(screen, (215, 195, 155), (cx0, 0, 135, SCREEN_HEIGHT))
            sign = 1 if side == 0 else -1
            for fx in range(cx0 + 15, cx0 + 135, 22):
                pygame.draw.line(screen, (182, 162, 122), (fx, 0), (fx + sign * 10, SCREEN_HEIGHT), 2)

    def _draw_chessboard_bg(self, screen: pygame.Surface) -> None:
        """歪む将棋盤: 市松模様に縦方向の軽い遠近ワープを加える。"""
        screen.fill((12, 10, 20))
        cell = 64
        t = self._fx_time
        for gy in range(0, SCREEN_HEIGHT, cell):
            warp = int(math.sin(t * 0.9 + gy * 0.02) * 10)
            for gx in range(0, SCREEN_WIDTH, cell):
                if (gx // cell + gy // cell) % 2 == 0:
                    pygame.draw.rect(screen, (24, 20, 38), (gx + warp, gy, cell, cell))
        # 盤の縦線（うっすら）
        for gx in range(0, SCREEN_WIDTH + cell, cell):
            pygame.draw.line(screen, (34, 30, 50), (gx, 0), (gx, SCREEN_HEIGHT), 1)

    # ── 描画ヘルパ ────────────────────────────────────────────────
    _OUTLINE_OFFSETS = ((-2, 0), (2, 0), (0, -2), (0, 2),
                        (-2, -2), (2, 2), (-2, 2), (2, -2))

    def _blit_outlined(self, screen: pygame.Surface, font: pygame.font.Font,
                       text: str, color: tuple[int, int, int],
                       cx: int, y: int, *, outline: bool = True,
                       x: int | None = None) -> None:
        """中央寄せ（または x 指定）でテキストを描く。outline=True で黒い8方向縁取り。"""
        base = font.render(text, True, color)
        bx = (cx - base.get_width() // 2) if x is None else x
        if outline:
            ol = font.render(text, True, (0, 0, 0))
            for dx, dy in self._OUTLINE_OFFSETS:
                screen.blit(ol, (bx + dx, y + dy))
        screen.blit(base, (bx, y))

    # ── 描画 ──────────────────────────────────────────────────────
    def draw(self, screen: pygame.Surface) -> None:
        self._draw_bg(screen)

        # シェイクオフセット
        ox = oy = 0
        if self._shake_t > 0:
            ox = random.randint(-5, 5)
            oy = random.randint(-5, 5)

        cx = SCREEN_WIDTH // 2 + ox
        cy = SCREEN_HEIGHT // 2 + oy
        is_light_bg = (self._theme == "window")

        # タイトル（任意）
        if self._title:
            tcol = (100, 40, 20) if is_light_bg else (120, 50, 30)
            tsurf = self._font_title.render(self._title, True, tcol)
            screen.blit(tsurf, (cx - tsurf.get_width() // 2, 44))

        if not self._pages:
            return
        pg = self._cur()

        glitch = self._glitch_t > 0
        from src.scenes.dialogue_panel import story_sides
        left_sp, right_sp = story_sides(self._story_active, self._story_partner)
        draw_story_panel(
            screen,
            self.game.resources,
            pg.speaker,
            pg.lines,
            left_speaker=left_sp,
            right_speaker=right_sp,
            chars=int(self._chars),
            page_index=self._page,
            total_pages=len(self._pages),
            complete=self._is_complete(),
            blink=self._blink,
            hint_last="ENTER: 続ける   X: スキップ",
            hint_next="ENTER: 次へ   X: スキップ",
            style=LIGHT_STYLE if is_light_bg else DARK_STYLE,
            text_transform=self._glitch_text if glitch else None,
            text_color=(210, 60, 60) if glitch else None,
            text_jitter=6 if glitch else 0,
            center=("center" in pg.fx),   # 強調ページ（fx に "center"）は中央寄せ
        )

        # フラッシュ（白）
        if self._flash_t > 0:
            a = int(200 * (self._flash_t / 0.35))
            fl = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            fl.fill((255, 255, 255, a))
            screen.blit(fl, (0, 0))

        # 赤後光（red_noise）: 脈動する赤いヴィネット
        if self._redglow:
            self._draw_red_glow(screen)

        # 追加描画フック（呼び出し元が渡したデコレーター）
        if self._decor is not None:
            progress = self._page / max(1, len(self._pages) - 1)
            self._decor(screen, progress)

        # 黒フェード（入場・退場）
        fade_a = 0
        if self._fade_in_t > 0:
            fade_a = int(255 * (self._fade_in_t / 0.45))
        elif self._fade_out_active:
            fade_a = int(255 * min(1.0, self._fade_out_t / 0.4))
        if fade_a > 0:
            fade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            fade.set_alpha(fade_a)
            fade.fill((0, 0, 0))
            screen.blit(fade, (0, 0))

    # ── FX ヘルパ ──────────────────────────────────────────────────
    _GLITCH_POOL = "▓▒░#%&@*+=<>0101ノイズ█▌▐"

    def _glitch_text(self, s: str) -> str:
        """一部の文字をランダムに置換した文字列を返す（文字化け表現）。"""
        out = []
        for ch in s:
            if ch != " " and random.random() < 0.3:
                out.append(random.choice(self._GLITCH_POOL))
            else:
                out.append(ch)
        return "".join(out)

    def _draw_red_glow(self, screen: pygame.Surface) -> None:
        """画面端から滲む赤い後光（脈動）。"""
        pulse = 0.5 + 0.5 * math.sin(self._fx_time * 5.0)
        a = int(50 + 60 * pulse)
        glow = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        # 四辺から内側へ赤を重ねる（簡易ヴィネット）
        band = 90
        for i in range(band):
            edge_a = int(a * (1 - i / band))
            if edge_a <= 0:
                continue
            col = (140, 0, 10, edge_a)
            pygame.draw.rect(glow, col, (i, i, SCREEN_WIDTH - i * 2, SCREEN_HEIGHT - i * 2), 1)
        screen.blit(glow, (0, 0))
