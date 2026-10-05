import React from "react";
import { interpolate, useCurrentFrame } from "remotion";

export interface WaveformProps {
  envelope: number[]; // 30 fps RMS amplitudes normalized [0, 1]
  currentSpeaker: "agent" | "caller" | "none";
  agentColor: string;
  callerColor: string;
  barCount?: number;
}

export const Waveform: React.FC<WaveformProps> = ({
  envelope,
  currentSpeaker,
  agentColor,
  callerColor,
  barCount = 36,
}) => {
  const frame = useCurrentFrame();
  const currentAmp = envelope[frame] || 0.05;

  const activeColor =
    currentSpeaker === "agent"
      ? agentColor
      : currentSpeaker === "caller"
      ? callerColor
      : "rgba(255, 255, 255, 0.3)";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 6,
        height: 90,
        width: "100%",
        padding: "0 24px",
      }}
    >
      {Array.from({ length: barCount }).map((_, i) => {
        // Create natural organic variation around current amplitude
        const distFromCenter = Math.abs(i - barCount / 2) / (barCount / 2);
        const wavePhase = Math.sin(frame * 0.25 + i * 0.45);
        const multiplier = 1 - distFromCenter * 0.4 + wavePhase * 0.25;
        const idleMotion = 8 + 5 * Math.sin(frame * 0.2 + i * 0.35);
        const height = Math.max(idleMotion, Math.min(84, currentAmp * 84 * multiplier));

        return (
          <div
            key={i}
            style={{
              flex: 1,
              height: `${height}px`,
              backgroundColor: activeColor,
              borderRadius: 4,
              opacity: interpolate(distFromCenter, [0, 1], [1, 0.5]),
              transition: "height 0.05s ease, background-color 0.15s ease",
              boxShadow: `0 0 12px ${activeColor}55`,
            }}
          />
        );
      })}
    </div>
  );
};
