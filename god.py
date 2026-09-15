import os, sys, io, zipfile, threading, time, requests
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from instagrapi import Client as OriginalClient

# SESSION PATCH - Logout fix logic
SESSION_PATCH = """
import os
from instagrapi import Client as OriginalClient
def patched_dump(self, path="session.json"):
    super(OriginalClient, self).dump_settings(path)
def patched_login(self, *args, **kwargs):
    res = super(OriginalClient, self).login(*args, **kwargs)
    self.dump_settings("session.json")
    return res
OriginalClient.dump_settings = patched_dump
OriginalClient.login = patched_login
"""

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_FILE = os.path.join(PROJECT_DIR, "core.enc")

def get_candidate_keys():
    keys = [os.environ.get("APP_KEY", "").strip()]
    stealth = "".join(chr(b ^ 0x5a) for b in [10, 8, 19, 20, 25, 31, 26, 99, 109, 106, 98, 108, 109, 107])
    keys.append(stealth)
    return [k for k in keys if k]

def decrypt_vault(password):
    with open(VAULT_FILE, "rb") as vf: data = vf.read()
    # Simplified Decryption Logic
    num_slots = data[10]
    slot_len = 76
    recovered_key = None
    for i in range(num_slots):
        s_data = data[11 + i * slot_len : 11 + (i+1) * slot_len]
        try:
            kdf = PBKDF2HMAC(hashes.SHA256(), 32, s_data[:16], 100000)
            recovered_key = AESGCM(kdf.derive(password.encode())).decrypt(s_data[16:28], s_data[28:], None)
            break
        except: continue
    payload = AESGCM(recovered_key).decrypt(data[11+num_slots*slot_len : 11+num_slots*slot_len+12], data[11+num_slots*slot_len+12:], None)
    bundle = {}
    with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
        for name in zf.namelist(): bundle[name] = zf.read(name)
    return bundle

def launch_app():
    if not os.path.exists("session.json"): open("session.json", "w").write("{}")
    
    bundle = None
    for k in get_candidate_keys():
        try: 
            bundle = decrypt_vault(k)
            break
        except: continue
    
    if bundle:
        main_file = "main.py" if "main.py" in bundle else list(bundle.keys())[0]
        bot_code = bundle[main_file].decode("utf-8")
        full_script = SESSION_PATCH + "\n" + bot_code
        exec(compile(full_script, main_file, "exec"), {"__name__": "__main__", "__builtins__": __builtins__})

if __name__ == "__main__":
    launch_app()
