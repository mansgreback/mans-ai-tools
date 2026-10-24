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
ABOUT = "AI Spacing spaces your font for you. The full version spaces everything, unlimited: any glyphs, and a lock mode with reference glyphs of your choice so your own spacing is respected."
BRIEF = "Spaces A–Z a–z in the current master."


OPTIONS = [("radio", "scope", "Space", (["All glyphs", "Selected glyphs"], "All glyphs")),
           ("check", "lock", "Keep my spacing on reference glyphs", False),
           ("radio", "refsrc", "References", (["Listed below", "All other glyphs"], "Listed below")),
           ("text", "refs", "Reference glyphs", "HOnoAVaeil"),
           ("check", "tab", "Open the spaced glyphs in a new tab", True)]


def space(opts=None):
	font = Glyphs.font; master = font.selectedFontMaster or font.masters[0]
	try: open(simple.LOG, "w").close()
	except Exception: pass
	glyphs = simple.worked(font, master)
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
	data = simple.font_json(font, master, glyphs, dict(refs=refs, targets=targets))
	answer = simple.run("space", data); res = answer["result"]; moves = res.get("moves") or {}
	font.disableUpdateInterface()
	try:
		n = 0; done = []
		for g in glyphs:
			mv = moves.get(str(g.name))
			if not mv: continue
			dx, adv = mv; L = g.layers[master.id]
			if str(g.name) in refs: continue
			if dx: L.applyTransform((1, 0, 0, 1, dx, 0))
			L.width = adv; n += 1; done.append(str(g.name))
	finally:
		font.enableUpdateInterface()
	simple.stamp(font, "Spacing", TITLE, answer)
	log("applied", n, "glyphs", "shift", res.get("shift"))
	return "%d glyphs spaced in %s." % (n, master.name), done


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
			self.dlg = simple.Dialog(TITLE, BRIEF, "Space", space, about=ABOUT, options=OPTIONS, prefs="com.mansgreback.AISpacing."); self.dlg.open()
		except Exception:
			traceback.print_exc(); log("DIALOG ERROR", traceback.format_exc())

	@objc.python_method
	def __file__(self):
		return __file__
