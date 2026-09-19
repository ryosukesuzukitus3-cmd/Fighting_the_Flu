"""Read an authored stage as compact encounter/reward windows for agent editing.

Reports use world coordinates from stage JSON. Counts describe placement, not
simultaneous live enemies or proof that an encounter is unavoidable.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def stage_report(stage_id: int, width: int = 800) -> dict:
    data = json.loads((ROOT/f'data/stages/stage{stage_id}.json').read_text(encoding='utf-8'))
    events = sorted(data.get('world_events', []), key=lambda e:e.get('x',e.get('trigger_x',0)))
    end = next((e['trigger_x'] for e in events if e['type']=='BossGate'), 0)
    windows = []
    for start in range(0, end, width):
        subset = [e for e in events if start <= e.get('x', e.get('trigger_x',0)) < start+width]
        counts = Counter()
        for event in subset:
            if event['type'].startswith('Enemy'):
                counts[event['type']] += event.get('count',1)
        windows.append(dict(start=start,end=min(end,start+width),enemies=dict(counts),
                            rewards=[dict(x=e['x'], source=e['type'],
                                          item=e.get('fixed_drop', 'WeaponItem'))
                                     for e in subset if e['type'] in ('weapon_gate', 'EnemyBilly')
                                     or e.get('fixed_drop') == 'WeaponItem']))
    return dict(stage=stage_id,boss_gate=end,window_width=width,windows=windows,
                events=[{k:v for k,v in e.items() if k in ('type','x','trigger_x','count',
                        'formation','anchor_y','y','hp','enhanced','preload','fixed_drop')} for e in events],
                limitation='Authored placement only; validate reachability and pressure in actual gameplay')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=int, choices=range(1,5))
    parser.add_argument('--window', type=int, default=800)
    parser.add_argument('--output', type=Path)
    args=parser.parse_args(argv)
    if args.window < 100:
        parser.error('--window must be at least 100 world pixels')
    report=[stage_report(s,args.window) for s in ([args.stage] if args.stage else range(1,5))]
    text=json.dumps(report,ensure_ascii=False,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text,encoding='utf-8')
    else:
        print(text)

if __name__ == '__main__':
    main()
