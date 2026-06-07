from __future__ import annotations
import pygame
from src.core.scene import Scene
from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT


def _build_pages(settings) -> list[dict]:
    """現在のキーバインドに追従した説明ページを生成する。"""
    fire   = settings.key_display("fire")
    laser  = settings.key_display("laser")
    wsel   = settings.key_display("weapon_select")
    pause  = settings.key_display("pause")
    return [
        {
            "title": "操作方法",
            "lines": [
                "  矢印キー    ……  移動",
                f"  {fire} キー       ……  通常射撃（長押しで連射）",
                f"  {laser} キー   ……  チャージレーザー",
                f"  {wsel} キー       ……  ウェポン選択画面",
                f"  {pause} キー       ……  ポーズ",
            ],
        },
        {
            "title": "アイテム / 強化",
            "lines": [
                "  W (黄)  ……  ウェポン在庫 +1",
                f"          取得後 {wsel} で選択画面 → ←→で選ぶ → ENTERで強化",
                "          MAIN / SPEED / LASER / HOMING / BARRIER",
                "  +  (緑)  ……  HP を回復",
            ],
        },
        {
            "title": "敵・ボス",
            "lines": [
                "  バイキン  ……  直進する通常敵",
                "  タケシ    ……  波打ちながら接近",
                "  ブロリー  ……  接近後に高速突進",
                "",
                "  ボス出現でカメラ停止。HPに応じて攻撃が激化。",
                "  ボスはステージごとに シールド / 装甲 / 砲台 など",
                "  弱点や攻撃チャンスが異なる。表示をよく見て攻めよう。",
            ],
        },
    ]


class TutorialScene(Scene):
    def on_enter(self) -> None:
        self._font_title = self.game.resources.pixelfont(36)
        self._font_body  = self.game.resources.pixelfont(22)
        self._pages      = _build_pages(self.game.settings)
        self._page       = 0

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        inp = self.game.input
        if inp.is_just_pressed(pygame.K_RIGHT) or inp.is_just_pressed(pygame.K_SPACE):
            if self._page < len(self._pages) - 1:
                self._page += 1
                self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)
            else:
                self.game.sound.play_se("music/se/メニュー操作SE：決定.mp3", volume=0.6)
                from src.scenes.title import TitleScene
                self.game.change_scene(TitleScene(self.game))
        if inp.is_just_pressed(pygame.K_LEFT):
            if self._page > 0:
                self._page -= 1
                self.game.sound.play_se("music/se/メニュー操作SE：カーソル移動.mp3", volume=0.5)
        if inp.is_just_pressed(pygame.K_x):
            self.game.sound.play_se("music/se/メニュー操作SE：キャンセル.mp3", volume=0.5)
            from src.scenes.title import TitleScene
            self.game.change_scene(TitleScene(self.game))

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((10, 20, 15))
        cx = SCREEN_WIDTH // 2
        page = self._pages[self._page]

        title = self._font_title.render(page["title"], True, (100, 220, 120))
        screen.blit(title, (cx - title.get_width() // 2, 80))

        for i, line in enumerate(page["lines"]):
            surf = self._font_body.render(line, True, (200, 200, 200))
            screen.blit(surf, (cx - 230, 180 + i * 44))

        # ページインジケーター
        dots = "  ".join(
            "●" if i == self._page else "○" for i in range(len(self._pages))
        )
        dot_surf = self._font_body.render(dots, True, (120, 200, 120))
        screen.blit(dot_surf, (cx - dot_surf.get_width() // 2, SCREEN_HEIGHT - 80))

        if self._page < len(self._pages) - 1:
            hint_text = "SPACE / → : 次ページ   X: タイトルへ"
        else:
            hint_text = "SPACE: タイトルへ戻る   X: タイトルへ"
        hint = self._font_body.render(hint_text, True, (100, 100, 100))
        screen.blit(hint, (cx - hint.get_width() // 2, SCREEN_HEIGHT - 46))
