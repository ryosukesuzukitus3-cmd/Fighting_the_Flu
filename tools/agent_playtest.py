"""Opt-in, fixed-frame input protocol using the ordinary game loop.

No action advances outside an explicit command. No invincibility, equipment,
teleports, scene skips or automated decisions are supplied by this runner.
Run `python tools/run.py agent-playtest --help` for usage.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.playtest_state import boundary, observe

ACTIONS = frozenset(('move_up', 'move_down', 'move_left', 'move_right', 'fire',
                     'laser', 'weapon_select', 'bomb', 'pause', 'ui_accept', 'ui_back',
                     'menu_up', 'menu_down', 'menu_left', 'menu_right', 'escape', 'tab'))
DT = 1 / 60


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True,
                                     allow_nan=False).encode()).hexdigest()


class Session:
    """One pygame session at a time. Output folders must be new or empty."""

    def __init__(self, output_dir, seed=1, diagnostic=False, *, visible=False):
        if type(seed) is not int:
            raise ValueError('seed must be an integer')
        self.output_dir = Path(output_dir).resolve()
        if self.output_dir.exists() and any(self.output_dir.iterdir()):
            raise ValueError('output directory must be new or empty')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = self.output_dir / 'user-data'
        self.data_dir.mkdir()
        self._environment = {key: os.environ.get(key) for key in
                             ('FLU_USER_DATA_DIR', 'SDL_VIDEODRIVER', 'SDL_AUDIODRIVER')}
        os.environ['FLU_USER_DATA_DIR'] = str(self.data_dir)
        if not visible:
            os.environ['SDL_VIDEODRIVER'] = 'dummy'
            os.environ['SDL_AUDIODRIVER'] = 'dummy'
        import pygame
        from src.core.game import Game
        from src.managers.input import InputManager
        self.pygame = pygame
        self.seed = seed
        self.diagnostic = diagnostic
        self.visible = visible
        self.closed = False
        self.frame = 0
        self.held_actions = set()
        self._held_keys = set()
        self._log = (self.output_dir / 'actions.jsonl').open('w', encoding='utf-8')
        random.seed(seed)
        self.game = Game()
        self.game.input = InputManager(self.game.settings, physical_input=False)
        self.game.start()
        self.game.step(DT, [], allow_debug=False)
        self.frame = 1
        self._cache()
        try:
            revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                               text=True, stderr=subprocess.DEVNULL).strip()
            dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT,
                                                 text=True, stderr=subprocess.DEVNULL).strip())
        except (OSError, subprocess.CalledProcessError):
            revision, dirty = 'unknown', True
        self.metadata = {'protocol': 1, 'seed': seed, 'dt': DT, 'revision': revision,
                         'dirty': dirty, 'python': sys.version, 'pygame': pygame.version.ver,
                         'observation': 'diagnostic' if diagnostic else 'screen',
                         'input': 'fixed-frame actions; unlimited thinking time',
                         'rule_overrides': [], 'visible': visible,
                         'user_data': str(self.data_dir),
                         'bindings': self.game.settings.get_key_bindings()}
        (self.output_dir / 'session.json').write_text(
            json.dumps(self.metadata, indent=2, ensure_ascii=False), encoding='utf-8')

    def _cache(self):
        self._screen = self.game.screen.copy()
        self._observation = observe(self.game, self.diagnostic)
        full_state = observe(self.game, True)
        full_state['rng'] = random.getstate()
        self._observation.update(type='observation', frame=self.frame,
                                 elapsed=self.game.elapsed_time,
                                 held_actions=sorted(self.held_actions),
                                 observation='diagnostic' if self.diagnostic else 'screen',
                                 state_digest=_digest(full_state),
                                 image_digest=hashlib.sha256(
                                     self.pygame.image.tobytes(self._screen, 'RGB')).hexdigest())

    def _response(self, image_name='latest.png'):
        path = self.output_dir / image_name
        self.pygame.image.save(self._screen, str(path))
        result = {**copy.deepcopy(self._observation), 'image': str(path)}
        (self.output_dir / 'observation.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return result

    def _key(self, action):
        fixed = {'menu_up': self.pygame.K_UP, 'menu_down': self.pygame.K_DOWN,
                 'menu_left': self.pygame.K_LEFT, 'menu_right': self.pygame.K_RIGHT,
                 'escape': self.pygame.K_ESCAPE, 'tab': self.pygame.K_TAB}
        return fixed[action] if action in fixed else self.game.settings.get_key(action)

    def _advance(self, actions, frames, stop_on_boundary=True):
        if self.closed:
            return 0
        before = boundary(self.game._scene)
        keys = {self._key(action) for action in actions}
        events = [self.pygame.event.Event(self.pygame.KEYUP, key=k, mod=0, unicode='')
                  for k in sorted(self._held_keys - keys)]
        events += [self.pygame.event.Event(self.pygame.KEYDOWN, key=k, mod=0, unicode='')
                   for k in sorted(keys - self._held_keys)]
        self.held_actions = set(actions)
        self._held_keys = keys
        advanced = 0
        for i in range(frames):
            if self.visible:
                # Pump only; OS keys never enter the game. Closing replay stops it.
                if any(e.type == self.pygame.QUIT for e in self.pygame.event.get()):
                    self._cache()  # Capture the last completed frame before pygame closes.
                    self.close()
                    break
            if not self.game.step(DT, events if i == 0 else [], allow_debug=False):
                break
            self.frame += 1
            advanced += 1
            if self.visible:
                self.game.clock.tick(60)
            if stop_on_boundary and (boundary(self.game._scene) != before
                                     or self.game._next_scene is not None):
                break
        if not self.closed:
            self._cache()
        return advanced

    @staticmethod
    def _validate(command):
        if not isinstance(command, dict):
            raise ValueError('command must be an object')
        fields = set(command)
        if fields == {'step', 'actions'}:
            frames, actions = command['step'], command['actions']
            if type(frames) is not int or not 1 <= frames <= 600:
                raise ValueError('step must be an integer from 1 to 600')
            if not isinstance(actions, list) or any(
                    not isinstance(a, str) or a not in ACTIONS for a in actions):
                raise ValueError('actions must be an array of supported action names')
            return 'step'
        if fields == {'tap'} and isinstance(command['tap'], str) and command['tap'] in ACTIONS:
            return 'tap'
        if fields == {'capture'}:
            label = command['capture']
            if isinstance(label, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', label):
                # Prefix avoids Windows device names such as CON.
                return 'capture'
        for key in ('observe', 'quit'):
            if fields == {key} and command[key] is True:
                return key
        raise ValueError('use step/actions, tap, observe:true, capture:label, or quit:true')

    def command(self, command):
        name = self._validate(command)
        if self.closed:
            raise ValueError('session is closed')
        frame_before = self.frame
        if name == 'quit':
            result = self._response()
            self.close()
            return {**result, 'type': 'closed', 'held_actions': []}
        if name == 'step':
            self._advance(command['actions'], command['step'])
        elif name == 'tap':
            # Always release before a tap, even if its action was already held.
            if self._key(command['tap']) in self._held_keys:
                self._advance([], 1)
            self._advance([command['tap']], 1)
            self._advance([], 1)
        result = self._response('capture-' + command['capture'] + '.png'
                                if name == 'capture' else 'latest.png')
        result['advanced'] = self.frame - frame_before
        if self.closed:
            return {**result, 'type': 'closed', 'held_actions': []}
        if name in ('step', 'tap'):
            record = {'command': command, 'frame': self.frame,
                      'state_digest': result['state_digest'],
                      'image_digest': result['image_digest']}
            self._log.write(json.dumps(record, ensure_ascii=True) + '\n')
            self._log.flush()
        return result

    def close(self):
        if self.closed:
            return
        self.closed = True
        # QUIT can arrive before the pending KEYUP events reach InputManager.
        for key in sorted(self._held_keys | self.game.input._pressed):
            self.game.input.handle_event(self.pygame.event.Event(
                self.pygame.KEYUP, key=key, mod=0, unicode=''))
        self.held_actions.clear()
        self._held_keys.clear()
        self.game.input.pre_update()
        try:
            self.game.close()
        finally:
            self._log.close()
            for key, previous in self._environment.items():
                if previous is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = previous


def replay(source, output_dir, visible=False):
    source = Path(source).resolve()
    metadata = json.loads((source / 'session.json').read_text(encoding='utf-8'))
    session = Session(output_dir, seed=metadata['seed'],
                      diagnostic=metadata['observation'] == 'diagnostic', visible=visible)
    checked = 0
    try:
        for line in (source / 'actions.jsonl').read_text(encoding='utf-8').splitlines():
            record = json.loads(line)
            result = session.command(record['command'])
            checked += 1
            if result['type'] == 'closed':
                return {'type': 'replay_cancelled', 'commands': checked, 'frame': session.frame}
            for key in ('frame', 'state_digest', 'image_digest'):
                if result[key] != record[key]:
                    raise ValueError(f'replay diverged at command {checked}, {key}')
        return {'type': 'replay_verified', 'commands': checked, 'frame': session.frame,
                'image': str(session.output_dir / 'latest.png')}
    finally:
        session.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new or empty evidence folder')
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--diagnostic', action='store_true', help='expose internal combat state')
    parser.add_argument('--replay', type=Path, help='folder containing session.json/actions.jsonl')
    parser.add_argument('--visible', action='store_true', help='normal-speed replay window; replay only')
    args = parser.parse_args(argv)
    if args.visible and not args.replay:
        parser.error('--visible requires --replay (interactive mode is offscreen)')
    output = sys.stdout
    def emit(value):
        print(json.dumps(value, ensure_ascii=True, allow_nan=False), file=output, flush=True)
    with contextlib.redirect_stdout(sys.stderr):
        if args.replay:
            emit(replay(args.replay, args.output, args.visible))
            return 0
        session = Session(args.output, args.seed, args.diagnostic)
        try:
            emit({**session.command({'observe': True}),
                  'type': 'ready', 'actions': sorted(ACTIONS)})
            for line in sys.stdin:
                try:
                    result = session.command(json.loads(line))
                    emit(result)
                    if session.closed:
                        break
                except (ValueError, TypeError, OSError) as exc:
                    emit({'type': 'error', 'message': str(exc), 'frame': session.frame})
        finally:
            session.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
