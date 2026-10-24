# encoding: utf-8
"""AI Anchors — Glyph ▸ AI Anchors…   (Måns AI Tools)

Places top and bottom anchors on A–Z a–z in the current master: the outlines go to the Måns Tools server, the anchor
net there answers with the positions. Full version: every glyph, settings, variants (G.ss01) as their base, and a context
menu on glyphs (AI Anchors ▸ Set / Reset / Custom anchors…)."""
from __future__ import division, print_function, unicode_literals
import os, sys, traceback

import objc
from Foundation import NSMakePoint
from GlyphsApp import Glyphs, GSAnchor
from GlyphsApp.plugins import GeneralPlugin

try:
	from GlyphsApp import GLYPH_MENU
except ImportError:
	GLYPH_MENU = "Glyph"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import simple
from simple import log

TITLE = "AI Anchors"
ABOUT = "AI Anchors places your anchors for you. The full version does any Latin glyph, unlimited: letters, accents and combining marks (_top, _bottom), ogonek, center, topright and topleft, with an editable rules table."
BRIEF = "Places top and bottom anchors on A–Z a–z in the current master."


OPTIONS = [("radio", "scope", "Place on", (["All glyphs", "Selected glyphs"], "All glyphs")),
           ("popup", "which", "Anchors", (["All rule anchors", "Top and bottom only"], "All rule anchors")),
           ("check", "replace", "Re-place anchors that already exist", True),
           ("check", "variants", "Variants get their base glyph's anchors (G.ss01, G.sc … as G)", True),
           ("check", "ai", "Glyphs in no list: let the model decide which anchors they need", False),
           ("check", "snap", "Snap anchor height to baseline / x-height / cap height when within 2 %", True),
           ("check", "tab", "Open the anchored glyphs in a new tab", True)]


def anchors(opts=None, targets=None, replace=None, reset=False, treat_as=None):
	"""One run. From the dialog: opts = its values. From the context menu (full version): targets = the glyphs, and
	replace (Set = add the missing anchors only, Reset = clear the glyph and place every anchor anew),
	treat_as = the name of the glyph whose anchor set the targets get (Custom anchors: H as R)."""
	font = Glyphs.font; master = font.selectedFontMaster or font.masters[0]
	try: open(simple.LOG, "w").close()
	except Exception: pass
	full = simple.TIER["tier"] == "full"; opts = opts or {}
	if targets is not None:
		if not full: raise RuntimeError("The full version is needed for this.")
		glyphs = [g for g in targets if g.layers[master.id] is not None and simple.closed_paths(g.layers[master.id])]
		if not glyphs: raise RuntimeError("No outlines in the selected glyphs.")
		for k, d in (("which", "All rule anchors"), ("ai", False), ("snap", True), ("variants", True)):   # the dialog's remembered settings apply
			opts.setdefault(k, simple.Dialog.pref_of("com.mansgreback.AIAnchors.", k, d))
	else:
		glyphs = simple.worked(font, master)
		if not glyphs: raise RuntimeError("None of A–Z a–z has outlines in this master.")
		if full and opts.get("scope") == "Selected glyphs":
			sel = simple.selected_names(font); glyphs = [g for g in glyphs if str(g.name) in sel]
			if not glyphs: raise RuntimeError("Select the glyphs first.")
	log("start", TITLE, font.familyName, master.name, len(glyphs), "glyphs", "as", treat_as, "reset", reset)
	if replace is None: replace = bool(opts.get("replace", True)) if full else True
	settings = dict(anchors="topbottom" if opts.get("which") == "Top and bottom only" else "all", ai=bool(opts.get("ai", False)), snap=bool(opts.get("snap", True)),
	                variants=bool(opts.get("variants", True)))
	if treat_as: settings["as"] = dict((str(g.name), str(treat_as)) for g in glyphs)
	data = simple.font_json(font, master, glyphs, settings)
	answer = simple.run("anchors", data); res = (answer["result"] or {}).get("anchors") or {}
	font.disableUpdateInterface()
	try:
		n = 0; moved = 0; done = []
		for g in glyphs:
			L = g.layers[master.id]; before = (n, moved)
			if reset and res.get(str(g.name)):
				L.anchors = []
			for name, (x, y) in (res.get(str(g.name)) or {}).items():
				a = L.anchors[name]
				if a is None:
					a = GSAnchor(); a.name = name; a.position = NSMakePoint(x, y); L.anchors.append(a); n += 1
				elif replace:
					a.position = NSMakePoint(x, y); moved += 1
			if (n, moved) != before: done.append(str(g.name))
	finally:
		font.enableUpdateInterface()
	simple.stamp(font, "Anchors", TITLE, answer)
	log("applied", n, "added", moved, "moved")
	return "%d anchors added, %d moved, in %s." % (n, moved, master.name), done


class AIAnchors(GeneralPlugin):

	@objc.python_method
	def settings(self):
		self.name = TITLE
		self.dlg = None

	@objc.python_method
	def start(self):
		try: simple.add_menu_item(self, GLYPH_MENU, TITLE + "…", self.openDialog_)
		except Exception: traceback.print_exc()
		try:                                                                 # the context menu (full version only; Glyphs asks addMenuItemsForEvent:toMenu:)
			from GlyphsApp import GSCallbackHandler
			GSCallbackHandler.addCallback_forOperation_(self, "GSContextMenuCallbackName")
		except Exception: traceback.print_exc(); log("context menu not registered", traceback.format_exc())
		simple.check_tier_later()                                            # a stored key: find out the tier now, so the context menu knows

	def addMenuItemsForEvent_toMenu_(self, event, menu):
		"""Right-click on glyphs (font view or edit view), full version: AI Anchors ▸ Set anchors / Reset anchors / Custom anchors…"""
		try:
			if simple.TIER["tier"] != "full" or Glyphs.font is None or not simple.selected_names(Glyphs.font): return
			from AppKit import NSMenu, NSMenuItem
			sub = NSMenu.alloc().initWithTitle_(TITLE)
			for title, sel in (("Set anchors", self.ctxSet_), ("Reset anchors", self.ctxReset_), ("Custom anchors…", self.ctxCustom_)):
				it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, sel, ""); it.setTarget_(self); sub.addItem_(it)
			top = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(TITLE, None, ""); top.setSubmenu_(sub)
			menu.addItem_(NSMenuItem.separatorItem()); menu.addItem_(top)
		except Exception:
			log("context menu", traceback.format_exc())

	@objc.python_method
	def targets(self):
		font = Glyphs.font; names = simple.selected_names(font)
		return [font.glyphs[n] for n in sorted(names) if font.glyphs[n] is not None]

	@objc.python_method
	def ctx_run(self, **kw):
		try:
			msg, names = simple.result_parts(anchors(targets=self.targets(), **kw))
			if simple.Dialog.pref_of("com.mansgreback.AIAnchors.", "tab", True): simple.open_tab(Glyphs.font, names)
		except Exception as e:
			traceback.print_exc(); log("CTX ERROR", traceback.format_exc()); msg = "Error: %s" % (str(e)[:300] or "see Macro panel output.")
		try: Glyphs.showNotification(simple.BRAND, msg)
		except Exception: pass

	def ctxSet_(self, sender):
		self.ctx_run(replace=False)                                          # adds the anchors that are missing, keeps the existing ones where they are

	def ctxReset_(self, sender):
		self.ctx_run(replace=True, reset=True)                               # clears the glyph's anchors and places every anchor anew

	def ctxCustom_(self, sender):
		"""Custom anchors: the targets get the anchor set of another glyph (H as R)."""
		import vanilla
		names = sorted(simple.selected_names(Glyphs.font)); M, GAP = simple.Dialog.M, simple.Dialog.GAP
		cw = vanilla.Window((360, 132), "Custom anchors"); self.cw = cw
		shown = ", ".join(names[:6]) + (" …" if len(names) > 6 else "")
		cw.text = vanilla.TextBox((M, 12, -M, 34), "Place anchors on %s as if %s:" % (shown, "it were" if len(names) == 1 else "they were"), sizeStyle="small")
		cw.name = vanilla.EditText((M, 48, -M, 24), "", placeholder="Glyph name, e.g. R")
		bw = (360 - 2 * M - GAP) / 2.0
		cw.close_ = vanilla.Button((M, 86, bw, 24), "Close", callback=lambda s: cw.close())
		cw.ok = vanilla.Button((M + bw + GAP, 86, bw, 24), "Place", callback=self.ctxCustomGo_)
		cw.setDefaultButton(cw.ok); cw.open()

	def ctxCustomGo_(self, sender):
		name = str(self.cw.name.get() or "").strip()
		if not name: return
		try: self.cw.close()
		except Exception: pass
		self.ctx_run(replace=True, reset=True, treat_as=name)

	def openDialog_(self, sender):
		try:
			self.dlg = simple.Dialog(TITLE, BRIEF, "Place", anchors, about=ABOUT, options=OPTIONS, prefs="com.mansgreback.AIAnchors."); self.dlg.open()
		except Exception:
			traceback.print_exc(); log("DIALOG ERROR", traceback.format_exc())

	@objc.python_method
	def __file__(self):
		return __file__
