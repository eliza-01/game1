"""Skill catalogue, reference validation and deterministic threat budget projection."""
from math import floor, prod
import re

DEBUFFS = {'poison','bleed','slow','root','stun','silence'}
BUFFS = {'might','haste'}
CONTROL_WEIGHTS = {'slow': .5, 'root': .75, 'stun': 1.5, 'silence': 0}
MAX_PROFILES = 24


def validate(data, number):
    skills = data['skills']
    if not isinstance(skills,list) or len(skills)>64: raise ValueError('Invalid skill catalogue')
    ids = {}
    for s in skills:
        if not isinstance(s,dict) or set(s) != {'id','name','owner','effect','duration','cooldown','power','tick'}: raise ValueError('Invalid skill row')
        if not isinstance(s['id'],str) or not re.fullmatch(r'skill_[a-z0-9_]{1,40}',s['id']) or s['id'] in ids: raise ValueError('Invalid / duplicate skill ID')
        if not isinstance(s['name'],str) or not 1<=len(s['name'])<=60 or any(ord(c)<32 for c in s['name']): raise ValueError('Invalid skill name')
        if s['owner']!='monster' or s['effect'] not in DEBUFFS|BUFFS: raise ValueError('Unsupported skill owner/effect')
        number(s['duration'], .5, 20, 'duration', False)
        number(s['cooldown'], s['duration']+1, 120, 'cooldown', False)
        number(s['power'], 1, 100, 'power', False)
        if s['effect'] in {'root','stun','silence'} and s['power']!=100: raise ValueError('Binary control power must be 100')
        if s['effect'] in {'poison','bleed'}: number(s['tick'], .5, s['duration'], 'tick', False)
        else: number(s['tick'],0,0,'tick')
        ids[s['id']]=s
    profiles=data['skilledMonsters']
    if not isinstance(profiles,list) or len(profiles)>MAX_PROFILES: raise ValueError('At most 24 skilled test monsters')
    seen=set()
    for p in profiles:
        if not isinstance(p,dict) or set(p)!={'id','level','type','skills'}: raise ValueError('Invalid skilled monster')
        if not isinstance(p['id'],str) or not re.fullmatch(r'skilled_[a-z0-9_]{1,40}',p['id']) or p['id'] in seen: raise ValueError('Invalid / duplicate profile ID')
        seen.add(p['id']); number(p['level'],1,35,'level')
        if p['type'] not in ('melee','ranged'): raise ValueError('Invalid skilled monster type')
        if not isinstance(p['skills'],list) or not 1<=len(p['skills'])<=8: raise ValueError('Assign 1–8 skills')
        effects=set()
        for a in p['skills']:
            if not isinstance(a,dict) or set(a)!={'skillId','downgrade','trigger','hpBelow'}: raise ValueError('Invalid skill assignment')
            if not isinstance(a['skillId'],str) or a['skillId'] not in ids or type(a['downgrade']) is not bool: raise ValueError('Unknown skill / downgrade')
            s=ids[a['skillId']]; e=s['effect']
            if e in effects: raise ValueError('Duplicate effect in profile')
            effects.add(e)
            if a['trigger'] not in (('hit',) if e in DEBUFFS else ('attacked','hpBelow','expired')): raise ValueError('Invalid skill trigger')
            number(a['hpBelow'],1,99,'HP threshold')


def budget(skill, base, crit_multiplier=2):
    e=skill['effect']; power=skill['power']/100; uptime=skill['duration']/skill['cooldown']
    if e in {'poison','bleed'}:
        cycle=1.8*100/base['attackSpeed']+.03
        return power*floor(skill['duration']/skill['tick']+1e-8)*min(1,cycle/skill['cooldown'])/(1+base['critChance']/100*(crit_multiplier-1))
    if e in CONTROL_WEIGHTS: return uptime*power*CONTROL_WEIGHTS[e]
    return uptime*power


def resolve(data):
    skills={s['id']:s for s in data['skills']}
    bases={(r['level'],r['type']):r for r in data['monsters']}
    out=[]
    for p in data['skilledMonsters']:
        base=bases[p['level'],p['type']]
        budgets={a['skillId']:budget(skills[a['skillId']],base,data['rules']['critMultiplier']) for a in p['skills']}
        factor=1/prod(1+budgets[a['skillId']] for a in p['skills'] if a['downgrade'])
        row=dict(base,id=p['id'],baseId=base['id'],damage=floor(base['damage']*factor+.5),factor=factor,skills=p['skills'],skillBudgets=budgets)
        out.append(row)
    return out
