# Manual review checklist

Tick these by hand before sharing the site. Each item says how to check it.

## First look
- [ ] The opening animation plays once: the header and panel rise into place over about a second. With Reduce Motion on (System Settings → Accessibility → Display), it's a plain fade instead.
- [ ] The headline reads in one glance and states what the list is ("clusters … more than 2 km from any site in the open lists"), not a claim of discovery.
- [ ] The honesty note links to "What this doesn't show".

## Map and list
- [ ] Clicking a list row opens its dossier and the map flies to it. Esc goes back.
- [ ] → / j and ← / k step through the list while a dossier is open.
- [ ] Clicking a map square or a site dot opens its dossier, and the matching row lights up.
- [ ] Panning and zooming stay smooth with every layer on, with no stutter or flicker.
- [ ] Rows beyond the top 40 open with the "pictures are drawn for the top 40" note, not a broken image.

## Dossier
- [ ] The Terrain / Mounds marked toggle swaps the picture with no layout jump.
- [ ] Unreviewed candidates show "area only" and the privacy note, with no coordinates anywhere on screen.
- [ ] A known site (El Palma, Chinkultic, Nadzca'an, Plan de Ayutla) says how far outside the strip it lies.

## Look
- [ ] Light and dark mode both look right (Settings → Theme). Check the map, the panel, the dossier, the settings dialog and the method page.
- [ ] At phone width (under 820 px) the panel stacks under the map and nothing scrolls sideways.
- [ ] Equations on "How it works" render typeset, with the symbols defined beneath each one.

## Settings and feedback
- [ ] ⌘, opens Settings. Theme, Strips and Sites persist after a reload. "Clear my preferences" resets them.
- [ ] The feedback tab opens a pre-filled GitHub issue in a new tab, and nothing is sent until you submit.

## Privacy and security
- [ ] `grep -c '"exact":false' site/data/candidates.geojson` matches the candidate count, and `data/private/` isn't in git (`git ls-files data/private` prints nothing).
- [ ] The browser's network panel shows only: the site itself, cdn.jsdelivr.net (pinned, with SRI), fonts.googleapis.com/gstatic, and tiles.openfreemap.org. No analytics.
- [ ] No console errors on load or on click.

## Live services
- [ ] The GitHub Pages URL loads the map in under 2 s on a normal connection.
- [ ] The source DOIs on "How it works" resolve.
