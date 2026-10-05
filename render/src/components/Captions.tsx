import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";

export interface WordTimestamp {
  word: string;
  start: number; // in seconds
  end: number;   // in seconds
  speaker: "agent" | "caller";
}

export interface CaptionsProps {
  words: WordTimestamp[];
  styleType: "word-highlight" | "karaoke" | "boxed";
  primaryColor: string;
  accentColor: string;
  textColor: string;
}

export const Captions: React.FC<CaptionsProps> = ({
  words,
  styleType,
  primaryColor,
  accentColor,
  textColor,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  // Find the active word or recent phrase
  const activeIndex = words.findIndex(
    (w) => currentTime >= w.start && currentTime <= w.end
  );

  // Group into short display chunks (e.g. 4-6 words around current time)
  let windowStart = 0;
  let windowEnd = 0;

  if (activeIndex !== -1) {
    windowStart = Math.max(0, activeIndex - 2);
    windowEnd = Math.min(words.length, activeIndex + 4);
  } else {
    // Find closest prior word
    const priorIndex = words.findLastIndex((w) => w.end <= currentTime);
    if (priorIndex !== -1 && currentTime - words[priorIndex].end < 0.6) {
      windowStart = Math.max(0, priorIndex - 2);
      windowEnd = Math.min(words.length, priorIndex + 2);
    } else {
      return null;
    }
  }

  const visibleWords = words.slice(windowStart, windowEnd);

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        alignItems: "center",
        gap: 12,
        padding: "16px 36px",
        minHeight: 120,
        width: "100%",
        maxWidth: 960,
        margin: "0 auto",
      }}
    >
      {visibleWords.map((w, idx) => {
        const isCurrent = currentTime >= w.start && currentTime <= w.end;
        const isPast = currentTime > w.end;

        if (styleType === "boxed") {
          return (
            <span
              key={`${w.start}-${idx}`}
              style={{
                fontSize: 44,
                fontWeight: 800,
                color: isCurrent ? "#FFFFFF" : isPast ? "rgba(255, 255, 255, 0.8)" : "rgba(255, 255, 255, 0.4)",
                backgroundColor: isCurrent ? primaryColor : "rgba(0, 0, 0, 0.6)",
                padding: "6px 14px",
                borderRadius: 10,
                transform: isCurrent ? "scale(1.08)" : "scale(1.0)",
                transition: "transform 0.1s ease",
                border: isCurrent ? `2px solid ${accentColor}` : "2px solid transparent",
                textTransform: "uppercase",
              }}
            >
              {w.word}
            </span>
          );
        }

        if (styleType === "karaoke") {
          return (
            <span
              key={`${w.start}-${idx}`}
              style={{
                fontSize: 46,
                fontWeight: 900,
                color: isCurrent ? accentColor : isPast ? "#FFFFFF" : "rgba(255, 255, 255, 0.35)",
                textShadow: isCurrent ? `0 0 20px ${accentColor}AA` : "0 2px 10px rgba(0,0,0,0.8)",
                transform: isCurrent ? "scale(1.14) translateY(-2px)" : "scale(1.0)",
                transition: "all 0.08s ease",
                textTransform: "uppercase",
              }}
            >
              {w.word}
            </span>
          );
        }

        // Default: word-highlight
        return (
          <span
            key={`${w.start}-${idx}`}
            style={{
              fontSize: 46,
              fontWeight: 800,
              color: isCurrent ? "#FFFFFF" : isPast ? textColor : "rgba(255, 255, 255, 0.4)",
              backgroundColor: isCurrent ? accentColor : "transparent",
              color: isCurrent ? "#000000" : isPast ? "#FFFFFF" : "rgba(255, 255, 255, 0.4)",
              padding: isCurrent ? "4px 12px" : "4px 2px",
              borderRadius: 8,
              transform: isCurrent ? "scale(1.1)" : "scale(1.0)",
              transition: "transform 0.08s ease",
            }}
          >
            {w.word}
          </span>
        );
      })}
    </div>
  );
};
