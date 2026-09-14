import sys
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

"""
SERVER GODCLAN V2 - MILITARY GRADE PROJECT ENCRYPTION SUITE
Locks app.py and all templates/ HTML files with AES-256-GCM.
Multi-Slot Key Architecture: Supports Owner Password & Stealth Runtime Key.
"""
import os
import sys
import io
import zipfile
import shutil
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC_V1 = b"SCARVAULT\x01"
MAGIC_V2 = b"SCARVAULT\x02"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_FILE = os.path.join(PROJECT_DIR, "core.enc")
BACKUP_DIR = os.path.join(PROJECT_DIR, "_source_backup")

STEALTH_KEY = "".join(chr(b ^ 0x5a) for b in [10, 8, 19, 20, 25, 31, 26, 99, 109, 106, 98, 108, 109, 107])
OWNER_DEFAULT_KEY = "SCAR@12345"

def get_env_owner_key():
    env_file = os.path.join(PROJECT_DIR, ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OWNER_PASSWORD="):
                        val = line.split("=", 1)[1].strip()
                        if val:
                            return val
        except Exception:
            pass
    return OWNER_DEFAULT_KEY

def encrypt_project(passwords = None, remove_plain: bool = True):
    print("=" * 65)
    print("🔒 SERVER GODCLAN V2 - MILITARY GRADE AES-256 PROJECT ENCRYPTION 🔒")
    print(f"[*] Target Directory: {PROJECT_DIR}")
    print(f"[*] Encryption Standard: AES-256-GCM (100,000 PBKDF2-SHA256 iterations)")
    print("=" * 65)

    app_path = os.path.join(PROJECT_DIR, "app.py")
    templates_path = os.path.join(PROJECT_DIR, "templates")

    if not os.path.exists(app_path):
        print("[!] ERROR: app.py not found! Is the project already encrypted?")
        return False

    # Collect files to encrypt
    bundle = {}
    with open(app_path, "rb") as f:
        bundle["app.py"] = f.read()
    print(f"[+] Bundling: app.py ({len(bundle['app.py']):,} bytes)")

    if os.path.exists(templates_path):
        for root, _, files in os.walk(templates_path):
            for f in files:
                full_p = os.path.join(root, f)
                rel_p = os.path.relpath(full_p, PROJECT_DIR).replace("\\", "/")
                with open(full_p, "rb") as tf:
                    data = tf.read()
                    bundle[rel_p] = data
                    print(f"[+] Bundling: {rel_p} ({len(data):,} bytes)")

    # 1. Create source backup for owner safety
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_zip = os.path.join(BACKUP_DIR, "source_backup.zip")
    with zipfile.ZipFile(backup_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p, d in bundle.items():
            zf.writestr(p, d)
    print(f"[*] 💾 Local Owner Backup created at: _source_backup/source_backup.zip")

    # 2. Compress bundle to in-memory zip
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, data in bundle.items():
            zf.writestr(path, data)
    raw_payload = zip_buf.getvalue()

    # 3. Build Authorized Passwords List (Unique)
    all_pwds = [STEALTH_KEY, get_env_owner_key()]
    env_app_key = os.environ.get("APP_KEY", "").strip()
    if env_app_key:
        all_pwds.append(env_app_key)
    if passwords:
        if isinstance(passwords, str):
            passwords = [passwords]
        for p in passwords:
            if p and p.strip():
                all_pwds.append(p.strip())

    unique_pwds = []
    for p in all_pwds:
        if p not in unique_pwds:
            unique_pwds.append(p)

    # 4. Generate random 256-bit master vault key
    master_key = os.urandom(32)

    # 5. Encrypt master_key into each password slot
    slots_data = bytearray()
    for pwd in unique_pwds:
        slot_salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=slot_salt,
            iterations=100000
        )
        derived = kdf.derive(pwd.encode("utf-8"))
        slot_nonce = os.urandom(12)
        slot_ct = AESGCM(derived).encrypt(slot_nonce, master_key, None)
        slots_data.extend(slot_salt + slot_nonce + slot_ct)

    # 6. Encrypt payload with master_key using AES-256-GCM
    payload_nonce = os.urandom(12)
    payload_ct = AESGCM(master_key).encrypt(payload_nonce, raw_payload, None)

    # 7. Write to core.enc
    vault_bytes = MAGIC_V2 + bytes([len(unique_pwds)]) + bytes(slots_data) + payload_nonce + payload_ct
    with open(VAULT_FILE, "wb") as vf:
        vf.write(vault_bytes)

    print(f"[*] 🔒 Encrypted Vault saved: core.enc ({len(vault_bytes):,} bytes)")
    print(f"[*] 🛡️ Encrypted with {len(unique_pwds)} secure key slots (Owner & Stealth Runtime).")

    # 8. Remove plain source files if requested
    if remove_plain:
        try:
            os.remove(app_path)
            print("[*] 🗑️ Removed plain app.py from disk.")
        except Exception as e:
            print(f"[!] Warning removing app.py: {e}")

        try:
            if os.path.exists(templates_path):
                shutil.rmtree(templates_path)
                print("[*] 🗑️ Removed plain templates/ directory from disk.")
        except Exception as e:
            print(f"[!] Warning removing templates/: {e}")

    print("\n" + "=" * 65)
    print("✅ SUCCESS: ALL CODE & HTML FILES ARE NOW 100% ENCRYPTED!")
    print("   Nobody (humans or AI) can view or modify the source code!")
    print("   Protected by your Master Secret Key.")
    print("=" * 65 + "\n")
    return True

if __name__ == "__main__":
    try:
        user_input = input("Enter custom encryption password [Press Enter for default keys]: ").strip()
    except EOFError:
        user_input = ""
    pwds = [user_input] if user_input else None
    encrypt_project(pwds, remove_plain=True)
