# Profile assets

The animated SVGs in [`/assets`](../../assets) are generated, not drawn by hand.

```bash
pip install -r scripts/profile/requirements.txt
python scripts/profile/build.py               # rebuild everything (light + dark)
python scripts/profile/build.py --only card   # just the project cards
```

- **Copy & content** live at the top of each component in `build.py`
  (`PROJECTS`, `STACK`, `PHRASES`, the hero's typed lines, the agent trace).
- **Colours** are the two palettes in `kit.py` (`THEMES`).
- **Fonts** (Geist, Geist Mono, Instrument Serif; SIL OFL) are subset per file
  and embedded, so GitHub's image proxy renders them exactly.
- **Motion** is CSS-only and switches off under `prefers-reduced-motion`.
- **Activity** (`activity-*.svg`) is rebuilt daily by
  `.github/workflows/profile-assets.yml` from the GitHub GraphQL API.
