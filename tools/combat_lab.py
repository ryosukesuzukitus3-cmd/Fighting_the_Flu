"""Repeatable boss trials using real Game.step and ordinary input after setup.

The arena/equipment setup is explicit and separate from a normal campaign.
No healing, invincibility, forced hits or enemy changes occur during a trial.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.agent_playtest import Session
from tools.agent_campaign import Campaign
from tools.playtest_state import mode


def run_trial(args):
    session = Session(args.output, args.seed, diagnostic=True)
    from src.scenes.game_scene import GameScene
    from tools.headless import apply_weapon
    game = session.game
    game.shared.stage = args.stage
    game.story.karonaru_available = args.stage < 4
    scene = GameScene(game, stage_id=args.stage)
    game._scene = scene
    scene.on_enter()
    scene.spawner.skip_all_events()
    for group in (scene.enemies, scene.enemy_bullets, scene.terrain, scene.items):
        group.empty()
    scene.camera.scroll_speed = 0
    scene._stage_banner_timer = scene._bgm_delay = 0
    scene.player._entering = False
    scene.player.sx, scene.player.sy = 140., 280.
    scene.player.rect.topleft = (140, 280)
    apply_weapon(scene, main=args.main, laser=args.laser, homing=args.homing)
    scene._queue_boss_spawn(args.stage)
    session._cache()
    setup = dict(stage=args.stage, main=args.main, laser=args.laser,
                 homing=args.homing, policy=args.policy, interval=args.interval,
                 arena='empty; normal boss introduction and rules', seed=args.seed)
    session.metadata['scenario_setup'] = setup
    (session.output_dir / 'session.json').write_text(json.dumps(session.metadata, indent=2), encoding='utf-8')
    controller = Campaign(session, interval=args.interval)
    events, samples, frames = [], [], Counter()
    previous_shot = None
    previous_form = None
    previous_heat = False
    previous_cue = None
    cue_count = 0
    overheats = 0
    result = 'timeout'
    try:
        while session.frame < args.seconds * 60:
            if (session.output_dir / "stop.request").exists():
                result = "stopped_by_request"
                break
            current = game._scene
            if current is not scene or scene.player.hp <= 0:
                result = 'defeated'
                break
            if scene._post_boss:
                result = 'boss_defeated'
                break
            state = mode(scene)
            actions = controller.decide() or []
            if state == 'combat':
                if args.policy == 'main':
                    actions = [a for a in actions if a != 'laser']
                elif args.policy in ('hold', 'reckless'):
                    actions = [a for a in actions if a != 'laser']
                    actions += ['fire', 'laser']
                    if args.policy == 'reckless':
                        actions = ['fire', 'laser']
            before = session.frame
            controller.decisions += 1
            controller.advance(actions)
            frames[state] += session.frame - before
            boss = scene._boss
            if boss is not None and state == 'combat':
                form = str(boss._form_key())
                shot = (form, boss._shot_variant)
                if shot != previous_shot and boss._shot_variant:
                    events.append(dict(frame=session.frame, form=form,
                                       pattern=boss._phase[1], volley=boss._shot_variant,
                                       charging=boss._beam_charge_pattern,
                                       hp=boss.hp))
                    previous_shot = shot
                if form != previous_form:
                    session.command({'capture': f'form-{form}'})
                    previous_form = form
                cue = 'warning' if boss._beam_charge_pattern else 'opening' if boss.is_stance_down else 'attack'
                if cue != previous_cue:
                    session.command({'capture': f'cue-{cue_count:03d}-{cue}'})
                    cue_count += 1
                    previous_cue = cue
                hot = bool(scene._heat and scene._heat.overheated)
                overheats += int(hot and not previous_heat)
                previous_heat = hot
                samples.append(dict(frame=session.frame, form=form, boss_hp=boss.hp,
                                    down=boss.is_stance_down, player_hp=scene.player.hp,
                                    heat=scene._heat.heat if scene._heat else 0,
                                    laser=scene.laser.state, actions=actions))
        session.command({'capture': 'result'})
        report = dict(setup=setup, result=result, combat_seconds=round(frames['combat']/60, 2),
                      player_hp=scene.player.hp, overheats=overheats,
                      events=events, damage=controller.damage,
                      inputs=controller.decisions, frames=dict(frames),
                      limitation='Prepared arena; diagnostic coordinates; not human difficulty or a campaign')
        (session.output_dir/'trial.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        (session.output_dir/'samples.json').write_text(json.dumps(samples), encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k not in ('events','damage')}, ensure_ascii=False), flush=True)
        return report
    finally:
        controller._trace.close()
        session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--stage', type=int, choices=range(1,5), default=2)
    parser.add_argument('--main', type=int, choices=range(5), default=4)
    parser.add_argument('--laser', type=int, choices=range(7), default=3)
    parser.add_argument('--homing', type=int, choices=range(8), default=0)
    parser.add_argument('--policy', choices=('adaptive','hold','main','reckless'), default='adaptive')
    parser.add_argument('--seed', type=int, default=11)
    parser.add_argument('--interval', type=int, default=12)
    parser.add_argument('--seconds', type=int, default=180)
    args = parser.parse_args()
    if args.seconds < 1:
        parser.error("--seconds must be positive")
    if not 12 <= args.interval <= 600:
        parser.error("--interval must be 12..600")
    report = run_trial(args)
    return 0 if report["result"] == "boss_defeated" else 1

if __name__ == '__main__':
    raise SystemExit(main())
