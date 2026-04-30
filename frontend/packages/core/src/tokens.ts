// Single source of truth for design tokens (decisions.md D17).
// Export a typed object: colors (recommendation enum colors, neutral scale,
// semantic background/foreground/border), spacing scale, typography
// (font family, size, weight, leading), radii, shadows.
// Consumed by:
//   - @ei-fe/ui/tailwind.preset.ts (theme.extend)
//   - runtime TS for conditional class names
// Mirror the same values as CSS custom properties in
// @ei-fe/app/src/styles/globals.css (manual sync per D17).
