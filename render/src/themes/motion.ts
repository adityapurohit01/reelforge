export interface MotionProfile {
  id: string;
  name: string;
  springDamping: number;
  springStiffness: number;
  springMass: number;
  captionPopScale: number;
  chipSlideDurationFrames: number;
}

export const MOTION_PROFILES: Record<string, MotionProfile> = {
  snappy_modern: {
    id: "snappy_modern",
    name: "Snappy Modern",
    springDamping: 14,
    springStiffness: 120,
    springMass: 0.6,
    captionPopScale: 1.12,
    chipSlideDurationFrames: 12,
  },
  smooth_gentle: {
    id: "smooth_gentle",
    name: "Smooth Gentle",
    springDamping: 20,
    springStiffness: 80,
    springMass: 1.0,
    captionPopScale: 1.06,
    chipSlideDurationFrames: 18,
  },
  energetic_bounce: {
    id: "energetic_bounce",
    name: "Energetic Bounce",
    springDamping: 10,
    springStiffness: 160,
    springMass: 0.5,
    captionPopScale: 1.20,
    chipSlideDurationFrames: 10,
  },
};
