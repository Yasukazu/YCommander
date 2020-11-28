import json
import csv
from typing import Dict, List
from pprint import pprint
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ycommander.session import KeeperSession
from ycommander.tsrecord import TsRecord, Uid
from ycommander import params as kparams


KEEPER_JSON = ['shared_folders', 'records']
KEEPER_RECORD = ['title', 'login', 'password', 'login_url', 'notes', 
'custom_fields', 'folders']
KEEPER_SHARED = ['uid', 'path', 'manage_users', 'manage_records', 'can_edit', 'can_share', 'permissions']
KEEPER_CUSTOM = ["TFC:Keeper"]
ENPASS_CSV = ["Title", "Username", "Email", "Password", "Website", "TOTP Secret Key", "Custom Field 1", "*Custom Field 2", "Note","Tags" ]
BITWARDEN_CSV_STR = "folder,favorite,type,name,notes,fields,login_uri,login_username,login_password,login_totp"
BITWARDEN_FIELDNAMES_DICT = {n:n for n in BITWARDEN_CSV_STR.split(',')}

class ExceedError(ValueError):
    pass

from collections import UserDict
import unicodedata
def but_control_char(s):
    return "".join(ch for ch in s if unicodedata.category(ch)[0]!="C")

class Fields(UserDict):
    def __init__(self, key_to_limit: Dict[str, int], default_limit=500):
        self.key_to_limit = key_to_limit
        self.default_limit = default_limit
        self.data = {}
        
    def __setitem__(self, key: str, value: str):
        limit = self.key_to_limit[key] if key in self.key_to_limit else self.default_limit
        if len(value) > self.default_limit:
            raise ExceedError(f"{key} exceeds {limit - len(value)}.")
        self.data[key] = but_control_char(value)

def save_bitwarden_csv(recs: List[TsRecord], fn: str):
    # from attrdict import AttrDict
    fieldnames = BITWARDEN_CSV_STR.split(',')
    with open(fn, 'w') as f:
        wtr = csv.DictWriter(f, fieldnames=fieldnames)
        # headers = BITWARDEN_CSV_STR.split(',')
        wtr.writerow(BITWARDEN_FIELDNAMES_DICT)
        fields = Fields({'notes': 5000})
        for rec in recs:
            # adic = AttrDict(ric)
            try:
                folder = ''
                try:
                   for fld in rec.folders:
                       folder = fld['folder']
                       break
                except:
                    pass
                fields['folder'] = folder
                fields['favorite'] = ''
                fields['type'] = 'login'
                fields['name'] = rec.title or ''
                fields['notes'] = expand_s(rec.notes) if rec.notes else ''
                fields['fields'] = expand_fields(rec.custom_fields) if rec.custom_fields else ''
                fields['login_uri'] = rec.login_node_url if rec.login_node_url else ''
                fields['login_username'] = rec.login if rec.login else ''
                fields['login_password'] = rec.password if rec.password else ''
                fields['login_totp'] = rec.totp if rec.totp else '' #  'TFC:Keeper'
                breakpoint()
                wtr.writerow(fields)
            except ExceedError: # as err:
                pprint(rec.to_dictionary())
                raise

def load_keeper_records(fn: str) -> List[Dict]:
    with open(fn, 'r') as f:
        s = f.read()
        dics = json.loads(s)
    return dics['records']

def expand_s(s: str):
    return s.replace(r'\n', '\n')

def expand_fields(il: List) -> str:
    if not len(il):
        return []
    ol = []
    for dic in il:
        if dic['type'] != 'text':
            raise ValueError(f"{dic['type']} is not supported.")
        ol.append(f"{dic['name']}:{dic['value']}")
    return '\n'.join(ol)

def list_all_records(sss: KeeperSession):
    return [TsRecord(sss[uid]) for uid in sss.get_every_uid()]

def main(user, password, csv_filename):
    param = kparams.KeeperParams()
    param.user = user
    param.password = password
    sss = KeeperSession(param) 
    recs = list_all_records(sss)
    save_bitwarden_csv(recs, csv_filename)

if __name__ == '__main__':
    import sys
    rr = load_keeper_records(sys.argv[1])
    save_bitwarden_csv(rr, sys.argv[2])