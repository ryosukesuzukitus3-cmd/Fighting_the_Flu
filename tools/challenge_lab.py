"""Compare equal-cost loadouts in authored road challenges or boss rooms.

The planned policy uses diagnostic state; reactive uses only current projectile
rectangles with a 300 ms observation interval. Neither estimates human deaths.
Setup grants the selected loadout once. During play only normal input is used.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.agent_playtest import Session
from tools.agent_campaign import Campaign
from tools.playtest_state import mode

BUILDS = {
 'balanced': ['speed','laser','weapon_main','weapon_main','laser','homing','speed','laser','weapon_main','weapon_main','homing','laser','speed'],
 'mobility': ['speed','weapon_main','speed','laser','weapon_main','speed','laser','weapon_main','homing','weapon_main','laser','homing','laser'],
 'laser': ['laser','weapon_main','laser','speed','laser','weapon_main','laser','speed','laser','weapon_main','laser','weapon_main','homing'],
 'homing': ['homing','weapon_main','speed','homing','weapon_main','homing','speed','homing','weapon_main','homing','weapon_main','homing','laser'],
}
BUDGETS = {'road': (2,5,8,11), 'boss': (3,6,9,13)}


def reactive_actions(scene):
    """Avoid nearby visible danger, with the same terrain safety as normal flight.

    Only the current nearby shot direction is read; future positions and attack
    schedules are ignored. Both policies
    decide every 200ms, so differences are not caused by a different reaction rate.
    """
    from src.entities.terrain_query import iter_collidable_terrain
    from src.core.balance import PLAYER_BASE_SPEED
    player = scene.player
    hit = player.hit_rect
    targets = list(scene.enemies) + ([scene._boss] if scene._boss else [])
    target_y = min(targets, key=lambda e:e.rect.left).rect.centery if targets else hit.centery
    dangers = [b.rect.inflate(100,100) for b in scene.enemy_bullets
               if not getattr(b, '_terrain_bounced', False)
               and b.rect.inflate(100,100).colliderect(hit)]
    shots = [b for b in scene.enemy_bullets if not getattr(b,'_terrain_bounced',False)
             and b.rect.inflate(100,100).colliderect(hit)]
    nearest = min(shots,key=lambda b:math.dist(hit.center,b.rect.center)) if shots else None
    horizontal = (nearest is not None and (nearest.rect.width > 180
                  or abs(getattr(nearest,'vx',0)) > abs(getattr(nearest,'vy',0))))
    terrain = list(iter_collidable_terrain(scene.terrain))
    choices = []
    for dx, dy, keys in ((0,0,()), (0,-1,('move_up',)), (0,1,('move_down',)),
                         (-1,0,('move_left',)), (1,0,('move_right',))):
        travel = PLAYER_BASE_SPEED * player.weapon.speed_multiplier * .2
        blocked = False
        for fraction in (.25,.5,.75,1):
            rect = hit.move((dx*travel + scene.camera.scroll_speed*.2)*fraction, dy*travel*fraction)
            if (rect.top < 85 or rect.bottom > 540 or rect.left < 16 or rect.right > 480
                    or any(rect.colliderect(t.rect) for t in terrain)):
                blocked = True
                break
        if blocked:
            continue
        # Prefer reducing overlap immediately, even if one 200ms step cannot
        # leave the danger zone entirely. A binary penalty would freeze in place.
        penalty = sum(10000 + 100*min(rect.bottom-d.top, d.bottom-rect.top,
                                     rect.right-d.left, d.right-rect.left)
                      for d in dangers if rect.colliderect(d))
        cost = penalty + abs(rect.centery-target_y) + abs(rect.centerx-170)*.2
        choices.append((cost, keys))
    if nearest is not None:
        perpendicular = ('move_up','move_down') if horizontal else ('move_left','move_right')
        sidesteps = [c for c in choices if any(k in c[1] for k in perpendicular)]
        if sidesteps:
            choices = sidesteps
    return ['fire','laser', *(min(choices)[1] if choices else ())]


def trial(args):
    from src.scenes.game_scene import GameScene
    session = Session(args.output,args.seed,diagnostic=True,save_step_images=False)
    game = session.game
    game.start_new_run()
    game.story.karonaru_available = args.stage < 4
    scene = GameScene(game,args.stage)
    game._scene = scene
    scene.on_enter()
    budget = BUDGETS[args.kind][args.stage-1]
    for upgrade in BUILDS[args.build][:budget]:
        scene.player.weapon.upgrade(upgrade)
    if scene._companion:
        # A limited, fixed support allocation for comparable player builds.
        for key in ['kt_hp','kt_supply','kt_shot','kt_magnet','kt_shot','kt_supply'][:budget//2]:
            scene._companion.apply_upgrade(key)
    if args.kind == 'road':
        scene.camera.x = scene.stage.learning['checkpoint_x']
        scene.spawner._spawn_due_world_events(scene.camera)
    else:
        boss_event = next(e for e in scene.stage.world_events if e['type']=='Boss')
        scene.camera.x = boss_event['x'] - 800
        scene.spawner.spawn_terrain_events(scene.stage.world_events,scene.camera)
        scene.spawner.skip_all_events()
    scene.terrain.update(0,scene.camera)
    for group in (scene.enemies,scene.enemy_bullets,scene.items):
        group.empty()
    scene._safe_restart_position()
    scene._stage_banner_timer = scene._bgm_delay = 0
    if args.kind == 'boss':
        scene.camera.scroll_speed = 0
        scene._queue_boss_spawn(args.stage)
    session._cache()
    setup = dict(stage=args.stage,kind=args.kind,build=args.build,points=budget,
                 weapon=scene.player.weapon.snapshot(),seed=args.seed,policy=args.policy)
    session.metadata['scenario_setup'] = setup
    (session.output_dir/'session.json').write_text(json.dumps(session.metadata,indent=2),encoding='utf-8')
    controller = Campaign(session, interval=12)
    combat_frames = 0
    outcome = 'timeout'
    result = None
    try:
        while session.frame < args.seconds*60:
            if (session.output_dir/'stop.request').exists():
                outcome='stopped';break
            if game._scene is not scene or scene.player.hp <= 0:
                outcome='defeated';break
            if scene._post_boss or args.kind=='road' and scene._learning_done:
                outcome='cleared';break
            state=mode(scene)
            if state=='combat' and args.policy != 'planned':
                actions=reactive_actions(scene) if args.policy=='reactive' else ['fire','laser']
                controller._planned_move_frames=None
                controller.last_plan={"policy":args.policy,"actions":actions}
            else:
                actions=controller.decide() or []
            before=session.frame
            controller.decisions+=1
            controller.advance(actions)
            if state=='combat':
                combat_frames+=session.frame-before
        session.command({'capture':'result'})
        result=dict(setup=setup,result=outcome,seconds=round(combat_frames/60,2),
                    hp=scene.player.hp,damage_count=len(controller.damage),
                    damage=controller.damage,frames=session.frame,
                    limitation='Prepared authored arena; input policies are diagnostic, not human players.')
        (session.output_dir/'trial.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='damage'},ensure_ascii=False),flush=True)
    finally:
        controller._trace.close()
        session.close()
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',type=int,choices=range(1,5),required=True)
    parser.add_argument('--kind',choices=('road','boss'),default='road')
    parser.add_argument('--build',choices=BUILDS,default='balanced')
    parser.add_argument('--policy',choices=('planned','reactive','stationary'),default='planned')
    parser.add_argument('--seed',type=int,default=11)
    parser.add_argument('--seconds',type=int,default=180)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    result=trial(args)
    return 0 if result['result']=='cleared' else 1
if __name__=='__main__':
    raise SystemExit(main())
