"""Normal-pack power tuning and one readable total per target in a group volley."""


def halve_normal_monster(monster):
    for field in ('max_hp','attack_min','attack_max','physical_armor','magic_resistance','armor_penetration','speed'):
        minimum = 1 if field in {'max_hp','attack_min','attack_max','speed'} else 0
        setattr(monster,field,max(minimum,round(getattr(monster,field)*.5)))
    monster.attack_max = max(monster.attack_min+1,monster.attack_max)
    monster.hp = monster.max_hp


def volley_popup(game,popups,key,damage,crit,*,enabled):
    if not enabled or damage<=0:
        return
    previous = popups.get(key,{})
    amount = int(previous.get('amount',0))+int(damage)
    popup = game._labyrinth_damage_popup_payload(amount,bool(crit or previous.get('crit')),enabled=True)
    popup.update(amount=amount,hits=int(previous.get('hits',0))+1)
    popups[key] = popup
