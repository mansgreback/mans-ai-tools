# Plugin Manager listing

Entries for `packages.plist` in https://github.com/schriftgestalt/glyphs-packages (branch `glyphs3`), under
`packages → plugins`. Open a pull request from the mansgreback account with the four blocks below added; Georg merges.

```
			{
				titles = {
					en = "Måns AI Kerning";
				};
				url = "https://github.com/mansgreback/mans-ai-tools";
				path = "AIKerning.glyphsPlugin";
				descriptions = {
					en = "Kerns your font for you. Free on A–Z a–z; the full version kerns the whole font or any selection, with kerning groups, exceptions, tolerance and threshold settings. Needs the vanilla module and internet access: the model runs on a server. One license unlocks all Måns AI Tools plugins.";
				};
				screenshot = "https://raw.githubusercontent.com/mansgreback/mans-ai-tools/main/screenshots/kern.png";
				minVersion = 3300;
			},
			{
				titles = {
					en = "Måns AI Spacing";
				};
				url = "https://github.com/mansgreback/mans-ai-tools";
				path = "AISpacing.glyphsPlugin";
				descriptions = {
					en = "Spaces your font for you. Free on A–Z a–z; the full version spaces any glyphs, with a lock mode that keeps your spacing on reference glyphs of your choice. Needs the vanilla module and internet access: the model runs on a server. One license unlocks all Måns AI Tools plugins.";
				};
				screenshot = "https://raw.githubusercontent.com/mansgreback/mans-ai-tools/main/screenshots/space.png";
				minVersion = 3300;
			},
			{
				titles = {
					en = "Måns AI Anchors";
				};
				url = "https://github.com/mansgreback/mans-ai-tools";
				path = "AIAnchors.glyphsPlugin";
				descriptions = {
					en = "Places your anchors for you. Free: top and bottom on A–Z a–z; the full version does letters of every script, accents and combining marks, ogonek, center, topright and topleft — plus a right-click menu to set, reset or custom-place anchors on any glyph. Needs the vanilla module and internet access: the model runs on a server. One license unlocks all Måns AI Tools plugins.";
				};
				screenshot = "https://raw.githubusercontent.com/mansgreback/mans-ai-tools/main/screenshots/anchors.png";
				minVersion = 3300;
			},
			{
				titles = {
					en = "Måns AI Variable Font";
				};
				url = "https://github.com/mansgreback/mans-ai-tools";
				path = "AIVariable.glyphsPlugin";
				descriptions = {
					en = "Makes a variable font for you from a single style font, with every node kept so the masters stay compatible. Free: Weight and Width masters for A–Z a–z; the full version does the whole font, your choice of axes, composites kept as components. Needs the vanilla module and internet access: the model runs on a server. One license unlocks all Måns AI Tools plugins.";
				};
				screenshot = "https://raw.githubusercontent.com/mansgreback/mans-ai-tools/main/screenshots/variable.png";
				minVersion = 3300;
			},
```

Pull request title: `Add Måns AI Tools (AI Kerning, AI Spacing, AI Anchors, AI Variable Font)`

Pull request text:

> Four plugins by Måns Grebäck, one repository, one bundle per entry. Free on A–Z a–z, full version by license.
> The models run on the author's server; the plugins send outlines and receive numbers. Tested in Glyphs 3.5.1 and 4.1.1.
> Dependency: vanilla.

`minVersion` 3300 = Glyphs 3.3; raise it if testing in 3.5.1 shows an older API is missing.
