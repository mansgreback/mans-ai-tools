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
CAUTION = ("Save a copy of your work before running this. Font and install data will be sent to and processed on aringtypeface.com "
           "server. Internet access is required. Do not submit any trademark/copyright protected or confidential works.")
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
		TIER.update(tier="free", msg=""); return "free"
	st, b = call(dict(tool=tool, action="status", key=k, install=identity(), move=bool(move)), 30)
	TIER["code"] = str(b.get("code") or "")
	if st == 200 and b.get("tier") == "full": TIER.update(tier="full", msg="Full version active.")
	elif st == 0: TIER.update(tier="free", msg=b.get("error") or "The server could not be reached.")
	elif TIER["code"] == "tied": TIER.update(tier="free", msg="This license is active on another computer. Click Move here to use it on this computer instead. The other computer will be deactivated permanently and it will not be possible to reactivate it on that machine.")
	else: TIER.update(tier="free", msg=(b.get("error") or "The license is not valid.") + " Running as the free version.")
	return TIER["tier"]


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
		blob = d.objectForKey_("User3"); paddle = d.objectForKey_("Paddle-Glyphs 3-650121-SD")
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


def call(body, timeout=900):
	"""-> (status, dict). status 0 = the server could not be reached."""
	from urllib.request import Request, urlopen
	from urllib.error import HTTPError, URLError
	url = server()
	req = Request(url, data=json.dumps(body, separators=(",", ":")).encode("utf-8"), headers={"Content-Type": "application/json", "User-Agent": "MansToolsSimple/1.0"}, method="POST")
	try:
		with urlopen(req, context=ssl.create_default_context() if url.startswith("https") else None, timeout=timeout) as r:
			return r.status, json.loads(r.read().decode("utf-8"))
	except HTTPError as e:
		try: return e.code, json.loads(e.read().decode("utf-8"))
		except Exception: return e.code, dict(error="The server answered %s." % e.code, code="http")
	except (URLError, OSError, ValueError) as e:
		return 0, dict(error="The server could not be reached (%s). Internet access is required." % getattr(e, "reason", e), code="offline")


def run(tool, data, timeout=900):
	"""One run on the server: no key, simple=True (the server works on A–Z a–z only and says so). -> result dict; raises with the server's message."""
	k = key() if TIER["tier"] == "full" else ""                      # a valid key: the full version (every glyph, no limit); else the simple run
	st, b = call(dict(tool=tool, action="run", key=k, simple=not k, install=identity(), data=data), timeout)
	log("server", tool, st, b.get("code"), b.get("tier"), b.get("error"))
	if st != 200:
		raise RuntimeError(b.get("error") or "The server answered %s." % st)
	return b


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


def selected_names(font):
	"""The glyphs selected in the font view or the current tab."""
	try: return set(str(l.parent.name) for l in (font.selectedLayers or []) if l is not None and l.parent is not None)
	except Exception: return set()


def worked(font, master, need_paths=True):
	"""The glyphs a run works on: A–Z a–z, or every glyph of the font with the full version (a valid key)."""
	pool = list(font.glyphs) if TIER["tier"] == "full" else letters(font)
	out = []
	for g in pool:
		L = g.layers[master.id]
		if L is None: continue
		if need_paths and not closed_paths(L): continue
		out.append(g)
	return out


def closed_paths(layer):
	try: paths = list(layer.paths)
	except Exception: paths = [s for s in layer.shapes if hasattr(s, "nodes")]
	return [p for p in paths if p.closed and len(p.nodes) >= 3]


def glyph_json(g, layer):
	uni = None
	try: uni = int(g.unicode, 16) if g.unicode else None
	except Exception: pass
	d = dict(name=str(g.name), unicode=uni, width=float(layer.width), lsb=float(layer.LSB), rsb=float(layer.RSB),
	         paths=[[[float(n.position.x), float(n.position.y), str(n.type)] for n in p.nodes] for p in closed_paths(layer)])
	try: d.update(cat=str(g.category or ""), sub=str(g.subCategory or ""), case=int(getattr(g, "case", 0) or 0), script=str(g.script or ""), export=bool(g.export), lg=str(g.leftKerningGroup) if g.leftKerningGroup else None, rg=str(g.rightKerningGroup) if g.rightKerningGroup else None)
	except Exception: pass
	return d


def font_json(font, master, glyphs, settings=None):
	"""The font data a simple plugin sends: metrics of the master and the A–Z a–z outlines."""
	return dict(upm=float(font.upm), cap=float(master.capHeight or 0), xheight=float(master.xHeight or 0), ascender=float(master.ascender or 0),
	            descender=float(master.descender or 0), italic=float(master.italicAngle or 0), grid=float(font.grid), family=str(font.familyName),
	            glyphs=[glyph_json(g, g.layers[master.id]) for g in glyphs if g.layers[master.id] is not None], settings=settings or {})


FULL = "One license, bought once, unlocks all Måns AI Tools plugins: AI Kerning, AI Spacing, AI Anchors and AI Variable Font."


class Dialog(object):
	"""The one window of every simple plugin, a stack of rows:
	  title · one-line brief · status line · "Settings ▾" · option rows · button row · "About ▸" "License key"; open About ends with a "More info" link to the buy page.
	Free: Buy full version / Close / action, three equal buttons; the options are shown greyed out and disabled and are never
	read (the free run sends no settings, and the server ignores settings on keyless runs anyway). Full: the options are live,
	Buy is gone, License key stays (Remove key there), Close / action are two equal buttons. "Settings" folds the option rows away (remembered). The callback gets the option values as a dict. Messages go to the status line."""
	W = 440; M = 16; GAP = 24

	def __init__(self, title, brief, action, callback, about="", options=(), prefs=""):
		self.title, self.brief, self.action, self.callback, self.options, self.prefs = title, brief, action, callback, list(options), prefs
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
		w.title = vanilla.TextBox((M, 0, -M, 22), self.title)
		try: w.title.getNSTextField().setFont_(NSFont.boldSystemFontOfSize_(15))
		except Exception: pass
		w.brief = vanilla.TextBox((M, 0, -M, 20), self.brief)
		w.msg = vanilla.TextBox((M, 0, -M, 32), TIER["msg"] if key() else "", sizeStyle="small")
		try: w.msg.getNSTextField().setTextColor_(NSColor.secondaryLabelColor())
		except Exception: pass
		# the options: a group of rows, live in the full version, shown but disabled (grey) in the free version, never read there
		self.controls = {}; y = 0; grey = []
		w.opts = vanilla.Group((0, 0, W, 10))
		for kind, name, label, default in self.options:
			val = self.pref(name, default) if full else (default[1] if kind in ("popup", "radio") else default)
			lab = None
			if kind == "check":
				c = vanilla.CheckBox((M, y, -M, 20), label, value=bool(val)); y += 26
			elif kind == "text":
				lab = vanilla.TextBox((M, y + 3, 150, 17), label); c = vanilla.EditText((M + 156, y, -M, 22), str(val)); y += 30
			elif kind == "popup":
				items, cur = default
				lab = vanilla.TextBox((M, y + 3, 150, 17), label); c = vanilla.PopUpButton((M + 156, y, -M, 22), items); c.set(items.index(val) if val in items else items.index(cur)); y += 30
			elif kind == "radio":
				items, cur = default
				lab = vanilla.TextBox((M, y + 3, 150, 17), label); c = vanilla.RadioGroup((M + 156, y, -M, 22), items, isVertical=False); c.set(items.index(val) if val in items else items.index(cur)); y += 30
			elif kind == "heading":
				lab = vanilla.TextBox((M, y + 6, -M, 17), label, sizeStyle="small"); y += 24; c = None
			else:
				continue
			if lab is not None: w.opts.__setattr__("lab_" + name, lab); grey.append(lab)
			if c is None: continue
			w.opts.__setattr__("opt_" + name, c)
			if full: self.controls[name] = (kind, c)
			else: c.enable(False)
		self.h_opts = y + 6 if self.options else 0
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
		w.about = vanilla.Button((0, 0, 90, 20), "About ▸", sizeStyle="small", callback=self.about_)
		if self.options: w.settings = vanilla.Button((0, 0, 100, 20), "", sizeStyle="small", callback=self.settings_)
		w.licence = vanilla.Button((0, 0, 100, 20), "License key", sizeStyle="small", callback=self.licence_)     # both tiers: activate, or remove the key
		w.about_text = vanilla.TextBox((M, 0, -M, 190), self.about_text, sizeStyle="small"); w.about_text.show(False)
		w.more = vanilla.Button(((W - 90) / 2.0, 0, 90, 20), "More info", sizeStyle="small", callback=self.buy_); w.more.show(False)   # under About: the same page, same tracking
		self.shown = False; self.opts_shown = bool(self.pref("_settings", True))
		self.layout(); w.setDefaultButton(w.go)

	def layout(self):
		"""Places the rows for the current state (settings shown or hidden, About open or closed) and sizes the window."""
		w = self.w; M, W = self.M, self.W; y = 14
		w.title.setPosSize((M, y, -M, 22)); y += 24
		w.brief.setPosSize((M, y, -M, 20)); y += 22
		w.msg.setPosSize((M, y, -M, 32)); y += 36
		show = self.opts_shown and self.h_opts > 0
		if hasattr(w, "settings"):                                          # the fold button sits right over the settings rows
			w.settings.setTitle("Settings ▾" if self.opts_shown else "Settings ▸"); w.settings.setPosSize((M - 6, y, 100, 20)); y += 26
		w.opts.show(show)
		if show: w.opts.setPosSize((0, y, W, self.h_opts)); y += self.h_opts
		y += 6
		for b in ("buy", "close_", "go"):
			if hasattr(w, b):
				x, _, bw, bh = getattr(w, b).getPosSize(); getattr(w, b).setPosSize((x, y, bw, bh))
		y += 34
		small = [w.about, w.licence]
		widths = [90 if b is w.about else 100 for b in small]; gap = 12; x = (W - sum(widths) - gap * (len(small) - 1)) / 2.0
		for b, bw in zip(small, widths):
			b.setPosSize((x, y, bw, 20)); x += bw + gap
		y += 26
		w.about_text.setPosSize((M, y, -M, 190)); w.about_text.show(self.shown)
		w.more.setPosSize(((W - 90) / 2.0, y + 194, 90, 20)); w.more.show(self.shown)
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
		lw.text = vanilla.TextBox((self.M, 12, -self.M, 17), "One key unlocks all Måns AI Tools plugins." if TIER["tier"] != "full" else "Full version active on this computer.", sizeStyle="small")
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
		tier = check_tier(move=move); self.lw.msg.set(TIER["msg"]); self.say(TIER["msg"])
		self.lw.ok.setTitle("Move here" if TIER.get("code") == "tied" else "Activate")
		if tier == "full":
			try: self.lw.close()
			except Exception: pass
			self.build(); self.w.open()                                      # the window again, now with the options and without Buy / Licence

	def go_(self, sender):
		from GlyphsApp import Glyphs
		self.say("")
		if Glyphs.font is None:
			self.say("Open a font first."); return
		opts = self.values()
		self.w.go.enable(False); self.w.go.setTitle("Working…")
		try:
			msg, names = result_parts(self.callback(opts))
		except Exception as e:
			traceback.print_exc(); log("ERROR", traceback.format_exc())
			self.say("Error: %s" % (str(e)[:300] or "see Macro panel output.")); self.w.go.enable(True); self.w.go.setTitle(self.action)
			return
		self.w.go.enable(True); self.w.go.setTitle(self.action)
		try: self.w.close()
		except Exception: pass
		if opts.get("tab", True): open_tab(Glyphs.font, names)
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
