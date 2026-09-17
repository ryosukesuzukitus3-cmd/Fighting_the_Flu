"""Read-only observations for agent_playtest; never update or draw here."""
from __future__ import annotations


def mode(scene):
    name = type(scene).__name__
    if getattr(scene, '_choosing', False):
        return 'choice'
    if getattr(scene, '_in_dialogue', False):
        return 'dialogue'
    if getattr(scene, '_paused', False):
        return 'pause'
    if getattr(scene, '_upgrading', False):
        return 'upgrade'
    final = getattr(scene, '_final', None)
    if final and final.input_gate_active:
        return 'input_gate'
    if (getattr(scene, '_cutin_active', False)
            or getattr(scene, '_defeat_dialogue_active', False)
            or (final and final.dialogue_active)
            or getattr(scene, '_boss_intro_state', '') in ('pre_dialogue', 'boss_dialogue')
            or name in ('CutsceneScene', 'BlackholeScene')):
        return 'dialogue'
    if name == 'GameScene':
        return 'combat' if scene._accepts_combat_input else 'transition'
    return name.removesuffix('Scene').lower()


def boundary(scene):
    """Stop a long input at a changed scene, mode, or dialogue page."""
    final = getattr(scene, '_final', None)
    return (id(scene), mode(scene), getattr(scene, '_page', None),
            getattr(scene, '_cutin_idx', None),
            getattr(scene, '_boss_intro_page_idx', None),
            getattr(scene, '_defeat_dialogue_index', None),
            getattr(final, '_final_dialogue_idx', None),
            getattr(final, 'seq', None), getattr(scene, '_dialogue_idx', None),
            getattr(scene, '_phase', None))


def _dialogue(scene):
    final = getattr(scene, '_final', None)
    candidates = [
        (scene, '_dialogue', '_dialogue_idx', getattr(scene, '_in_dialogue', False)),
        (scene, '_pages', '_page', hasattr(scene, '_page')),
        (scene, '_cutin_pages', '_cutin_idx', getattr(scene, '_cutin_active', False)),
        (scene, '_boss_intro_pages', '_boss_intro_page_idx',
         getattr(scene, '_boss_intro_state', '') in ('pre_dialogue', 'boss_dialogue')),
        (scene, '_defeat_dialogue_pages', '_defeat_dialogue_index',
         getattr(scene, '_defeat_dialogue_active', False)),
        (final, '_final_dialogue_pages', '_final_dialogue_idx',
         final is not None and final.dialogue_active),
    ]
    for owner, pages_key, index_key, active in candidates:
        pages = getattr(owner, pages_key, ())
        idx = getattr(owner, index_key, 0)
        if active and 0 <= idx < len(pages):
            page = pages[idx]
            lines = list(getattr(page, 'lines', (str(page),)))
            chars = getattr(owner, '_chars', None) if pages_key == '_pages' else None
            if chars is not None:
                remaining = int(chars)
                visible = []
                for line in lines:
                    visible.append(line[:max(0, remaining)])
                    remaining -= len(line)
                lines = visible
            return {'speaker': getattr(page, 'speaker', ''), 'lines': lines}
    if getattr(scene, '_boss_dialogue_timer', 0) > 0:
        return {'speaker': scene._boss_dialogue_speaker,
                'lines': list(scene._boss_dialogue_lines)}
    return None


def _entity(entity):
    result = {'kind': type(entity).__name__, 'rect': list(entity.rect)}
    for key in ('hp', 'max_hp', 'sx', 'sy', 'vx', 'vy', 'world_x', 'world_y',
                'requires_laser', 'terrain_visual_only', '_state', '_phase', '_form'):
        value = getattr(entity, key, None)
        if isinstance(value, (int, float, str, bool)):
            result[key] = value
    return result


def observe(game, diagnostic=False):
    scene = game._scene
    result = {'scene': type(scene).__name__, 'mode': mode(scene),
              'score': game.shared.score, 'stage': game.shared.stage,
              'lives': game.shared.lives}
    dialogue = _dialogue(scene)
    if dialogue:
        result['dialogue'] = dialogue
    if type(scene).__name__ == 'TutorialScene':
        result['tutorial_phase'] = scene._phase
        if scene._choosing:
            result['choice'] = scene._choice
            result['options'] = ['はい', 'いいえ']
        hint = scene._hint
        if hint and not scene._in_dialogue and not scene._choosing:
            result['hint'] = list(hint.lines)
    if hasattr(scene, '_cursor'):
        result['cursor'] = scene._cursor
    if getattr(scene, '_paused', False):
        result['cursor'] = scene._pause_cursor
    player = getattr(scene, 'player', None)
    if player:
        result['player'] = {'rect': list(player.rect), 'hp': player.hp,
                            'max_hp': player.max_hp, 'weapon': player.weapon.snapshot()}
    heat = getattr(scene, '_heat', None)
    if heat:
        result['heat'] = {'temperature': round(heat.display_temp, 2),
                          'overheated': heat.overheated}
    laser = getattr(scene, 'laser', None)
    if laser:
        result['laser'] = laser.state
    if getattr(scene, '_upgrading', False):
        result['upgrade'] = {'zone': scene._upg_zone,
                             'top_cursor': scene._upg_top_cursor,
                             'bottom_cursor': scene._upg_bottom_cursor,
                             'top_choice': scene._upg_top_choice,
                             'bottom_choice': scene._upg_bottom_choice}
    if diagnostic:
        extra = {'pending_scene': type(game._next_scene).__name__ if game._next_scene else None}
        for attr in ('_stage_elapsed', '_boss_intro_state', '_post_boss', '_phase',
                     '_page', '_cutin_idx', '_boss_intro_page_idx', '_defeat_dialogue_index'):
            if hasattr(scene, attr):
                extra[attr.removeprefix('_')] = getattr(scene, attr)
        for name in ('enemies', 'enemy_bullets', 'player_bullets', 'items', 'terrain'):
            group = getattr(scene, name, None)
            if group is not None:
                extra[name] = [_entity(entity) for entity in group
                               if entity.rect.right >= 0 and entity.rect.left <= 800
                               and entity.rect.bottom >= 0 and entity.rect.top <= 600]
                extra[name + '_total'] = len(group)
        boss = getattr(scene, '_boss', None)
        if boss:
            extra['boss'] = _entity(boss)
        companion = getattr(scene, '_companion', None)
        if companion:
            extra['companion'] = {'active': companion.is_active,
                                  'stock': companion.stock}
        final = getattr(scene, '_final', None)
        if final:
            extra['final'] = {'phase': final.phase, 'seq': final.seq,
                              'gate_released': final._gate_released}
        extra['story'] = game.story.snapshot()
        extra['kills'] = game.shared.kill_count
        result['diagnostic'] = extra
    return result
