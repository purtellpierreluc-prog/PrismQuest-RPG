"""Lossless, additive local town records; escrow is ownership, ledgers are not."""

import copy


def empty_town():
    return {'version':1,'listings':[],'ledger':[],'guild_id':'','charters':[],'last_name':''}


def normalize_town(raw):
    if not isinstance(raw,dict):
        return empty_town()
    return {**empty_town(),**copy.deepcopy(raw)}


def validate_town(raw,validate_item):
    if not isinstance(raw,dict):
        raise TypeError('Town records must be an object.')
    if type(raw.get('version',1)) is not int or raw.get('version',1) != 1:
        raise ValueError('This town record requires a newer game version.')
    for key in ('listings','ledger','charters'):
        if not isinstance(raw.get(key,[]),list):
            raise TypeError(f'Town {key} must be a list.')
    if not isinstance(raw.get('guild_id',''),str) or not isinstance(raw.get('last_name',''),str):
        raise TypeError('Town identity fields must be text.')
    ids = set()
    for listing in raw.get('listings',[]):
        if not isinstance(listing,dict) or not isinstance(listing.get('id'),str) or not listing['id'] or listing['id'] in ids:
            raise ValueError('Town listing identities must be unique.')
        ids.add(listing['id'])
        if type(listing.get('price')) is not int or not 1 <= listing['price'] <= 1_000_000:
            raise ValueError('Town listing price is invalid.')
        if type(listing.get('revision')) is not int or listing['revision'] < 1 or listing.get('status') not in {'active','returned','sold'}:
            raise ValueError('Town listing revision/status is invalid.')
        validate_item(listing.get('item'),'town listing')
    for charter in raw.get('charters',[]):
        if not isinstance(charter,dict) or not all(isinstance(charter.get(k),str) for k in ('id','code','name','created')) or type(charter.get('founder')) is not int or not 0 <= charter['founder'] < 3:
            raise ValueError('Local guild charter is invalid.')
        if not isinstance(charter.get('messages',[]),list):
            raise TypeError('Guild messages must be a list.')
        for message in charter.get('messages',[]):
            if not isinstance(message,dict) or not all(isinstance(message.get(k),str) for k in ('id','author','body','created')):
                raise ValueError('Guild message record is invalid.')
    for row in raw.get('ledger',[]):
        if not isinstance(row,dict) or not all(isinstance(row.get(k),str) for k in ('id','kind','other','created','name')) or type(row.get('gold')) is not int:
            raise ValueError('Town ledger record is invalid.')
        if row.get('item') is not None:
            validate_item(row['item'],'town ledger snapshot')
