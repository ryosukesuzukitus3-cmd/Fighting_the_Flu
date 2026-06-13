"""ボス弾幕パターン プレビューツール。

ステージを起動せずにボスの弾幕だけをウィンドウで確認する。
プレイヤー位置はマウスカーソルに追従するのでインタラクティブに確認できる。

使い方:
  python tools/preview_boss.py --stage 4 --pattern vortex3
  python tools/preview_boss.py --stage 4              # 実際のフェーズ遷移を再現
  python tools/preview_boss.py --stage 4 --pattern all  # 全パターンを自動切替
  python tools/preview_boss.py --list                 # パターン一覧を表示して終了
"""
from __future__ import annotations
import argparse
import math
import sys
from pathlib import Path

# プロジェクトルートを sys.path に追加
sys.path.insert(0, str(Path(__file__).parent.parent))

import pygame

# ── 定数 ────────────────────────────────────────────────────────
WIN_W, WIN_H = 800, 600
BOSS_SX      = 580
BOSS_SY      = WIN_H // 2
FPS          = 60
AUTO_CYCLE   = 4.0   # --pattern all のときに自動切替する秒数

# boss.py の _PHASE_CONFIGS を唯一のソースとして使う
from src.entities.enemies.boss import _PHASE_CONFIGS as _BOSS_PHASE_CONFIGS
_ALL_PATTERNS: list[str] = sorted({
    pat
    for phases in _BOSS_PHASE_CONFIGS.values()
    for _, pat, _ in phases
})

# ── モックオブジェクト ───────────────────────────────────────────

class _MockResources:
    """pygame.Surface ダミー画像を返すリソースマネージャのスタブ"""
    def image(self, path: str) -> pygame.Surface:
        s = pygame.Surface((68, 80))
        s.fill((180, 60, 60))
        pygame.draw.rect(s, (220, 100, 100), (4, 4, 60, 72), 2)
        return s

    def sound(self, *a, **kw):
        return None


class _MockSound:
    def play_se(self, *a, **kw): pass
    def play_se_alias(self, *a, **kw): pass
    def play_bgm(self, *a, **kw): pass
    def stop_bgm(self, *a, **kw): pass


class _MockGame:
    resources = _MockResources()
    sound     = _MockSound()


class _MockPlayer:
    """プレイヤー位置をマウスに追従させる"""
    sx: float = WIN_W / 2
    sy: float = WIN_H / 2


# ── パターン固定ボスラッパー ────────────────────────────────────

class _PreviewBoss:
    """Boss を最小限ラップし、指定パターンを強制的に発射させる。"""

    def __init__(self, stage_id: int, pattern: str | None, interval: float = 0.55) -> None:
        from src.entities.enemies.boss import Boss, _PHASE_CONFIGS
        self._boss          = Boss(_MockGame(), stage_id=stage_id)
        self._boss._state   = "fight"   # 入場アニメをスキップ
        self._boss.sx       = float(BOSS_SX)
        self._boss.sy       = float(BOSS_SY)
        self._boss.rect.center = (BOSS_SX, BOSS_SY)
        self._fixed_pattern = pattern   # None のとき実際のフェーズに従う
        self._fixed_interval = interval
        self._shoot_timer   = 0.5

        # フィールドキャッシュ
        self._PHASE_CONFIGS = _PHASE_CONFIGS
        self._stage_id      = stage_id

    def _phase_override(self) -> tuple:
        if self._fixed_pattern:
            return (1.0, self._fixed_pattern, self._fixed_interval)
        # 実フェーズを返す（HP依存）
        return self._boss._phase

    def update(self, dt: float, bullets: pygame.sprite.Group, player: _MockPlayer) -> None:
        self._boss._time += dt
        self._boss._spiral_angle = self._boss._spiral_angle  # keep
        self._shoot_timer -= dt
        if self._shoot_timer <= 0:
            # _phase を一時的に差し替えてから _shoot を呼ぶ
            orig_phase_prop = type(self._boss)._phase
            fixed = self._phase_override()
            type(self._boss)._phase = property(lambda s: fixed)
            self._boss._shoot(bullets, player)
            type(self._boss)._phase = orig_phase_prop
            self._shoot_timer = fixed[2]

    @property
    def image(self) -> pygame.Surface:
        return self._boss.image

    @property
    def rect(self) -> pygame.Rect:
        return self._boss.rect

    @property
    def current_pattern(self) -> str:
        if self._fixed_pattern:
            return self._fixed_pattern
        return self._boss._phase[1]


# ── メインループ ────────────────────────────────────────────────

def run(stage_id: int, pattern: str | None, auto_all: bool) -> None:
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("Boss Pattern Preview")
    clock  = pygame.time.Clock()

    patterns     = _ALL_PATTERNS if auto_all else ([pattern] if pattern else [None])
    pat_idx      = 0
    cycle_timer  = AUTO_CYCLE
    bullets: pygame.sprite.Group = pygame.sprite.Group()
    player  = _MockPlayer()

    boss = _PreviewBoss(stage_id, patterns[pat_idx])

    font_lg = pygame.font.SysFont("ms gothic", 22, bold=True)
    font_sm = pygame.font.SysFont("ms gothic", 16)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        # ── イベント ───────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    # 手動で次パターンへ
                    bullets.empty()
                    pat_idx  = (pat_idx + 1) % len(patterns)
                    boss     = _PreviewBoss(stage_id, patterns[pat_idx])
                    cycle_timer = AUTO_CYCLE
                elif event.key == pygame.K_r:
                    # リセット（同パターンを最初から）
                    bullets.empty()
                    boss = _PreviewBoss(stage_id, patterns[pat_idx])
                elif event.key == pygame.K_LEFTBRACKET:
                    # 射撃間隔を長く
                    boss._fixed_interval = min(boss._fixed_interval + 0.1, 3.0)
                elif event.key == pygame.K_RIGHTBRACKET:
                    # 射撃間隔を短く
                    boss._fixed_interval = max(boss._fixed_interval - 0.1, 0.05)

        # マウス位置をプレイヤー位置に反映
        mx, my = pygame.mouse.get_pos()
        player.sx = float(mx)
        player.sy = float(my)

        # ── 更新 ───────────────────────────────────────────────
        boss.update(dt, bullets, player)

        for b in list(bullets):
            b.update(dt)
            if b.is_off_screen():
                b.kill()

        # auto_all: 自動切替
        if auto_all:
            cycle_timer -= dt
            if cycle_timer <= 0:
                bullets.empty()
                pat_idx     = (pat_idx + 1) % len(patterns)
                boss        = _PreviewBoss(stage_id, patterns[pat_idx])
                cycle_timer = AUTO_CYCLE

        # ── 描画 ───────────────────────────────────────────────
        screen.fill((15, 15, 30))

        # グリッド（補助線）
        for x in range(0, WIN_W, 80):
            pygame.draw.line(screen, (30, 30, 50), (x, 0), (x, WIN_H))
        for y in range(0, WIN_H, 60):
            pygame.draw.line(screen, (30, 30, 50), (0, y), (WIN_W, y))

        # プレイヤー照準
        pygame.draw.circle(screen, (80, 200, 80), (int(player.sx), int(player.sy)), 8, 2)
        pygame.draw.line(screen, (80, 200, 80),
                         (int(player.sx) - 14, int(player.sy)),
                         (int(player.sx) + 14, int(player.sy)), 1)
        pygame.draw.line(screen, (80, 200, 80),
                         (int(player.sx), int(player.sy) - 14),
                         (int(player.sx), int(player.sy) + 14), 1)

        # 弾・ボス
        bullets.draw(screen)
        screen.blit(boss.image, boss.rect)

        # HUD
        pat_name = boss.current_pattern or "（フェーズ追従）"
        interval = boss._fixed_interval
        hud_lines = [
            f"Stage {stage_id}  Pattern: {pat_name}  interval={interval:.2f}s",
            f"Bullets: {len(bullets)}",
            "SPACE: 次パターン  R: リセット  [/]: 間隔調整  ESC: 終了",
        ]
        if auto_all:
            hud_lines[0] += f"  （{cycle_timer:.1f}s で自動切替）"
            hud_lines.insert(1, f"({pat_idx+1}/{len(patterns)})")

        for i, line in enumerate(hud_lines):
            color = (255, 220, 80) if i == 0 else (160, 160, 160)
            s = (font_lg if i == 0 else font_sm).render(line, True, color)
            screen.blit(s, (10, 10 + i * 22))

        pygame.display.flip()

    pygame.quit()


# ── エントリポイント ────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="ボス弾幕パターン プレビューツール")
    parser.add_argument("--stage",   type=int, default=4,
                        help="ステージ番号 1-4 (default: 4)")
    parser.add_argument("--pattern", type=str, default=None,
                        help="パターン名 (省略時はフェーズ追従)")
    parser.add_argument("--all",     action="store_true",
                        help="全パターンを AUTO_CYCLE 秒ごとに自動切替")
    parser.add_argument("--list",    action="store_true",
                        help="パターン一覧を表示して終了")
    args = parser.parse_args()

    if args.list:
        print("利用可能なパターン:")
        for p in _ALL_PATTERNS:
            print(f"  {p}")
        return

    if args.pattern and args.pattern not in _ALL_PATTERNS:
        print(f"ERROR: 不明なパターン '{args.pattern}'")
        print(f"利用可能: {', '.join(_ALL_PATTERNS)}")
        sys.exit(1)

    run(stage_id=args.stage, pattern=args.pattern, auto_all=args.all)


if __name__ == "__main__":
    main()
