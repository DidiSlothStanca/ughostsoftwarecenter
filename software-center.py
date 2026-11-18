#!/usr/bin/env python3
"""Software Center - lightweight Qt6 app store for Linux (APT, DNF, pacman, zypper) + Flatpak."""
import filecmp, glob, gzip, hashlib, json, os, re, shlex, shutil, subprocess, sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from string import Template
from functools import lru_cache
from html import escape

from PySide6.QtCore import Qt, QThread, Signal, QProcess, QTimer, QEvent, QStandardPaths
from PySide6.QtGui import QIcon, QPalette, QColor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QLineEdit, QPushButton, QLabel, QScrollArea, QGridLayout,
    QFrame, QStackedWidget, QProgressBar, QTextEdit, QDialog, QTabWidget, QCheckBox, QComboBox,
    QTreeWidget, QTreeWidgetItem, QMessageBox, QMenu)

# ------------------------------------------------------------ settings + i18n
CFG = os.path.expanduser("~/.config/software-center/settings.json")
DEFAULTS = {"lang": "en", "unverified": True, "show_repo": True, "show_flatpak": True, "theme": "auto"}


def load_cfg():
    try:
        c = json.load(open(CFG))
    except Exception:
        return dict(DEFAULTS)
    if "show_apt" in c and "show_repo" not in c:  # setting renamed when other distros were added
        c["show_repo"] = c.pop("show_apt")
    return {**DEFAULTS, **c}


def save_cfg(c):
    os.makedirs(os.path.dirname(CFG), exist_ok=True)
    json.dump(c, open(CFG, "w"))


S = load_cfg()  # first run: English

APP_NAME = "Ughost Software Center"
VERSION = "0.0.1-Beta"
DEVELOPER = "Opensource OS Gathering Republic"
MAINTAINER = "Didi Sloth Stanca"

ID = {
    "All apps": "Semua aplikasi", "Manage": "Kelola", "Internet": "Internet",
    "Office": "Perkantoran", "Graphics": "Grafis", "Multimedia": "Multimedia", "Games": "Permainan",
    "Development": "Pengembangan", "Education": "Pendidikan", "System": "Sistem", "Utilities": "Utilitas",
    "Search apps…": "Cari aplikasi…", "⟳ Update lists": "⟳ Perbarui daftar", "⚙ Settings": "⚙ Pengaturan",
    "← Back": "← Kembali", "Install": "Pasang", "Remove": "Hapus", "Open": "Buka",
    "Loading catalog…": "Memuat katalog…", "Results for “{q}”": "Hasil untuk “{q}”",
    "{title}  ({a}–{b} of {m})": "{title}  ({a}–{b} dari {m})", "Page {p} / {n}": "Halaman {p} / {n}",
    "← Previous": "← Sebelumnya", "Next →": "Berikutnya →",
    "{name} repository": "Repositori {name}", "{name} repositories": "Repositori {name}",
    "Show {name} repository apps": "Tampilkan aplikasi repositori {name}",
    "No description.": "Tidak ada deskripsi.",
    "Unverified developer: this app is not verified by its repository.":
        "Pengembang belum terverifikasi: aplikasi ini tidak diverifikasi oleh repositorinya.",
    "This package has no launcher.": "Paket ini tidak punya peluncur aplikasi.",
    "Done": "Selesai", "Failed (code {c})": "Gagal (kode {c})",
    "Failed, see the log": "Gagal, lihat log",
    "{n} apps in catalog. Use search to find any repository package.":
        "{n} aplikasi di katalog. Gunakan pencarian untuk semua paket repo.",
    "Updating package lists…": "Memperbarui daftar paket…",
    "Check for updates": "Cek pembaruan", "Update all": "Perbarui semua", "Remove selected": "Hapus terpilih",
    "Name": "Nama", "Source": "Sumber", "Package": "Paket", "Status": "Status",
    "Update available": "Ada pembaruan", "Checking updates…": "Memeriksa pembaruan…",
    "Everything is up to date.": "Semua sudah terbaru.", "{n} updates available": "{n} pembaruan tersedia",
    "Remove {name}?": "Hapus {name}?", "Settings": "Pengaturan", "General": "Umum", "Language": "Bahasa",
    "The app restarts to apply the language.": "Aplikasi dimulai ulang untuk menerapkan bahasa.",
    "Show unverified Flatpak apps": "Tampilkan aplikasi Flatpak tidak terverifikasi",
    "Show Flatpak apps": "Tampilkan aplikasi Flatpak", "Repositories": "Repositori",
    "Flatpak repositories (tick = enabled)": "Repositori Flatpak (centang = aktif)",
    "Add Flatpak repository": "Tambah repositori Flatpak", "Repository name": "Nama repositori",
    "Repository URL (.flatpakrepo)": "URL repositori (.flatpakrepo)", "Close": "Tutup",
    "Add repository": "Tambah repositori",
    "deb line, e.g. deb [signed-by=/usr/share/keyrings/x.gpg] https://… stable main":
        "baris deb, mis. deb [signed-by=/usr/share/keyrings/x.gpg] https://… stable main",
    "Invalid name or URL/line.": "Nama atau URL/baris tidak valid.",
    "Added. Press “Update lists” to refresh the catalog.": "Ditambahkan. Tekan “Perbarui daftar” untuk memperbarui katalog.",
    "Only repositories added by Software Center can be removed.":
        "Hanya repositori yang ditambahkan Software Center yang bisa dihapus.",
    "Theme": "Tema", "Follow system": "Ikuti sistem", "Light": "Terang", "Dark": "Gelap",
    "About": "Tentang", "App Name": "Nama Aplikasi", "Version": "Versi", "Developer": "Pengembang",
    "Maintainer": "Pemelihara",
    "Add to Desktop": "Tambah ke Desktop", "Remove from Desktop": "Hapus dari Desktop",
    "Shortcut added to the Desktop: {path}": "Pintasan ditambahkan ke Desktop: {path}",
    "Shortcut removed from the Desktop.": "Pintasan dihapus dari Desktop.",
    "A different file with this name already exists on the Desktop.":
        "File lain dengan nama yang sama sudah ada di Desktop.",
    "Install from:": "Pasang dari:", "installed": "terpasang",
    "Warning: add repositories only from sources you trust, and install their signing key.":
        "Peringatan: tambahkan repositori hanya dari sumber tepercaya, dan pasang kunci tanda tangannya.",
    "Editing this list is not supported here; edit {file} manually.":
        "Mengubah daftar ini tidak didukung di sini; ubah {file} secara manual.",
    "URL of a .repo file, e.g. https://example.com/example.repo": "URL berkas .repo, mis. https://example.com/example.repo",
    "Repository URL, e.g. https://example.com/repo": "URL repositori, mis. https://example.com/repo",
    "No package manager found: only Flatpak apps are available.":
        "Pengelola paket tidak ditemukan: hanya aplikasi Flatpak yang tersedia.",
    "No supported package manager on this system.": "Tidak ada pengelola paket yang didukung di sistem ini.",
}


def T(s, **kw):
    s = ID.get(s, s) if S["lang"] == "id" else s
    return s.format(**kw) if kw else s


LANG = "{http://www.w3.org/XML/1998/namespace}lang"
FLATHUB = "https://dl.flathub.org/repo/flathub.flatpakrepo"
VERIFY = "flathub::verification::verified"

CATS = {
    "Internet": ("applications-internet", {"Network", "WebBrowser", "Email", "Chat", "InstantMessaging", "FileTransfer", "P2P"}),
    "Office": ("applications-office", {"Office", "Calendar", "ContactManagement", "Dictionary", "Finance", "Spreadsheet", "WordProcessor"}),
    "Graphics": ("applications-graphics", {"Graphics", "Photography", "Scanning", "2DGraphics", "3DGraphics", "RasterGraphics", "VectorGraphics"}),
    "Multimedia": ("applications-multimedia", {"AudioVideo", "Audio", "Video", "Music", "Player", "Recorder", "Midi", "Mixer"}),
    "Games": ("applications-games", {"Game"}),
    "Development": ("applications-development", {"Development", "IDE", "Debugger", "TextEditor"}),
    "Education": ("applications-science", {"Education", "Science", "Math", "Astronomy", "Chemistry", "Geography"}),
    "System": ("applications-system", {"System", "Monitor", "PackageManager", "Settings", "Security", "Emulator"}),
    "Utilities": ("applications-utilities", {"Utility", "Accessibility", "Archiving", "FileManager", "Calculator"}),
}


# Built-in APT catalogue (edit for your distro): package -> (name, category).
# Debian/Devuan usually ship no AppStream XML, so this list is what makes APT apps show up in the grid.
# Packages that do not exist in the configured repositories are skipped; everything else is found via search.
CURATED = {
    "firefox-esr": ("Firefox", "Internet"), "chromium": ("Chromium", "Internet"),
    "thunderbird": ("Thunderbird", "Internet"), "transmission-gtk": ("Transmission", "Internet"),
    "filezilla": ("FileZilla", "Internet"), "hexchat": ("HexChat", "Internet"),
    "libreoffice": ("LibreOffice", "Office"), "evince": ("Document Viewer", "Office"),
    "gnumeric": ("Gnumeric", "Office"), "gimp": ("GIMP", "Graphics"),
    "inkscape": ("Inkscape", "Graphics"), "krita": ("Krita", "Graphics"),
    "blender": ("Blender", "Graphics"), "vlc": ("VLC", "Multimedia"),
    "audacity": ("Audacity", "Multimedia"), "obs-studio": ("OBS Studio", "Multimedia"),
    "kdenlive": ("Kdenlive", "Multimedia"), "handbrake": ("HandBrake", "Multimedia"),
    "audacious": ("Audacious", "Multimedia"), "mpv": ("mpv", "Multimedia"),
    "supertux": ("SuperTux", "Games"), "0ad": ("0 A.D.", "Games"),
    "geany": ("Geany", "Development"), "meld": ("Meld", "Development"),
    "gparted": ("GParted", "System"), "synaptic": ("Synaptic", "System"),
    "timeshift": ("Timeshift", "System"), "gnome-disk-utility": ("Disks", "System"),
    "file-roller": ("Archive Manager", "Utilities"), "galculator": ("Galculator", "Utilities"),
    "bleachbit": ("BleachBit", "Utilities"), "keepassxc": ("KeePassXC", "Utilities"),
    "flameshot": ("Flameshot", "Utilities"),
    "qbittorrent": ("qBittorrent", "Internet"), "pidgin": ("Pidgin", "Internet"), "remmina": ("Remmina", "Internet"),
    "epiphany-browser": ("Web", "Internet"), "falkon": ("Falkon", "Internet"), "evolution": ("Evolution", "Internet"),
    "okular": ("Okular", "Office"), "calibre": ("calibre", "Office"), "scribus": ("Scribus", "Office"),
    "abiword": ("AbiWord", "Office"), "gnucash": ("GnuCash", "Office"), "qpdfview": ("qpdfview", "Office"),
    "zathura": ("Zathura", "Office"), "darktable": ("darktable", "Graphics"), "rawtherapee": ("RawTherapee", "Graphics"),
    "gwenview": ("Gwenview", "Graphics"), "simple-scan": ("Document Scanner", "Graphics"),
    "shotwell": ("Shotwell", "Graphics"), "ristretto": ("Ristretto", "Graphics"),
    "rhythmbox": ("Rhythmbox", "Multimedia"), "shotcut": ("Shotcut", "Multimedia"),
    "openshot-qt": ("OpenShot", "Multimedia"), "pitivi": ("Pitivi", "Multimedia"), "ardour": ("Ardour", "Multimedia"),
    "lmms": ("LMMS", "Multimedia"), "cheese": ("Cheese", "Multimedia"), "strawberry": ("Strawberry", "Multimedia"),
    "supertuxkart": ("SuperTuxKart", "Games"), "wesnoth": ("Battle for Wesnoth", "Games"),
    "xonotic": ("Xonotic", "Games"), "gnome-mines": ("Mines", "Games"), "aisleriot": ("AisleRiot Solitaire", "Games"),
    "frozen-bubble": ("Frozen Bubble", "Games"), "vim-gtk3": ("Vim", "Development"), "gedit": ("gedit", "Development"),
    "mousepad": ("Mousepad", "Development"), "kate": ("Kate", "Development"), "codeblocks": ("Code::Blocks", "Development"),
    "freecad": ("FreeCAD", "Development"), "kicad": ("KiCad", "Development"), "qtcreator": ("Qt Creator", "Development"),
    "stellarium": ("Stellarium", "Education"), "gcompris-qt": ("GCompris", "Education"),
    "kalzium": ("Kalzium", "Education"), "celestia-gnome": ("Celestia", "Education"), "kturtle": ("KTurtle", "Education"),
    "gnome-system-monitor": ("System Monitor", "System"), "baobab": ("Disk Usage Analyzer", "System"),
    "virt-manager": ("Virtual Machine Manager", "System"), "virtualbox": ("VirtualBox", "System"),
    "gnome-terminal": ("Terminal", "System"), "xfce4-terminal": ("Xfce Terminal", "System"),
    "gnome-calculator": ("Calculator", "Utilities"), "kcalc": ("KCalc", "Utilities"), "ark": ("Ark", "Utilities"),
    "xarchiver": ("Xarchiver", "Utilities"), "gnome-screenshot": ("Screenshot", "Utilities"),
    "copyq": ("CopyQ", "Utilities"), "thunar": ("Thunar", "Utilities"), "pcmanfm": ("PCManFM", "Utilities"),
    "nemo": ("Nemo", "Utilities"),
}


# ---------------------------------------------------------------- backend
def run(cmd, c=False, t=90):
    """Run a command and return stdout. c=True forces the C locale so the output can be parsed."""
    env = {**os.environ, "LC_ALL": "C", "LANG": "C", "LANGUAGE": "C"} if c else None
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=t, env=env).stdout
    except Exception:
        return ""


def fp_installed():
    """{app id: 'user'|'system'}"""
    d = {}
    for l in run(["flatpak", "list", "--app", "--columns=application,installation"]).splitlines():
        p = l.split()
        if len(p) >= 2:
            d[p[0]] = p[1]
    return d


def flatpak_remotes():
    out = []
    for l in run(["flatpak", "remotes", "--columns=name,url,options"]).splitlines():
        p = l.split()
        if len(p) >= 2:
            o = " ".join(p[2:])
            out.append(dict(name=p[0], url=p[1], scope="user" if "user" in o else "system", disabled="disabled" in o))
    return out


FP_EXPORTS = {"user": os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
              "system": "/var/lib/flatpak/exports/share/applications"}


def fp_gui_installed():
    res = {}
    for l in run(["flatpak", "list", "--app", "--columns=application,name,installation"]).splitlines():
        p = l.split("\t")
        if len(p) >= 3:
            scope = p[2].strip()
            f = os.path.join(FP_EXPORTS.get(scope, FP_EXPORTS["system"]), p[0] + ".desktop")
            res[p[0]] = dict(src="flatpak", pkg=p[0], name=p[1], summary="", desc="", cat="Utilities",
                             icon=None, scope=scope, verified=True, desktop=f if os.path.exists(f) else None)
    return res


# ---- desktop shortcuts
def desktop_dir():
    """The user's Desktop folder (follows ~/.config/user-dirs.dirs, so translated names work)."""
    return QStandardPaths.writableLocation(QStandardPaths.DesktopLocation) or os.path.expanduser("~/Desktop")


def shortcut_path(a):
    return os.path.join(desktop_dir(), os.path.basename(a["desktop"])) if a.get("desktop") else None


def has_shortcut(a):
    dst = shortcut_path(a)
    try:
        return bool(dst) and os.path.exists(dst) and filecmp.cmp(a["desktop"], dst, shallow=False)
    except OSError:
        return False


def add_shortcut(a):
    """Copy the app's .desktop file to the Desktop. -> (True, path) or (False, reason)."""
    src, dst = a.get("desktop"), shortcut_path(a)
    if not src or not os.path.exists(src):
        return False, "nolauncher"
    if os.path.exists(dst) and not has_shortcut(a):
        return False, "exists"  # never overwrite a file the user made
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        os.chmod(dst, 0o755)  # KDE, LXQt, ... only need the executable bit
        if have("gio"):  # GNOME, Cinnamon (trusted) and Xfce (checksum) ask before launching otherwise
            run(["gio", "set", dst, "metadata::trusted", "true"])
            run(["gio", "set", dst, "metadata::xfce-exe-checksum", hashlib.sha256(open(dst, "rb").read()).hexdigest()])
    except OSError as e:
        return False, str(e)
    return True, dst


def remove_shortcut(a):
    if not has_shortcut(a):  # only remove the copy we made, never a different file
        return False
    try:
        os.remove(shortcut_path(a))
    except OSError:
        return False
    return True


def fp_updates():
    return {l.split()[0] for l in run(["flatpak", "remote-ls", "--updates", "--app", "--columns=application"]).splitlines() if l.strip()}


# ---------------------------------------------------------------- distro / package-manager backends
def _os_release():
    d = {}
    for f in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            for l in open(f):
                k, _, v = l.strip().partition("=")
                if k and not k.startswith("#"):
                    d[k] = v.strip().strip("\"'")
            break
        except OSError:
            continue
    return d


OSREL = _os_release()
DISTRO = OSREL.get("NAME") or "Linux"  # e.g. "Fedora Linux", "Arch Linux", "Devuan GNU/Linux"


def repo_label():
    return T("{name} repository", name=DISTRO)


def have(cmd):
    return shutil.which(cmd) is not None


def _noise(n):
    """Library / documentation / debug packages are not applications."""
    return n.startswith(("lib", "fonts-", "font-", "ttf-", "otf-", "python-", "python3-", "perl-", "golang-")) \
        or n.endswith(("-dev", "-devel", "-dbg", "-dbgsym", "-debuginfo", "-debugsource", "-doc", "-docs",
                       "-data", "-common", "-l10n", "-lang", "-langpack", "-headers", "-help"))


def desktop_entries(owner):
    """{desktop file: package} -> {package: app dict} for installed packages that ship a menu entry."""
    res = {}
    for f, pkg in owner.items():
        name = icon = None
        hide = False
        try:
            for line in open(f, errors="ignore"):
                if line.startswith("[Desktop Action"):
                    break
                if line.startswith("Name=") and not name:
                    name = line[5:].strip()
                elif line.startswith("Icon=") and not icon:
                    icon = line[5:].strip()
                elif line.strip() in ("NoDisplay=true", "Hidden=true"):
                    hide = True
        except OSError:
            continue
        if name and not hide:
            res.setdefault(pkg, dict(src="sys", pkg=pkg, name=name, summary="", desc="", cat="Utilities", icon=icon,
                                     desktop=f))
    return res


def rpm_repos(pattern):
    """List the [sections] of .repo files (used by DNF and zypper)."""
    out = []
    for f in sorted(glob.glob(pattern)):
        try:
            lines = open(f, errors="ignore").read().splitlines()
        except OSError:
            continue
        ents, cur = [], None
        for l in lines:
            l = l.strip()
            if l.startswith("[") and l.endswith("]"):
                cur = dict(id=l[1:-1], name="", enabled=True)
                ents.append(cur)
            elif cur is not None and "=" in l:
                k, _, v = l.partition("=")
                k, v = k.strip().lower(), v.strip()
                if k == "name":
                    cur["name"] = v
                elif k == "enabled":
                    cur["enabled"] = v.lower() not in ("0", "false", "no")
        for e in ents:
            out.append((f"[{e['id']}] {e['name']}{'' if e['enabled'] else '  (disabled)'}   ({os.path.basename(f)})", f))
    return out


class Backend:
    """Base class. Also used when no supported package manager exists: only Flatpak is available."""
    key, short, repo_file, repo_hint, editable = "none", "", "", "", False

    @classmethod
    def available(cls):
        return False

    # --- queries
    def installed(self):
        return set()

    def show(self, pkgs):
        """{package: (summary, description)} for the packages that exist in the repositories."""
        return {}

    def describe(self, pkg):
        return self.show([pkg]).get(pkg, ("", ""))

    def search(self, q):
        return []

    def owners(self, files):
        """{file: package} for the given files."""
        return {}

    def files(self, pkg):
        return []

    def updates(self):
        return set()

    def gui_installed(self):
        return desktop_entries(self.owners(glob.glob("/usr/share/applications/*.desktop")))

    def curated(self):
        return {ALIAS.get(self.key, {}).get(p, p): v for p, v in CURATED.items()}

    # --- actions (argv lists / shell snippets run through pkexec)
    def install(self, pkg):
        return None

    def remove(self, pkg):
        return None

    def refresh(self):
        return ""

    def upgrade(self):
        return ""

    # --- repositories shown in Settings
    def repos(self):
        return []

    def repo_ok(self, spec):
        return False

    def repo_add(self, name, spec):
        return None

    def repo_del(self, f):
        return None


class AptBackend(Backend):
    key, short, editable = "apt", "APT", True
    repo_file = "/etc/apt/sources.list"
    repo_hint = "deb line, e.g. deb [signed-by=/usr/share/keyrings/x.gpg] https://… stable main"

    @classmethod
    def available(cls):
        return have("apt-get") and have("dpkg-query")

    def installed(self):
        out = run(["dpkg-query", "-W", "-f=${Package}\t${db:Status-Abbrev}\n"])
        return {l.split("\t")[0] for l in out.splitlines() if "\tii" in l}

    def show(self, pkgs):
        res = {}
        for block in run(["apt-cache", "show", "--no-all-versions", *pkgs]).split("\n\n"):
            name, summ, desc, ind = None, "", [], False
            for line in block.splitlines():
                if line.startswith("Package: "):
                    name = line[9:].strip()
                elif line.startswith("Description") and not line.startswith("Description-md5"):
                    summ, ind = line.split(": ", 1)[-1], True
                elif ind and line.startswith(" "):
                    desc.append("" if line.strip() == "." else line.strip())
                elif not line.startswith(" "):
                    ind = False
            if name:
                res[name] = (summ, "\n".join(desc))
        return res

    def search(self, q):
        out = []
        for l in run(["apt-cache", "search", *q.split()]).splitlines():
            n, _, s_ = l.partition(" - ")
            if not _noise(n):
                out.append((n, s_))
        return out[:80]

    def owners(self, files):
        owner = {}
        for l in run(["dpkg", "-S", *files]).splitlines():
            p, _, f = l.partition(": ")
            if f:
                owner[f.strip()] = p.split(",")[0].split(":")[0]
        return owner

    def files(self, pkg):
        return run(["dpkg", "-L", pkg]).split()

    def updates(self):
        return {l.split("/")[0] for l in run(["apt", "list", "--upgradable"]).splitlines()
                if "/" in l and "upgradable" in l}

    def install(self, pkg):
        return ["pkexec", "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y", pkg]

    def remove(self, pkg):
        return ["pkexec", "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "remove", "-y", pkg]

    def refresh(self):
        return "pkexec apt-get update"

    def upgrade(self):
        return "pkexec env DEBIAN_FRONTEND=noninteractive apt-get upgrade -y"

    def repos(self):
        out = []
        for f in [self.repo_file] + sorted(glob.glob("/etc/apt/sources.list.d/*")):
            try:
                lines = open(f).read().splitlines()
            except OSError:
                continue
            for l in lines:
                l = l.strip()
                if l.startswith(("deb ", "URIs:")):
                    out.append((f"{l}   ({os.path.basename(f)})", f))
        return out

    def repo_ok(self, spec):
        return spec.startswith("deb ")

    def repo_add(self, name, spec):
        return ["pkexec", "sh", "-c", 'printf "%s\\n" "$1" > "/etc/apt/sources.list.d/software-center-$0.list"', name, spec]

    def repo_del(self, f):
        return ["pkexec", "rm", "-f", f]


class RpmBackend(Backend):
    """Shared by DNF (Fedora, RHEL...) and zypper (openSUSE): both sit on top of rpm."""

    def installed(self):
        return {l.strip() for l in run(["rpm", "-qa", "--qf", "%{NAME}\n"], c=True).splitlines() if l.strip()}

    def owners(self, files):
        want, owner = set(files), {}
        for l in run(["rpm", "-qa", "--filesbypkg"], c=True, t=180).splitlines():
            p = l.split(None, 1)
            if len(p) == 2 and p[1].strip() in want:
                owner[p[1].strip()] = p[0]
        return owner

    def files(self, pkg):
        return run(["rpm", "-ql", pkg], c=True).split()


RPM_ARCH = "x86_64|noarch|i686|i386|aarch64|armv7hl|ppc64le|s390x|riscv64"


class DnfBackend(RpmBackend):
    key, short, editable = "dnf", "DNF", True
    repo_file = "/etc/yum.repos.d"
    repo_hint = "URL of a .repo file, e.g. https://example.com/example.repo"

    def __init__(self):
        self.cmd = "dnf" if have("dnf") else "dnf5"

    @classmethod
    def available(cls):
        return have("rpm") and (have("dnf") or have("dnf5"))

    def show(self, pkgs):
        res, want = {}, set(pkgs)
        out = run([self.cmd, "-q", "repoquery", "--queryformat", "%{name} :: %{summary}\n", "--latest-limit", "1", *pkgs],
                  c=True, t=180)
        for l in out.splitlines():
            l = l.strip()
            n, sep, s_ = l.partition(" :: ")
            if sep and n in want:
                res.setdefault(n, (s_.strip(), ""))
        return res

    def describe(self, pkg):
        summ, desc, mode = "", [], False
        for l in run([self.cmd, "-q", "info", pkg], c=True, t=120).splitlines():
            cont = re.match(r"^\s+:\s?(.*)$", l)
            if mode:
                if cont:
                    desc.append(cont.group(1).strip())
                    continue
                break
            m = re.match(r"^(\w[\w ]*?)\s*:\s?(.*)$", l)
            if not m:
                continue
            if m.group(1) == "Summary" and not summ:
                summ = m.group(2).strip()
            elif m.group(1) == "Description":
                desc.append(m.group(2).strip())
                mode = True
        return summ, "\n".join(desc).strip()

    def search(self, q):
        pat = re.compile(rf"^\s*(\S+?)\.(?:{RPM_ARCH})\s*(?::\s*)?(.*)$")  # dnf4 "name.arch : summary", dnf5 "name.arch  summary"
        out, seen = [], set()
        for l in run([self.cmd, "-q", "search", *q.split()], c=True, t=180).splitlines():
            m = pat.match(l)
            if m and m.group(1) not in seen and not _noise(m.group(1)):
                seen.add(m.group(1))
                out.append((m.group(1), m.group(2).strip()))
        return out[:80]

    def updates(self):
        pat = re.compile(rf"^(\S+?)\.(?:{RPM_ARCH})\s+\S+\s+\S+")
        return {m.group(1) for m in (pat.match(l) for l in run([self.cmd, "-q", "check-update"], c=True, t=180).splitlines()) if m}

    def install(self, pkg):
        return ["pkexec", self.cmd, "install", "-y", pkg]

    def remove(self, pkg):
        return ["pkexec", self.cmd, "remove", "-y", pkg]

    def refresh(self):
        return f"pkexec {self.cmd} -y makecache --refresh"

    def upgrade(self):
        return f"pkexec {self.cmd} upgrade -y"

    def repos(self):
        return rpm_repos("/etc/yum.repos.d/*.repo")

    def repo_ok(self, spec):
        return re.fullmatch(r"https?://\S+\.repo", spec) is not None

    def repo_add(self, name, spec):
        return ["pkexec", "curl", "-fsSL", "-o", f"/etc/yum.repos.d/software-center-{name}.repo", spec]

    def repo_del(self, f):
        return ["pkexec", "rm", "-f", f]


class ZypperBackend(RpmBackend):
    key, short, editable = "zypper", "zypper", True
    repo_file = "/etc/zypp/repos.d"
    repo_hint = "Repository URL, e.g. https://example.com/repo"

    @classmethod
    def available(cls):
        return have("rpm") and have("zypper")

    def show(self, pkgs):
        res, want = {}, set(pkgs)
        for block in run(["zypper", "-n", "info", *pkgs], c=True, t=180).split("Information for package"):
            name = summ = ""
            desc, mode = [], False
            for l in block.splitlines():
                if mode:
                    if l.startswith((" ", "\t")):
                        desc.append(l.strip())
                        continue
                    mode = False
                k, _, v = l.partition(":")
                k = k.strip()
                if k == "Name" and not name:
                    name = v.strip()
                elif k == "Summary" and not summ:
                    summ = v.strip()
                elif k == "Description":
                    mode = True
                    if v.strip():
                        desc.append(v.strip())
            if name in want:
                res.setdefault(name, (summ, "\n".join(desc).strip()))
        return res

    def search(self, q):
        out, seen = [], set()
        for l in run(["zypper", "-n", "search", "-d", "-t", "package", *q.split()], c=True, t=180).splitlines():
            c = [x.strip() for x in l.split("|")]
            if len(c) >= 3 and c[1] not in ("", "Name") and not l.startswith("-") and c[1] not in seen and not _noise(c[1]):
                seen.add(c[1])
                out.append((c[1], c[2]))
        return out[:80]

    def updates(self):
        res = set()
        for l in run(["zypper", "-n", "list-updates"], c=True, t=180).splitlines():
            c = [x.strip() for x in l.split("|")]
            if len(c) >= 5 and c[0] != "S" and c[2] and not l.startswith("-"):
                res.add(c[2])
        return res

    def install(self, pkg):
        return ["pkexec", "zypper", "-n", "install", "--auto-agree-with-licenses", pkg]

    def remove(self, pkg):
        return ["pkexec", "zypper", "-n", "remove", pkg]

    def refresh(self):
        return "pkexec zypper -n refresh"

    def upgrade(self):
        return "pkexec zypper -n update"

    def repos(self):
        return rpm_repos("/etc/zypp/repos.d/*.repo")

    def repo_ok(self, spec):
        return re.fullmatch(r"https?://\S+", spec) is not None

    def repo_add(self, name, spec):
        return ["pkexec", "zypper", "--gpg-auto-import-keys", "-n", "addrepo", "-f", spec, f"software-center-{name}"]

    def repo_del(self, f):
        return ["pkexec", "zypper", "-n", "removerepo", os.path.basename(f).removesuffix(".repo")]


class PacmanBackend(Backend):
    """Arch, Manjaro, EndeavourOS... The repository list is read-only (it lives in /etc/pacman.conf)."""
    key, short, repo_file = "pacman", "pacman", "/etc/pacman.conf"

    @classmethod
    def available(cls):
        return have("pacman")

    def installed(self):
        return {l.strip() for l in run(["pacman", "-Qq"], c=True).splitlines() if l.strip()}

    def show(self, pkgs):
        avail = {p[1] for p in (l.split() for l in run(["pacman", "-Sl"], c=True).splitlines()) if len(p) >= 3}
        want = [p for p in pkgs if p in avail]  # pacman -Si aborts on the first unknown package
        res = {}
        if not want:
            return res
        for block in run(["pacman", "-Si", *want], c=True, t=120).split("\n\n"):
            name = desc = ""
            for l in block.splitlines():
                k, _, v = l.partition(":")
                k = k.strip()
                if k == "Name" and not name:
                    name = v.strip()
                elif k == "Description" and not desc:
                    desc = v.strip()
            if name:
                res.setdefault(name, (desc, ""))
        return res

    def search(self, q):
        out, lines = [], run(["pacman", "-Ss", *q.split()], c=True).splitlines()
        for i, l in enumerate(lines):
            if l and not l.startswith(" ") and "/" in l.split()[0]:
                n = l.split()[0].split("/", 1)[1]
                if not _noise(n):
                    out.append((n, lines[i + 1].strip() if i + 1 < len(lines) else ""))
        return out[:80]

    def owners(self, files):
        owner = {}
        for l in run(["pacman", "-Qo", *files], c=True).splitlines():
            m = re.match(r"^(.+) is owned by (\S+) \S+$", l)
            if m:
                owner[m.group(1)] = m.group(2)
        return owner

    def files(self, pkg):
        return [l.split(None, 1)[1].strip() for l in run(["pacman", "-Ql", pkg], c=True).splitlines() if " " in l]

    def updates(self):
        out = run(["checkupdates"], c=True, t=120) if have("checkupdates") else run(["pacman", "-Qu"], c=True)
        return {l.split()[0] for l in out.splitlines() if l.strip()}

    def install(self, pkg):
        return ["pkexec", "pacman", "-S", "--noconfirm", "--needed", pkg]

    def remove(self, pkg):
        return ["pkexec", "pacman", "-Rs", "--noconfirm", pkg]

    def refresh(self):
        return "pkexec pacman -Sy"

    def upgrade(self):
        return "pkexec pacman -Syu --noconfirm"

    def repos(self):
        out = []
        try:
            for l in open(self.repo_file):
                l = l.strip()
                if l.startswith("[") and l.endswith("]") and l[1:-1] != "options":
                    out.append((l, self.repo_file))
        except OSError:
            pass
        return out


BACKENDS = (AptBackend, DnfBackend, PacmanBackend, ZypperBackend)
FAMILIES = {
    "apt": {"debian", "ubuntu", "devuan", "linuxmint", "pop", "raspbian", "kali", "mx", "elementary", "zorin", "neon"},
    "dnf": {"fedora", "rhel", "centos", "rocky", "almalinux", "ol", "nobara", "amzn"},
    "pacman": {"arch", "manjaro", "endeavouros", "artix", "garuda", "cachyos"},
    "zypper": {"suse", "opensuse", "opensuse-leap", "opensuse-tumbleweed", "sles", "sled"},
}
# Debian package name -> name on other distributions (names that are not listed are assumed to be the same)
ALIAS = {
    "dnf": {"firefox-esr": "firefox", "handbrake": "handbrake-gui", "vim-gtk3": "vim-X11", "qtcreator": "qt-creator",
            "celestia-gnome": "celestia", "openshot-qt": "openshot", "epiphany-browser": "epiphany"},
    "pacman": {"firefox-esr": "firefox", "libreoffice": "libreoffice-fresh", "vim-gtk3": "gvim",
               "epiphany-browser": "epiphany", "openshot-qt": "openshot", "celestia-gnome": "celestia"},
    "zypper": {"firefox-esr": "MozillaFirefox", "thunderbird": "MozillaThunderbird", "vim-gtk3": "gvim",
               "handbrake": "handbrake-gtk", "epiphany-browser": "epiphany", "openshot-qt": "openshot",
               "qtcreator": "qt-creator", "celestia-gnome": "celestia"},
}


def detect_backend():
    """Pick the package manager: by distro family first, then by whichever tool is installed.
    SC_BACKEND=apt|dnf|pacman|zypper|none overrides the detection."""
    want = os.environ.get("SC_BACKEND", "").lower()
    if want == "none":
        return Backend()
    ids = {OSREL.get("ID", "").lower(), *OSREL.get("ID_LIKE", "").lower().split()}
    cands = [c for c in BACKENDS if not want or c.key == want]
    for c in cands:
        if (want or ids & FAMILIES[c.key]) and c.available():
            return c()
    for c in cands:
        if c.available():
            return c()
    return Backend()


PM = detect_backend()


def _norm(s):
    s = re.sub(r"[^a-z0-9]", "", s.lower())
    for suf in ("esr", "gtk", "qt", "bin"):
        if s.endswith(suf) and len(s) > len(suf) + 2:
            s = s[:-len(suf)]
    return s


def alt_keys(a):
    """Keys used to recognise the same application in APT and in Flatpak."""
    last = a["pkg"].rsplit(".", 1)[-1] if a["src"] == "flatpak" else a["pkg"]
    return {k for k in (_norm(a["name"]), _norm(last)) if k}


def map_cat(cats):
    for name, (_, xdg) in CATS.items():
        if xdg & set(cats):
            return name
    return "Utilities"


def txt(el, tag):
    for c in el.findall(tag):
        if c.get(LANG) is None:
            return (c.text or "").strip()
    return ""


SYS_BASES = tuple(d for p in ("/var/lib/swcatalog/icons/*", "/usr/share/swcatalog/icons/*",
                              "/usr/share/app-info/icons/*", "/var/lib/app-info/icons/*") for d in glob.glob(p))


def parse_appstream(path):
    flat = "/flatpak/appstream/" in path
    bases = (os.path.join(os.path.dirname(path), "icons"),) if flat else SYS_BASES
    remote = path.split(os.sep)[-4] if flat else ""
    scope = "user" if path.startswith(os.path.expanduser("~")) else "system"
    out = []
    try:
        with (gzip.open(path, "rb") if path.endswith(".gz") else open(path, "rb")) as f:
            for _, el in ET.iterparse(f):
                if el.tag != "component":
                    continue
                if el.get("type") in ("desktop-application", "desktop"):
                    cid = txt(el, "id").removesuffix(".desktop")
                    pkg, name = (cid if flat else txt(el, "pkgname")), txt(el, "name")
                    if pkg and name:
                        d = el.find("description")
                        desc = "\n\n".join("".join(p.itertext()).strip() for p in d.findall("p")
                                           if p.get(LANG) is None) if d is not None else ""
                        icon = None
                        for ic in el.findall("icon"):
                            t = ic.get("type")
                            if t == "cached" and (icon is None or ic.get("width") == "64"):
                                icon = (ic.text or "").strip()
                            elif t == "stock" and icon is None:
                                icon = (ic.text or "").strip()
                        ver = any(v.get("key") == VERIFY and (v.text or "").strip() == "true"
                                  for v in el.findall("custom/value"))
                        out.append(dict(src="flatpak" if flat else "sys", pkg=pkg, name=name,
                                        summary=txt(el, "summary"), desc=desc,
                                        cat=map_cat([c.text for c in el.findall("categories/category")]),
                                        icon=icon, ibases=bases, remote=remote, scope=scope,
                                        verified=ver or not flat))
                el.clear()
    except Exception:
        pass
    return out


def appstream_files():
    pats = ["/usr/share/swcatalog/xml/*", "/var/lib/swcatalog/xml/*", "/usr/share/app-info/xmls/*",
            "/var/lib/app-info/xmls/*", "/var/lib/flatpak/appstream/*/*/active/appstream.xml*",
            os.path.expanduser("~/.local/share/flatpak/appstream/*/*/active/appstream.xml*")]
    return [f for p in pats for f in glob.glob(p)]


@lru_cache(maxsize=None)
def find_icon(name, bases):
    for b in bases:
        for sub in ("64x64", "128x128", "48x48"):
            p = os.path.join(b, sub, name)
            if os.path.exists(p):
                return p
    return None


def get_icon(app):
    n = app.get("icon")
    if n:
        p = find_icon(n, tuple(app.get("ibases", ())))
        if p:
            return QIcon(p)
        ic = QIcon.fromTheme(n)
        if ic.isNull():
            ic = QIcon.fromTheme(n.rsplit(".", 1)[0])
        if not ic.isNull():
            return ic
    ic = QIcon.fromTheme(app["pkg"])
    if not ic.isNull():
        return ic
    return QIcon.fromTheme(CATS.get(app.get("cat"), ("application-x-executable",))[0],
                           QIcon.fromTheme("application-x-executable"))


def launch(app):
    if app["src"] == "flatpak":
        subprocess.Popen(["flatpak", "run", app["pkg"]])
        return True
    for f in PM.files(app["pkg"]):
        if f.startswith("/usr/share/applications/") and f.endswith(".desktop"):
            for line in open(f, errors="ignore"):
                if line.startswith("Exec="):
                    subprocess.Popen([x for x in shlex.split(line[5:]) if not x.startswith("%")])
                    return True
    return False


class Loader(QThread):
    partial = Signal(object, object, object)
    done = Signal(object, object, object)

    def run(self):
        names = PM.curated()
        info = PM.show(list(names))
        cur = {("sys", p): dict(src="sys", pkg=p, name=n, summary=info[p][0], desc=info[p][1],
                                cat=c, icon=None, verified=True)
               for p, (n, c) in names.items() if p in info}
        ia, ifp = PM.installed(), fp_installed()
        self.partial.emit(list(cur.values()), ia, ifp)  # show the repository apps right away
        apps = {}
        for path in appstream_files():
            for a in parse_appstream(path):
                apps.setdefault((a["src"], a["pkg"]), a)
        for k, a in cur.items():
            apps.setdefault(k, a)
        self.done.emit(list(apps.values()), ia, ifp)


class Job(QThread):
    done = Signal(object)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn())
        except Exception:
            self.done.emit(None)


# --------------------------------------------------------------------- UI
C = {"warn": "#c64600", "ok": "#26a269", "dim": "#888888"}  # colours used inside rich text (see Card)
THEME = {"sys": None, "busy": False, "forced": False, "win": None}

STYLE = Template("""
QWidget{font-size:13px}
QMainWindow,#page{background:$win}
#side{background:$side;color:$text;border:0;outline:0;padding:6px}
#side::item{padding:9px 10px;border-radius:6px;margin:1px 4px}
#side::item:selected{background:$acc;color:$acct}
QLineEdit{padding:7px 14px;border:1px solid $border;border-radius:16px;background:$base;color:$text}
#card{background:$base;border:1px solid $cardb;border-radius:10px}
#card:hover{border-color:$acc}
#sub{color:$sub}
#warn{color:$warn}
#title{font-size:20px;font-weight:bold}
QPushButton{padding:7px 18px;border-radius:6px;border:1px solid $border;background:$btn;color:$text}
QPushButton#primary{background:$acc;color:$acct;border:0}
QPushButton#danger{background:#e01b24;color:white;border:0}
QPushButton:disabled{background:$disb;color:$disf;border:0}
QScrollArea{border:0;background:transparent}
""")


def _mix(a, b, t):
    return QColor.fromRgbF(a.redF() * (1 - t) + b.redF() * t, a.greenF() * (1 - t) + b.greenF() * t,
                           a.blueF() * (1 - t) + b.blueF() * t)


def _is_dark(p):
    return p.color(QPalette.Window).lightness() < 128


def gtk_prefers_dark():
    """Fallback for desktops that tell GTK, but not Qt, about a dark theme."""
    if "dark" in os.environ.get("GTK_THEME", "").lower():
        return True
    for v in ("3.0", "4.0"):
        try:
            for l in open(os.path.expanduser(f"~/.config/gtk-{v}/settings.ini")):
                k, _, val = l.partition("=")
                k, val = k.strip(), val.strip().lower()
                if k == "gtk-application-prefer-dark-theme" and val in ("1", "true"):
                    return True
                if k == "gtk-theme-name" and "dark" in val:
                    return True
        except OSError:
            pass
    return False


def dark_palette():
    p, c = QPalette(), QColor
    for role, col in ((QPalette.Window, "#2b2b2e"), (QPalette.WindowText, "#e6e6e6"), (QPalette.Base, "#1f1f22"),
                      (QPalette.AlternateBase, "#2b2b2e"), (QPalette.Text, "#e6e6e6"), (QPalette.Button, "#3a3a3e"),
                      (QPalette.ButtonText, "#e6e6e6"), (QPalette.ToolTipBase, "#3a3a3e"),
                      (QPalette.ToolTipText, "#e6e6e6"), (QPalette.PlaceholderText, "#8d8d92"),
                      (QPalette.Highlight, "#3584e4"), (QPalette.HighlightedText, "#ffffff"),
                      (QPalette.Link, "#62a0ea"), (QPalette.BrightText, "#ff5555")):
        p.setColor(role, c(col))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, c("#7a7a7a"))
    return p


def want_dark(app):
    mode = S.get("theme", "auto")
    if mode in ("dark", "light"):
        return mode == "dark"
    try:
        cs = app.styleHints().colorScheme()          # Qt >= 6.5: asks the desktop / xdg portal
        if cs == Qt.ColorScheme.Dark:
            return True
        light = cs == Qt.ColorScheme.Light
    except AttributeError:
        light = False
    if _is_dark(THEME["sys"]):                       # dark palette from qt6ct / kvantum / gtk platform theme
        return True
    return not light and gtk_prefers_dark()


def build_style(p):
    col = lambda r: p.color(r)
    win, base, text, black = col(QPalette.Window), col(QPalette.Base), col(QPalette.WindowText), QColor("black")
    dark = _is_dark(p)
    sub = _mix(text, win, .38)
    C.update(warn="#ff9a57" if dark else "#c64600", ok="#57e389" if dark else "#26a269", dim=sub.name())
    return STYLE.substitute(
        win=win.name(), base=base.name(), text=text.name(), sub=sub.name(), warn=C["warn"],
        side=_mix(win, black, .28 if dark else .05).name(), border=_mix(win, text, .28).name(),
        cardb=_mix(win, text, .16).name(), acc=col(QPalette.Highlight).name(),
        acct=col(QPalette.HighlightedText).name(), btn=(_mix(win, text, .08) if dark else base).name(),
        disb=_mix(win, text, .14).name(), disf=_mix(text, win, .55).name())


def apply_theme(app=None):
    """Follow the distro's light/dark theme (or the user's override in Settings)."""
    app = app or QApplication.instance()
    sysp = THEME["sys"]
    dark = want_dark(app)
    if dark == _is_dark(sysp):
        pal = sysp
    else:
        pal = dark_palette() if dark else app.style().standardPalette()
    THEME["busy"] = True
    try:
        if pal is sysp:
            if THEME["forced"]:
                app.setPalette(sysp)
                THEME["forced"] = False
        else:
            app.setPalette(pal)
            THEME["forced"] = True
        app.setStyleSheet(build_style(pal))
    finally:
        THEME["busy"] = False
    if THEME["win"]:
        THEME["win"].refresh_view()


class SCApp(QApplication):
    def event(self, e):
        r = super().event(e)
        if e.type() == QEvent.ApplicationPaletteChange and not THEME["busy"] and THEME["sys"] is not None:
            QTimer.singleShot(0, self.system_changed)   # the desktop changed its palette while we run
        return r

    def system_changed(self):
        if not THEME["forced"]:
            THEME["sys"] = self.palette()
        apply_theme(self)


def btn(text, slot, name=None):
    b = QPushButton(T(text))
    b.clicked.connect(slot)
    if name:
        b.setObjectName(name)
    return b


class Card(QFrame):
    clicked = Signal(object)

    def __init__(self, app, installed):
        super().__init__()
        self.app = app
        self.setObjectName("card")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(92)
        lay = QHBoxLayout(self)
        ic = QLabel()
        ic.setPixmap(get_icon(app).pixmap(48, 48))
        ic.setFixedSize(52, 52)
        fp = app["src"] == "flatpak"
        tag = f' <span style="color:{C["dim"]};font-size:11px">Flatpak</span>' if fp else ""
        if fp and not app.get("verified"):
            tag += f' <span style="color:{C["warn"]}">⚠</span>'
        ok = f' <span style="color:{C["ok"]}">✔</span>' if installed else ""
        name = QLabel(f"<b>{escape(app['name'])}</b>{tag}{ok}")
        s = app["summary"]
        sub = QLabel(escape(s[:85] + ("…" if len(s) > 85 else "")))
        sub.setObjectName("sub")
        sub.setWordWrap(True)
        col = QVBoxLayout()
        col.addWidget(name)
        col.addWidget(sub)
        col.addStretch()
        lay.addWidget(ic, 0, Qt.AlignTop)
        lay.addLayout(col, 1)

    def mousePressEvent(self, e):
        self.clicked.emit(self.app)


class SettingsDlg(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(T("Settings"))
        self.resize(680, 560)
        self.lang_changed = self.repos_changed = False
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        lay.addWidget(tabs)
        lay.addWidget(btn("Close", self.accept), 0, Qt.AlignRight)

        g = QWidget()
        gl = QVBoxLayout(g)
        gl.addWidget(QLabel(T("Language")))
        self.lang = QComboBox()
        self.lang.addItem("English", "en")
        self.lang.addItem("Bahasa Indonesia", "id")
        self.lang.setCurrentIndex(self.lang.findData(S["lang"]))
        self.lang.currentIndexChanged.connect(self.set_lang)
        gl.addWidget(self.lang)
        note = QLabel(T("The app restarts to apply the language."))
        note.setObjectName("sub")
        gl.addWidget(note)
        gl.addWidget(QLabel(T("Theme")))
        self.theme = QComboBox()
        for label, val in (("Follow system", "auto"), ("Light", "light"), ("Dark", "dark")):
            self.theme.addItem(T(label), val)
        self.theme.setCurrentIndex(max(0, self.theme.findData(S.get("theme", "auto"))))
        self.theme.currentIndexChanged.connect(self.set_theme)
        gl.addWidget(self.theme)
        for key, label in (("show_repo", T("Show {name} repository apps", name=DISTRO)),
                           ("show_flatpak", T("Show Flatpak apps")),
                           ("unverified", T("Show unverified Flatpak apps"))):
            if key == "show_repo" and PM.key == "none":
                continue
            cb = QCheckBox(label)
            cb.setChecked(S[key])
            cb.toggled.connect(lambda v, k=key: self.set(k, v))
            gl.addWidget(cb)
        gl.addStretch()
        tabs.addTab(g, T("General"))

        r = QWidget()
        rl = QVBoxLayout(r)
        rl.addWidget(QLabel(T("Flatpak repositories (tick = enabled)")))
        self.fl = QListWidget()
        self.fl.itemChanged.connect(self.remote_toggled)
        rl.addWidget(self.fl)
        row = QHBoxLayout()
        self.fn = QLineEdit(placeholderText=T("Repository name"))
        self.fu = QLineEdit(placeholderText=T("Repository URL (.flatpakrepo)"))
        row.addWidget(self.fn, 1)
        row.addWidget(self.fu, 2)
        rl.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(btn("Add Flatpak repository", self.add_remote, "primary"))
        row.addWidget(btn("Remove selected", self.del_remote))
        row.addStretch()
        rl.addLayout(row)
        self.al = None
        if PM.key != "none":
            rl.addWidget(QLabel(T("{name} repositories", name=DISTRO)))
            self.al = QListWidget()
            rl.addWidget(self.al)
            if PM.editable:
                row = QHBoxLayout()
                self.an = QLineEdit(placeholderText=T("Repository name"))
                self.ad = QLineEdit(placeholderText=T(PM.repo_hint))
                row.addWidget(self.an, 1)
                row.addWidget(self.ad, 3)
                rl.addLayout(row)
                row = QHBoxLayout()
                row.addWidget(btn("Add repository", self.add_sys, "primary"))
                row.addWidget(btn("Remove selected", self.del_sys))
                row.addStretch()
                rl.addLayout(row)
                w = QLabel(T("Warning: add repositories only from sources you trust, and install their signing key."))
                w.setObjectName("warn")
            else:
                w = QLabel(T("Editing this list is not supported here; edit {file} manually.", file=PM.repo_file))
                w.setObjectName("sub")
            w.setWordWrap(True)
            rl.addWidget(w)
        tabs.addTab(r, T("Repositories"))

        ab = QWidget()
        al = QVBoxLayout(ab)
        logo = QLabel()
        logo.setPixmap(QIcon.fromTheme("system-software-install", QIcon.fromTheme("applications-system")).pixmap(72, 72))
        al.addWidget(logo, 0, Qt.AlignHCenter)
        info = QGridLayout()
        info.setHorizontalSpacing(16)
        info.setVerticalSpacing(10)
        for i, (k, v) in enumerate(((T("App Name"), APP_NAME), (T("Version"), VERSION),
                                    (T("Developer"), DEVELOPER), (T("Maintainer"), MAINTAINER))):
            kl = QLabel(f"<b>{k}</b>")
            vl = QLabel(v)
            vl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            info.addWidget(kl, i, 0, Qt.AlignTop)
            info.addWidget(QLabel(":"), i, 1, Qt.AlignTop)
            info.addWidget(vl, i, 2)
        info.setColumnStretch(2, 1)
        al.addLayout(info)
        al.addStretch()
        tabs.addTab(ab, T("About"))
        self.fill_remotes()
        self.fill_sys()

    def set(self, k, v):
        S[k] = v
        save_cfg(S)

    def set_theme(self):
        self.set("theme", self.theme.currentData())
        apply_theme()

    def set_lang(self):
        self.set("lang", self.lang.currentData())
        self.lang_changed = True

    def sh(self, cmd):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            QMessageBox.warning(self, T("Settings"), (r.stderr or r.stdout or str(r.returncode)).strip()[:500])
            return False
        return True

    @staticmethod
    def scoped(scope, cmd):
        return cmd if scope == "user" else ["pkexec"] + cmd

    def fill_remotes(self):
        self.fl.blockSignals(True)
        self.fl.clear()
        for r in flatpak_remotes():
            it = QListWidgetItem(f"{r['name']} — {r['url']}  [{r['scope']}]")
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked if r["disabled"] else Qt.Checked)
            it.setData(Qt.UserRole, r)
            self.fl.addItem(it)
        self.fl.blockSignals(False)

    def remote_toggled(self, it):
        r = it.data(Qt.UserRole)
        en = it.checkState() == Qt.Checked
        self.sh(self.scoped(r["scope"], ["flatpak", "remote-modify", "--enable" if en else "--disable",
                                          f"--{r['scope']}", r["name"]]))
        self.repos_changed = True

    def add_remote(self):
        n, u = self.fn.text().strip(), self.fu.text().strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", n) or not u.startswith(("http://", "https://", "file://")):
            return QMessageBox.warning(self, T("Settings"), T("Invalid name or URL/line."))
        if self.sh(["flatpak", "remote-add", "--user", "--if-not-exists", n, u]):
            self.repos_changed = True
            self.fill_remotes()
            QMessageBox.information(self, T("Settings"), T("Added. Press “Update lists” to refresh the catalog."))

    def del_remote(self):
        it = self.fl.currentItem()
        if it:
            r = it.data(Qt.UserRole)
            if self.sh(self.scoped(r["scope"], ["flatpak", "remote-delete", "--force", f"--{r['scope']}", r["name"]])):
                self.repos_changed = True
                self.fill_remotes()

    def fill_sys(self):
        if self.al is None:
            return
        self.al.clear()
        for text, f in PM.repos():
            it = QListWidgetItem(text)
            it.setData(Qt.UserRole, f)
            self.al.addItem(it)

    def add_sys(self):
        n, spec = self.an.text().strip(), self.ad.text().strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]+", n) or not PM.repo_ok(spec):
            return QMessageBox.warning(self, T("Settings"), T("Invalid name or URL/line."))
        if self.sh(PM.repo_add(n, spec)):
            self.repos_changed = True
            self.fill_sys()
            QMessageBox.information(self, T("Settings"), T("Added. Press “Update lists” to refresh the catalog."))

    def del_sys(self):
        it = self.al.currentItem()
        if not it:
            return
        f = it.data(Qt.UserRole)
        if not os.path.basename(f).startswith("software-center-"):
            return QMessageBox.information(self, T("Settings"), T("Only repositories added by Software Center can be removed."))
        if self.sh(PM.repo_del(f)):
            self.repos_changed = True
            self.fill_sys()


class Win(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1050, 680)
        self.apps, self.index, self.inst_sys, self.inst_fp, self.off = [], {}, set(), {}, set()
        self.cur, self.cards, self.cols, self.reload_after, self.m_scopes = None, [], 0, False, set()
        self.alt_idx, self.group, self.jobs, self.mjob_id = defaultdict(list), [], set(), 0
        self.results, self.rtitle, self.page = [], "", 0
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyRead.connect(self.on_out)
        self.proc.finished.connect(self.on_done)

        root = QWidget()
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self.side = QListWidget()
        self.side.setObjectName("side")
        self.side.setFixedWidth(210)
        items = [("All apps", "view-grid")]
        items += [(n, ic) for n, (ic, _) in CATS.items()] + [("Manage", "preferences-system")]
        for key, icon in items:
            it = QListWidgetItem(QIcon.fromTheme(icon), T(key))
            it.setData(Qt.UserRole, key)
            self.side.addItem(it)
        self.side.currentRowChanged.connect(self.on_cat)
        # currentRowChanged already handles a changed row; itemClicked only matters when the same row
        # is clicked again from the detail page (otherwise the handler would run twice)
        self.side.itemClicked.connect(lambda it: self.stack.currentIndex() == 1 and self.on_cat(self.side.row(it)))
        h.addWidget(self.side)

        right = QWidget()
        right.setObjectName("page")
        rv = QVBoxLayout(right)
        top = QHBoxLayout()
        self.search = QLineEdit(placeholderText=T("Search apps…"))
        self.timer = QTimer(singleShot=True)
        self.timer.timeout.connect(self.on_search)
        self.search.textChanged.connect(lambda: self.timer.start(350))
        top.addWidget(self.search, 1)
        top.addWidget(btn("⟳ Update lists", self.refresh_lists))
        top.addWidget(btn("⚙ Settings", self.open_settings))
        rv.addLayout(top)
        self.stack = QStackedWidget()
        rv.addWidget(self.stack, 1)
        h.addWidget(right, 1)

        # page 0: grid
        pg = QWidget()
        pv = QVBoxLayout(pg)
        pv.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel("")
        self.title.setObjectName("title")
        pv.addWidget(self.title)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        box = QWidget()
        self.grid = QGridLayout(box)
        self.grid.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(box)
        pv.addWidget(self.scroll)
        self.pager = QWidget()
        pr = QHBoxLayout(self.pager)
        pr.setContentsMargins(0, 0, 0, 0)
        self.b_prev = btn("← Previous", lambda: self.goto(self.page - 1))
        self.b_next = btn("Next →", lambda: self.goto(self.page + 1))
        self.pg_lbl = QLabel()
        self.pg_lbl.setAlignment(Qt.AlignCenter)
        self.pg_lbl.setMinimumWidth(130)
        for w_ in (None, self.b_prev, self.pg_lbl, self.b_next, None):
            pr.addStretch() if w_ is None else pr.addWidget(w_)
        pv.addWidget(self.pager)
        self.pager.hide()
        self.stack.addWidget(pg)

        # page 1: detail
        dt = QWidget()
        dv = QVBoxLayout(dt)
        dv.addWidget(btn("← Back", lambda: self.stack.setCurrentIndex(0)), 0, Qt.AlignLeft)
        hd = QHBoxLayout()
        self.d_icon = QLabel()
        self.d_icon.setFixedSize(100, 100)
        hd.addWidget(self.d_icon)
        col = QVBoxLayout()
        self.d_name = QLabel()
        self.d_name.setObjectName("title")
        self.d_sum = QLabel()
        self.d_sum.setWordWrap(True)
        self.d_src = QLabel()
        self.d_src.setObjectName("sub")
        self.d_warn = QLabel(T("Unverified developer: this app is not verified by its repository."))
        self.d_warn.setObjectName("warn")
        self.d_warn.setWordWrap(True)
        for w in (self.d_name, self.d_sum, self.d_src, self.d_warn):
            col.addWidget(w)
        self.src_row = QWidget()
        sr = QHBoxLayout(self.src_row)
        sr.setContentsMargins(0, 0, 0, 0)
        sr.addWidget(QLabel(T("Install from:")))
        self.c_src = QComboBox()
        self.c_src.setMinimumWidth(320)
        self.c_src.currentIndexChanged.connect(self.pick_source)
        sr.addWidget(self.c_src)
        sr.addStretch()
        col.addWidget(self.src_row)
        row = QHBoxLayout()
        self.b_inst = btn("Install", lambda: self.act("install"), "primary")
        self.b_rm = btn("Remove", lambda: self.act("remove"), "danger")
        self.b_open = btn("Open", self.open_app)
        for b in (self.b_inst, self.b_open, self.b_rm):
            row.addWidget(b)
        row.addStretch()
        col.addLayout(row)
        hd.addLayout(col, 1)
        dv.addLayout(hd)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(130)
        self.d_desc = QLabel()
        self.d_desc.setWordWrap(True)
        self.d_desc.setAlignment(Qt.AlignTop)
        dv.addWidget(self.bar)
        dv.addWidget(self.log)
        dv.addWidget(self.d_desc, 1)
        self.stack.addWidget(dt)

        # page 2: manage
        mg = QWidget()
        mv = QVBoxLayout(mg)
        mv.setContentsMargins(0, 0, 0, 0)
        self.m_title = QLabel("")
        self.m_title.setObjectName("title")
        mv.addWidget(self.m_title)
        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setHeaderLabels([T("Name"), T("Source"), T("Package"), T("Status")])
        self.tree.setColumnWidth(0, 260)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 220)
        self.tree.currentItemChanged.connect(lambda *_: self.update_desk_btn())
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.manage_menu)
        mv.addWidget(self.tree, 1)
        row = QHBoxLayout()
        row.addWidget(btn("Check for updates", self.manage_refresh))
        row.addWidget(btn("Update all", self.update_all, "primary"))
        row.addWidget(btn("Open", self.manage_open))
        self.b_desk = btn("Add to Desktop", self.manage_shortcut)
        self.b_desk.setEnabled(False)
        row.addWidget(self.b_desk)
        row.addWidget(btn("Remove selected", self.manage_remove, "danger"))
        row.addStretch()
        mv.addLayout(row)
        self.mbar = QProgressBar()
        self.mbar.setRange(0, 0)
        self.mlog = QTextEdit()
        self.mlog.setReadOnly(True)
        self.mlog.setFixedHeight(110)
        mv.addWidget(self.mbar)
        mv.addWidget(self.mlog)
        self.stack.addWidget(mg)

        for w in (self.bar, self.log, self.mbar, self.mlog, self.d_warn, self.src_row):
            w.hide()
        self.side.setCurrentRow(0)
        self.title.setText(T("Loading catalog…"))
        self.load()

    # ---- data
    def load(self):
        self.statusBar().showMessage(T("Loading catalog…"))
        self.loader = Loader()
        self.loader.partial.connect(self.on_partial)
        self.loader.done.connect(self.on_loaded)
        self.loader.start()

    def set_data(self, apps, ia, ifp):
        self.apps, self.inst_sys, self.inst_fp = apps, ia, ifp
        self.index = {(a["src"], a["pkg"]): a for a in apps}
        self.alt_idx = defaultdict(list)
        for a in apps:
            for k in alt_keys(a):
                self.alt_idx[k].append(a)
        self.off = {r["name"] for r in flatpak_remotes() if r["disabled"]}

    def visible(self, a):
        if a["src"] == "sys":
            return S["show_repo"] and PM.key != "none"
        if not S["show_flatpak"] or a.get("remote") in self.off:
            return False
        return S["unverified"] or a.get("verified", False)

    def refresh_view(self):
        if self.stack.currentIndex() in (1, 2):
            return
        if self.search.text().strip():
            self.on_search()
        elif self.side.currentRow() < 0:
            self.side.setCurrentRow(0)
        else:
            self.on_cat(self.side.currentRow())

    def on_partial(self, apps, ia, ifp):
        self.set_data(apps, ia, ifp)
        self.refresh_view()

    def on_loaded(self, apps, ia, ifp):
        self.set_data(apps, ia, ifp)
        self.statusBar().showMessage(T("No package manager found: only Flatpak apps are available.") if PM.key == "none"
                                     else T("{n} apps in catalog. Use search to find any repository package.", n=len(apps)))
        self.refresh_view()

    def is_inst(self, a):
        return a["pkg"] in (self.inst_fp if a["src"] == "flatpak" else self.inst_sys)

    # ---- list
    def on_cat(self, row):
        if row < 0:
            return
        it = self.side.item(row)
        key = it.data(Qt.UserRole)
        if key == "Manage":
            self.stack.setCurrentIndex(2)
            self.manage_refresh()
            return
        self.stack.setCurrentIndex(0)
        if key == "All apps":
            apps = self.apps
        else:
            apps = [a for a in self.apps if a["cat"] == key]
        self.render(apps, it.text())

    def on_search(self):
        q = self.search.text().strip()
        if not q:
            r = self.side.currentRow()
            self.side.setCurrentRow(0) if r < 0 else self.on_cat(r)
            return
        ql = q.lower()
        res = {(a["src"], a["pkg"]): a for a in self.apps
               if ql in a["name"].lower() or ql in a["summary"].lower() or ql in a["pkg"].lower()}
        for pkg, s in PM.search(q):
            k = ("sys", pkg)
            if k not in res:
                res[k] = self.index.get(k) or dict(src="sys", pkg=pkg, name=pkg, summary=s, desc="",
                                                   cat="Utilities", icon=None, verified=True)
        self.side.setCurrentRow(-1)
        self.stack.setCurrentIndex(0)
        self.render(sorted(res.values(), key=lambda a: (not a["name"].lower().startswith(ql), a["name"].lower())),
                    T("Results for “{q}”", q=q), sort=False)

    PAGE = 150  # cards per page

    def render(self, apps, title, sort=True):
        apps = [a for a in apps if self.visible(a)]
        if sort:
            apps = sorted(apps, key=lambda a: a["name"].lower())
        self.results, self.rtitle, self.page = apps, title, 0
        self.show_page()

    def goto(self, page):
        pages = max(1, -(-len(self.results) // self.PAGE))
        self.page = min(max(page, 0), pages - 1)
        self.show_page()

    def show_page(self):
        n, P = len(self.results), self.PAGE
        pages = max(1, -(-n // P))
        start, end = self.page * P, min(n, (self.page + 1) * P)
        self.title.setText(T("{title}  ({a}–{b} of {m})", title=self.rtitle, a=start + 1, b=end, m=n)
                           if n > P else self.rtitle)
        self.pager.setVisible(n > P)
        self.pg_lbl.setText(T("Page {p} / {n}", p=self.page + 1, n=pages))
        self.b_prev.setEnabled(self.page > 0)
        self.b_next.setEnabled(self.page < pages - 1)
        for c in self.cards:
            c.setParent(None)
            c.deleteLater()
        self.cards = []
        for a in self.results[start:end]:
            c = Card(a, self.is_inst(a))
            c.clicked.connect(self.open_detail)
            self.cards.append(c)
        self.cols = 0
        self.relayout()
        bar = self.scroll.verticalScrollBar()
        bar.setValue(0)
        QTimer.singleShot(0, lambda: bar.setValue(0))

    def relayout(self):
        cols = max(1, (self.scroll.viewport().width() - 20) // 300)
        if cols == self.cols:
            return
        for i in range(max(cols, self.cols)):
            self.grid.setColumnStretch(i, 1 if i < cols else 0)
        self.cols = cols
        for i, c in enumerate(self.cards):
            self.grid.removeWidget(c)
            self.grid.addWidget(c, i // cols, i % cols)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.relayout()

    # ---- detail
    def alternatives(self, a):
        seen, out = {id(a)}, []
        for k in alt_keys(a):
            for b in self.alt_idx.get(k, ()):
                if id(b) not in seen and b["src"] != a["src"] and self.visible(b):
                    seen.add(id(b))
                    out.append(b)
        return out

    def open_detail(self, a):
        # all versions of this app (APT first, then Flatpak), so the user can choose where to install from
        self.group = sorted([a] + self.alternatives(a), key=lambda x: (x["src"] != "sys", x.get("remote") or ""))
        self.c_src.blockSignals(True)
        self.c_src.clear()
        for x in self.group:
            label = (repo_label() if x["src"] == "sys" else f"Flatpak · {x.get('remote') or 'flathub'}") \
                + f" ({x['pkg']})" + (f"  ✔ {T('installed')}" if self.is_inst(x) else "")
            self.c_src.addItem(label)
        self.c_src.setCurrentIndex(self.group.index(a))
        self.c_src.blockSignals(False)
        self.src_row.setVisible(len(self.group) > 1)
        self.log.clear()
        self.log.hide()
        self.bar.hide()
        self.show_app(a)
        self.stack.setCurrentIndex(1)

    def pick_source(self, i):
        if 0 <= i < len(self.group) and self.proc.state() == QProcess.NotRunning:
            self.show_app(self.group[i])

    def show_app(self, a):
        self.cur = a
        if not a["desc"] and a["src"] == "sys":
            s, d = PM.describe(a["pkg"])
            a["summary"], a["desc"] = a["summary"] or s, d
        fp = a["src"] == "flatpak"
        self.d_icon.setPixmap(get_icon(a).pixmap(96, 96))
        self.d_name.setText(a["name"])
        self.d_sum.setText(a["summary"])
        self.d_desc.setText(a["desc"] or ("" if a["summary"] else T("No description.")))
        self.d_src.setText((f"Flatpak · {a.get('remote') or 'flathub'}" if fp else repo_label()) + f" · {a['pkg']}")
        self.d_warn.setVisible(fp and not a.get("verified"))
        self.refresh_buttons()

    def refresh_buttons(self, busy=False):
        inst = self.is_inst(self.cur)
        self.b_inst.setVisible(not inst)
        self.b_rm.setVisible(inst)
        self.b_open.setVisible(inst)
        for b in (self.b_inst, self.b_rm, self.b_open):
            b.setEnabled(not busy)

    def fp_cmd(self, a, kind):
        rem = a.get("remote") or "flathub"
        if kind == "install":
            if rem == "flathub" or a.get("scope") == "user":
                pre = f"flatpak remote-add --user --if-not-exists flathub {FLATHUB}; " if rem == "flathub" else ""
                return ["sh", "-c", pre + f'flatpak install --user -y --noninteractive {shlex.quote(rem)} "$0"', a["pkg"]]
            return ["pkexec", "flatpak", "install", "--system", "-y", "--noninteractive", rem, a["pkg"]]
        sc = self.inst_fp.get(a["pkg"], "user")
        return (["flatpak", "uninstall", "--user"] if sc == "user" else ["pkexec", "flatpak", "uninstall", "--system"]) \
            + ["-y", "--noninteractive", a["pkg"]]

    def act(self, kind):
        a = self.cur
        if a["src"] == "flatpak":
            cmd = self.fp_cmd(a, kind)
        else:
            cmd = PM.install(a["pkg"]) if kind == "install" else PM.remove(a["pkg"])
            if not cmd:
                return self.statusBar().showMessage(T("No supported package manager on this system."))
        self.start(cmd)

    def start(self, cmd):
        for w in (self.log, self.bar, self.mlog, self.mbar):
            w.show()
        self.on_out(("$ " + " ".join(cmd)).encode())
        if self.cur:
            self.refresh_buttons(busy=True)
        self.proc.start(cmd[0], cmd[1:])

    def on_out(self, data=None):
        s = (data if data is not None else bytes(self.proc.readAll())).decode(errors="ignore").rstrip()
        for w in (self.log, self.mlog):
            w.append(s)

    def on_done(self, code, _):
        for w in (self.bar, self.mbar):
            w.hide()
        self.on_out((T("Done") if code == 0 else T("Failed (code {c})", c=code)).encode())
        self.statusBar().showMessage(T("Done") if code == 0 else T("Failed, see the log"))
        self.inst_sys, self.inst_fp = PM.installed(), fp_installed()
        if self.cur:
            self.refresh_buttons()
            for i, x in enumerate(self.group):
                base = self.c_src.itemText(i).split("  ✔")[0]
                self.c_src.setItemText(i, base + (f"  ✔ {T('installed')}" if self.is_inst(x) else ""))
        if self.reload_after:
            self.reload_after = False
            self.load()
        if self.stack.currentIndex() == 2:
            self.manage_refresh()

    def open_app(self):
        if not launch(self.cur):
            self.statusBar().showMessage(T("This package has no launcher."))

    def refresh_lists(self):
        self.reload_after = True
        self.statusBar().showMessage(T("Updating package lists…"))
        steps = [PM.refresh(), f"flatpak remote-add --user --if-not-exists flathub {FLATHUB}",
                 "flatpak update --user --appstream", "pkexec flatpak update --system --appstream"]
        self.start(["sh", "-c", "; ".join(x for x in steps if x)])

    # ---- manage
    def manage_refresh(self):
        self.m_title.setText(T("Checking updates…"))
        self.mjob_id += 1
        jid = self.mjob_id
        job = Job(lambda: (PM.gui_installed(), fp_gui_installed(), PM.updates(), fp_updates()))
        self.jobs.add(job)  # keep a reference until the thread has finished
        job.done.connect(lambda r, j=jid: self.manage_fill(r, j))
        job.finished.connect(lambda j=job: (self.jobs.discard(j), j.deleteLater()))
        job.start()

    def manage_fill(self, r, jid=None):
        if jid is not None and jid != self.mjob_id:
            return  # a newer refresh is running; ignore stale results
        if r is None:
            self.m_title.setText(T("Failed, see the log"))
            return
        apt, fp, ua, uf = r
        self.tree.clear()
        for a in sorted(list(apt.values()) + list(fp.values()), key=lambda a: a["name"].lower()):
            up = a["pkg"] in (uf if a["src"] == "flatpak" else ua)
            it = QTreeWidgetItem([a["name"], "Flatpak" if a["src"] == "flatpak" else PM.short, a["pkg"],
                                  T("Update available") if up else ""])
            it.setIcon(0, get_icon(a))
            it.setData(0, Qt.UserRole, a)
            self.tree.addTopLevelItem(it)
        self.m_scopes = {a["scope"] for a in fp.values()}
        n = len(ua) + len(uf)
        self.m_title.setText(T("{n} updates available", n=n) if n else T("Everything is up to date."))
        self.update_desk_btn()

    def sel_app(self):
        it = self.tree.currentItem()
        return it.data(0, Qt.UserRole) if it else None

    def update_desk_btn(self):
        a = self.sel_app()
        self.b_desk.setEnabled(bool(a and a.get("desktop")))
        self.b_desk.setText(T("Remove from Desktop") if a and has_shortcut(a) else T("Add to Desktop"))

    def manage_shortcut(self):
        a = self.sel_app()
        if not a:
            return
        if has_shortcut(a):
            msg = T("Shortcut removed from the Desktop.") if remove_shortcut(a) else ""
        else:
            ok, info = add_shortcut(a)
            msg = T("Shortcut added to the Desktop: {path}", path=info) if ok else \
                {"nolauncher": T("This package has no launcher."),
                 "exists": T("A different file with this name already exists on the Desktop.")}.get(info, info)
        self.statusBar().showMessage(msg)
        self.update_desk_btn()

    def manage_menu(self, pos):
        if not self.tree.itemAt(pos):
            return
        self.tree.setCurrentItem(self.tree.itemAt(pos))
        m = QMenu(self)
        m.addAction(T("Open"), self.manage_open)
        m.addAction(self.b_desk.text(), self.manage_shortcut).setEnabled(self.b_desk.isEnabled())
        m.addSeparator()
        m.addAction(T("Remove"), self.manage_remove)
        m.exec(self.tree.viewport().mapToGlobal(pos))

    def manage_open(self):
        a = self.sel_app()
        if a and not launch(a):
            self.statusBar().showMessage(T("This package has no launcher."))

    def manage_remove(self):
        a = self.sel_app()
        if a and QMessageBox.question(self, APP_NAME, T("Remove {name}?", name=a["name"])) == QMessageBox.Yes:
            self.cur = a
            self.act("remove")

    def update_all(self):
        parts = [PM.upgrade(), "flatpak update --user -y --noninteractive"] if PM.upgrade() else \
            ["flatpak update --user -y --noninteractive"]
        if "system" in self.m_scopes:
            parts.append("pkexec flatpak update --system -y --noninteractive")
        self.cur = None
        self.start(["sh", "-c", "; ".join(parts)])

    def closeEvent(self, e):
        for t in [getattr(self, "loader", None), *list(self.jobs)]:  # avoid "QThread: Destroyed while thread is still running"
            try:
                if t is not None:
                    t.wait(3000)
            except RuntimeError:
                pass
        super().closeEvent(e)

    def open_settings(self):
        d = SettingsDlg(self)
        d.exec()
        if d.lang_changed:
            os.execv(sys.executable, [sys.executable] + sys.argv)  # restart to apply the language
        if d.repos_changed:
            self.refresh_lists()
        else:
            self.set_data(self.apps, self.inst_sys, self.inst_fp)
            self.refresh_view()


if __name__ == "__main__":
    if not os.path.exists(CFG):
        save_cfg(S)
    app = SCApp(sys.argv)
    app.setApplicationName(APP_NAME)
    if QIcon.themeName() in ("", "hicolor"):
        for t in ("Papirus", "Adwaita", "gnome"):
            if os.path.isdir(f"/usr/share/icons/{t}"):
                QIcon.setThemeName(t)
                break
    THEME["sys"] = app.palette()
    apply_theme(app)
    try:
        app.styleHints().colorSchemeChanged.connect(lambda *_: apply_theme(app))  # live light/dark switch
    except AttributeError:
        pass
    w = Win()
    THEME["win"] = w
    w.show()
    sys.exit(app.exec())
