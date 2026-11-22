# encoding: utf-8
"""AI Anchors — Glyph ▸ AI Anchors…   (Måns AI Tools)

Places top and bottom anchors on A–Z a–z in the current master: the outlines go to the Måns Tools server, the anchor
net there answers with the positions. Full version: every glyph, settings, variants (G.ss01) as their base, and a context
menu on glyphs (AI Anchors ▸ Set / Reset / Custom anchors…)."""
from __future__ import division, print_function, unicode_literals
import os, sys, traceback

import objc
from Foundation import NSMakePoint
from GlyphsApp import Glyphs, GSAnchor, GSGlyph
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
ABOUT = "AI Anchors places your anchors for you. The full version places anchors on any glyph, unlimited: top, bottom, ogonek, center, topright and topleft on letters, and _top and _bottom on accents and combining marks, with custom anchor sets and a right-click menu."
BRIEF = "Places anchors in the current master."


BASIC = "A–Z, a–z, marks"
CUSTOM = "Custom…"
AI_DECIDES = "Let the AI decide"
WHEN = dict(snap_units=lambda v: v.get("snap_on"), dotless=lambda v: v.get("scope") == BASIC)           # rows shown only when they have an effect
PREFS = "com.mansgreback.AIAnchors."
OPTIONS = [("radio", "scope", "Place on", ([BASIC, "Selected glyphs"], BASIC)),
           ("popup", "which", "Anchors", (["All rule anchors", "Top and bottom only", AI_DECIDES, CUSTOM], "All rule anchors")),
           ("check", "replace", "Replace anchors that already exist", True),
           ("check", "snap_on", "Snap height to baseline, x-height or cap height", False),
           ("text", "snap_units", "Snap within (units)", "20"),
           ("check", "dotless", "Make idotless and jdotless if missing", False),
           ("check", "tab", "Open the anchored glyphs in a new tab", True)]


DOTLESS = (("idotless", "i", "0131", "dotlessi"), ("jdotless", "j", "0237", "dotlessj"))


def is_dotless(glyph):
	"""idotless / jdotless, by name (also the old spellings) or by code point."""
	try: return str(glyph.name) in ("idotless", "jdotless", "dotlessi", "dotlessj") or str(glyph.unicode or "").upper() in ("0131", "0237")
	except Exception: return False


def find_dotless(font, row):
	name, _, uni, old = row
	for g in font.glyphs:
		if str(g.name) in (name, old) or str(g.unicode or "").upper() == uni: return g
	return None


def without_dot(layer):
	"""The outlines of an i or j without its dot, as copies: the outlines are put in groups that overlap in height, and the top
	group goes if it is clearly separate from the rest and small. -> list of paths, or None when no dot can be told apart."""
	L = layer
	try:
		if len(list(layer.components)): L = layer.copyDecomposedLayer()
	except Exception: pass
	paths = [p for p in L.paths if p.closed]
	if len(paths) < 2: return None
	box = lambda p: (p.bounds.origin.y, p.bounds.origin.y + p.bounds.size.height)
	groups = []
	for p in sorted(paths, key=lambda q: box(q)[0]):
		lo, hi = box(p)
		if groups and lo <= groups[-1][1]:
			groups[-1][1] = max(groups[-1][1], hi); groups[-1][2].append(p)
		else:
			groups.append([lo, hi, [p]])
	if len(groups) < 2: return None
	total = groups[-1][1] - groups[0][0]
	if total <= 0 or (groups[-1][1] - groups[-1][0]) > 0.4 * total: return None    # too tall for a dot
	return [p.copy() for g in groups[:-1] for p in g[2]]


def make_dotless(font):
	"""Makes the missing idotless / jdotless from i / j in every master: same outlines without the dot, same width and kerning
	groups. i and j are not changed. -> (names made, [(name, why not)])"""
	made, failed = [], []
	for row in DOTLESS:
		name, base, uni, _ = row
		if find_dotless(font, row) is not None: continue
		src = font.glyphs[base]
		if src is None:
			failed.append((name, "the font has no %s" % base)); continue
		parts = {}
		for m in font.masters:
			L = src.layers[m.id]; kept = without_dot(L) if L is not None else None
			if not kept: break
			parts[m.id] = (kept, L.width)
		if len(parts) != len(font.masters):
			failed.append((name, "no separate dot in %s" % base)); continue
		g = GSGlyph(name); font.glyphs.append(g); g = font.glyphs[name]
		g.unicode = uni; g.leftKerningGroup = src.leftKerningGroup; g.rightKerningGroup = src.rightKerningGroup
		for mid, (kept, width) in parts.items():
			nl = g.layers[mid]; nl.width = width
			for p in kept: nl.shapes.append(p)
		made.append(name)
	return made, failed


def units(text):
	try: return abs(float(str(text).replace(",", ".").strip() or 0))
	except Exception: return 20.0


def saved_sets():
	"""The custom anchor sets the user saved: {name: {glyph: {"anchors": [...], "as": ref}}} (in the Glyphs preferences)."""
	import json
	try: return json.loads(str(Glyphs.defaults[PREFS + "sets"] or "{}"))
	except Exception: return {}


def save_sets(sets):
	import json
	Glyphs.defaults[PREFS + "sets"] = json.dumps(sets)


def options():
	"""OPTIONS with the saved sets in the Anchors popup, over Custom…"""
	out = []
	for kind, name, label, default in OPTIONS:
		if name == "which": default = (default[0][:3] + sorted(saved_sets()) + [CUSTOM], default[1])
		out.append((kind, name, label, default))
	return out


def anchors(opts=None, targets=None, replace=None, reset=False, treat_as=None):
	"""One run. From the dialog: opts = its values. From the context menu (full version): targets = the glyphs, and
	replace (Set = add the missing anchors only, Reset = clear the glyph and place every anchor anew),
	treat_as = the name of the glyph whose anchor set the targets get (Custom anchors: H as R)."""
	font, master = simple.target()
	try: open(simple.LOG, "w").close()
	except Exception: pass
	full = simple.TIER["tier"] == "full"; opts = opts or {}; made_dotless = []; failed_dotless = []
	if targets is not None:
		if not full: raise RuntimeError("The full version is needed for this.")
		glyphs = [g for g in targets if g.layers[master.id] is not None and simple.closed_paths(g.layers[master.id], True)]
		if not glyphs: raise RuntimeError("No outlines in the selected glyphs.")
		for k, d in (("which", "All rule anchors"), ("snap_on", False), ("snap_units", "20")):   # the dialog's remembered settings apply
			opts.setdefault(k, simple.Dialog.pref_of("com.mansgreback.AIAnchors.", k, d))
	else:
		if full and opts.get("scope") != "Selected glyphs" and opts.get("dotless"):
			made_dotless, failed_dotless = make_dotless(font)
		glyphs = simple.worked(font, master, components=True)                 # composites (d = b + …, Aacute) count by their decomposed outlines
		if full and opts.get("scope") == "Selected glyphs":                   # any glyph; one in no rule list gets a reference glyph's anchor set (Aacute → A, ampersand → E)
			sel = simple.selected_names(font); glyphs = [g for g in glyphs if str(g.name) in sel]
			if not glyphs: raise RuntimeError("Select the glyphs first (with outlines or components).")
		elif full:                                                             # the letters of every script, the marks (acutecomb, dieresis …), and the glyphs of a chosen custom set (Mans 2026-11-22: no script left out)
			mine = saved_sets().get(str(opts.get("which") or "")) or {}
			glyphs = [g for g in glyphs if str(g.category or "") in ("Letter", "Mark") or is_dotless(g) or str(g.name) in mine]
		if not glyphs: raise RuntimeError("No letters or marks have outlines in this master." if full else "None of A–Z a–z has outlines in this master.")
	log("start", TITLE, font.familyName, master.name, len(glyphs), "glyphs", "as", treat_as, "reset", reset)
	if replace is None: replace = bool(opts.get("replace", True)) if full else True
	settings = dict(anchors={"Top and bottom only": "topbottom", AI_DECIDES: "ai"}.get(opts.get("which"), "all"), ai=opts.get("which") == AI_DECIDES, snap=bool(opts.get("snap_on", False)), snap_units=units(opts.get("snap_units", "20")),
	                any=targets is not None or opts.get("scope") == "Selected glyphs",
	                variants=True)                                       # variants (X.ss01, X.sc …) always get their base glyph's anchor names
	custom = saved_sets().get(str(opts.get("which") or "")) if full else None
	if custom: settings["custom"] = custom
	if treat_as: settings["as"] = dict((str(g.name), str(treat_as)) for g in glyphs)
	data = simple.font_json(font, master, glyphs, settings, components=True)
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
	r = answer["result"] or {}; refs = r.get("refs") or {}; skipped = r.get("skipped") or []
	msg = "%d anchors added, %d moved, in %s." % (n, moved, master.name)
	if made_dotless: msg += " Made %s." % " and ".join(made_dotless)
	if failed_dotless: msg += " Could not make %s." % "; ".join("%s (%s)" % kv for kv in failed_dotless)
	if full and targets is None and opts.get("scope") != "Selected glyphs":
		missing = [row[0] for row in DOTLESS if find_dotless(font, row) is None and row[0] not in dict(failed_dotless)]
		if missing: msg += " Recommended: create %s before running, or tick Make idotless and jdotless." % " and ".join(missing)
	if refs: msg += " As their reference glyph: %s." % ", ".join("%s as %s" % kv for kv in sorted(refs.items())[:6]) + (" …" if len(refs) > 6 else "")
	if skipped: msg += " No reference for %s: use Custom anchors, or Let the AI decide." % (", ".join(skipped[:6]) + (" …" if len(skipped) > 6 else ""))
	return msg, done


class SetEditor(object):
	"""Custom… : a named anchor set. Add any glyph (search the font's glyph names); its row shows the anchors it gets by
	default, comma separated, to edit freely, and an empty "Place anchors as if glyph" field (the AI's reference glyph, as
	right-click ▸ Custom anchors). Saved sets appear in the Anchors popup over Custom…"""
	W = 640

	def __init__(self, dialog, font):
		import vanilla
		self.dialog, self.font, self.defaults = dialog, font, {}
		M, W = simple.Dialog.M, self.W; w = vanilla.Window((W, 470), "Custom anchors", minSize=(W, 360)); self.w = w
		names = [str(g.name) for g in font.glyphs]
		w.nameLabel = vanilla.TextBox((M, 15, 90, 17), "Set name")
		w.name = vanilla.EditText((M + 96, 12, 190, 22), "", placeholder="e.g. My font", callback=lambda s: self.refresh())
		sets = sorted(saved_sets())
		w.openSavedLabel = vanilla.TextBox((W - M - 300, 15, 90, 17), "Open saved", alignment="right")
		w.openSaved = vanilla.PopUpButton((W - M - 200, 12, 200, 22), ["—"] + sets, callback=self.open_)
		w.addLabel = vanilla.TextBox((M, 51, 90, 17), "Add glyph")
		w.glyph = vanilla.ComboBox((M + 96, 48, 250, 22), names, completes=True, callback=None)
		w.add = vanilla.Button((M + 356, 48, 80, 22), "Add", callback=self.add_)
		w.addSel = vanilla.Button((M + 446, 48, W - 2 * M - 446, 22), "Add selected glyphs", callback=self.addSelected_)
		cols = [dict(title="Glyph", key="glyph", editable=False, width=120),
		        dict(title="Anchors (comma separated)", key="anchors", editable=True),
		        dict(title="Place anchors as if glyph", key="as", editable=True, width=170)]
		w.rows = vanilla.List((M, 84, -M, -86), [], columnDescriptions=cols, editCallback=self.edited_, selectionCallback=lambda s: self.refresh(), enableDelete=True, drawFocusRing=False)
		w.hint = vanilla.TextBox((M, -78, -M, 32), "Any anchor name works. Names the AI knows (top, ogonek …) and related ones (top.2, upper, low) go where they belong; others go just over top and under bottom, alternating.", sizeStyle="small")
		w.remove = vanilla.Button((M, -38, 120, 24), "Remove row", callback=self.remove_)
		w.delete = vanilla.Button((M + 132, -38, 120, 24), "Delete set", callback=self.delete_); w.delete.enable(False)
		w.cancel = vanilla.Button((W - M - 250, -38, 120, 24), "Cancel", callback=self.cancel_)
		w.save = vanilla.Button((W - M - 120, -38, 120, 24), "Save", callback=self.save_)
		w.setDefaultButton(w.add); self.loaded = None; self.closing = False; self.clean = self.state()
		w.bind("should close", self.should_close); self.refresh(); w.open()

	def state(self):
		return (str(self.w.name.get() or "").strip(), tuple(sorted((r["glyph"], r["anchors"], r["as"]) for r in self.items())))

	def dirty(self):
		return self.state() != self.clean

	def can_save(self):
		"""Save is possible with a name (not one of the built-in choices), at least one glyph, and a change to save."""
		name, rows = self.state()
		return bool(name) and name not in ("All rule anchors", "Top and bottom only", CUSTOM) and bool(rows) and self.dirty()

	def refresh(self):
		try: self.w.save.enable(self.can_save())
		except Exception: pass

	def cancel_(self, sender):
		"""Unsaved changes: the first click warns, the second closes without saving."""
		if self.dirty() and self.w.cancel.getTitle() != "Discard changes":
			self.w.cancel.setTitle("Discard changes"); self.say("Your changes are not saved. Click Save to keep them, or Discard changes to close without saving."); return
		self.close(None)

	def should_close(self, sender):
		"""The window's close button: same warning as Cancel."""
		if self.closing or not self.dirty() or self.w.cancel.getTitle() == "Discard changes":
			if not self.closing: self.closing = True; self.back(None)
			return True
		self.w.cancel.setTitle("Discard changes"); self.say("Your changes are not saved. Click Save to keep them, or Discard changes to close without saving.")
		return False

	def ask(self, rows):
		"""The anchors the server gives these glyphs by default: [{name, as}] -> {name: "top, bottom, ogonek"}"""
		data = []
		for r in rows:
			g = self.font.glyphs[r["name"]]; d = dict(name=r["name"], unicode=None, comps=[], **{"as": r.get("as") or ""})
			if g is not None:
				try: d["unicode"] = int(g.unicode, 16) if g.unicode else None
				except Exception: pass
				try: d["comps"] = [str(c.componentName) for c in g.layers[0].components]
				except Exception: pass
			data.append(d)
		st, b = simple.call(dict(tool="anchors", action="defaults", key=simple.key(), simple=False, install=simple.identity(), data=dict(glyphs=data)), 30)
		if st != 200: raise RuntimeError(b.get("error") or "The server answered %s." % st)
		return dict((n, ", ".join(a)) for n, a in (b.get("defaults") or {}).items())

	def items(self):
		return [dict(glyph=str(r.get("glyph") or ""), anchors=str(r.get("anchors") or ""), **{"as": str(r.get("as") or "")}) for r in self.w.rows.get()]

	def add_names(self, names):
		have = set(r["glyph"] for r in self.items()); new = [n for n in names if n and n not in have]
		missing = [n for n in new if self.font.glyphs[n] is None]
		if missing: self.say("Not in the font: %s" % ", ".join(missing[:5])); new = [n for n in new if n not in missing]
		if not new: return
		try: d = self.ask([dict(name=n) for n in new])
		except Exception as e: self.say("Error: %s" % e); return
		for n in new:
			self.defaults[n] = d.get(n, ""); self.w.rows.append(dict(glyph=n, anchors=d.get(n, ""), **{"as": ""}))
		self.refresh()

	def add_(self, sender):
		self.add_names([str(self.w.glyph.get() or "").strip()]); self.w.glyph.set("")

	def addSelected_(self, sender):
		self.add_names(sorted(simple.selected_names(self.font)))

	def edited_(self, sender):
		"""A new "as if" glyph: the row gets that glyph's default anchors, unless the user changed the anchors already."""
		self.refresh(); rows = self.items()
		for i, r in enumerate(rows):
			if self.defaults.get(("as", r["glyph"])) == r["as"]: continue
			self.defaults[("as", r["glyph"])] = r["as"]
			if r["anchors"] != self.defaults.get(r["glyph"], r["anchors"]): continue
			try: d = self.ask([dict(name=r["glyph"], **{"as": r["as"]})])
			except Exception: continue
			self.defaults[r["glyph"]] = d.get(r["glyph"], ""); r["anchors"] = d.get(r["glyph"], "")
			self.w.rows[i] = r
		self.refresh()

	def remove_(self, sender):
		for i in sorted(self.w.rows.getSelection(), reverse=True): del self.w.rows[i]
		self.refresh()

	def open_(self, sender):
		i = sender.get()
		if i == 0: return
		name = sorted(saved_sets())[i - 1]; rows = saved_sets().get(name) or {}
		self.w.name.set(name); self.loaded = name; self.w.delete.enable(True)
		self.w.rows.set([dict(glyph=g, anchors=", ".join(r.get("anchors") or []), **{"as": r.get("as") or ""}) for g, r in sorted(rows.items())])
		for g, r in rows.items(): self.defaults[g] = ", ".join(r.get("anchors") or []); self.defaults[("as", g)] = r.get("as") or ""
		self.clean = self.state(); self.w.cancel.setTitle("Cancel"); self.refresh()

	def delete_(self, sender):
		if self.loaded is None: return
		if self.w.delete.getTitle() != "Yes, delete":
			self.w.delete.setTitle("Yes, delete"); self.say("Delete the set %s? Click again to delete it." % self.loaded); return
		sets = saved_sets(); sets.pop(self.loaded, None); save_sets(sets); self.close(None)

	def save_(self, sender):
		name = str(self.w.name.get() or "").strip()
		if not name: self.say("Give the set a name."); return
		if name in ("All rule anchors", "Top and bottom only", CUSTOM): self.say("Choose another name."); return
		rows = dict((r["glyph"], dict(anchors=[a.strip() for a in r["anchors"].split(",") if a.strip()], **{"as": r["as"].strip()})) for r in self.items())
		if not rows: self.say("Add at least one glyph."); return
		sets = saved_sets()
		if self.loaded and self.loaded != name: sets.pop(self.loaded, None)
		sets[name] = rows; save_sets(sets); self.close(name)

	def say(self, text):
		self.w.hint.set(text)

	def close(self, chosen):
		self.closing = True
		try: self.w.close()
		except Exception: pass
		self.back(chosen)

	def back(self, chosen):
		"""Back to the AI Anchors dialog: the saved set chosen in its Anchors popup (or the previous choice)."""
		d = self.dialog
		Glyphs.defaults[PREFS + "which"] = chosen or d.previous_which
		d.options = options(); d.build(); d.w.open()


simple.register("anchors", anchors, OPTIONS, extra=("reset", "treat_as"))                 # scripts and the Glyphs MCP server: MansAITools.anchors(…)


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
			if Glyphs.font.currentTab is None and simple.Dialog.pref_of("com.mansgreback.AIAnchors.", "tab", True):   # right-click in an edit tab: stay in it, no new tab
				simple.open_tab(Glyphs.font, names)
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
			self.dlg = simple.Dialog(TITLE, BRIEF, "Place", anchors, about=ABOUT, options=options(), prefs=PREFS, hooks=dict(which=self.which_changed), when=WHEN)
			self.dlg.previous_which = simple.Dialog.pref_of(PREFS, "which", "All rule anchors"); self.dlg.open()
		except Exception:
			traceback.print_exc(); log("DIALOG ERROR", traceback.format_exc())

	@objc.python_method
	def which_changed(self, dialog, value):
		"""The Anchors popup: Custom… opens the set editor; any other choice is remembered as the one to go back to."""
		if value != CUSTOM:
			dialog.previous_which = value; return
		try: self.editor = SetEditor(dialog, Glyphs.font)
		except Exception:
			traceback.print_exc(); log("SET EDITOR ERROR", traceback.format_exc()); dialog.set_option("which", dialog.previous_which)

	@objc.python_method
	def __file__(self):
		return __file__
