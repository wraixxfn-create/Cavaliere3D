import subprocess, os, re, json, collections

BPY = "/home/user/Cavaliere3D/.venv/lib/python3.11/site-packages/bpy"
OUT = "/home/user/wsx-libs"
EXTRA = f"{OUT}/extra.json"

PREFIX = {
    "libXfixes.so.3":    ("XFixes",),
    "libXrender.so.1":   ("XRender",),
    "libxkbcommon.so.0": ("xkb_", "xkbcommon"),
    "libXi.so.6":        ("_Xi","XInput","XOpenDevice","XCloseDevice","XQueryDevice","XSelectExtensionEvent",
                          "XListInputDevices","XGetExtensionVersion","XAllowDeviceEvents","XChangeDevice",
                          "XGrabDevice","XUngrabDevice","XFree","XSync","XFlush","XGetDeviceButtonMapping",
                          "XGetDeviceControl","XGetSelectedExtensionEvents","XChangeDeviceControl",
                          "XGetDeviceKeyMapping","XGetDeviceMotionEvents","XGetDeviceFocus","XSetDeviceFocus",
                          "XQueryDeviceState","XGetFeedbackControl","XChangeFeedbackControl",
                          "XGetDeviceDontPropagateList","XSetDeviceModifierMapping","XGetDeviceModifierMapping",
                          "XChangeKeyboardDevice","XChangePointerDevice","XGetDevicePointerMapping",
                          "XSetDevicePointerMapping","XQueryDeviceKeyMapping"),
    "libSM.so.6":        ("Smc","Sms"),
    "libICE.so.6":       ("Ice",),
    "libGL.so.1":        ("glA","glB","glC","glD","glE","glF","glG","glH","glI","glL","glM","glN","glP",
                          "glR","glS","glT","glU","glV","glW","glX","glZ","glColor","glTex"),
}

def scan():
    blobs = [f"{BPY}/__init__.so", f"{BPY}/lib/libusd_ms.so"]
    for root, _, files in os.walk(f"{BPY}/4.5"):
        blobs += [os.path.join(root,f) for f in files if f.endswith(".so")]
    syms = set()
    for b in blobs:
        out = subprocess.run(["nm","-D","--undefined-only",b], capture_output=True, text=True).stdout
        for line in out.splitlines():
            p = line.split()
            if len(p) == 2: syms.add(p[1])
    return syms

def build(syms, extra):
    for lib, prefixes in PREFIX.items():
        picked = collections.defaultdict(list)
        cand = set(s for s in syms if any(s.partition("@")[0].startswith(p) for p in prefixes))
        cand |= set(extra.get(lib, []))
        for s in cand:
            name, _, ver = s.partition("@")
            ver = ver.split("@@")[0].strip()
            picked[ver or None].append(name)
        if not picked: continue
        csrc, maps = [], []
        for ver, names in sorted(picked.items(), key=lambda kv:(kv[0] is not None, kv[0])):
            for n in sorted(set(names)): csrc.append(f"void *{n}(void){{return 0;}}")
            if ver: maps.append(f'{ver} {{ global: {"; ".join(sorted(set(names)))}; }};')
        open(f"{OUT}/stub_tmp.c","w").write("\n".join(csrc)+"\n")
        cmd = ["gcc","-shared","-fPIC",f"-Wl,-soname,{lib}","-o",f"{OUT}/{lib}"]
        if maps:
            open(f"{OUT}/stub_tmp.map","w").write("\n".join(maps)+"\n")
            cmd.append(f"-Wl,--version-script={OUT}/stub_tmp.map")
        cmd.append(f"{OUT}/stub_tmp.c")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode: print("BUILD FAIL", lib, r.stderr[:800]); return False
        print(f"  built {lib}: {sum(len(v) for v in picked.values())} syms")
    return True

if __name__ == "__main__":
    extra = json.load(open(EXTRA)) if os.path.exists(EXTRA) else {}
    if not build(scan(), extra): raise SystemExit(1)
    env = dict(os.environ, LD_LIBRARY_PATH=OUT)
    for attempt in range(60):
        r = subprocess.run(["/home/user/Cavaliere3D/.venv/bin/python","-c","import bpy; print('BPY_OK', bpy.app.version_string)"],
                           capture_output=True, text=True, env=env, cwd="/home/user/Cavaliere3D")
        if r.returncode == 0:
            print("IMPORT", r.stdout.strip()); break
        m = re.search(r"undefined symbol: (\S+)", r.stderr)
        if not m:
            print("OTHER ERROR:\n", r.stderr[-2500:]); raise SystemExit(1)
        sym = m.group(1)
        for lib, prefixes in PREFIX.items():
            if sym.startswith(prefixes): extra.setdefault(lib, []).append(sym); break
        else:
            extra.setdefault("libXi.so.6", []).append(sym)
        print("  +", sym)
        json.dump(extra, open(EXTRA,"w"))
        if not build(scan(), extra): raise SystemExit(1)
