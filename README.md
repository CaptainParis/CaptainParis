<div align="center">

<img src="./ascii.svg" width="460" alt="Paris"/>

<img src="./stats.svg" width="620" alt="Contributions in the last year"/>

Seattle, Washington

</div>

<img src="./hd-about.svg" width="620" alt="about"/>

> Paper plugins, from Seattle.

I write Minecraft plugins for live servers — packet-level player<br>
capture, sprites in chat, and editors that never leave the world.

<img src="./hd-stack.svg" width="620" alt="stack"/>

<samp>java &nbsp; kotlin &nbsp; python &nbsp; typescript &nbsp; paper &nbsp; protocollib &nbsp; docker &nbsp; git</samp>

<img src="./hd-projects.svg" width="620" alt="projects"/>

**[Mocap](https://github.com/CaptainParis/Mocap)** &nbsp;·&nbsp; <samp>java, paper</samp><br>
Record a player and the chunks around them, then replay the take as<br>
packet actors — ProtocolLib entities, not NPCs or fake players.

**[HeadSprites](https://github.com/CaptainParis/HeadSprites)** &nbsp;·&nbsp; <samp>java, paper</samp><br>
Draw an 8×8 sprite or paste an image. MineSkin signs a head, and<br>
<code>&lt;head:heart&gt;</code> puts it in chat. No resource pack. Paper 1.21.9+.

**BlockDisplayEditor** &nbsp;·&nbsp; <samp>kotlin, paper</samp><br>
Move, rotate, and compose block displays in-game. No export step —<br>
you build the scene from inside the world.

<img src="./hd-stats.svg" width="620" alt="stats"/>

<div align="center">

<img src="./streak.svg" width="620" alt="Current and longest streak"/>

<img src="./langs.svg" width="620" alt="Top languages by bytes and by repo"/>

<img src="./year.svg" width="620" alt="The last year, one character per day"/>

</div>

<img src="./hd-about-this-page.svg" width="620" alt="about this page"/>

Every graphic here is generated, not embedded from anyone else's server.<br>
`ascii.svg` is a photo pushed through a character ramp by<br>
[`scripts/make_portrait.py`](scripts/make_portrait.py); the stat graphics and<br>
these section headings are drawn by [a scheduled action](.github/workflows/stats.yml)<br>
straight from the GitHub GraphQL API, once a day, committing only what changed.

They animate with SMIL inside the SVG, because GitHub strips scripts from<br>
READMEs — and since nothing loads from a third party, nothing here can<br>
rate-limit or go dark. The headings are SVGs for the same reason: GitHub also<br>
strips CSS, so an image is the only way to put this page's own typeface on them.

The typeface is [JetBrains Mono](scripts/fonts), subset to just the characters<br>
each graphic draws and inlined as base64. That isn't only for looks: the<br>
portrait's grid assumes an advance width of exactly 0.600 em, and a viewer whose<br>
default monospace is narrower would otherwise see it squeezed.

Language totals cover public repositories only. `year.svg` uses the portrait's<br>
character ramp: `:` `+` `#` `@`, quiet to loud.
