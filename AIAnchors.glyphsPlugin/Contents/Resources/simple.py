# encoding: utf-8
"""Måns Tools — simple versions: what the four simple plugins share (AI Kerning, AI Spacing, AI Anchors, AI Variable Font).
A simple plugin works on A–Z a–z of the current master only, has no settings, is for non-commercial use, and does its work on
the Måns Tools server: the font data (outlines, widths) goes there together with the hash of this copy of Glyphs, nothing
runs locally. No licence, no key: "Buy full version" opens the shop page. No application logo on any dialog:
every message is written into the plugin's own window. Plain AppKit + vanilla, nothing else needed."""
from __future__ import division, print_function, unicode_literals
import hashlib, json, os, ssl, subprocess, tempfile, time, traceback

SERVER = "https://aringtypeface.com/mans-tools/api"
BUY_URL = "https://aringtypeface.com/mans-tools/"
PREF_SERVER = "com.mansgreback.MansTools.server"
PREF_KEY = "com.mansgreback.MansTools.key"                  # one key for all Måns AI Tools plugins (the full plugins use the same)            # defaults write com.GeorgSeifert.Glyphs4 com.mansgreback.MansTools.server http://127.0.0.1:5720/api
BRAND = "Måns AI Tools"
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
CAUTION = ("Save a copy of your work first. Font data is sent to the aringtypeface.com server; see Privacy and Terms in the manual.")
LOG = os.path.join(tempfile.gettempdir(), "MansToolsSimple.log")


def log(*a):
	try:
		with open(LOG, "a") as f:
			f.write(time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a) + "\n")
	except Exception:
		pass


def server():
	try:
		from Foundation import NSUserDefaults
		return str(NSUserDefaults.standardUserDefaults().stringForKey_(PREF_SERVER) or "").strip() or SERVER
	except Exception:
		return SERVER


def key():
	try:
		from Foundation import NSUserDefaults
		return str(NSUserDefaults.standardUserDefaults().stringForKey_(PREF_KEY) or "").strip()
	except Exception:
		return ""


def set_key(k):
	from Foundation import NSUserDefaults
	NSUserDefaults.standardUserDefaults().setObject_forKey_(str(k).strip(), PREF_KEY)


TIER = {"tier": "free", "msg": "", "code": ""}


def check_tier(tool="anchors", move=False):
	"""Ask the server what the stored key is worth (no run counted). -> "full" | "free"; TIER holds the answer, a message and the
	server's code ("tied" = the licence is active on another computer; a second call with move=True moves it here for good)."""
	k = key(); TIER["code"] = ""
	if not k:
		TIER.update(tier="free", msg="")
		try: TIER["latest"] = str(call(dict(tool=tool, action="status"), 10)[1].get("latest") or "")   # only for the update notice
		except Exception: pass
		return "free"
	st, b = call(dict(tool=tool, action="status", key=k, install=identity(), move=bool(move)), 30)
	TIER["code"] = str(b.get("code") or ""); TIER["latest"] = str(b.get("latest") or "")
	if st == 200 and b.get("tier") == "full": TIER.update(tier="full", msg="", kind=str(b.get("kind") or "pro"), days=b.get("days_left"))
	elif st == 0: TIER.update(tier="free", msg=b.get("error") or "The server could not be reached.")
	elif TIER["code"] == "expired": TIER.update(tier="free", msg="This demo license has expired. Running as the free version.")
	elif TIER["code"] == "tied": TIER.update(tier="free", msg="This license is active on another computer. Click Move here to use it on this computer instead. The other computer will be deactivated permanently and it will not be possible to reactivate it on that machine.")
	else: TIER.update(tier="free", msg=(b.get("error") or "The license is not valid.") + " Running as the free version.")
	return TIER["tier"]


def version_parts(v=None):
	"""1.1.0 -> (1, 1, 0); None = this plugin's own version (CFBundleShortVersionString of the bundle's Info.plist)."""
	try:
		if v is None:
			import plistlib
			with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Info.plist"), "rb") as f:
				v = plistlib.load(f).get("CFBundleShortVersionString")
		p = [int(x) for x in str(v or "").split(".") if x.strip().isdigit()]
		return tuple((p + [0, 0, 0])[:3]) if p else None
	except Exception:
		return None


def version_text(v=None):
	"""A version as shown in the dialog: 1.0.0 -> v1.000; None = this plugin's own."""
	p = version_parts(v)
	return "v%d.%d%02d" % p if p else ""


def update_text():
	"""-> "Update available: v1.200" when the server names a newer release than this plugin, else "" """
	mine, new = version_parts(), version_parts(TIER.get("latest"))
	return "Update available: %s" % version_text(TIER["latest"]) if mine and new and new > mine else ""


def status_line():
	"""-> (text, the part to show bold or ""): Måns Tools v1.000 · Professional / Student / Demo: expires in 23 days / Free Version,
	then " · Update available: v1.200" (bold) when the server names a newer release"""
	text, bold = license_line(); upd = update_text()
	return (text + " · " + upd, upd) if upd else (text, bold)


def license_line():
	head = ("Måns Tools " + version_text()).strip() + " · "
	if TIER["tier"] != "full": return head + "Free Version", ""
	kind = TIER.get("kind") or "pro"
	if kind == "demo":
		d = TIER.get("days")
		if d is None: return head + "Demo", ""
		d = max(1, int(d)); return head + "Demo: expires in %d day%s" % (d, "" if d == 1 else "s"), str(d)
	return head + ("Student" if kind == "student" else "Professional"), ""


def show_status(box):
	"""The status line in a text box: a message when there is one (license moved elsewhere, server unreachable …), else the
	version and license line, the days of a demo in bold."""
	try:
		from AppKit import NSFont, NSColor, NSMutableAttributedString, NSFontAttributeName, NSForegroundColorAttributeName
		text, bold = (TIER["msg"], "") if TIER.get("msg") else status_line()
		size = NSFont.smallSystemFontSize()
		a = NSMutableAttributedString.alloc().initWithString_attributes_(text, {NSFontAttributeName: NSFont.systemFontOfSize_(size), NSForegroundColorAttributeName: NSColor.secondaryLabelColor()})
		if bold:
			i = text.rfind(bold)
			a.addAttribute_value_range_(NSFontAttributeName, NSFont.boldSystemFontOfSize_(size), (i, len(bold)))
		box.getNSTextField().setAttributedStringValue_(a)
	except Exception:
		try: box.set(TIER.get("msg") or status_line()[0])
		except Exception: pass


def buy_url(title=""):
	"""The Buy link: source, plugin and a hash of this installation (sha256 of Glyphs hash + computer hash, 16 hex; nothing readable),
	so the website can count clicks from Glyphs and match a click with the purchase. The page drops the parameters at once."""
	inst = identity(); base = (inst.get("glyphs_hash") or "") + (inst.get("hw_hash") or "")
	v = hashlib.sha256(base.encode("utf-8")).hexdigest()[:16] if base else ""
	tool = title.lower().replace("ai ", "").strip().replace(" ", "-")
	return BUY_URL + "?src=glyphs&tool=%s&v=%s" % (tool, v)


def check_tier_later():
	"""With a stored key: the tier check on a background thread (data only), so a plugin knows its tier before any dialog is opened."""
	if not key(): return
	import threading
	t = threading.Thread(target=lambda: (check_tier(), None)[1]); t.daemon = True; t.start()


def identity():
	"""The hash of this copy of Glyphs (its licence data) and of this computer; nothing readable leaves the machine."""
	out = dict(glyphs_hash="", hw_hash="", glyphs_major=0, app="")
	try:
		from GlyphsApp import Glyphs
		out["glyphs_major"] = int(Glyphs.versionNumber); out["app"] = "%s (%s)" % (Glyphs.versionNumber, Glyphs.buildNumber)
	except Exception:
		pass
	try:
		from Foundation import NSUserDefaults
		d = NSUserDefaults.standardUserDefaults()
		blob = d.objectForKey_("User3") or d.objectForKey_("User4")   # User4 = Glyphs 4 bought without Glyphs 3 (2026-11-16)
		paddle = d.objectForKey_("Paddle-Glyphs 3-650121-SD")
		if blob: out["glyphs_hash"] = hashlib.sha256(bytes(blob)).hexdigest()
		elif paddle: out["glyphs_hash"] = hashlib.sha256(str(paddle).encode()).hexdigest()
	except Exception:
		pass
	try:
		t = subprocess.run(["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], capture_output=True, text=True, timeout=10).stdout
		u = [l.split('"')[-2] for l in t.splitlines() if "IOPlatformUUID" in l]
		if u: out["hw_hash"] = hashlib.sha256(("manstools:" + u[0]).encode()).hexdigest()
	except Exception:
		pass
	return out


def tls():
	"""An HTTPS context that trusts the usual roots. Glyphs 3's Python ships without them (CERTIFICATE_VERIFY_FAILED), so
	fall back to certifi or the macOS bundle when the default paths hold no certificates."""
	ctx = ssl.create_default_context()
	if ctx.cert_store_stats().get("x509_ca"): return ctx
	for f in (lambda: __import__("certifi").where(), lambda: "/etc/ssl/cert.pem"):
		try:
			cafile = f()
			if cafile and os.path.exists(cafile): return ssl.create_default_context(cafile=cafile)
		except Exception: pass
	return ctx


def call(body, timeout=900):
	"""-> (status, dict). status 0 = the server could not be reached."""
	from urllib.request import Request, urlopen
	from urllib.error import HTTPError, URLError
	url = server()
	req = Request(url, data=json.dumps(body, separators=(",", ":")).encode("utf-8"), headers={"Content-Type": "application/json", "User-Agent": "MansToolsSimple/1.0"}, method="POST")
	try:
		with urlopen(req, context=tls() if url.startswith("https") else None, timeout=timeout) as r:
			return r.status, json.loads(r.read().decode("utf-8"))
	except HTTPError as e:
		try: return e.code, json.loads(e.read().decode("utf-8"))
		except Exception: return e.code, dict(error="The server answered %s." % e.code, code="http")
	except (URLError, OSError, ValueError) as e:
		return 0, dict(error="The server could not be reached (%s). Internet access is required." % getattr(e, "reason", e), code="offline")


def run(tool, data, timeout=900):
	"""One run on the server: no key, simple=True (the server works on A–Z a–z only and says so). -> result dict; raises with the server's message.
	The run goes on in the background on the server (the host's gateway cuts any request after about a minute): the server
	answers at once with a job number, and the plugin asks for the answer every few seconds until it is there."""
	k = key() if TIER["tier"] == "full" else ""                      # a valid key: the full version (every glyph, no limit); else the simple run
	ident = identity()
	st, b = call(dict(tool=tool, action="run", key=k, simple=not k, install=ident, data=data, background=True), timeout)
	log("server", tool, st, b.get("code"), b.get("tier"), b.get("error"), b.get("job"))
	if st == 202 and b.get("job"):
		st, b = wait_job(tool, b["job"], k, ident)
		log("server", tool, "job", st, b.get("code"), b.get("error"))
	if st != 200:
		raise RuntimeError(b.get("error") or "The server answered %s." % st)
	return b


def wait_job(tool, job, k, ident, most=1500):
	"""Asks the server for a background job until it is done (the dialog's spinner keeps turning meanwhile). -> (status, body).
	A few failed asks in a row (a dropped connection, a busy host) are retried."""
	t0 = time.time(); pause = 1.0; misses = 0
	while True:
		time.sleep(pause); pause = min(pause + 0.5, 3.0)
		st, b = call(dict(tool=tool, action="job", job=job, key=k, install=ident), 30)
		if st == 202:
			misses = 0
		elif st in (0, 429, 500, 502, 503, 504) and b.get("code") not in ("died", "server", "input"):
			misses += 1
			if misses > 10: return st, b
		else:
			return st, b
		if time.time() - t0 > most:
			return 504, dict(error="The server did not finish the run in time.")


def stamp(font, what, title, answer):
	"""Into the font's note AND its Description (name ID 10, exported with OTF/TTF):
	'<What> by Måns Grebäck's <Plugin> plugin, generation ID: <job>' (one line per run)."""
	line = "%s by Måns Grebäck's %s plugin, generation ID: %s" % (what, title, answer.get("job") or "-")
	for field in ("note", "description"):
		try:
			old = str(getattr(font, field) or "")
			setattr(font, field, (old + "\n" + line) if old else line)
		except Exception:
			log(field + " not written", traceback.format_exc())
	return line


def is_letter(glyph):
	"""One of A–Z a–z: named as the letter and encoded as it (the server checks the same)."""
	try:
		n = str(glyph.name); u = glyph.unicode
		return len(n) == 1 and n in LETTERS and bool(u) and int(u, 16) == ord(n)
	except Exception:
		return False


def letters(font):
	return [g for g in font.glyphs if is_letter(g)]


CALL = {}                                                                # the call in progress from a script / the Glyphs MCP server (register())
API = {}


def register(name, fn, options, extra=()):
	"""Makes a plugin's run callable from scripts and the Glyphs MCP server, on any thread, nothing opened or shown:
	    import MansAITools
	    MansAITools.kern(font=Glyphs.fonts[0], glyphs=["A", "V"], strength="80")
	Keyword arguments = the dialog's options by key, values as the dialog has them (True/False, the label of a choice, text);
	left out = the dialog's default. font = any open font (default the front one), master = a master or its name (default
	the selected one), glyphs = glyph names to work on instead of the selection. Returns (message, names of the adjusted glyphs).
	The free version works on A–Z a–z with the defaults, as in the dialog. MansAITools.API lists the tools."""
	defaults = dict((k, d[1] if isinstance(d, tuple) else d) for _, k, _, d in options)
	choices = dict((k, d[0]) for kind, k, _, d in options if kind in ("popup", "radio"))

	def call(font=None, master=None, glyphs=None, **opts):
		kw = dict((k, opts.pop(k)) for k in list(opts) if k in extra)
		bad = sorted(set(opts) - set(defaults))
		if bad: raise TypeError("%s: unknown option %s. Options: %s" % (name, ", ".join(bad), ", ".join(sorted(defaults) + list(extra))))
		o = dict(defaults); o.update(opts)
		if glyphs is not None:
			glyphs = [str(n) for n in ([glyphs] if isinstance(glyphs, str) else glyphs)]
			if "scope" in o and o["scope"] == defaults["scope"]: o["scope"] = choices["scope"][1]   # glyphs given and no selection mode chosen: the tool's first selection mode
		CALL.clear(); CALL.update(font=font, master=master, glyphs=glyphs)
		try:
			if TIER["tier"] != "full" and key(): check_tier(name)                 # a script may run before the plugin's own check came back
			if kw:
				f = font or Glyphs_font()
				if glyphs is None: raise ValueError("%s: give glyphs=[…] with %s." % (name, ", ".join(sorted(kw))))
				return result_parts(fn(o, targets=[f.glyphs[n] for n in glyphs if f.glyphs[n] is not None], **kw))
			return result_parts(fn(o))
		finally:
			CALL.clear()
	call.__name__ = str(name); call.__doc__ = "%s(font=None, master=None, glyphs=None, %s)\n\n%s" % (
		name, ", ".join("%s=%r" % kv for kv in sorted(defaults.items())) + "".join(", %s=…" % k for k in extra), register.__doc__)
	API[name] = call; globals()[name] = call
	return call


def Glyphs_font():
	from GlyphsApp import Glyphs
	return Glyphs.font


def target():
	"""-> (font, master) of the run: the script's choice, else the front font and its selected master."""
	font = CALL.get("font") or Glyphs_font()
	if font is None: raise RuntimeError("Open a font first.")
	m = CALL.get("master")
	if isinstance(m, str):
		m = next((x for x in font.masters if str(x.name) == m), None)
		if m is None: raise ValueError("No master called %r." % CALL.get("master"))
	return font, m or font.selectedFontMaster or font.masters[0]


def on_main_thread():
	try:
		from Foundation import NSThread
		return bool(NSThread.isMainThread())
	except Exception:
		return True


import sys as _sys, types as _types
_sys.modules.setdefault("MansAITools", _sys.modules[__name__])
_OPEN = _sys.modules.setdefault("_mans_ai_tools_open", _types.ModuleType("_mans_ai_tools_open"))   # the open dialog, shared by every plugin's copy of this file


def selected_names(font):
	"""The glyphs selected in the font view or the current tab (or the ones a script named)."""
	if CALL.get("glyphs") is not None: return set(CALL["glyphs"])
	try: return set(str(l.parent.name) for l in (font.selectedLayers or []) if l is not None and l.parent is not None)
	except Exception: return set()


def worked(font, master, need_paths=True, components=False):
	"""The glyphs a run works on: A–Z a–z, or every glyph of the font with the full version (a valid key).
	components=True: glyphs made of components count by their decomposed outlines."""
	pool = list(font.glyphs) if TIER["tier"] == "full" else letters(font)
	out = []
	for g in pool:
		L = g.layers[master.id]
		if L is None: continue
		if need_paths and not closed_paths(L, components): continue
		out.append(g)
	return out


def closed_paths(layer, components=False):
	"""The closed outlines of a layer; components=True also those of its components (decomposed, as drawn)."""
	if components:
		try:
			if len(list(layer.components)): layer = layer.copyDecomposedLayer()
		except Exception: pass
	try: paths = list(layer.paths)
	except Exception: paths = [s for s in layer.shapes if hasattr(s, "nodes")]
	return [p for p in paths if p.closed and len(p.nodes) >= 3]


def glyph_json(g, layer, components=False):
	uni = None
	try: uni = int(g.unicode, 16) if g.unicode else None
	except Exception: pass
	d = dict(name=str(g.name), unicode=uni, width=float(layer.width), lsb=float(layer.LSB), rsb=float(layer.RSB),
	         paths=[[[float(n.position.x), float(n.position.y), str(n.type)] for n in p.nodes] for p in closed_paths(layer, components)])
	try: d['comps'] = [str(c.componentName) for c in layer.components]
	except Exception: pass
	try: d.update(cat=str(g.category or ""), sub=str(g.subCategory or ""), case=int(getattr(g, "case", 0) or 0), script=str(g.script or ""), export=bool(g.export), lg=str(g.leftKerningGroup) if g.leftKerningGroup else None, rg=str(g.rightKerningGroup) if g.rightKerningGroup else None)
	except Exception: pass
	return d


def metric(font, master, attr, glyph_names=(), default=0.0):
	"""A master metric, or (missing: Glyphs 3 answers NSNotFound, Glyphs 4 a default) the top of the first of glyph_names that
	has outlines, else default × upm."""
	upm = float(font.upm or 1000)
	try: v = float(getattr(master, attr) or 0)
	except Exception: v = 0.0
	if 0 < abs(v) < 4 * upm and not (attr == "capHeight" and glyph_names and v == 720 and not cap_defined(font)): return v
	for n in glyph_names:
		g = font.glyphs[n]; L = g.layers[master.id] if g is not None else None
		if L is not None and closed_paths(L):
			b = L.bounds; return float(b.origin.y + b.size.height)
	return v if 0 < abs(v) < 4 * upm else default * upm


def cap_defined(font):
	"""Whether the font defines a cap height metric (Glyphs 3 file format: font.metrics, type 2 = cap height)."""
	try: return any(getattr(m, "type", None) == 2 for m in font.metrics)
	except Exception: return True


def font_json(font, master, glyphs, settings=None, components=False):
	"""The font data a simple plugin sends: metrics of the master and the A–Z a–z outlines."""
	return dict(upm=float(font.upm), cap=metric(font, master, "capHeight", ("H", "I", "E"), 0.7), xheight=float(master.xHeight or 0), ascender=float(master.ascender or 0),
	            descender=float(master.descender or 0), italic=float(master.italicAngle or 0), grid=float(font.grid), family=str(font.familyName),
	            glyphs=[glyph_json(g, g.layers[master.id], components) for g in glyphs if g.layers[master.id] is not None], settings=settings or {})


FULL = "One license, bought once, unlocks all Måns AI Tools plugins: AI Kerning, AI Spacing, AI Anchors and AI Variable Font."


def note_color():
	"""Dark amber on the light window (about 5:1 contrast), the system yellow in dark mode."""
	from AppKit import NSColor
	light = NSColor.colorWithSRGBRed_green_blue_alpha_(0.54, 0.35, 0.0, 1.0)
	try:
		from AppKit import NSAppearanceNameAqua, NSAppearanceNameDarkAqua
		dark = NSColor.systemYellowColor()
		return NSColor.colorWithName_dynamicProvider_(None, lambda ap: dark if ap.bestMatchFromAppearancesWithNames_([NSAppearanceNameAqua, NSAppearanceNameDarkAqua]) == NSAppearanceNameDarkAqua else light)
	except Exception:
		return light


class Dialog(object):
	"""The one window of every simple plugin, a stack of rows:
	  title · one-line brief · status line · "Settings ▾" · option rows · button row · "About ▸" "License key"; open About ends with a "More info" link to the buy page.
	Free: Buy full version / Close / action, three equal buttons; the options are shown greyed out and disabled and are never
	read (the free run sends no settings, and the server ignores settings on keyless runs anyway). Full: the options are live,
	Buy is gone, License key stays (Remove key there), Close / action are two equal buttons. "Settings" folds the option rows away (remembered). The callback gets the option values as a dict. Messages go to the status line."""
	W = 440; M = 16; GAP = 24

	def __init__(self, title, brief, action, callback, about="", options=(), prefs="", hooks=None, when=None, check=None, info=None):
		self.info = info                                                     # info(option values) -> a grey line over the buttons (AI Kerning: the most pairs)
		self.title, self.brief, self.action, self.callback, self.options, self.prefs = title, brief, action, callback, list(options), prefs
		self.check = check; self.warned = None                              # check(option values) -> a warning before a long run ("" = none); shown once, the next click runs
		self.when = when or {}                                               # option name -> function(current values): show the row only when it has an effect
		self.hooks = hooks or {}                                             # option name -> function(dialog, value), called when a popup changes (full version)
		self.about_text = (about + "\n\n" + FULL + "\n\n" + CAUTION).strip(); self.shown = False; self.w = None

	def pref(self, name, default):
		return self.pref_of(self.prefs, name, default)

	@staticmethod
	def pref_of(prefs, name, default):
		try:
			from GlyphsApp import Glyphs
			v = Glyphs.defaults[prefs + name]
			return default if v is None else v
		except Exception:
			return default

	def build(self):
		import vanilla
		from AppKit import NSFont, NSColor
		full = TIER["tier"] == "full"; M, W = self.M, self.W
		if self.w is not None:
			try: self.w.close()
			except Exception: pass
		w = vanilla.Window((W, 10), self.title); self.w = w
		w.msg = vanilla.TextBox((M, 0, -M, 32), "", sizeStyle="small"); show_status(w.msg)          # Måns Tools v1.000 · Professional, or a message
		w.info = vanilla.TextBox((M, 0, -M, 17), "", sizeStyle="small"); w.info.show(bool(self.info))
		try: w.info.getNSTextField().setTextColor_(NSColor.secondaryLabelColor())
		except Exception: pass
		w.note = vanilla.TextBox((M, 0, -M, 10), "", sizeStyle="small"); w.note.show(False); self.note_h = 0   # a note before a long run, right over the buttons, amber
		try: w.note.getNSTextField().setTextColor_(note_color())
		except Exception: pass
		# the options: a group of rows, live in the full version, shown but disabled (grey) in the free version, never read there
		self.controls = {}; y = 0; grey = []; self.rows = []                # rows: (name, [(control, y offset)], height); shown or hidden by self.when
		w.opts = vanilla.Group((0, 0, W, 10)); ch = self.changed_
		for kind, name, label, default in self.options:
			val = self.pref(name, default) if full else (default[1] if kind in ("popup", "radio") else default)
			lab = None
			if kind == "check":
				c = vanilla.CheckBox((M, 0, -M, 20), label, value=bool(val), callback=ch); h = 26
			elif kind == "text":
				lab = vanilla.TextBox((M, 3, 150, 17), label); c = vanilla.EditText((M + 156, 0, -M, 22), str(val)); h = 30
			elif kind == "popup":
				items, cur = default
				lab = vanilla.TextBox((M, 3, 150, 17), label); c = vanilla.PopUpButton((M + 156, 0, -M, 22), items, callback=self.hook(name, items)); c.set(items.index(val) if val in items else items.index(cur)); h = 30
			elif kind == "radio":
				items, cur = default
				lab = vanilla.TextBox((M, 3, 150, 17), label); c = vanilla.RadioGroup((M + 156, 0, -M, 22), items, isVertical=False, callback=ch); c.set(items.index(val) if val in items else items.index(cur)); h = 30
			elif kind == "heading":
				lab = vanilla.TextBox((M, 6, -M, 17), label, sizeStyle="small"); h = 24; c = None
			else:
				continue
			parts = []
			if lab is not None: w.opts.__setattr__("lab_" + name, lab); grey.append(lab); parts.append((lab, lab.getPosSize()[1]))
			if c is not None:
				w.opts.__setattr__("opt_" + name, c); parts.append((c, 0))
				if full: self.controls[name] = (kind, c)
				else: c.enable(False)
			self.rows.append((name, parts, h))
		self.place_rows()
		if not full:
			for lab in grey:
				try: lab.getNSTextField().setTextColor_(NSColor.tertiaryLabelColor())
				except Exception: pass
		if full:
			bw = (W - 2 * M - self.GAP) / 2.0
			w.close_ = vanilla.Button((M, 0, bw, 24), "Close", callback=self.close_)
			w.go = vanilla.Button((M + bw + self.GAP, 0, bw, 24), self.action, callback=self.go_)
		else:
			bw = (W - 2 * M - 2 * self.GAP) / 3.0
			w.buy = vanilla.Button((M, 0, bw, 24), "Buy full version", callback=self.buy_)
			w.close_ = vanilla.Button((M + bw + self.GAP, 0, bw, 24), "Close", callback=self.close_)
			w.go = vanilla.Button((M + 2 * (bw + self.GAP), 0, bw, 24), self.action, callback=self.go_)
		w.spin = vanilla.ProgressSpinner((0, 0, 16, 16), displayWhenStopped=False, sizeStyle="small")   # turns while the server works: Glyphs is busy, not frozen
		try: w.spin.getNSProgressIndicator().setUsesThreadedAnimation_(True)
		except Exception: pass
		w.about = vanilla.Button((0, 0, 90, 20), "About ▸", sizeStyle="small", callback=self.about_)
		if self.options: w.settings = vanilla.Button((0, 0, 100, 20), "", sizeStyle="small", callback=self.settings_)
		w.licence = vanilla.Button((0, 0, 100, 20), "License key", sizeStyle="small", callback=self.licence_)     # both tiers: activate, or remove the key
		w.about_text = vanilla.TextBox((M, 0, -M, 190), self.about_text, sizeStyle="small"); w.about_text.show(False)
		w.more = vanilla.Button(((W - 90) / 2.0, 0, 90, 20), "More info", sizeStyle="small", callback=self.buy_); w.more.show(False)   # under About: the same page, same tracking
		self.shown = False; self.opts_shown = bool(self.pref("_settings", True))
		self.layout(); w.setDefaultButton(w.go)
		if self.info:
			w.bind("became key", lambda sender: self.refresh_info())              # back from Glyphs: the selection may have changed
			self.refresh_info()

	def hook(self, name, items):
		f = self.hooks.get(name)
		if f is None: return self.changed_
		return lambda sender: (f(self, items[sender.get()]), self.changed_(sender))

	def current(self):
		"""The option values as the dialog shows them now (no prefs written)."""
		out = {}
		for kind, name, label, default in self.options:
			if kind == "heading": continue
			if name in self.controls:
				k, c = self.controls[name]
				out[name] = bool(c.get()) if k == "check" else (default[0][c.get()] if k in ("popup", "radio") else str(c.get()))
			else:
				out[name] = default[1] if kind in ("popup", "radio") else default
		return out

	def place_rows(self):
		"""Stacks the option rows, leaving out the ones self.when says have no effect now (snap units while snapping is off)."""
		cur = self.current(); y = 0
		for name, parts, h in self.rows:
			f = self.when.get(name); show = True
			if f is not None:
				try: show = bool(f(cur))
				except Exception: show = True
			for c, dy in parts:
				x, _, cw, chh = c.getPosSize(); c.setPosSize((x, y + dy, cw, chh)); c.show(show)
			if show: y += h
		self.h_opts = y + 6 if self.options else 0

	def changed_(self, sender):
		try:
			if self.when and self.w is not None: self.place_rows(); self.layout()
			self.refresh_info()
		except Exception:
			log("changed", traceback.format_exc())

	def set_option(self, name, value):
		"""Selects a popup's item by its label (e.g. back to the previous choice)."""
		for kind, n, label, default in self.options:
			if n == name and name in self.controls and value in default[0]: self.controls[name][1].set(default[0].index(value))

	def layout(self):
		"""Places the rows for the current state (settings shown or hidden, About open or closed) and sizes the window."""
		w = self.w; M, W = self.M, self.W; y = 14
		w.msg.setPosSize((M, y, -M, 32)); y += 36
		show = self.opts_shown and self.h_opts > 0
		if hasattr(w, "settings"):                                          # the fold button sits right over the settings rows
			w.settings.setTitle("Settings ▾" if self.opts_shown else "Settings ▸"); w.settings.setPosSize((M - 6, y, 100, 20)); y += 26
		w.opts.show(show)
		if show: w.opts.setPosSize((0, y, W, self.h_opts)); y += self.h_opts
		y += 6
		if self.info: w.info.setPosSize((M, y + 2, -M, 17)); y += 22          # the most pairs, right over the buttons (and the note)
		nh = getattr(self, "note_h", 0); w.note.show(nh > 0)                # the note before a long run: right over the buttons
		if nh: w.note.setPosSize((M, y + 2, -M, nh)); y += nh + 8
		for b in ("buy", "close_", "go"):
			if hasattr(w, b):
				x, _, bw, bh = getattr(w, b).getPosSize(); getattr(w, b).setPosSize((x, y, bw, bh))
		gx, _, gw, _ = w.go.getPosSize(); w.spin.setPosSize((gx + 12, y + 4, 16, 16))       # inside the action button, left of "Working…"
		y += 34
		full = TIER["tier"] == "full"                                       # licensed: License key moves under About (inside it); free: next to About
		small = [w.about] if full else [w.about, w.licence]
		widths = [90 if b is w.about else 100 for b in small]; gap = 12; x = (W - sum(widths) - gap * (len(small) - 1)) / 2.0
		for b, bw in zip(small, widths):
			b.setPosSize((x, y, bw, 20)); x += bw + gap
		y += 26
		w.about_text.setPosSize((M, y, -M, 190)); w.about_text.show(self.shown)
		under = [w.more, w.licence] if full else [w.more]
		widths = [90 if b is w.more else 100 for b in under]; x = (W - sum(widths) - gap * (len(under) - 1)) / 2.0
		for b, bw in zip(under, widths):
			b.setPosSize((x, y + 194, bw, 20)); x += bw + gap
		w.more.show(self.shown); w.licence.show(self.shown or not full)
		self.h_short = y + 4; self.h_long = y + 224
		w.resize(W, self.h_long if self.shown else self.h_short)

	def settings_(self, sender):
		self.opts_shown = not self.opts_shown
		try:
			from GlyphsApp import Glyphs
			Glyphs.defaults[self.prefs + "_settings"] = self.opts_shown
		except Exception:
			pass
		self.layout()

	def open(self):
		if key(): check_tier()
		prev = getattr(_OPEN, "dialog", None)                                # one Måns AI Tools window at a time, across all four plugins (Mans 2026-11-23)
		if prev is not None and prev is not self:
			try: prev.w.close()
			except Exception: pass
		_OPEN.dialog = self
		self.build(); self.w.open()

	def values(self):
		"""The option values (full version), by name; the free version gets the defaults."""
		out = {}
		for kind, name, label, default in self.options:
			if name in self.controls:
				k, c = self.controls[name]
				v = bool(c.get()) if k == "check" else (default[0][c.get()] if k in ("popup", "radio") else str(c.get()))
			elif kind == "heading":
				continue
			else:
				v = default[1] if kind in ("popup", "radio") else default
			out[name] = v
			try:
				from GlyphsApp import Glyphs
				if name in self.controls: Glyphs.defaults[self.prefs + name] = v
			except Exception:
				pass
		return out

	def about_(self, sender):
		self.shown = not self.shown; self.w.about.setTitle("About ▾" if self.shown else "About ▸"); self.layout()

	def note(self, text):
		"""The amber ⚠️ note right over the buttons ("" hides it); as tall as its text."""
		try:
			from Foundation import NSMakeRect
			self.w.note.set(("\u26a0\ufe0f " + text) if text else ""); h = 0   # ⚠️ in front
			if text: h = int(self.w.note.getNSTextField().cell().cellSizeForBounds_(NSMakeRect(0, 0, self.W - 2 * self.M, 2000)).height) + 4
			if h != self.note_h: self.note_h = h; self.layout()
		except Exception:
			log("note", traceback.format_exc())

	def refresh_info(self):
		if not self.info or self.w is None: return
		try: self.w.info.set(self.info(self.current()))
		except Exception: log("info", traceback.format_exc())

	def spin(self, on):
		"""The spinner in the action button. Drawn by the system's animation, so it keeps turning while Glyphs waits for the server."""
		try:
			self.w.spin.start() if on else self.w.spin.stop()
			self.w.getNSWindow().displayIfNeeded()
			import objc
			objc.lookUpClass("CATransaction").flush()                                        # hand the animation to the window server before the main thread blocks
		except Exception:
			pass

	def say(self, text):
		try: self.w.msg.set(str(text))
		except Exception: pass

	def close_(self, sender):
		self.w.close()

	def buy_(self, sender):
		try:
			from AppKit import NSWorkspace
			from Foundation import NSURL
			NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(buy_url(self.title)))
		except Exception:
			log("buy page not opened", traceback.format_exc())

	def licence_(self, sender):
		"""The license window: the key, Activate (checked with the server), Remove key (back to the free version), Close."""
		import vanilla
		LW = self.W
		lw = vanilla.Window((LW, 156), "License key"); self.lw = lw
		lw.text = vanilla.TextBox((self.M, 12, -self.M, 17), "One key unlocks all Måns AI Tools plugins." if TIER["tier"] != "full" else status_line()[0], sizeStyle="small")
		lw.key = vanilla.EditText((self.M, 36, -self.M, 24), key(), placeholder="License key")
		lw.msg = vanilla.TextBox((self.M, 100, -self.M, 48), "", sizeStyle="small")
		if key():                                                             # a key stored: Close / Remove key / Activate, three equal buttons spaced as the main row
			bw = (LW - 2 * self.M - 2 * self.GAP) / 3.0
			lw.close_ = vanilla.Button((self.M, 68, bw, 24), "Close", callback=lambda s: lw.close())
			lw.remove = vanilla.Button((self.M + bw + self.GAP, 68, bw, 24), "Remove key", callback=self.remove_key_)
			lw.ok = vanilla.Button((self.M + 2 * (bw + self.GAP), 68, bw, 24), "Activate", callback=self.activate_)
		else:                                                                 # free, no key: Close / Activate
			bw = (LW - 2 * self.M - self.GAP) / 2.0
			lw.close_ = vanilla.Button((self.M, 68, bw, 24), "Close", callback=lambda s: lw.close())
			lw.ok = vanilla.Button((self.M + bw + self.GAP, 68, bw, 24), "Activate", callback=self.activate_)
		lw.setDefaultButton(lw.ok); lw.open()

	def remove_key_(self, sender):
		"""Forgets the key on this computer: the plugins run as the free version again. The license itself stays valid and
		can be pasted again here (same computer: no move) or on another computer (move). Two clicks: the first one warns."""
		try:
			if sender is not None and hasattr(self.lw, "remove") and str(self.lw.remove.getTitle()) != "Yes, remove":
				self.lw.msg.set("Remove the license key from this computer? All Måns AI Tools plugins go back to the free version. The key stays valid and can be pasted again later.")
				self.lw.remove.setTitle("Yes, remove"); return
		except Exception:
			pass
		set_key(""); TIER.update(tier="free", msg="", code="")
		try: self.lw.close()
		except Exception: pass
		self.build(); self.w.open(); self.say("Key removed: free version.")

	def activate_(self, sender):
		typed = str(self.lw.key.get() or "").strip(); set_key(typed)
		if not typed:
			self.remove_key_(None); return                                       # an empty field + Activate: the same as removing, no warning needed
		move = str(self.lw.ok.getTitle()) == "Move here"                      # second click after a "tied" answer: move the licence here
		tier = check_tier(move=move); show_status(self.lw.msg); show_status(self.w.msg)
		self.lw.ok.setTitle("Move here" if TIER.get("code") == "tied" else "Activate")
		if tier == "full":
			try: self.lw.close()
			except Exception: pass
			self.build(); self.w.open()                                      # the window again, now with the options and without Buy / Licence

	def go_(self, sender):
		from GlyphsApp import Glyphs
		show_status(self.w.msg)                                          # the version / licence line stays (a message from the last click is cleared)
		if Glyphs.font is None:
			self.say("Open a font first."); return
		opts = self.values(); self.refresh_info()
		if self.check:
			try: warning = self.check(opts) or ""
			except Exception: warning = ""; log("check", traceback.format_exc())
			if warning and warning != self.warned:                         # first click: the warning and a second button title; the same warning again = go
				self.warned = warning; show_status(self.w.msg); self.note(warning); self.w.go.setTitle(self.action + " anyway"); return
		self.warned = None; self.note("")
		self.w.go.enable(False); self.w.go.setTitle("Working…"); self.spin(True)
		try:
			msg, names = result_parts(self.callback(opts))
		except Exception as e:
			traceback.print_exc(); log("ERROR", traceback.format_exc())
			self.spin(False); self.say("Error: %s" % (str(e)[:300] or "see Macro panel output.")); self.w.go.enable(True); self.w.go.setTitle(self.action)
			return
		self.spin(False); self.w.go.enable(True); self.w.go.setTitle(self.action)
		try: self.w.close()
		except Exception: pass
		if opts.get("tab", False): open_tab(Glyphs.font, names)          # only plugins with the new-tab option open one
		try: Glyphs.showNotification(BRAND, msg)
		except Exception: pass


def result_parts(result):
	"""A callback returns a message, or (message, names of the glyphs it adjusted)."""
	if isinstance(result, (tuple, list)): return str(result[0] or "Done."), list(result[1] or [])
	return str(result or "Done."), []


def open_tab(font, names):
	"""A new tab with exactly the glyphs adjusted: characters where a glyph has one, /name otherwise; A–Z a–z on two lines."""
	if font is None or not names: return
	try:
		want = set(str(n) for n in names); parts = []
		for g in font.glyphs:
			if str(g.name) not in want: continue
			u = g.unicode
			try: ch = chr(int(u, 16)) if u else None
			except Exception: ch = None
			parts.append(ch if ch and len(ch) == 1 and ch not in "\n/" else "/%s " % g.name)
		text = "".join(parts)
		if want <= set(LETTERS):
			text = "".join(p for p in parts if p.isupper()) + ("\n" if any(p.isupper() for p in parts) and any(p.islower() for p in parts) else "") + "".join(p for p in parts if p.islower())
		if text.strip(): font.newTab(text)
	except Exception:
		log("tab not opened", traceback.format_exc())


def add_menu_item(owner, menu_name, title, selector):
	"""A menu item at the end of Glyphs' menu (File, Glyph, …)."""
	from AppKit import NSApp, NSMenuItem
	from GlyphsApp import Glyphs
	it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, selector, ""); it.setTarget_(owner)
	menu = None
	try:
		top = Glyphs.menu[menu_name]
		if top is not None and top.submenu() is not None: menu = top.submenu()
	except Exception:
		pass
	if menu is None:
		for top in NSApp.mainMenu().itemArray():
			if top.submenu() is not None and str(top.title()) == menu_name.replace("_MENU", "").title(): menu = top.submenu()
	if menu is not None: menu.addItem_(it)
	else: Glyphs.menu[menu_name].append(it)
