export interface FontPairing {
  id: string;
  name: string;
  heading: string;
  body: string;
  monospace: string;
}

export const FONT_PAIRINGS: Record<string, FontPairing> = {
  modern_clean: {
    id: "modern_clean",
    name: "Modern Clean",
    heading: "'Outfit', sans-serif",
    body: "'Inter', sans-serif",
    monospace: "'JetBrains Mono', monospace",
  },
  tech_grotesk: {
    id: "tech_grotesk",
    name: "Tech Grotesk",
    heading: "'Space Grotesk', sans-serif",
    body: "'DM Sans', sans-serif",
    monospace: "'Space Mono', monospace",
  },
  corporate_sleek: {
    id: "corporate_sleek",
    name: "Corporate Sleek",
    heading: "'Plus Jakarta Sans', sans-serif",
    body: "'Inter', sans-serif",
    monospace: "'Roboto Mono', monospace",
  },
  editorial_chic: {
    id: "editorial_chic",
    name: "Editorial Chic",
    heading: "'Cinzel', serif",
    body: "'Plus Jakarta Sans', sans-serif",
    monospace: "'Courier New', monospace",
  },
  friendly_rounded: {
    id: "friendly_rounded",
    name: "Friendly Rounded",
    heading: "'DM Sans', sans-serif",
    body: "'Inter', sans-serif",
    monospace: "'JetBrains Mono', monospace",
  },
  bold_impact: {
    id: "bold_impact",
    name: "Bold Impact",
    heading: "'Outfit', sans-serif",
    body: "'Plus Jakarta Sans', sans-serif",
    monospace: "'Space Mono', monospace",
  },
};
