import os
import io
import re
import sys
import zipfile
import struct
import base64
from PIL import Image, ImageDraw
from sign_apk import signer, keys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "static", "downloads")
BASE_CACHE = os.path.join(DOWNLOADS_DIR, "base_smartwebview.apk")
OUTPUT_APK = os.path.join(DOWNLOADS_DIR, "server_godclan_v2_mod.apk")
TUNNEL_FILE = os.path.join(BASE_DIR, "tunnel_url.txt")
LOGO_FILE = os.path.join(BASE_DIR, "static", "logo.png")
KEY_FILE = os.path.join(DOWNLOADS_DIR, "apk_key.pem")
CERT_FILE = os.path.join(DOWNLOADS_DIR, "apk_cert.pem")

def get_target_url():
    tunnel_url = "https://shame-provided-charleston-rare.trycloudflare.com"
    if os.path.exists(TUNNEL_FILE):
        try:
            with open(TUNNEL_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content.startswith("http"):
                    tunnel_url = content
        except Exception as e:
            print(f"[!] Error reading tunnel_url.txt: {e}")
    return tunnel_url

def build_godclan_apk(target_url=None):
    if not target_url:
        target_url = get_target_url()

    print(f"[*] Target Server URL for APK: {target_url}")
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)

    if not os.path.exists(BASE_CACHE):
        raise FileNotFoundError(f"Base APK not found at {BASE_CACHE}")

    with open(BASE_CACHE, "rb") as f:
        apk_content = f.read()

    in_zip = zipfile.ZipFile(io.BytesIO(apk_content))

    # Load custom logo image
    base_logo_img = None
    logo_b64 = ""
    if os.path.exists(LOGO_FILE):
        try:
            raw_logo = Image.open(LOGO_FILE).convert("RGBA")
            w, h = raw_logo.size
            min_dim = min(w, h)
            left = (w - min_dim) // 2
            top = (h - min_dim) // 2
            base_logo_img = raw_logo.crop((left, top, left + min_dim, top + min_dim))
            buf_b64 = io.BytesIO()
            base_logo_img.resize((128, 128), Image.Resampling.LANCZOS).save(buf_b64, format="PNG")
            logo_b64 = base64.b64encode(buf_b64.getvalue()).decode("ascii")
            print("[+] Loaded custom logo image successfully from static/logo.png")
        except Exception as e:
            print(f"[!] Warning loading logo image: {e}")

    def create_app_icon(size, is_round=False):
        if base_logo_img is not None:
            resized = base_logo_img.resize((size, size), Image.Resampling.LANCZOS)
            mask = Image.new("L", (size, size), 0)
            draw = ImageDraw.Draw(mask)
            if is_round:
                draw.ellipse((0, 0, size, size), fill=255)
            else:
                radius = int(size * 0.22)
                draw.rounded_rectangle([0, 0, size, size], radius=radius, fill=255)
            output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            output.paste(resized, (0, 0), mask)
            return output

        img = Image.new("RGBA", (size, size), (15, 10, 25, 255))
        return img

    icon_sizes = {
        "res/mipmap-mdpi-v4/ic_launcher.webp": 48,
        "res/mipmap-mdpi-v4/ic_launcher_round.webp": 48,
        "res/mipmap-mdpi-v4/ic_launcher_foreground.webp": 108,
        "res/mipmap-hdpi-v4/ic_launcher.webp": 72,
        "res/mipmap-hdpi-v4/ic_launcher_round.webp": 72,
        "res/mipmap-hdpi-v4/ic_launcher_foreground.webp": 162,
        "res/mipmap-xhdpi-v4/ic_launcher.webp": 96,
        "res/mipmap-xhdpi-v4/ic_launcher_round.webp": 96,
        "res/mipmap-xhdpi-v4/ic_launcher_foreground.webp": 216,
        "res/mipmap-xxhdpi-v4/ic_launcher.webp": 144,
        "res/mipmap-xxhdpi-v4/ic_launcher_round.webp": 144,
        "res/mipmap-xxhdpi-v4/ic_launcher_foreground.webp": 324,
        "res/mipmap-xxxhdpi-v4/ic_launcher.webp": 192,
        "res/mipmap-xxxhdpi-v4/ic_launcher_round.webp": 192,
        "res/mipmap-xxxhdpi-v4/ic_launcher_foreground.webp": 432,
    }

    generated_icons = {}
    for path, sz in icon_sizes.items():
        is_round = "round" in path
        icon_img = create_app_icon(sz, is_round=is_round)
        buf = io.BytesIO()
        icon_img.save(buf, format="WEBP", quality=95)
        generated_icons[path] = buf.getvalue()

    def replace_res_string(arsc_bytes, old_str_list, new_str):
        if isinstance(old_str_list, str):
            old_str_list = [old_str_list]
        arsc = bytearray(arsc_bytes)

        for old_str in old_str_list:
            target_str = new_str
            if len(target_str) != len(old_str):
                if len(target_str) < len(old_str):
                    target_str = target_str.ljust(len(old_str))
                else:
                    target_str = target_str[:len(old_str)]

            old_utf8 = old_str.encode('utf-8')
            new_utf8 = target_str.encode('utf-8')
            old_entry = bytes([len(old_str), len(old_utf8)]) + old_utf8 + b'\x00'
            new_entry = bytes([len(target_str), len(new_utf8)]) + new_utf8 + b'\x00'
            pos = arsc.find(old_entry)
            if pos != -1:
                arsc[pos:pos+len(old_entry)] = new_entry
                print(f"[+] Replaced '{old_str}' with '{target_str}' in resources.arsc")
                return bytes(arsc)

        return bytes(arsc)

    custom_offline_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>SERVER GODCLAN V2</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
  body {{
    background: #04060a;
    color: #f8fafc;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 24px;
    text-align: center;
    background-image: 
      radial-gradient(circle at 50% 20%, rgba(225, 29, 72, 0.20) 0%, transparent 50%),
      radial-gradient(circle at 50% 80%, rgba(168, 85, 247, 0.20) 0%, transparent 50%);
  }}
  .card {{
    background: linear-gradient(145deg, rgba(22, 16, 32, 0.90) 0%, rgba(10, 11, 20, 0.96) 100%);
    border: 1px solid rgba(244, 63, 94, 0.35);
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.85), 0 0 25px rgba(225, 29, 72, 0.2);
    border-radius: 24px;
    padding: 28px 22px;
    width: 100%;
    max-width: 420px;
  }}
  .logo {{
    width: 76px;
    height: 76px;
    margin: 0 auto 16px;
    border-radius: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 36px;
    overflow: hidden;
    border: 2px solid #f43f5e;
    box-shadow: 0 0 25px rgba(244, 63, 94, 0.4);
  }}
  .logo img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
  }}
  h1 {{ font-size: 20px; font-weight: 900; letter-spacing: 1px; color: #fb7185; margin-bottom: 6px; text-transform: uppercase; }}
  p.sub {{ font-size: 13px; color: #94a3b8; margin-bottom: 20px; }}
  .badge {{
    display: inline-block;
    padding: 6px 14px;
    background: rgba(244, 63, 94, 0.15);
    border: 1px solid rgba(244, 63, 94, 0.4);
    color: #fb7185;
    font-size: 12px;
    border-radius: 20px;
    margin-bottom: 20px;
    font-weight: 700;
  }}
  .btn {{
    display: block;
    width: 100%;
    padding: 14px;
    border-radius: 14px;
    font-size: 13px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border: none;
    cursor: pointer;
    margin-bottom: 12px;
    transition: all 0.2s ease;
  }}
  .btn-primary {{
    background: linear-gradient(135deg, #e11d48, #f43f5e);
    color: #ffffff;
    box-shadow: 0 4px 20px rgba(225, 29, 72, 0.45);
  }}
  .btn-secondary {{
    background: rgba(255, 255, 255, 0.08);
    color: #f8fafc;
    border: 1px solid rgba(255, 255, 255, 0.15);
  }}
  .input-box {{
    width: 100%;
    padding: 12px 14px;
    background: rgba(4, 6, 10, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 12px;
    color: #fff;
    font-size: 13px;
    margin-bottom: 12px;
    text-align: center;
  }}
  .input-box:focus {{ outline: none; border-color: #f43f5e; }}
  .info {{ font-size: 11px; color: #64748b; line-height: 1.5; margin-top: 14px; }}
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    {"<img src='data:image/png;base64," + logo_b64 + "' alt='SERVER GODCLAN'>" if logo_b64 else "&#9889;"}
  </div>
  <h1>SERVER GODCLAN V2</h1>
  <p class="sub">Autonomous Command Controller</p>
  <div class="badge" id="statusBadge">&#9888; Server Connecting / Offline</div>

  <button class="btn btn-primary" id="retryBtn" onclick="retryConnect()">&#128260; Reconnect Server</button>

  <div style="margin: 18px 0 10px; border-top: 1px dashed rgba(255,255,255,0.15); padding-top: 14px;">
    <p style="font-size: 12px; color: #94a3b8; margin-bottom: 8px;">Agar Cloudflare link change hui ho, nayi link yahan daalein:</p>
    <input type="text" id="urlInput" class="input-box" placeholder="https://....trycloudflare.com">
    <button class="btn btn-secondary" onclick="updateUrl()">&#9889; Connect to New URL</button>
  </div>

  <p class="info">Direct Samsung S23 Ultra TLS Anti-Logout Tunnel.<br>100% Synced with Server Godclan Fleet.</p>
</div>

<script>
  const DEFAULT_URL = "{target_url}";
  let savedUrl = localStorage.getItem("god_panel_url") || DEFAULT_URL;
  document.getElementById("urlInput").value = savedUrl;

  function retryConnect() {{
    const btn = document.getElementById("retryBtn");
    btn.innerText = "Connecting...";
    btn.disabled = true;
    window.location.href = savedUrl;
  }}

  function updateUrl() {{
    let val = document.getElementById("urlInput").value.trim();
    if (!val) return alert("Please enter valid URL");
    if (!val.startsWith("http://") && !val.startsWith("https://")) {{
      val = "https://" + val;
    }}
    localStorage.setItem("god_panel_url", val);
    savedUrl = val;
    window.location.href = val;
  }}
</script>
</body>
</html>
"""

    out_buf = io.BytesIO()
    out_zip = zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED)

    print("[*] Processing APK files and customizing for SERVER GODCLAN V2...")
    for item in in_zip.infolist():
        # Strip old signatures
        if item.filename.startswith("META-INF/") and (
            item.filename.endswith(".SF")
            or item.filename.endswith(".RSA")
            or item.filename.endswith(".DSA")
            or item.filename.endswith(".MF")
        ):
            continue

        if item.filename in generated_icons:
            out_zip.writestr(item, generated_icons[item.filename])
            continue

        data = in_zip.read(item.filename)

        if item.filename == "assets/swv.properties":
            text = data.decode("utf-8")
            text = re.sub(r"app\.url=.*", f"app.url={target_url}", text)
            text = re.sub(r"feature\.open\.external\.urls=.*", "feature.open.external.urls=false", text)
            text = re.sub(r"debug\.mode=.*", "debug.mode=false", text)
            text = re.sub(r"feature\.pull\.refresh=.*", "feature.pull.refresh=true", text)
            text = re.sub(r"plugins\.playground\.enabled=.*", "plugins.playground.enabled=false", text)
            text = re.sub(r"ui\.splash\.extend=.*", "ui.splash.extend=true", text)
            data = text.encode("utf-8")

        elif item.filename == "assets/web/offline.html":
            data = custom_offline_html.encode("utf-8")

        elif item.filename == "resources.arsc":
            data = replace_res_string(data, ["Smart WebView", "SERVERGOD MOD", "ServerGod MOD"], "SERVERGODCLAN")

        out_zip.writestr(item, data)

    out_zip.close()
    unsigned_bytes = out_buf.getvalue()

    unsigned_apk_path = os.path.join(DOWNLOADS_DIR, "unsigned_temp.apk")
    with open(unsigned_apk_path, "wb") as f:
        f.write(unsigned_bytes)

    # Sign APK with persistent debug key (v2 + v3 schemes)
    if os.path.exists(KEY_FILE) and os.path.exists(CERT_FILE):
        try:
            key_mat = keys.load_pem(KEY_FILE, CERT_FILE, password=None)
            print("[+] Loaded persistent Android signing key.")
        except Exception as e:
            print(f"[!] Generating new key: {e}")
            key_mat = keys.generate_debug_key()
            keys.save_pem(key_mat, KEY_FILE, CERT_FILE)
    else:
        print("[*] Generating persistent Android cryptographic debug key...")
        key_mat = keys.generate_debug_key()
        keys.save_pem(key_mat, KEY_FILE, CERT_FILE)

    result = signer.sign_apk(unsigned_apk_path, OUTPUT_APK, key_mat, v2=True, v3=True)
    print(f"[+] Sign result: {result}")

    if os.path.exists(unsigned_apk_path):
        os.remove(unsigned_apk_path)

    if os.path.exists(OUTPUT_APK):
        size_mb = os.path.getsize(OUTPUT_APK) / (1024 * 1024)
        print(f"\n[SUCCESS] MOD APK Generated Successfully!")
        print(f"Path: {OUTPUT_APK}")
        print(f"Size: {size_mb:.2f} MB")
        return True
    else:
        print("[!] Error: Target APK was not generated.")
        return False

if __name__ == "__main__":
    build_godclan_apk()
