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


OPTIONS = [("radio", "scope", "Kern", (["All glyphs", "Selected glyphs"], "All glyphs")),                 # inputs, then checkboxes, then grouping with its own inputs
           ("radio", "accents", "Accented glyphs", (["Kern individually", "Inherit base"], "Kern individually")),
           ("text", "strength", "Strength %", "100"),
           ("text", "threshold", "Skip adjustments under", "5"),
           ("check", "uc", "Uppercase", True), ("check", "lc", "Lowercase", True), ("check", "fig", "Figures", True), ("check", "punct", "Punctuation and symbols", True),
           ("check", "fill", "Fill in missing kerning only (keep existing pairs)", False),
           ("check", "group", "Group glyphs that kern alike", True),
           ("check", "keep", "Keep the font's kerning groups", False),
           ("text", "tolerance", "Group tolerance", "5"),
           ("text", "exceptions", "Exceptions %", "5"),
           ("check", "tab", "Open the kerned glyphs in a new tab", True)]
WHEN = dict(keep=lambda v: v.get("group"), tolerance=lambda v: v.get("group"), exceptions=lambda v: v.get("group"))   # grouping off: these do nothing


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
		settings = dict(scope="selected" if opts.get("scope") == "Selected glyphs" else "all", uc=bool(opts.get("uc", True)), lc=bool(opts.get("lc", True)),
		                fig=bool(opts.get("fig", True)), punct=bool(opts.get("punct", True)), accents="inherit" if str(opts.get("accents", "")).startswith("Inherit") else "individual",
		                fill=bool(opts.get("fill", False)), strength=num("strength", 100) / 100.0, group=bool(opts.get("group", True)), keep_groups=bool(opts.get("keep", False)),
		                tolerance=num("tolerance", 5), exceptions=num("exceptions", 5), threshold=num("threshold", 5))
		if settings["scope"] == "selected":
			sel = simple.selected_names(font); settings["selected"] = sorted(sel)
			if not sel: raise RuntimeError("Select the glyphs to kern first.")
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


simple.register("kern", kern, OPTIONS)                 # scripts and the Glyphs MCP server: MansAITools.kern(…)


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
			self.dlg = simple.Dialog(TITLE, BRIEF, "Kern", kern, about=ABOUT, options=OPTIONS, prefs="com.mansgreback.AIKerning.", when=WHEN); self.dlg.open()
		except Exception:
			traceback.print_exc(); log("DIALOG ERROR", traceback.format_exc())

	@objc.python_method
	def __file__(self):
		return __file__
