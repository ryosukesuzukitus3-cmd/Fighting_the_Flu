"""Diagnostic campaign controller using only agent_playtest input commands.

This is not a human difficulty benchmark: it reads current diagnostic positions
and waits at least 12 simulated frames before choosing another input. It never
changes a game object, grants equipment, heals, warps, or forces an enemy death.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.agent_playtest import Session
from tools.playtest_state import boundary, mode


def _swept_intersects(start, end, other_start, other_end):
    """Strict AABB overlap at any time while both rectangles move linearly."""
    entry, leave = 0.0, 1.0
    for a_min, a_max, b_min, b_max, relative in (
        (start.left, start.right, other_start.left, other_start.right,
         end.x - start.x - (other_end.x - other_start.x)),
        (start.top, start.bottom, other_start.top, other_start.bottom,
         end.y - start.y - (other_end.y - other_start.y)),
    ):
        if relative == 0:
            if a_max <= b_min or a_min >= b_max:
                return False
            continue
        t1 = (b_min - a_max) / relative
        t2 = (b_max - a_min) / relative
        entry = max(entry, min(t1, t2))
        leave = min(leave, max(t1, t2))
        if entry >= leave:
            return False
    return entry < leave


def _escape_distance(hit, danger, bounds, obstacles=()):
    """Distance to a clear cardinal exit inside the playable area.

    A nearby edge of a beam is useless if reaching it needs leaving the screen
    or crossing solid terrain. Positions and rectangles are read-only inputs.
    """
    if not hit.colliderect(danger):
        return 0
    offsets = ((danger.left - hit.right - 2, 0),
               (danger.right - hit.left + 2, 0),
               (0, danger.top - hit.bottom - 2),
               (0, danger.bottom - hit.top + 2))
    distances = []
    for dx, dy in offsets:
        destination = hit.move(dx, dy)
        if not bounds.contains(destination):
            continue
        path = hit.union(destination)
        if any(destination.colliderect(wall) or
               (not hit.colliderect(wall) and path.colliderect(wall))
               for wall in obstacles):
            continue
        distances.append(abs(dx) + abs(dy))
    # All cardinal exits can be blocked. Do not invent an offscreen escape.
    return min(distances, default=bounds.width + bounds.height)


class Campaign:
    def __init__(self, session, interval=12, max_frames=72000):
        if type(interval) is not int or not 12 <= interval <= 600:
            raise ValueError("decision interval must be 12..600 frames")
        self.session = session
        self.interval = interval
        self.max_frames = max_frames
        self.decisions = 0
        self.victory_reached = False
        self.completed = False
        self.reason = "frame budget"
        self.scenes = []
        self.deaths = []
        self.damage = []
        self.upgrades = []
        self._previous_boundary = None
        self._previous_scene = None
        self._previous_hp = None
        self._previous_attacks = []
        self._previous_player_rect = None
        self._previous_player_position = None
        self._previous_note_frame = None
        self._previous_weapon = None
        self._previous_position = {}
        self._last_plan_frame = None
        self._scene_generation = 0
        self._last_page = None
        self.pages = []
        self._cooling = False
        self._attack_target = False
        self._laser_target = False
        sources = [*sorted((ROOT / "src").rglob("*.py")), Path(__file__).resolve(),
                   ROOT / "tools/agent_playtest.py", ROOT / "tools/playtest_state.py"]
        (session.output_dir / "source-fingerprints.json").write_text(json.dumps({
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sources}, indent=2), encoding="utf-8")
        self._trace = (session.output_dir / "campaign.jsonl").open("w", encoding="utf-8")

    def pulse(self, action):
        return [] if action in self.session.held_actions else [action]

    def note(self, observation):
        scene = self.session.game._scene
        name = type(scene).__name__
        changed_scene = scene is not self._previous_scene
        if changed_scene:
            self._scene_generation += 1
            entry = {"frame": observation["frame"], "scene": name,
                     "stage": self.session.game.shared.stage}
            self.scenes.append(entry)
            self.session.command({"capture": f"scene-{self._scene_generation:03d}-{name}"})
            print(json.dumps({"event": "scene", **entry}), flush=True)
            self._previous_scene = scene
            self._previous_hp = None
            self._previous_attacks = []
            self._previous_player_rect = None
            self._previous_player_position = None
            self._previous_note_frame = None
            self._previous_weapon = None
            self._previous_position.clear()
            self._cooling = False
            if name == "GameOverScene":
                self.deaths.append({**entry, "score": observation["score"],
                                    "lives": observation["lives"]})
            if name == "GameClearScene":
                self.victory_reached = True
            elif name == "TitleScene" and self.victory_reached:
                self.completed = True
                self.reason = "completed campaign and returned to title"
        player = getattr(scene, "player", None)
        if player is not None:
            if self._previous_hp is not None and player.hp < self._previous_hp:
                event = {"frame": observation["frame"], "stage": observation["stage"],
                         "from": self._previous_hp, "to": player.hp,
                         "position": list(player.rect.center),
                         "actions": list(observation["held_actions"]),
                         "previous_frame": self._previous_note_frame,
                         "previous_player_rect": self._previous_player_rect,
                         "previous_player_position": self._previous_player_position,
                         "previous_attacks": self._previous_attacks}
                event["heat"] = getattr(getattr(scene, "_heat", None), "heat", None)
                event["nearby_attacks"] = [
                    {"kind": type(b).__name__, "rect": list(b.rect),
                     "damage": getattr(b, "damage", None),
                     "warning": getattr(b, "warning_only", False),
                     "terrain_bounced": getattr(b, "_terrain_bounced", False)}
                    for b in getattr(scene, "enemy_bullets", ())
                    if b.rect.inflate(160, 160).colliderect(player.rect)]
                event["enemies"] = [{"kind": type(e).__name__, "rect": list(e.rect),
                                     "state": getattr(e, "_state", None)}
                                    for e in getattr(scene, "enemies", ())]
                event["image"] = self.session.command({"capture": f"damage-{len(self.damage):03d}"})["image"]
                self.damage.append(event)
                print(json.dumps({"event": "damage", **event}), flush=True)
            self._previous_hp = player.hp
            self._previous_note_frame = observation["frame"]
            self._previous_player_rect = list(player.rect)
            self._previous_player_position = list(player.rect.center)
            self._previous_attacks = [
                {"kind": type(b).__name__, "rect": list(b.rect),
                 "vx": getattr(b, "vx", 0), "vy": getattr(b, "vy", 0),
                 "damage": getattr(b, "damage", None),
                 "warning": getattr(b, "warning_only", False),
                 "terrain_bounced": getattr(b, "_terrain_bounced", False)}
                for b in getattr(scene, "enemy_bullets", ())]
            weapon = player.weapon.snapshot()
            if self._previous_weapon is not None and weapon != self._previous_weapon:
                self.upgrades.append({"frame": observation["frame"], "weapon": weapon})
            self._previous_weapon = weapon
        current_boundary = boundary(scene)
        dialogue = observation.get("dialogue")
        page_key = (self._scene_generation, current_boundary, repr(dialogue))
        if dialogue and page_key != self._last_page:
            self.pages.append({"frame": observation["frame"], "scene": name,
                               "stage": observation["stage"], "dialogue": dialogue})
            self._last_page = page_key
        record = {"frame": observation["frame"], "scene": name, "mode": mode(scene),
                  "stage": observation["stage"], "hp": getattr(player, "hp", None),
                  "actions": observation["held_actions"], "state_digest": observation["state_digest"]}
        if name == "GameScene":
            boss = getattr(scene, "_boss", None)
            record.update(position=list(player.rect.center), stage_elapsed=scene._stage_elapsed,
                          camera_x=scene.camera.x, heat=round(scene._heat.heat, 2) if scene._heat else None,
                          overheated=bool(scene._heat and scene._heat.overheated),
                          laser=scene.laser.state,
                          weapon=player.weapon.snapshot(), companion=scene._companion is not None,
                          boss=({"hp": boss.hp, "form2": boss._form2, "form3": boss._form3,
                                 "act": boss._form3_act} if boss is not None else None))
        if current_boundary != self._previous_boundary:
            record["boundary"] = True
            if dialogue:
                record["dialogue"] = dialogue
            self._previous_boundary = current_boundary
        self._trace.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._trace.flush()

    def advance(self, actions):
        # Boundary stops expose intermediate screens but do not speed up decisions.
        remaining = self.interval
        while remaining > 0:
            result = self.session.command({"step": remaining, "actions": sorted(set(actions))})
            remaining -= result["advanced"]
            self.note(result)
            if result["advanced"] == 0:
                raise RuntimeError("game stopped without advancing")
        return result

    def upgrade_input(self, scene):
        from src.scenes.game.config import UPGRADE_SLOTS, COMPANION_SLOTS

        weapon = scene.player.weapon
        zone = scene._upg_zone
        if zone == "top":
            choices = scene._top_available_indices()
            priorities = []
            if weapon.main_level < 2:
                priorities += ["weapon_main"]
            if weapon.laser_level < 1:
                priorities += ["laser"]
            if weapon.speed_level < 1:
                priorities += ["speed"]
            if weapon.main_level < 4:
                priorities += ["weapon_main"]
            if weapon.laser_level < 3:
                priorities += ["laser"]
            if weapon.speed_level < 2:
                priorities += ["speed"]
            priorities += ["homing", "laser", "speed", "weapon_main"]
            desired = next((i for key in priorities for i in choices if UPGRADE_SLOTS[i][0] == key), None)
            return self.pulse("ui_accept" if scene._upg_top_cursor == desired else "menu_right")
        if zone == "bottom":
            choices = scene._bottom_available_indices()
            comp = scene._companion
            priorities = []
            if comp.lv_supply < 1:
                priorities += ["kt_supply"]
            if comp.lv_magnet < 2:
                priorities += ["kt_magnet"]
            if comp.lv_shot < 3:
                priorities += ["kt_shot"]
            priorities += ["kt_supply", "kt_hp", "kt_magnet", "kt_shot"]
            desired = next((i for key in priorities for i in choices if COMPANION_SLOTS[i][0] == key), None)
            return self.pulse("ui_accept" if scene._upg_bottom_cursor == desired else "menu_right")
        return self.pulse("ui_accept")

    def movement(self, scene):
        from src.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT
        from src.entities.terrain_query import iter_collidable_terrain

        player = scene.player
        center = player.rect.center
        camera = getattr(scene, "camera", None)
        scroll = camera.scroll_speed if camera else 0
        boss = getattr(scene, "_boss", None)
        enemies = list(getattr(scene, "enemies", ()))
        dummy = getattr(scene, "_dummy", None)
        if dummy is not None:
            enemies.append(dummy)
        terrain = list(iter_collidable_terrain(getattr(scene, "terrain", ())))
        items = [item for item in getattr(scene, "items", ()) if -20 < item.rect.centerx < 770]
        needed = [item for item in items if type(item).__name__ != "HealItem" or player.hp < 85]
        target_x, target_y = 170.0, 300.0
        target = None
        cannons = [e for e in enemies if type(e).__name__ == "EnemyBroly"
                   and player.rect.right < e.rect.centerx < 830]
        self._attack_target = bool(boss or enemies or any(getattr(t, "destructible", False)
                                   and player.rect.right < t.rect.left < 800 for t in terrain))
        self._laser_target = self._attack_target
        if cannons:
            target = min(cannons, key=lambda e: e.rect.left)
            target_y = target.rect.centery
            target_x = min(200, max(80, target.rect.left - 220))
        elif needed:
            target = min(needed, key=lambda item: math.dist(center, item.rect.center)
                         - (110 if type(item).__name__ == "WeaponItem" else 0))
            target_x, target_y = target.rect.center
        else:
            gates = [t for t in terrain if getattr(t, "fixed_drop", None) == "WeaponItem"
                     and player.rect.right + 30 < t.rect.left < 800]
            targets = ([boss] if boss is not None else []) + gates + [e for e in enemies
                       if e.rect.centerx > player.rect.right and e.rect.left < 800]
            if targets:
                target = targets[0] if boss else min(targets, key=lambda e: e.rect.left)
                target_y = target.rect.centery
                target_x = min(200, max(80, target.rect.left - 220))
            elif getattr(scene, "_post_boss", False):
                target_x = 785
        target_y = max(40, min(540, target_y))
        bullets = [b for b in getattr(scene, "enemy_bullets", ())
                   if type(b).__name__ not in ("LaserMuzzleFlash", "LaserChargeOrb")
                   and not getattr(b, "_terrain_bounced", False)]
        hazards = []
        for obj in bullets:
            # Visible warnings are future danger, even before collision activates.
            weight = 0.8 if getattr(obj, "warning_only", False) else 1.0
            hazards.append((obj.rect, getattr(obj, "vx", 0), getattr(obj, "vy", 0), weight))
        for obj in enemies + ([boss] if boss is not None else []):
            previous = self._previous_position.get(id(obj))
            elapsed = ((self.session.frame - self._last_plan_frame) / 60
                       if self._last_plan_frame is not None else 0)
            vx = (obj.rect.centerx - previous[0]) / elapsed if previous and elapsed else -scroll
            vy = (obj.rect.centery - previous[1]) / elapsed if previous and elapsed else 0
            hazards.append((obj.rect, vx, vy, 1.7))
        for obj in terrain:
            hazards.append((obj.rect, -scroll, 0, 2.5))
        speed = 280 * player.weapon.speed_multiplier
        best = None
        best_cost = (True, float("inf"))
        period = self.interval / 60
        # Keep the whole player sprite on screen, even when scoring its smaller
        # collision rectangle. Terrain is projected using the same horizon.
        hit_bounds = player.rect.__class__(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
        hit_bounds = hit_bounds.inflate(player.hit_rect.width - player.rect.width,
                                        player.hit_rect.height - player.rect.height)
        predictions = [(horizon,
                        [(rect.move(int(vx * horizon), int(vy * horizon)), weight)
                         for rect, vx, vy, weight in hazards],
                        [obj.rect.move(int(-scroll * horizon), 0) for obj in terrain])
                       for horizon in (period / 4, period / 2, period, period * 2)]
        for dx, dy in ((0, 0), (0, -1), (0, 1), (-1, 0), (1, 0),
                       (-1, -1), (-1, 1), (1, -1), (1, 1)):
            scale = math.sqrt(0.5) if dx and dy else 1
            cost = 0.0
            enters_terrain = False
            previous_hit = player.hit_rect
            previous_hazards = [rect for rect, _, _, _ in hazards]
            previous_terrain = [obj.rect for obj in terrain]
            for horizon, predicted_hazards, predicted_terrain in predictions:
                px = max(player.rect.width / 2, min(SCREEN_WIDTH - player.rect.width / 2,
                     center[0] + dx * speed * scale * horizon))
                py = max(player.rect.height / 2, min(SCREEN_HEIGHT - player.rect.height / 2,
                     center[1] + dy * speed * scale * horizon))
                hit = player.hit_rect.copy()
                hit.center = int(px), int(py)
                for before, (predicted, weight) in zip(previous_hazards, predicted_hazards):
                    # A narrow bullet can cross the player entirely between
                    # sampled endpoints. Score that path as a collision too.
                    if (not previous_hit.colliderect(before)
                            and _swept_intersects(previous_hit, hit, before, predicted)):
                        cost += 14000 * weight
                    gap_x = max(predicted.left - hit.right, hit.left - predicted.right, 0)
                    gap_y = max(predicted.top - hit.bottom, hit.top - predicted.bottom, 0)
                    distance = math.hypot(gap_x, gap_y)
                    if distance < 1:
                        depth = _escape_distance(hit, predicted, hit_bounds, predicted_terrain)
                        cost += (14000 + depth * 350) * weight
                    elif distance < 70:
                        cost += 220 * weight / (distance + 3)
                if horizon <= period:
                    enters_terrain |= any(
                        not player.hit_rect.colliderect(obj.rect)
                        and _swept_intersects(previous_hit, hit, before, after)
                        for obj, before, after in zip(terrain, previous_terrain, predicted_terrain))
                previous_hit = hit
                previous_hazards = [rect for rect, _ in predicted_hazards]
                previous_terrain = predicted_terrain
                cost += (abs(px - target_x) * 0.18 + abs(py - target_y) * 0.42) / 4
                if px < 55 or py < 35 or py > 545:
                    cost += 25
            # The game pushes the player out of solid terrain. A forecast that
            # travels through it is not an achievable escape path. Prefer a
            # clear path, retaining a least-cost fallback if every path is hit.
            candidate_cost = (enters_terrain, cost)
            if candidate_cost < best_cost:
                best_cost, best = candidate_cost, (dx, dy)
        self._previous_position = {id(obj): obj.rect.center for obj in enemies + ([boss] if boss else [])}
        self._last_plan_frame = self.session.frame
        dx, dy = best
        actions = []
        if dx:
            actions.append("move_right" if dx > 0 else "move_left")
        if dy:
            actions.append("move_down" if dy > 0 else "move_up")
        return actions, bullets

    def decide(self):
        scene = self.session.game._scene
        name = type(scene).__name__
        state = mode(scene)
        if name == "TitleScene" and self.victory_reached:
            self.completed = True
            self.reason = "completed campaign and returned to title"
            return None
        if name == "GameOverScene":
            if self.session.game.shared.lives <= 0:
                self.reason = "continues exhausted"
                return None
            return self.pulse("ui_accept")
        if state == "dialogue":
            return self.pulse("ui_accept")
        if state == "choice":
            return self.pulse("ui_accept")
        if state == "input_gate":
            return self.pulse("fire")
        if state == "upgrade":
            return self.upgrade_input(scene)
        if state == "pause":
            return self.pulse("pause")
        if name in ("DisclaimerScene", "TitleScene", "StageClearScene", "GameClearScene"):
            return self.pulse("ui_accept")
        if name == "TutorialScene":
            if scene._phase == "move":
                return ["move_up"] if scene._moved_h else ["move_right"]
            actions, _ = self.movement(scene)
            return actions + ["fire"]
        if name != "GameScene":
            return []
        if not scene._accepts_combat_input and not scene._post_boss:
            return []
        if scene._top_available_indices() or scene._bottom_available_indices():
            return self.pulse("weapon_select")
        actions, bullets = self.movement(scene)
        heat = scene._heat
        if heat is not None:
            if heat.overheated or heat.heat >= 80:
                self._cooling = True
            elif heat.heat <= 48:
                self._cooling = False
        if not self._cooling and self._attack_target:
            actions.append("fire")
        if not (heat and heat.overheated) and scene.player.weapon.has_laser:
            if scene.laser.state == "charging" and scene.laser.charge_ratio < 0.85:
                actions.append("laser")
            elif (scene.laser.state == "ready" and self._laser_target
                  and (heat is None or heat.heat < 66)):
                actions.append("laser")
        if scene._pieces and "bomb" not in self.session.held_actions:
            if any(math.dist(scene.player.rect.center, b.rect.center) < 140 for b in bullets):
                actions.append("bomb")
        return actions

    def run(self):
        started = time.monotonic()
        self.note(self.session.command({"observe": True}))
        try:
            while self.session.frame < self.max_frames:
                if (self.session.output_dir / "stop.request").exists():
                    self.reason = "stopped by request"
                    break
                actions = self.decide()
                if actions is None:
                    break
                self.decisions += 1
                self.advance(actions)
                if self.decisions % 100 == 0:
                    scene = self.session.game._scene
                    print(json.dumps({"event": "progress", "frame": self.session.frame,
                                      "scene": type(scene).__name__, "stage": self.session.game.shared.stage,
                                      "score": self.session.game.shared.score,
                                      "hp": getattr(getattr(scene, "player", None), "hp", None),
                                      "heat": getattr(getattr(scene, "_heat", None), "heat", None),
                                      "boss_hp": getattr(getattr(scene, "_boss", None), "hp", None)}), flush=True)
        except Exception as exc:
            self.completed = False
            self.reason = f"controller error: {type(exc).__name__}: {exc}"
            raise
        finally:
            final = self.session.command({"capture": "campaign-final"})
            summary = {"controller": "diagnostic position-reading bot; not human difficulty evidence",
                       "rule_overrides": [], "minimum_decision_frames": self.interval,
                       "victory_reached": self.victory_reached,
                       "completed": self.completed, "reason": self.reason,
                       "frame": self.session.frame, "simulated_seconds": self.session.game.elapsed_time,
                       "wall_seconds": time.monotonic() - started, "decisions": self.decisions,
                       "score": self.session.game.shared.score, "kills": self.session.game.shared.kill_count,
                       "scenes": self.scenes, "deaths": self.deaths, "damage": self.damage,
                       "weapon_changes": self.upgrades, "observed_dialogue_samples": self.pages,
                       "final": final}
            (self.session.output_dir / "campaign-summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            self._trace.close()
        return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--interval", type=int, default=12)
    parser.add_argument("--max-frames", type=int, default=72000)
    args = parser.parse_args(argv)
    session = Session(args.output, seed=args.seed, diagnostic=True)
    try:
        result = Campaign(session, args.interval, args.max_frames).run()
        print(json.dumps({key: result[key] for key in
                          ("victory_reached", "completed", "reason", "frame", "score", "kills")}), flush=True)
        return 0 if result["completed"] else 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
