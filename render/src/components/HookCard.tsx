import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export interface HookCardProps {
  hookText: string;
  businessName: string;
  vertical: string;
  primaryColor: string;
  accentColor: string;
}

export const HookCard: React.FC<HookCardProps> = ({
  hookText,
  businessName,
  vertical,
  primaryColor,
  accentColor,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Active during first 75 frames (2.5 seconds)
  if (frame > 75) return null;

  const scale = spring({
    frame,
    fps,
    config: { damping: 12, stiffness: 120, mass: 0.5 },
  });

  const fadeOut = interpolate(frame, [60, 75], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        padding: "0 48px",
        backgroundColor: "rgba(10, 15, 26, 0.7)",
        backdropFilter: "blur(16px)",
        opacity: fadeOut,
        zIndex: 100,
        textAlign: "center",
      }}
    >
      <div
        style={{
          transform: `scale(${scale})`,
          maxWidth: 900,
        }}
      >
        <div
          style={{
            fontSize: 24,
            fontWeight: 800,
            textTransform: "uppercase",
            letterSpacing: "0.15em",
            color: accentColor,
            marginBottom: 24,
            padding: "8px 20px",
            borderRadius: 30,
            backgroundColor: "rgba(255, 255, 255, 0.1)",
            display: "inline-block",
          }}
        >
          {businessName} • {vertical}
        </div>
        <h1
          style={{
            fontSize: 68,
            fontWeight: 900,
            lineHeight: 1.15,
            color: "#FFFFFF",
            textShadow: "0 10px 40px rgba(0, 0, 0, 0.8)",
            margin: 0,
          }}
        >
          {hookText}
        </h1>
      </div>
    </div>
  );
};
