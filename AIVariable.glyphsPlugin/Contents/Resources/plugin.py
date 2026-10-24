# encoding: utf-8
"""AI Variable Font — File ▸ AI Variable Font…   (Måns AI Tools)

Builds a NEW font beside the open one from its current master: Weight and Width axes, nine masters (Thin/Regular/Black ×
Condensed/Regular/Extended), the named styles and one variable-font setting. Only A–Z a–z are in it, with outlines from the model;
every other glyph is left out. No settings. Non-commercial use. The outlines are computed on
the Måns Tools server (the A–Z a–z outlines and widths are sent there and kept)."""
from __future__ import division, print_function, unicode_literals
import copy, os, sys, tempfile, traceback, uuid

import objc
from Foundation import NSMakePoint
from GlyphsApp import Glyphs, GSAxis, GSInstance
from GlyphsApp.plugins import GeneralPlugin

try:
	from GlyphsApp import FILE_MENU
except ImportError:
	FILE_MENU = "File"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import simple
from simple import log

TITLE = "AI Variable Font"
ABOUT = "AI Variable Font makes a variable font for you, from a single style font, with every node kept so the masters stay compatible. The full version does everything, unlimited: the whole font, your choice of axes, composites kept as components."
BRIEF = "Makes a new variable font (Weight, Width) from the current master. A–Z a–z only."
WEIGHTS = [(100, "Thin"), (300, "Light"), (400, "Regular"), (700, "Bold"), (900, "Black")]
WIDTHS = [(75, "Condensed"), (87.5, "SemiCondensed"), (100, ""), (112.5, "SemiExtended"), (125, "Extended")]
ALL_WEIGHTS = [(100, "Thin"), (200, "ExtraLight"), (300, "Light"), (400, "Regular"), (500, "Medium"), (600, "SemiBold"), (700, "Bold"), (800, "ExtraBold"), (900, "Black")]


OPTIONS = [("check", "weight", "Weight axis", True), ("check", "width", "Width axis", True), ("check", "tab", "Open the glyphs in a new tab", True)]


def font_json(font, master, weight=True, width=True):
	"""What the server gets: the master's metrics and the outlines (the server's format for the variable tool). A–Z a–z, or
	with the full version every glyph (empty ones too: the space follows the width)."""
	glyphs = []
	for g in (list(font.glyphs) if simple.TIER["tier"] == "full" else simple.letters(font)):
		layer = g.layers[master.id]
		if layer is None: continue
		uni = None
		try: uni = int(g.unicode, 16) if g.unicode else None
		except Exception: pass
		empty = not simple.closed_paths(layer) and not len(list(layer.components)) and not len(list(layer.paths))
		glyphs.append(dict(name=str(g.name), unicode=uni, width=float(layer.width), empty=bool(empty),
		                   paths=[[[float(n.position.x), float(n.position.y), str(n.type)] for n in p.nodes] for p in simple.closed_paths(layer)]))
	return dict(upm=float(font.upm), cap=float(master.capHeight or 0), grid=float(font.grid), family=str(font.familyName), weight=bool(weight), width=bool(width), glyphs=glyphs)


def set_axes(font, tags):
	names = dict(wght="Weight", wdth="Width"); axes = []
	for t in tags:
		a = GSAxis(); a.name = names[t]; a.axisTag = t; axes.append(a)
	font.axes = axes


def add_master(font, src_master, name, values, glyphs_out, old_width):
	"""A new master copied from src_master, with the outlines the server returned. Composites keep their components; loose
	components and anchors follow the width change of their base (as the full Make Variable Font plugin does)."""
	m = copy.copy(src_master); m.id = str(uuid.uuid4()).upper(); m.name = name
	font.masters.append(m); m.axes = values
	try: del m.customParameters["Axis Location"]                   # the copy's Axis Location says 0/0 for every master: Glyphs hangs on that
	except Exception: pass
	try:
		if name.startswith("Black") or name.startswith("Bold"): m.iconName = "Bold"
		elif name.startswith("Thin") or name.startswith("Light"): m.iconName = "Light"
	except Exception:
		pass
	ratio = {}
	for n, g in glyphs_out.items():
		if old_width.get(n): ratio[n] = float(g["width"]) / old_width[n]
	for g in font.glyphs:
		src = g.layers[src_master.id]
		if src is None: continue
		layer = copy.copy(src); layer.layerId = m.id; layer.associatedMasterId = m.id; g.layers[m.id] = layer; layer = g.layers[m.id]
		out = glyphs_out.get(str(g.name)); paths = simple.closed_paths(layer); r = 1.0
		if out is not None and paths and len(out["paths"]) == len(paths) and all(len(a) == len(p.nodes) for a, p in zip(out["paths"], paths)):
			for a, p in zip(out["paths"], paths):
				for xy, node in zip(a, p.nodes): node.position = NSMakePoint(xy[0], xy[1])
			r = ratio.get(str(g.name), 1.0); layer.width = out["width"]; loose = [c for c in layer.components]
		elif out is not None and not paths and not len(list(layer.components)) and not len(list(layer.paths)):
			layer.width = out["width"]; loose = []                     # an empty glyph (the space): its width follows the font
		else:
			comps = [c for c in layer.components]; base = str(comps[0].componentName) if comps else None
			r = ratio.get(base, 1.0) if base else 1.0
			loose = [c for c in comps if not getattr(c, "automaticAlignment", False)]
			if comps and not all(getattr(c, "automaticAlignment", False) for c in comps): layer.width = src.width * r
		if abs(r - 1.0) > 1e-6:
			for c in loose:
				try: c.position = NSMakePoint(c.position.x * r, c.position.y)
				except Exception: pass
			for a in layer.anchors: a.position = NSMakePoint(a.position.x * r, a.position.y)
	return m


def add_instances(font, family, wght, wdth):
	font.instances = []
	try: v = GSInstance.alloc().initWithType_(1)
	except Exception: v = GSInstance(1)
	v.name = "Regular"
	try: v.familyName = family + " Variable"
	except Exception: traceback.print_exc()
	font.instances.append(v)
	ws = [None]; ds = [None]
	if wght:
		ws = [(w, n) for w, n in WEIGHTS if wght[0] - 1 <= w <= wght[1] + 1]
		for end in wght:
			if not any(abs(end - w) < 26 for w, _ in ws): ws.append((end, min(ALL_WEIGHTS, key=lambda a: abs(a[0] - end))[1]))
		ws = sorted(dict((n, (w, n)) for w, n in ws).values())
	if wdth:
		ds = [(d, n) for d, n in WIDTHS if wdth[0] - 0.1 <= d <= wdth[1] + 0.1]
		for end in wdth:
			if not any(abs(end - d) < 3 for d, _ in ds): ds.append((end, "SemiCondensed" if end < 100 else "SemiExtended"))
		ds = sorted(dict((n, (d, n)) for d, n in ds).values())
	wclass = lambda w: int(min(900, max(100, round(w / 100.0) * 100)))
	dclass = lambda d: 3 if d <= 80 else 4 if d < 100 else 5 if d == 100 else 6 if d < 120 else 7
	for w in ws:
		for d in ds:
			i = GSInstance(); wn = w[1] if w else ""; dn = d[1] if d else ""
			i.name = (" ".join(x for x in (wn if wn != "Regular" or not dn else "", dn) if x)) or "Regular"
			font.instances.append(i); i.axes = [x[0] for x in (w, d) if x]
			try:
				if w: i.weightClass = wclass(w[0])
				if d: i.widthClass = dclass(d[0])
				if w and w[1] == "Bold" and any(a[1] == "Regular" for a in ws): i.isBold = True; i.linkStyle = dn or "Regular"
			except Exception:
				traceback.print_exc()


def settle_alignment(font_):
	"""Touch every component layer now, so Glyphs does not do it later from inside a read lock (frozen Glyphs, 2026-10-21)."""
	n = 0
	for g in font_.glyphs:
		for l in g.layers:
			try:
				if len(list(l.components)): l.hasAlignedWidth(); n += 1
			except Exception:
				pass
	log("component alignment settled", n, "layers")


def make(opts=None):
	opts = opts or {}; weight = bool(opts.get("weight", True)); width = bool(opts.get("width", True))
	if not weight and not width: raise RuntimeError("Choose at least one axis.")
	font = Glyphs.font; master = font.selectedFontMaster or font.masters[0]
	try: open(simple.LOG, "w").close()
	except Exception: pass
	log("start", TITLE, font.familyName, "master", master.name, "Glyphs", Glyphs.versionNumber, Glyphs.buildNumber)
	data = font_json(font, master, weight, width); log("collected", len(data["glyphs"]), "glyphs")
	if not [g for g in data["glyphs"] if g["paths"]]: raise RuntimeError("No glyphs with outlines in this master.")
	answer = simple.run("variable", data); out = answer["result"]; log("result", [m["name"] for m in out["masters"]])
	new = font.copy()
	if simple.TIER["tier"] != "full":                                 # simple: the new font holds the worked letters only (Mans 2026-10-22)
		keep = set(str(g.name) for g in simple.letters(font))
		for g in list(new.glyphs):
			if str(g.name) not in keep:
				try: del new.glyphs[str(g.name)]
				except Exception: traceback.print_exc()
		log("kept", len(new.glyphs), "letters, removed", len(font.glyphs) - len(new.glyphs), "other glyphs")
	for key in ("Axis Mappings", "Axis Location"):
		try: del new.customParameters[key]
		except Exception: pass
	src = next((m for m in new.masters if m.id == master.id), new.masters[0])
	old_width = dict((str(g.name), float(g.layers[src.id].width)) for g in new.glyphs if g.layers[src.id] is not None)
	tags = [t for t in ("wght", "wdth") if out.get(t)]; old_masters = list(new.masters)
	kern = None
	try:
		allk = new.kerning; k = allk[src.id] if (allk is not None and src.id in allk) else None
		if k: kern = dict((str(l), dict((str(r), float(v)) for r, v in dict(rs).items())) for l, rs in dict(k).items())
		if kern:                                                     # only pairs between kept glyphs (ids) or groups
			ok = set(str(g.id) for g in new.glyphs)
			kern = dict((l, dict((r, v) for r, v in rs.items() if r.startswith("@") or r in ok)) for l, rs in kern.items() if l.startswith("@") or l in ok)
			kern = dict((l, rs) for l, rs in kern.items() if rs)
	except Exception:
		traceback.print_exc()
	set_axes(new, tags); made = []
	for m in out["masters"]:
		made.append(add_master(new, src, m["name"], [m[t] for t in tags], m["glyphs"], old_width)); log("master", m["name"])
	for m in old_masters:
		try: new.masters.remove(m)
		except Exception: new.removeFontMaster_(m)
	try:
		reg = next((mm for mm, o in zip(made, out["masters"]) if o.get("source")), None)
		if reg is not None: new.customParameters["Variable Font Origin"] = reg.id
	except Exception:
		log("origin not set", traceback.format_exc())
	if kern:
		try: new.kerning = dict((m.id, dict((l, dict(rs)) for l, rs in kern.items())) for m in made)
		except Exception: traceback.print_exc()
	add_instances(new, str(font.familyName), out.get("wght"), out.get("wdth"))
	simple.stamp(new, "Axis", TITLE, answer)
	ids = set(str(m.id) for m in new.masters); gone = 0
	for g in new.glyphs:
		for l in list(g.layers):
			try:
				if str(l.layerId) not in ids and str(l.associatedMasterId or "") not in ids: del g.layers[l.layerId]; gone += 1
			except Exception:
				traceback.print_exc()
	log("orphan layers removed", gone)
	settle_alignment(new)
	fam = (str(font.familyName) or "Font").replace("/", "-")
	path = os.path.join(tempfile.mkdtemp(prefix="makevariable_"), fam + " Variable.glyphs")
	try:
		new.save(path, formatVersion=3); Glyphs.open(path); log("opened from file", path)
	except Exception:
		log("save/open failed, appending instead", traceback.format_exc()); Glyphs.fonts.append(new)
	return "%d masters: %s, %d glyphs." % (len(out["masters"]), ", ".join(m["name"] for m in out["masters"]), len(data["glyphs"])), [g["name"] for g in data["glyphs"]]


class AIVariable(GeneralPlugin):

	@objc.python_method
	def settings(self):
		self.name = TITLE
		self.dlg = None

	@objc.python_method
	def start(self):
		try: simple.add_menu_item(self, FILE_MENU, TITLE + "…", self.openDialog_)
		except Exception: traceback.print_exc()

	def openDialog_(self, sender):
		try:
			self.dlg = simple.Dialog(TITLE, BRIEF, "Make", make, about=ABOUT, options=OPTIONS, prefs="com.mansgreback.AIVariableFont."); self.dlg.open()
		except Exception:
			traceback.print_exc(); log("DIALOG ERROR", traceback.format_exc())

	@objc.python_method
	def __file__(self):
		return __file__
