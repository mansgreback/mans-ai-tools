# encoding: utf-8
"""AI Spacing — Glyph ▸ AI Spacing…   (Måns AI Tools)

Spaces A–Z a–z in the current master: the outlines go to the Måns Tools server, the spacing model there answers with new
sidebearings for every letter (auto mode, no locked references), and the outlines are moved and the widths set. Kerning
is not touched. No settings. Non-commercial use."""
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

TITLE = "AI Spacing"
ABOUT = "AI Spacing spaces your font for you. The full version spaces any glyph, unlimited, and can keep the spacing of reference glyphs of your choice and fit the other glyphs to them."
BRIEF = "Spaces the current master."


OPTIONS = [("radio", "scope", "Space", (["All glyphs", "Selected glyphs"], "All glyphs")),
           ("check", "lock", "Keep spacing on reference glyphs", False),
           ("radio", "refsrc", "References", (["Listed below", "All other glyphs"], "Listed below")),
           ("text", "refs", "Reference glyphs", "HOnoAVaeil"),
           ("check", "tab", "Open the spaced glyphs in a new tab", True)]
WHEN = dict(refsrc=lambda v: v.get("lock") and v.get("scope") == "Selected glyphs",          # "All other glyphs" only means something for a selection
            refs=lambda v: v.get("lock") and (v.get("refsrc") == "Listed below" or v.get("scope") != "Selected glyphs"))


def comp_edges(layer):
	"""Where each component of a layer is drawn: its left edge, in order (None for an empty one)."""
	out = []
	for c in layer.components:
		try:
			bb = c.bounds; out.append(float(bb.origin.x) if bb.size.width > 0 else None)
		except Exception: out.append(None)
	return out


def hold(layer, before):
	"""Sets each component back to where it was drawn (`before`), after its base glyph moved: the glyph stays exactly as drawn."""
	for c, x0 in zip(layer.components, before):
		if x0 is None: continue
		try:
			bb = c.bounds; d = float(bb.origin.x) - x0
			if abs(d) >= 0.01: c.position = (c.position.x - d, c.position.y)
		except Exception: pass


def aligned(layer):
	"""Whether Glyphs keeps this layer aligned to its components (then its spacing follows the base glyphs). A layer that
	also has its own paths (A = turned V + crossbar) is not, even when its components are set to align."""
	try: return bool(layer.isAligned)
	except Exception: pass
	try: return not len(list(layer.paths)) and any(bool(getattr(c, "automaticAlignment", False)) for c in layer.components)
	except Exception: return False


def space(opts=None):
	font, master = simple.target()
	try: open(simple.LOG, "w").close()
	except Exception: pass
	glyphs = simple.worked(font, master, components=True)               # glyphs made of components (Aacute, b from a flipped d) count as drawn
	log("start", TITLE, font.familyName, master.name, len(glyphs), "letters")
	if not glyphs: raise RuntimeError("None of A–Z a–z has outlines in this master.")
	opts = opts or {}; refs = []; targets = None
	if simple.TIER["tier"] == "full":
		if opts.get("scope") == "Selected glyphs":
			sel = simple.selected_names(font); targets = [str(g.name) for g in glyphs if str(g.name) in sel]
			if not targets: raise RuntimeError("Select the glyphs to space first.")
		if opts.get("lock"):
			if opts.get("refsrc") == "All other glyphs" and targets is not None: refs = [str(g.name) for g in glyphs if str(g.name) not in targets]
			else:
				want = [c for c in str(opts.get("refs") or "")]; refs = [str(g.name) for g in glyphs if g.unicode and chr(int(g.unicode, 16)) in want and (targets is None or str(g.name) not in targets)]
	data = simple.font_json(font, master, glyphs, dict(refs=refs, targets=targets), components=True)
	answer = simple.run("space", data); res = answer["result"]; moves = res.get("moves") or {}
	# glyphs made of components are measured like drawn ones (their decomposed shape goes to the model). Their automatic
	# alignment is never turned off (Mans 2026-10-25): an aligned glyph keeps following its base glyph, as Glyphs does it.
	# Every other glyph with components keeps its drawing exactly: when a base glyph moves (V), each component that moved
	# with it (the turned V in A) is set back to where it was drawn, in every such glyph of the font, in the run or not.
	# Then the glyphs of the run get their own spacing. Deepest glyphs last, so a component of a component is settled first.
	depth = {}
	def deep(name, seen=()):
		if name in depth: return depth[name]
		g = font.glyphs[name]; L = g.layers[master.id] if g is not None else None
		comps = [str(c.componentName) for c in L.components] if L is not None else []
		depth[name] = 0 if not comps or name in seen else 1 + max(deep(c, seen + (name,)) for c in comps)
		return depth[name]
	built = [g for g in font.glyphs if g.layers[master.id] is not None and len(list(g.layers[master.id].components)) and not aligned(g.layers[master.id])]
	drawn = dict((str(g.name), comp_edges(g.layers[master.id])) for g in built)
	font.disableUpdateInterface()
	try:
		n = 0; done = []; followed = 0
		run = set(str(g.name) for g in glyphs); todo = dict((str(g.name), g) for g in glyphs); todo.update((str(g.name), g) for g in built)
		for g in sorted(todo.values(), key=lambda g: deep(str(g.name))):
			L = g.layers[master.id]
			if str(g.name) in drawn: hold(L, drawn[str(g.name)])
			mv = moves.get(str(g.name))
			if not mv or str(g.name) not in run or str(g.name) in refs: continue
			dx, adv = mv
			if len(list(L.components)) and aligned(L):
				followed += 1; done.append(str(g.name)); continue
			if dx: L.applyTransform((1, 0, 0, 1, dx, 0))
			L.width = adv; n += 1; done.append(str(g.name))
	finally:
		font.enableUpdateInterface()
	simple.stamp(font, "Spacing", TITLE, answer)
	log("applied", n, "glyphs", "shift", res.get("shift"))
	return "%d glyphs spaced in %s%s." % (n, master.name, (", %d with aligned components follow their base glyph" % followed) if followed else ""), done


simple.register("space", space, OPTIONS)                 # scripts and the Glyphs MCP server: MansAITools.space(…)


class AISpacing(GeneralPlugin):

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
			self.dlg = simple.Dialog(TITLE, BRIEF, "Space", space, about=ABOUT, options=OPTIONS, prefs="com.mansgreback.AISpacing.", when=WHEN); self.dlg.open()
		except Exception:
			traceback.print_exc(); log("DIALOG ERROR", traceback.format_exc())

	@objc.python_method
	def __file__(self):
		return __file__
