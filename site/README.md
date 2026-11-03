# site/

`PmMacroLab.tsx` is the architecture page for the portfolio website (evangoh-frontend).

To add it: copy it to `src/pages/PmMacroLab.tsx` there and add
`<Route path="/projects/pm-macro-lab" element={<PmMacroLab />} />` in `src/App.tsx`.

It uses the site's own Tailwind theme tokens (`--color-background`, `--color-accent`, ...), so colours and fonts follow evangoh.com. Dependencies already in the site: `react`, `react-router-dom`, `lucide-react`.

Checked: strict `tsc --noEmit` passes. Not yet checked: rendered in the site, lint, `vite build`. The backtest, risk and dashboard boxes are marked "Planned" because only the design exists.
