import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Sparkles, ArrowRight } from "lucide-react";

export interface EndCardProps {
  productName: string;
  tagline: string;
  ctaUrl: string;
  ctaHandle: string;
  primaryColor: string;
  accentColor: string;
  totalDurationFrames: number;
}

export const EndCard: React.FC<EndCardProps> = ({
  productName,
  tagline,
  ctaUrl,
  ctaHandle,
  primaryColor,
  accentColor,
  totalDurationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Appears during the last 80 frames (~2.6 seconds)
  const startFrame = Math.max(0, totalDurationFrames - 80);
  if (frame < startFrame) return null;

  const animFrames = frame - startFrame;
  const progress = spring({
    frame: animFrames,
    fps,
    config: { damping: 14, stiffness: 120, mass: 0.6 },
  });

  const opacity = interpolate(progress, [0, 1], [0, 1]);
  const scale = interpolate(progress, [0, 1], [0.9, 1]);

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(11, 15, 25, 0.95)",
        backdropFilter: "blur(24px)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        padding: "0 48px",
        opacity,
        transform: `scale(${scale})`,
        zIndex: 100,
        textAlign: "center",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          backgroundColor: "rgba(99, 102, 241, 0.15)",
          border: `1.5px solid ${primaryColor}`,
          padding: "10px 24px",
          borderRadius: 30,
          color: accentColor,
          fontSize: 20,
          fontWeight: 700,
          marginBottom: 32,
        }}
      >
        <Sparkles size={24} />
        <span>Powered by {productName}</span>
      </div>

      <h2
        style={{
          fontSize: 64,
          fontWeight: 900,
          color: "#FFFFFF",
          lineHeight: 1.15,
          marginBottom: 20,
        }}
      >
        {tagline}
      </h2>

      <p
        style={{
          fontSize: 28,
          color: "#94A3B8",
          maxWidth: 720,
          lineHeight: 1.4,
          marginBottom: 48,
        }}
      >
        Automate 24/7 client bookings, inquiries, and customer calls on WhatsApp & phone.
      </p>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          backgroundColor: primaryColor,
          color: "#FFFFFF",
          padding: "20px 44px",
          borderRadius: 40,
          fontSize: 32,
          fontWeight: 800,
          boxShadow: `0 12px 35px ${primaryColor}66`,
        }}
      >
        <span>Try Free at {ctaUrl}</span>
        <ArrowRight size={32} />
      </div>

      <div
        style={{
          marginTop: 36,
          fontSize: 22,
          color: "#64748B",
          fontWeight: 600,
        }}
      >
        Follow {ctaHandle} for live voice agent demos
      </div>
    </div>
  );
};
