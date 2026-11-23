# encoding: utf-8
"""AI Kerning — Glyph ▸ AI Kerning…   (Måns AI Tools)

Kerns A–Z a–z against each other in the current master: the outlines go to the Måns Tools server, the kerning model there answers
with glyph pairs, and they are written into the master's kerning as plain glyph-to-glyph pairs (kerning groups are not
touched). No settings. Non-commercial use."""
from __future__ import division, print_function, unicode_literals
import os, sys, traceback

import objc
from GlyphsApp import Glyphs
from GlyphsApp.plugins import GeneralPlugin

try:
	from GlyphsApp import GLYPH_MENU
except ImportError:
	GLYPH_MENU = "Glyph"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import simple
from simple import log

TITLE = "AI Kerning"
ABOUT = "AI Kerning kerns your font for you. The full version kerns the whole font or any selection, unlimited, with kerning groups, exceptions, a group tolerance and a lower limit for pairs."
BRIEF = "Kerns the current master."


ALL, AGAINST, ONLY = "All glyphs", "Selected against all", "Selected only"      # every pair / the selection against every glyph / the selection against itself
AZ = "A\u2013Z a\u2013z"                                                    # the 52 letters against each other (= Selected only with A–Z a–z as the selection); the free version always does this
BOTH, LEFT, RIGHT = "Both", "Left", "Right"                              # the selected glyph's own side: Left = its left edge (VA), Right = its right edge (AV)
LEGACY = {"Selected glyphs": AGAINST}                                     # v1.000's choice, from saved settings and scripts
OWN, LIKE_BASE = "Kern on their own", "Kern like their base letter"      # accented letters (Mans 2026-11-23; were "Kern individually" / "Inherit base", default individually)

# before a long run (full version only; the free version kerns A–Z a–z, at most 2,704 pairs): the server does about
# PAIRS_PER_S pairs a second (measured on the host 2026-11-23); its memory grows with the number of glyphs in the font
PAIRS_PER_S = 700
SLOW_S = 60                    # note above about a minute
STOP_S = 1200                  # the server stops a run after 20 minutes (core.JOB_MAX; runs go on in the background since 1.1.1, no gateway limit)
LATE_S = 600                   # from a 10-minute estimate the note says it may be stopped after 20 min: the estimate is rough (Mans 2026-11-23)
MANY_GLYPHS = 1000             # "All glyphs" on more than this: recommend kerning a selection at a time
MEMORY_GLYPHS = 2500           # a 2,919-glyph font ran out of memory on the host


def duration(sec):
	return ("%d min" % max(1, round(sec / 60.0))) if sec < 5400 else ("%d hours" % round(sec / 3600.0))


def pair_count(opts):
	"""-> (glyphs in the font, glyphs kerned, the most pairs the run can make, selection, glyphs, scope); None = nothing selected yet.
	The most: the server leaves out glyphs it cannot kern and pairs of unchecked categories, so a run usually makes fewer."""
	font, master = simple.target()
	if simple.TIER["tier"] != "full":                                    # the free version: A–Z a–z against each other
		L = [g for g in font.glyphs if simple.is_letter(g) and g.layers[master.id] is not None and len(g.layers[master.id].shapes)]
		return len(L), len(L), len(L) * len(L), set(str(g.name) for g in L), L, AZ
	glyphs = [g for g in font.glyphs if g.layers[master.id] is not None and len(g.layers[master.id].shapes)]
	n = len(glyphs); scope = LEGACY.get(opts.get("scope"), opts.get("scope")); sel = set()
	if scope in (AGAINST, ONLY, AZ):
		sel = set(str(g.name) for g in glyphs if simple.is_letter(g)) if scope == AZ else set(simple.selected_names(font))
		if not sel: return None
		lg = set(str(g.leftKerningGroup) for g in glyphs if str(g.name) in sel and g.leftKerningGroup)
		rg = set(str(g.rightKerningGroup) for g in glyphs if str(g.name) in sel and g.rightKerningGroup)
		s = sum(1 for g in glyphs if str(g.name) in sel or (g.leftKerningGroup and str(g.leftKerningGroup) in lg) or (g.rightKerningGroup and str(g.rightKerningGroup) in rg))   # a group is kerned as one: its members come along
		if scope == AZ: s = len(sel)                                         # A–Z a–z: only the letters are kerned, the rest of their groups follow them
		if scope in (ONLY, AZ): pairs = s * s
		elif opts.get("sides") in (LEFT, RIGHT): pairs = s * n
		else: pairs = 2 * s * n - s * s                                       # selected first + selected second, the pairs among the selection once
	else:
		s = n; pairs = n * n
	return n, s, pairs, sel, glyphs, scope


def info(opts):
	"""The line over the buttons: the most pairs this run can make with the current choice and selection."""
	try:
		c = pair_count(opts)
		if c is None: return "Select the glyphs to kern."
		return "Up to %s pair%s." % (format(c[2], ","), "" if c[2] == 1 else "s")
	except Exception:
		return ""


def estimate(opts):
	"""-> a note for the status line before a slow run, or one that may run out of server memory; '' = none.
	The dialog shows it on the first click and runs on the second ("Kern anyway")."""
	if simple.TIER["tier"] != "full": return ""
	c = pair_count(opts)
	if c is None: return ""                                              # kern() says "Select the glyphs to kern first."
	n, s, pairs, sel, glyphs, scope = c
	sec = 5 + pairs / float(PAIRS_PER_S); slow = sec > SLOW_S; late = sec > LATE_S; memory = n > MEMORY_GLYPHS and scope not in (ONLY, AZ)   # Selected only / A–Z a–z: the server works on the selection + A–Z a–z, not the font
	if scope not in (AGAINST, ONLY, AZ) and (n > MANY_GLYPHS or slow):
		risks = [x for x, on in (("be stopped after 20 min", late), ("run out of server memory", memory)) if on]
		return ("Kerning all %s glyphs against each other is up to %s pairs. It takes about %s%s and is rarely needed. Select the glyphs you want kerned, "
		        "a group at a time, and choose \u201cSelected only\u201d." % (format(n, ","), format(pairs, ","), duration(sec), (", may " + " or ".join(risks) + ",") if risks else ""))
	notes = []
	if slow:
		k = len(sel & set(str(g.name) for g in glyphs)) or len(sel)
		who = ("your %d and the rest of their kerning groups" % k) if s > k else "the selection"
		risk = [x for x, on in (("be stopped after 20 min", late), ("run out of server memory", memory)) if on]
		notes.append("This takes about %s: %s glyphs (%s) against %s%s. Kern a smaller selection at a time, in batches." % (
		             duration(sec), format(s, ","), who, "each other" if scope in (ONLY, AZ) else format(n, ","), (", and may " + " or ".join(risk)) if risk else ""))
	elif memory:
		notes.append("This font has %s glyphs, so the server may run out of memory. If it does, kern using a selection, in smaller batches." % format(n, ","))
	return " ".join(notes)


OPTIONS = [("popup", "scope", "Kern", ([AZ, ALL, AGAINST, ONLY], AZ)),                         # inputs, then checkboxes, then grouping with its own inputs
           ("popup", "sides", "Sides", ([BOTH, LEFT, RIGHT], BOTH)),
           ("popup", "accents", "Accented letters", ([LIKE_BASE, OWN], LIKE_BASE)),
           ("text", "strength", "Strength %", "100"),
           ("text", "threshold", "Skip adjustments under", "5"),
           ("check", "uc", "Uppercase", True), ("check", "lc", "Lowercase", True), ("check", "fig", "Figures", True), ("check", "punct", "Punctuation and symbols", True),
           ("check", "fill", "Fill in missing kerning only (keep existing pairs)", False),
           ("check", "group", "Make kerning groups", True),
           ("check", "keep", "Keep the font's kerning groups", False),
           ("text", "tolerance", "Group tolerance", "5"),
           ("text", "exceptions", "Exceptions %", "5"),
           ("check", "tab", "Open the kerned glyphs in a new tab", True)]
WHEN = dict(sides=lambda v: v.get("scope") == AGAINST,                  # only "Selected against all" has sides: the other two kern both anyway
            keep=lambda v: v.get("group"), tolerance=lambda v: v.get("group"), exceptions=lambda v: v.get("group"))   # grouping off: these do nothing


CONTEXT = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.)")    # the font's A–Z a–z as the sample of its style; "." ")" for calibration


def subset(glyphs, sel, inherit, mid=None):
	""""Selected only" and A–Z a–z: the glyphs the model needs = the selection, the rest of its kerning groups, with "Inherit
	base" the accented forms of selected letters, and the font's A–Z a–z; then every kerning group with a member in that set,
	complete. The same rule as the server's core.kern_subset (which also applies it for older plugins that send the whole font)."""
	import unicodedata
	lgs = lambda g: str(g.leftKerningGroup) if g.leftKerningGroup else None
	rgs = lambda g: str(g.rightKerningGroup) if g.rightKerningGroup else None
	def ch(g):
		try: return chr(int(g.unicode, 16)) if g.unicode else None
		except Exception: return None
	lg = {lgs(g) for g in glyphs if str(g.name) in sel and lgs(g)}; rg = {rgs(g) for g in glyphs if str(g.name) in sel and rgs(g)}
	base = {ch(g) for g in glyphs if str(g.name) in sel and ch(g)} if inherit else set()
	def need(g):
		if str(g.name) in sel or (lgs(g) and lgs(g) in lg) or (rgs(g) and rgs(g) in rg): return True
		c = ch(g)
		if not c: return False
		if c in CONTEXT: return True
		return bool(base) and unicodedata.normalize("NFD", c)[:1] in base and c not in base
	def comps(g):
		try: return [str(c.componentName) for c in (g.layers[mid] if mid else g.layers[0]).components]
		except Exception: return []
	built = lambda g: inherit and len(comps(g)) >= 2 and any(c in sel for c in comps(g))   # "like their base letter": a selected letter + marks
	first = [g for g in glyphs if need(g) or built(g)]
	lg2 = {lgs(g) for g in first if lgs(g)}; rg2 = {rgs(g) for g in first if rgs(g)}
	keep = {str(g.name) for g in glyphs if need(g) or built(g) or (lgs(g) and lgs(g) in lg2) or (rgs(g) and rgs(g) in rg2)}
	keep |= {c for g in glyphs if str(g.name) in keep for c in comps(g)}   # their components (marks): the server reads what a glyph is made of
	out = [g for g in glyphs if str(g.name) in keep]
	return out if len(out) >= 2 else glyphs


def kern(opts=None):
	font, master = simple.target()
	try: open(simple.LOG, "w").close()
	except Exception: pass
	glyphs = simple.worked(font, master, components=True)               # glyphs made of components (Aacute, b from a flipped d) count as drawn
	log("start", TITLE, font.familyName, master.name, len(glyphs), "letters")
	if len(glyphs) < 2: raise RuntimeError("Fewer than two of A–Z a–z have outlines in this master.")
	opts = opts or {}; settings = {}
	if simple.TIER["tier"] == "full":
		num = lambda k, d: float(str(opts.get(k, d)).replace(",", ".") or d)
		scope = LEGACY.get(opts.get("scope"), opts.get("scope")); side = opts.get("sides")
		settings = dict(scope="selected" if scope in (AGAINST, ONLY, AZ) else "all", pairs="among" if scope in (ONLY, AZ) else "all",
		                sides="right" if (scope == AGAINST and side == LEFT) else "left" if (scope == AGAINST and side == RIGHT) else "both", uc=bool(opts.get("uc", True)), lc=bool(opts.get("lc", True)),
		                fig=bool(opts.get("fig", True)), punct=bool(opts.get("punct", True)), accents="inherit" if str(opts.get("accents", "")) in (LIKE_BASE, "Inherit base") else "individual",
		                fill=bool(opts.get("fill", False)), strength=num("strength", 100) / 100.0, group=bool(opts.get("group", True)), keep_groups=bool(opts.get("keep", False)),
		                tolerance=num("tolerance", 5), exceptions=num("exceptions", 5), threshold=num("threshold", 5))
		if scope == AZ:
			sel = set(str(g.name) for g in glyphs if simple.is_letter(g)); settings["selected"] = sorted(sel); settings["letters"] = True   # the letters lead their kerning groups
			if len(sel) < 2: raise RuntimeError("Fewer than two of A\u2013Z a\u2013z have outlines in this master.")
		elif settings["scope"] == "selected":
			sel = simple.selected_names(font); settings["selected"] = sorted(sel)
			if not sel: raise RuntimeError("Select the glyphs to kern first.")
	if settings.get("scope") == "selected" and settings.get("pairs") == "among":
		glyphs = subset(glyphs, set(settings.get("selected") or []), settings.get("accents") == "inherit", master.id)   # send only what the server keeps (a 12,576-glyph font: 50 MB -> under 2 MB)
	data = simple.font_json(font, master, glyphs, settings, components=True)
	if settings.get("scope") == "selected":                            # the kerning the model may change: the selection; the rest is context
		data["kerning"] = []
	try:                                                                 # existing kerning of this master, so the model can keep / fill it
		data["kerning"] = [[str(a), str(b), float(v)] for a, bs in (font.kerningLTR.get(master.id) or {}).items() for b, v in bs.items()] if simple.TIER["tier"] == "full" else []
		ids = dict((str(g.id), str(g.name)) for g in font.glyphs); data["kerning"] = [[ids.get(a, a), ids.get(b, b), v] for a, b, v in data["kerning"]]
	except Exception:
		data["kerning"] = []
	answer = simple.run("kern", data); res = answer["result"]
	names = set(str(g.name) for g in font.glyphs)                   # Glyphs' setKerningForPair takes glyph NAMES or @MMK_ group names
	ok = lambda k: k.startswith("@") or k in names
	font.disableUpdateInterface()
	try:
		n_set = n_rm = n_grp = 0
		for name, (lg, rg) in (res.get("groups") or {}).items():       # full version with groups: the model's kerning groups
			g = font.glyphs[name]
			if g is None: continue
			g.leftKerningGroup = lg or None; g.rightKerningGroup = rg or None; n_grp += 1
		for a, b in res.get("remove", []):
			try:
				if ok(a) and ok(b): font.removeKerningForPair(master.id, a, b); n_rm += 1
			except Exception:
				pass
		for a, b, v in res.get("set", []):
			if ok(a) and ok(b):
				font.setKerningForPair(master.id, a, b, float(v)); n_set += 1
	finally:
		font.enableUpdateInterface()
	log("applied", n_set, "pairs set", n_rm, "removed")
	scope = set(str(g.name) for g in glyphs)                            # the glyphs whose kerning changed: the sides of the pairs set, groups expanded
	if settings.get("scope") == "selected": scope &= set(settings.get("selected") or [])
	left = {}; right = {}
	for g in font.glyphs:
		if g.rightKerningGroup: left.setdefault("@MMK_L_" + str(g.rightKerningGroup), []).append(str(g.name))
		if g.leftKerningGroup: right.setdefault("@MMK_R_" + str(g.leftKerningGroup), []).append(str(g.name))
	touched = set()
	for a, b, v in res.get("set", []):
		for side, table in ((a, left), (b, right)):
			for n in (table.get(side, []) if side.startswith("@") else [side]):
				if n in scope: touched.add(n)
	return "%d pairs kerned in %s%s." % (n_set, master.name, (", %d glyphs grouped" % n_grp) if n_grp else ""), sorted(touched)


SCRIPT_OPTIONS = [(k, nm, lab, ([ALL, AGAINST, ONLY, AZ], ALL)) if nm == "scope" else (k, nm, lab, d) for k, nm, lab, d in OPTIONS]   # scripts keep All glyphs as default; glyphs=[…] alone = Selected against all (the second item)
simple.register("kern", kern, SCRIPT_OPTIONS)          # scripts and the Glyphs MCP server: MansAITools.kern(…)


class AIKerning(GeneralPlugin):

	@objc.python_method
	def settings(self):
		self.name = TITLE
		self.dlg = None

	@objc.python_method
	def start(self):
		try: simple.add_menu_item(self, GLYPH_MENU, TITLE + "…", self.openDialog_)
		except Exception: traceback.print_exc()

	def openDialog_(self, sender):
		try:
			try:                                                         # v1.000 saved "Selected glyphs": the same thing is now "Selected against all"
				old = Glyphs.defaults["com.mansgreback.AIKerning.scope"]
				if old in LEGACY: Glyphs.defaults["com.mansgreback.AIKerning.scope"] = LEGACY[old]
				elif old is None and simple.TIER["tier"] == "full":        # the full version's first dialog starts on A–Z a–z (Mans 2026-11-23; was Selected only); scripts keep All glyphs
					Glyphs.defaults["com.mansgreback.AIKerning.scope"] = AZ
			except Exception:
				pass
			self.dlg = simple.Dialog(TITLE, BRIEF, "Kern", kern, about=ABOUT, options=OPTIONS, prefs="com.mansgreback.AIKerning.", when=WHEN, check=estimate, info=info); self.dlg.open()
		except Exception:
			traceback.print_exc(); log("DIALOG ERROR", traceback.format_exc())

	@objc.python_method
	def __file__(self):
		return __file__
